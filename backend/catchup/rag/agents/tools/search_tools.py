import asyncio
from collections import Counter
from datetime import datetime
from typing import Optional

import structlog
from langchain_core.documents import Document
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.rag.nodes.search_vector_db.search_vector_db import (
    _deduplicate_search_results,
)
from catchup.rag.nodes.search_vector_db.search_vector_db import (
    _get_hybrid_search_results,
)
from catchup.rag.nodes.utils import log_node
from catchup.rag.nodes.utils import resolve_temporal_context
from catchup.rag.schemas.structures import VectorDbSearchQuery
from catchup.rag.state import AgentState

logger = structlog.get_logger()


# ---- LLM에 바인딩할 tool 스키마 ----
# 실제 실행은 search_tool_executor_node에서 처리한다.


@tool
def search_and_rerank(
    query: str,
    reason: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """벡터 DB에서 문서를 검색합니다.
    이전 검색 결과가 부족하거나, 다른 각도의 쿼리가 필요할 때 호출하세요."""
    raise NotImplementedError


@tool
def parallel_search(
    queries: list[str],
    reason: str,
) -> str:
    """독립적인 여러 쿼리를 병렬로 실행하고 결과를 통합합니다.
    서로 다른 관점의 정보를 동시에 수집해야 할 때 사용하세요."""
    raise NotImplementedError


REACT_TOOLS = [search_and_rerank, parallel_search]


# ---- 검색 실행 헬퍼 ----
# rerank는 모든 tool 호출이 끝난 뒤 collect_docs → rerank_node에서 한 번만 실행한다.


async def _run_search(
    query: str,
    tool_filters: list,
    vector_db_service: BaseVectorDbService,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> tuple[list[Document], str]:
    """단일 쿼리 벡터 검색 (rerank 없음)."""
    search_query = VectorDbSearchQuery(
        query=query,
        start_date=datetime.fromisoformat(start_date) if start_date else None,
        end_date=datetime.fromisoformat(end_date) if end_date else None,
    )
    results = await _get_hybrid_search_results(
        vector_db_service=vector_db_service,
        queries=[search_query],
        tool_filters=tool_filters or [],
        k=100,
        weights=[0.6, 0.4],
    )
    docs = _deduplicate_search_results(results)
    summary = _build_search_summary(query=query, docs=docs)
    return docs, summary


def _build_search_summary(query: str, docs: list[Document]) -> str:
    """Agent가 다음 결정에 활용할 검색 결과 요약 문자열 생성."""
    if not docs:
        return f"검색 완료: 쿼리='{query}' | 결과 없음"

    source_counts = Counter(d.metadata.get("source", "unknown") for d in docs)
    source_str = ", ".join(f"{src}:{cnt}" for src, cnt in source_counts.items())

    lines = [f"검색 완료: 쿼리='{query}' | 결과 {len(docs)}건 ({source_str})", "상위 문서 요약:"]
    for i, doc in enumerate(docs[:3], 1):
        source = doc.metadata.get("source", "unknown")
        temporal = resolve_temporal_context(doc.metadata)
        snippet = doc.page_content[:150].replace("\n", " ")
        lines.append(f"[{i}] ({source}) {temporal}\n    {snippet}")
    return "\n".join(lines)


# ---- 실행 노드 ----


@log_node
async def search_tool_executor_node(
    state: AgentState,
    vector_db_service: BaseVectorDbService,
):
    """Agent의 tool_calls를 읽어 벡터 검색을 실행하고 ToolMessage를 반환.

    rerank는 여기서 수행하지 않는다. 모든 반복이 끝난 뒤
    collect_docs_node → rerank_node에서 accumulated_docs 전체를 한 번만 rerank한다.
    """
    messages = state.get("messages", [])
    if not messages:
        return {}

    last_message = messages[-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {}

    tool_filters = state.get("tool_filters") or []

    tool_messages: list[ToolMessage] = []
    all_docs: list[Document] = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        args = tool_call["args"]
        call_id = tool_call["id"]

        try:
            if tool_name == "search_and_rerank":
                docs, summary = await _run_search(
                    query=args["query"],
                    tool_filters=tool_filters,
                    vector_db_service=vector_db_service,
                    start_date=args.get("start_date"),
                    end_date=args.get("end_date"),
                )
            elif tool_name == "parallel_search":
                queries: list[str] = args["queries"]
                tasks = [
                    _run_search(
                        query=q,
                        tool_filters=tool_filters,
                        vector_db_service=vector_db_service,
                    )
                    for q in queries
                ]
                results_list = await asyncio.gather(*tasks, return_exceptions=True)
                docs = []
                summaries = []
                for q, result in zip(queries, results_list):
                    if isinstance(result, Exception):
                        logger.warning("parallel_search_query_failed", query=q, error=str(result))
                        summaries.append(f"쿼리='{q}': 실패")
                    else:
                        d, s = result
                        docs.extend(d)
                        summaries.append(s)
                summary = "\n---\n".join(summaries)
            else:
                docs, summary = [], f"알 수 없는 tool: {tool_name}"

        except Exception as e:
            logger.warning("tool_executor_failed", tool=tool_name, error=str(e), exc_info=True)
            docs, summary = [], f"실행 오류: {str(e)}"

        all_docs.extend(docs)
        tool_messages.append(ToolMessage(content=summary, tool_call_id=call_id))

    # 기존 누적 문서에 이번 턴 신규 문서를 id 기준 중복 제거 후 통합
    existing = state.get("accumulated_docs") or []
    existing_ids = {doc.id for doc in existing if doc.id}
    new_unique = [doc for doc in all_docs if doc.id not in existing_ids]
    merged = existing + new_unique

    logger.info(
        "tool_executor_completed",
        tool_count=len(last_message.tool_calls),
        new_docs=len(new_unique),
        total_accumulated=len(merged),
    )

    return {
        "messages": tool_messages,
        "accumulated_docs": merged,
    }
