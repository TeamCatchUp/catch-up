"""CatchUp 지식베이스 검색 도구.

search (vector 검색, 누적) + rerank (누적 전체 재순위화) 두 액션으로 분리한다.
generation은 Execution Agent LLM이 직접 담당한다.
"""
from contextvars import ContextVar
from functools import lru_cache
from functools import partial
from typing import Literal

import structlog
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langgraph.graph import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel
from pydantic import Field

from catchup.agents.tools.base import ActionType
from catchup.agents.tools.base import BaseTool
from catchup.agents.tools.base import action
from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.factory import get_llm_service
from catchup.components.llm.service import ModelCapacity
from catchup.components.reranker.constants import RerankerProvider
from catchup.components.reranker.factory import get_rerank_service
from catchup.components.vector_db.factory import get_vector_db_service
from catchup.components.vector_db.pgvector.constants import VectorDbProvider
from catchup.db.models import SourceType
from catchup.rag.nodes import generate_vector_queries_node
from catchup.rag.nodes import rerank_node
from catchup.rag.nodes import search_vector_db_node
from catchup.rag.nodes.utils import build_docs_summary
from catchup.rag.nodes.utils import deduplicate_documents
from catchup.rag.schemas.context import GlobalContext
from catchup.rag.state import AgentState

logger = structlog.get_logger(__name__)

_context_var: ContextVar[GlobalContext | None] = ContextVar(
    "catchup_kb_context", default=None
)
_accumulated_docs_var: ContextVar[list[Document] | None] = ContextVar(
    "catchup_kb_accumulated_docs", default=None
)


@lru_cache(maxsize=1)
def _get_search_graph() -> CompiledStateGraph:
    """vector 검색 전용 LangGraph subgraph를 빌드하고 컴파일한다.

    generate_vector_queries → search_vector_db 순서로 실행한다.
    rewrite와 rerank는 포함하지 않는다.
    """
    llm_small = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.SMALL,
        streaming=False,
        isolated=True,
        max_attempts=0,
    ).get_llm()
    embeddings = get_embedding_service(
        EmbeddingProvider.AWS_BEDROCK,
        max_attempts=0,
    ).get_embedder()
    vector_db_service = get_vector_db_service(VectorDbProvider.PGVECTOR, embeddings)

    graph = StateGraph(AgentState)
    graph.add_node(
        "generate_vector_queries",
        partial(generate_vector_queries_node, llm=llm_small, timeout=15.0),
    )
    graph.add_node(
        "search_vector_db",
        partial(search_vector_db_node, vector_db_service=vector_db_service),
    )
    graph.set_entry_point("generate_vector_queries")
    graph.add_edge("generate_vector_queries", "search_vector_db")
    graph.add_edge("search_vector_db", END)

    return graph.compile()


@lru_cache(maxsize=1)
def _get_rerank_service_cached():
    """rerank 서비스를 lru_cache 싱글톤으로 반환한다."""
    return get_rerank_service(RerankerProvider.AWS_BEDROCK)


async def _run_vector_search(
    query: str,
    global_context: GlobalContext,
    tool_filters: list | None,
) -> list[Document]:
    """vector 검색 subgraph를 실행하고 검색된 문서 목록을 반환한다."""
    graph = _get_search_graph()
    result = await graph.ainvoke({
        "messages": [HumanMessage(content=query)],
        "original_query": query,
        "global_context": global_context,
        "tool_filters": tool_filters,
        "max_pipeline_type": "simple",
        "rewritten_query": query,
        "vector_search_queries": [],
        "retrieved_docs": [],
        "rerank_count": 0,
        "essential_doc_ids": [],
        "agent_seen_doc_ids": [],
        "agent_stop_reason": None,
        "pipeline_plan": None,
        "slack_thread_context": None,
    })
    return result.get("retrieved_docs", [])


class SearchInput(BaseModel):
    reason: str = Field(
        description=(
            "One sentence explaining why this search is being performed. "
            "State this before searching — it sharpens query focus."
        ),
    )
    original_query: str = Field(
        description=(
            "The user's original message verbatim (copy the exact text from the trigger context). "
            "Pass this through unchanged — it is used as the reranking reference when rerank() is called."
        ),
    )
    query: str = Field(
        description=(
            "English-only search query. "
            "Write a semantic phrase, not a keyword list. "
            "Try a different angle if the previous search was insufficient."
        ),
    )
    sources: list[Literal["slack", "github", "jira", "confluence", "channel_talk"]] | None = Field(
        default=None,
        description=(
            "Source filter. Only specify when confident the information lives in a particular source. "
            "Leave as None to search across all sources."
        ),
    )


