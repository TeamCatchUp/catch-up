import logging
from functools import partial
from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END
from langgraph.graph import StateGraph

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.llm.factory import LlmProvider
from catchup.components.llm.factory import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.components.reranker.constants import RerankerProvider
from catchup.components.reranker.factory import get_rerank_service
from catchup.components.vector_db.factory import get_vector_db_service
from catchup.components.vector_db.pgvector.constants import VectorDbProvider
from catchup.rag.conditional_edges import route_after_supervisor
from catchup.rag.nodes import chitchat_node
from catchup.rag.nodes import supervisor_node
from catchup.rag.state import AgentState
from catchup.rag.subgraphs import build_complex_react_subgraph
from catchup.rag.subgraphs import build_reuse_subgraph
from catchup.rag.subgraphs import build_simple_subgraph
from catchup.rag.subgraphs import build_standard_react_subgraph

logger = logging.getLogger(__name__)


def get_compiled_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None,
):
    # 분석용 (SMALL, non-streaming)
    # rewrite, generate_vector_queries, standard_agent
    analysis_llm = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.SMALL,
        streaming=False,
        isolated=True,
    ).get_llm()

    # 잡담용 (SMALL, streaming)
    chitchat_llm = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.SMALL,
        streaming=True,
        isolated=True,
    ).get_llm()

    # Supervisor + complex_agent (LARGE, non-streaming) — structured output / tool calling
    large_llm = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.LARGE,
        streaming=False,
        isolated=True,
    ).get_llm()

    # 최종 답변 생성용 (LARGE, streaming)
    final_llm = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.LARGE,
        streaming=True,
        isolated=True,
    ).get_llm()

    # Extended Thinking (LARGE, non-streaming)
    # complex_planner, gap_analysis
    thinking_llm = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.LARGE,
        streaming=False,
        isolated=True,
        extended_thinking=True,
        thinking_budget_tokens=8000,
    ).get_llm()

    # Common
    embeddings = get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
    vector_db_service = get_vector_db_service(VectorDbProvider.PGVECTOR, embeddings)
    rerank_service = get_rerank_service(RerankerProvider.AWS_BEDROCK)

    # Subgraph 빌드
    reuse_subgraph = build_reuse_subgraph(llm_large=final_llm)

    simple_subgraph = build_simple_subgraph(
        llm_small=analysis_llm,
        llm_fast=final_llm,
        vector_db_service=vector_db_service,
        rerank_service=rerank_service,
    )

    standard_subgraph = build_standard_react_subgraph(
        llm_small=analysis_llm,
        llm_large=final_llm,
        vector_db_service=vector_db_service,
        rerank_service=rerank_service,
    )

    complex_subgraph = build_complex_react_subgraph(
        llm_agent=large_llm,
        llm_final=final_llm,
        llm_thinking=thinking_llm,
        vector_db_service=vector_db_service,
        rerank_service=rerank_service,
    )

    # ---- 메인 그래프 ----
    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", partial(supervisor_node, llm=large_llm))
    workflow.add_node("chitchat", partial(chitchat_node, llm=chitchat_llm))
    workflow.add_node("reuse", reuse_subgraph)
    workflow.add_node("simple", simple_subgraph)
    workflow.add_node("standard", standard_subgraph)
    workflow.add_node("complex", complex_subgraph)

    workflow.set_entry_point("supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "chitchat": "chitchat",
            "reuse": "reuse",
            "simple": "simple",
            "standard": "standard",
            "complex": "complex",
        },
    )
    workflow.add_edge("chitchat", END)
    workflow.add_edge("reuse", END)
    workflow.add_edge("simple", END)
    workflow.add_edge("standard", END)
    workflow.add_edge("complex", END)

    if checkpointer is not None:
        return workflow.compile(checkpointer=checkpointer)

    return workflow.compile()
