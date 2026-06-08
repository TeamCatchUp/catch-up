from __future__ import annotations

from functools import lru_cache
from functools import partial
from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from catchup.automations.nodes.generate_guide import generate_guide_node
from catchup.automations.nodes.grade import grade_node
from catchup.automations.nodes.send_slack import send_slack_node
from catchup.automations.state import AutomationState
from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.components.reranker.constants import RerankerProvider
from catchup.components.reranker.factory import get_rerank_service
from catchup.components.reranker.service import BaseRerankService
from catchup.components.vector_db.base import BaseVectorDbService
from catchup.components.vector_db.factory import get_vector_db_service
from catchup.components.vector_db.pgvector.constants import VectorDbProvider
from catchup.rag.nodes import generate_vector_queries_node
from catchup.rag.nodes import rerank_node
from catchup.rag.nodes import search_vector_db_node


def _route_after_grade(state: AutomationState) -> str:
    """grade_result에 따라 다음 노드를 결정한다."""
    grade_result = state.get("grade_result")
    if grade_result and grade_result.get("reusable"):
        return "generate_guide"
    return "prepare_hybrid_search"


async def _prepare_hybrid_search_node(state: AutomationState) -> dict[str, Any]:
    """hybrid search 전 tool_filters를 초기화하고 retrieved_docs를 비운다."""
    return {
        "tool_filters": None,
        "retrieved_docs": [],
    }


def build_inquiry_automation_graph(
    *,
    llm_small: BaseChatModel,
    llm_grade: BaseChatModel,
    llm_large: BaseChatModel,
    vector_db_service: BaseVectorDbService,
    rerank_service: BaseRerankService,
) -> CompiledStateGraph:
    """문의 대응 자동화 LangGraph 파이프라인을 빌드하고 컴파일한다."""
    graph = StateGraph(AutomationState)

    graph.add_node(
        "generate_vector_queries",
        partial(generate_vector_queries_node, llm=llm_small, timeout=15.0),
    )
    graph.add_node(
        "search_channel_talk",
        partial(search_vector_db_node, vector_db_service=vector_db_service),
    )
    graph.add_node(
        "grade",
        partial(grade_node, llm=llm_grade),
    )
    graph.add_node(
        "prepare_hybrid_search",
        _prepare_hybrid_search_node,
    )
    graph.add_node(
        "search_hybrid",
        partial(search_vector_db_node, vector_db_service=vector_db_service),
    )
    graph.add_node(
        "rerank",
        partial(rerank_node, rerank_service=rerank_service),
    )
    graph.add_node(
        "generate_guide",
        partial(generate_guide_node, llm=llm_large),
    )
    graph.add_node("send_slack", send_slack_node)

    graph.set_entry_point("generate_vector_queries")
    graph.add_edge("generate_vector_queries", "search_channel_talk")
    graph.add_edge("search_channel_talk", "grade")
    graph.add_conditional_edges(
        "grade",
        _route_after_grade,
        {
            "generate_guide": "generate_guide",
            "prepare_hybrid_search": "prepare_hybrid_search",
        },
    )
    graph.add_edge("prepare_hybrid_search", "search_hybrid")
    graph.add_edge("search_hybrid", "rerank")
    graph.add_edge("rerank", "generate_guide")
    graph.add_edge("generate_guide", "send_slack")
    graph.add_edge("send_slack", END)

    return graph.compile()


@lru_cache(maxsize=1)
def get_inquiry_automation_graph() -> CompiledStateGraph:
    """프로덕션용 파이프라인 싱글톤을 반환한다."""
    llm_small = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.SMALL,
        streaming=False,
        isolated=True,
        max_attempts=0,
    ).get_llm()
    llm_large = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.LARGE,
        streaming=False,
        isolated=True,
        max_attempts=0,
    ).get_llm()
    embeddings = get_embedding_service(
        EmbeddingProvider.AWS_BEDROCK, max_attempts=0
    ).get_embedder()
    vector_db_service = get_vector_db_service(VectorDbProvider.PGVECTOR, embeddings)
    rerank_service = get_rerank_service(RerankerProvider.AWS_BEDROCK)

    return build_inquiry_automation_graph(
        llm_small=llm_small,
        llm_grade=llm_small,
        llm_large=llm_large,
        vector_db_service=vector_db_service,
        rerank_service=rerank_service,
    )
