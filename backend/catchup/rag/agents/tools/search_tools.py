import asyncio
from collections import Counter
from datetime import datetime

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
from catchup.rag.schemas.structures import VectorDbSearchQuery, MultiSearchRequest
from catchup.rag.state import AgentState

logger = structlog.get_logger()


# ---- LLM에 바인딩할 tool 스키마 ----
# 실제 실행은 search_tool_executor_node에서 처리한다.


@tool
def single_query_search(
    query: str,
    reason: str,
    keyword_tokens: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """
    벡터 DB에서 문서를 검색합니다.
    이전 검색 결과가 부족하거나, 다른 각도의 쿼리가 필요할 때 호출하세요.
    """
    raise NotImplementedError


@tool
def multi_query_search(
    search_requests: list[MultiSearchRequest],
    reason: str,
) -> str:
    """
    독립적인 여러 쿼리를 병렬로 실행하고 결과를 통합합니다.
    서로 다른 관점의 정보를 동시에 수집해야 할 때 사용하세요.
    """
    raise NotImplementedError


REACT_TOOLS = [single_query_search, multi_query_search]

# 헬퍼
async def _run_search(
    query: str,
    tool_filters: list,
    vector_db_service: BaseVectorDbService,
    keyword_tokens: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[list[Document], str]:
    """단일 쿼리 하이브리드 검색"""
    end_dt = datetime.fromisoformat(end_date) if end_date else None
    # date-only 문자열("YYYY-MM-DD")은 자정으로 파싱되어 
    # start==end==00:00:00이 되므로 하루 끝으로 보정
    if end_dt and end_dt.hour == 0 and end_dt.minute == 0 and end_dt.second == 0 and end_dt.microsecond == 0:
        end_dt = end_dt.replace(hour=23, minute=59, second=59)

    search_query = VectorDbSearchQuery(
        query=query,
        keyword_tokens=keyword_tokens or [],
        start_date=datetime.fromisoformat(start_date) if start_date else None,
        end_date=end_dt,
    )
    results = await _get_hybrid_search_results(
        vector_db_service=vector_db_service,
        queries=[search_query],
        tool_filters=tool_filters or [],
        k=40,
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


# 실행 노드
@log_node
async def search_tool_executor_node(
    state: AgentState,
    vector_db_service: BaseVectorDbService,
):
    """
    Agent의 tool_calls를 읽어 벡터 검색을 실행하고 ToolMessage를 반환.

    rerank는 여기서 수행하지 않는다. 모든 반복이 끝난 뒤
    collect_docs_node -> rerank_node에서 accumulated_docs 전체를 한 번만 rerank한다.
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
            if tool_name == "single_query_search":
                logger.debug(
                    "tool_executing",
                    tool=tool_name,
                    query=args["query"],
                    keyword_tokens=args.get("keyword_tokens"),
                    start_date=args.get("start_date"),
                    end_date=args.get("end_date"),
                )
                docs, summary = await _run_search(
                    query=args["query"],
                    tool_filters=tool_filters,
                    vector_db_service=vector_db_service,
                    keyword_tokens=args.get("keyword_tokens"),
                    start_date=args.get("start_date"),
                    end_date=args.get("end_date"),
                )
            elif tool_name == "multi_query_search":
                search_requests: list[dict] = args.get("search_requests", [])
                logger.debug(
                    "tool_executing",
                    tool=tool_name,
                    query_count=len(search_requests),
                    requests=search_requests,
                )
                tasks = [
                    _run_search(
                        query=req.get("query"),
                        tool_filters=tool_filters,
                        vector_db_service=vector_db_service,
                        keyword_tokens=req.get("keyword_tokens"),
                        start_date=req.get("start_date"),
                        end_date=req.get("end_date"),
                    )
                    for req in search_requests
                ]
                results_list = await asyncio.gather(*tasks, return_exceptions=True)
                docs = []
                summaries = []
                for req, result in zip(search_requests, results_list):
                    q = req.get("query")
                    if isinstance(result, Exception):
                        logger.warning("multi_query_search_failed", query=q, error=str(result))
                        summaries.append(f"search_query='{q}': failed")
                    else:
                        d, s = result
                        docs.extend(d)
                        summaries.append(s)
                summary = "\n---\n".join(summaries)
            else:
                docs, summary = [], f"unknown tool: {tool_name}"

        except Exception as e:
            logger.warning("tool_executor_failed", tool=tool_name, error=str(e), exc_info=True)
            docs, summary = [], f"execution error: {str(e)}"

        all_docs.extend(docs)
        tool_messages.append(ToolMessage(content=summary, tool_call_id=call_id))

    # 기존 누적 문서에 이번 턴 신규 문서를 id 기준 중복 제거 후 통합
    existing = state.get("accumulated_docs") or []
    seen_ids = {doc.id for doc in existing if doc.id}
    new_unique = []
    for doc in all_docs:
        doc_identifier = doc.id if doc.id else hash(doc.page_content)
        if doc_identifier not in seen_ids:
            new_unique.append(doc)
            seen_ids.add(doc_identifier)
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