class RerankInput(BaseModel):
    original_query: str = Field(
        description=(
            "The user's original message verbatim. "
            "All accumulated search results are reranked against this query."
        ),
    )


class CatchUpKnowledgeBaseTool(BaseTool):
    """CatchUp에 인덱싱된 문서를 대상으로 vector 검색 및 rerank를 실행하는 도구.

    search()를 여러 번 호출해 문서를 누적한 뒤, rerank()를 한 번 호출해
    전체 누적 문서를 재순위화한다.
    GlobalContext는 ContextVar로 주입되며, 실행 전 bind()를 호출해야 한다.
    """

    def __init__(self) -> None:
        super().__init__(
            name="catchup_kb",
            display_name="CatchUp 지식베이스",
            description=(
                "Search the company knowledge base indexed from Slack, GitHub, Jira, Confluence, and ChannelTalk. "
                "Call search() one or more times with different queries to retrieve documents. "
                "Then call rerank() once to get the final ranked results. "
                "Synthesize your answer from the reranked passages."
            ),
        )

    @classmethod
    def bind(cls, global_context: GlobalContext) -> None:
        """실행 전 GlobalContext를 ContextVar에 바인딩하고 누적 문서를 초기화한다."""
        _context_var.set(global_context)
        _accumulated_docs_var.set([])

    def bind_execution_context(
        self,
        *,
        global_context: GlobalContext,
        trigger_event,
    ) -> None:
        self.bind(global_context)

    @action(
        input_model=SearchInput,
        output_model=None,
        description=(
            "Run vector search over the company knowledge base. "
            "Results accumulate across multiple calls. "
            "Call with different queries to cover different angles, then call rerank() once for the final ranked result."
        ),
        type=ActionType.READ,
    )
    async def search(
        self,
        reason: str,
        original_query: str,
        query: str,
        sources: list[str] | None = None,
    ) -> str:
        global_context = _context_var.get()
        if global_context is None:
            raise RuntimeError(
                "GlobalContext not bound. Call CatchUpKnowledgeBaseTool.bind() before running."
            )

        tool_filters = [SourceType(s) for s in sources] if sources else None

        logger.info(
            "kb_search_started",
            reason=reason,
            original_query=original_query,
            query=query,
            sources=sources,
        )

        docs = await _run_vector_search(query, global_context, tool_filters)

        accumulated = _accumulated_docs_var.get() or []
        accumulated.extend(docs)
        _accumulated_docs_var.set(accumulated)

        logger.info(
            "kb_search_completed",
            query=query,
            new_doc_count=len(docs),
            total_accumulated=len(accumulated),
        )

        return build_docs_summary(docs) if docs else "No relevant documents found."

    @action(
        input_model=RerankInput,
        output_model=None,
        description=(
            "Rerank all accumulated search results against the original user query. "
            "Call this once after all search() calls are done. "
            "Returns the final ranked passages — synthesize your answer from these."
        ),
        type=ActionType.READ,
    )
    async def rerank(self, original_query: str) -> str:
        accumulated = _accumulated_docs_var.get() or []

        if not accumulated:
            return "No documents to rerank. Call search() first."

        deduped = deduplicate_documents(accumulated)

        logger.info(
            "kb_rerank_started",
            original_query=original_query,
            doc_count=len(deduped),
        )

        rerank_service = _get_rerank_service_cached()
        result = await rerank_node(
            {
                "retrieved_docs": deduped,
                "rewritten_query": original_query,
                "rerank_count": 0,
                "pipeline_plan": None,
                "max_pipeline_type": "simple",
                "essential_doc_ids": [],
                "agent_seen_doc_ids": [],
                "agent_stop_reason": None,
            },
            rerank_service=rerank_service,
        )
        reranked_docs = result.get("retrieved_docs", deduped)

        _accumulated_docs_var.set([])

        logger.info("kb_rerank_completed", doc_count=len(reranked_docs))

        return build_docs_summary(reranked_docs) if reranked_docs else "No relevant documents found."
