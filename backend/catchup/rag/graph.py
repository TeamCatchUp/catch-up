import logging
from functools import partial
from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END
from langgraph.graph import StateGraph
from langgraph.types import RetryPolicy

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
from catchup.rag.nodes import clarify_node
from catchup.rag.nodes import direct_answer_node
from catchup.rag.nodes import supervisor_node
from catchup.rag.retryable import RETRYABLE_ERRORS
from catchup.rag.state import AgentState
from catchup.rag.subgraphs import build_complex_react_subgraph
from catchup.rag.subgraphs import build_reuse_subgraph
from catchup.rag.subgraphs import build_simple_subgraph
from catchup.rag.subgraphs import build_standard_react_subgraph

logger = logging.getLogger(__name__)

# Timeout 기반 재시도 정책
# max_attempt는 최초 시도 횟수를 포함.
TIMEOUT_RETRY_POLICY = RetryPolicy(
    retry_on=RETRYABLE_ERRORS,
    max_attempts=3,
    initial_interval=1.0,
    backoff_factor=2.0,
)

# Agent는 내부 루프가 길어 재시도 횟수를 제한
AGENT_TIMEOUT_RETRY_POLICY = RetryPolicy(
    retry_on=RETRYABLE_ERRORS,
    max_attempts=2,
    initial_interval=1.0,
    backoff_factor=2.0,
)


def get_compiled_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None,
):
    # RAG 파이프라인에서는 LangGraph RetryPolicy를 사용하므로
    # botocore 레벨의 retry는 비활성화(max_attempts=0).
    rag_max_attempts = 0

    # SMALL, non-streaming — rewrite, generate_vector_queries
    llm_small = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.SMALL,
        streaming=False,
        isolated=True,
        max_attempts=rag_max_attempts,
    ).get_llm()

    # SMALL, streaming — direct_answer
    llm_small_stream = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.SMALL,
        streaming=True,
        isolated=True,
        max_attempts=rag_max_attempts,
    ).get_llm()

    # LARGE, non-streaming — supervisor, complex_agent, standard_agent (structured output / tool calling)
    llm_large = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.LARGE,
        streaming=False,
        isolated=True,
        max_attempts=rag_max_attempts,
    ).get_llm()

    # LARGE, streaming — 모든 최종 답변 생성 (reuse / simple / standard / complex)
    llm_large_stream = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.LARGE,
        streaming=True,
        isolated=True,
        max_attempts=rag_max_attempts,
    ).get_llm()

    # LARGE, streaming, extended thinking — standard_agent, complex_planner, complex_agent.
    # tool-calling/structured-output 응답이라 response 부분은 짧게 캡(1024)해 총 wall-clock을 제한한다.
    llm_thinking = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.LARGE,
        streaming=True,
        isolated=True,
        extended_thinking=True,
        thinking_budget_tokens=2048,
        max_response_tokens=1024,
        max_attempts=rag_max_attempts,
    ).get_llm()

    # Common
    embeddings = get_embedding_service(
        EmbeddingProvider.AWS_BEDROCK,
        max_attempts=rag_max_attempts,
    ).get_embedder()
    vector_db_service = get_vector_db_service(VectorDbProvider.PGVECTOR, embeddings)
    rerank_service = get_rerank_service(RerankerProvider.AWS_BEDROCK)

    # Subgraphs
    reuse_subgraph = build_reuse_subgraph(
        llm_small=llm_small,
        llm_large_stream=llm_large_stream,
        rerank_service=rerank_service,
    )

    simple_subgraph = build_simple_subgraph(
        llm_small=llm_small,
        llm_large_stream=llm_large_stream,
        vector_db_service=vector_db_service,
        rerank_service=rerank_service,
    )

    standard_subgraph = build_standard_react_subgraph(
        llm_small=llm_small,
        llm_large_stream=llm_large_stream,
        llm_thinking=llm_thinking,
        vector_db_service=vector_db_service,
        rerank_service=rerank_service,
    )

    complex_subgraph = build_complex_react_subgraph(
        llm_small=llm_small,
        llm_large_stream=llm_large_stream,
        llm_thinking=llm_thinking,
        vector_db_service=vector_db_service,
        rerank_service=rerank_service,
    )

    # Main Graph
    workflow = StateGraph(AgentState)

    workflow.add_node(
        "supervisor",
        partial(supervisor_node, llm=llm_large, timeout=15.0),
        retry=TIMEOUT_RETRY_POLICY,
    )
    workflow.add_node(
        "direct_answer",
        partial(direct_answer_node, llm=llm_small_stream, timeout=30.0),
        metadata={"tags": ["stream_target"]},
        # streaming 노드는 retry 적용 제외
    )
    workflow.add_node(
        "clarify",
        clarify_node,
        metadata={"tags": ["stream_target"]},
    )
    workflow.add_node("reuse", reuse_subgraph)
    workflow.add_node("simple", simple_subgraph)
    workflow.add_node("standard", standard_subgraph)
    workflow.add_node("complex", complex_subgraph)

    workflow.set_entry_point("supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "clarify": "clarify",
            "direct_answer": "direct_answer",
            "reuse": "reuse",
            "simple": "simple",
            "standard": "standard",
            "complex": "complex",
        },
    )
    workflow.add_edge("clarify", END)
    workflow.add_edge("direct_answer", END)
    workflow.add_edge("reuse", END)
    workflow.add_edge("simple", END)
    workflow.add_edge("standard", END)
    workflow.add_edge("complex", END)

    if checkpointer is not None:
        return workflow.compile(checkpointer=checkpointer)

    return workflow.compile()
