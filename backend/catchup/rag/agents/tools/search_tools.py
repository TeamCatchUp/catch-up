import asyncio
import json
from datetime import datetime

import structlog
from langchain_core.callbacks import adispatch_custom_event
from langchain_core.documents import Document
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.rag.nodes.utils import build_docs_summary
from catchup.rag.nodes.utils import deduplicate_documents
from catchup.rag.nodes.utils import get_document_id
from catchup.rag.nodes.utils import log_node
from catchup.rag.schemas.structures import MultiSearchRequest
from catchup.rag.state import AgentState

logger = structlog.get_logger()

_PREVIEW_LIMIT = 10  # ToolMessage에서 한 번에 보여줄 신규 문서 수


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


@tool
def submit_result(
    key_document_indices: list[int],
    key_documents: list[str],
    search_coverage: list[str],
    reason_for_stopping: str,
) -> str:
    """
    검색을 완료하고 결과를 제출합니다.
    수집된 문서가 충분하거나 검색이 포화 상태일 때 반드시 이 도구를 호출하세요.
    절대 자유 형식 텍스트로 답변을 작성하지 마세요 — 이 도구만 사용하세요.
    """
    raise NotImplementedError


REACT_TOOLS = [single_query_search, multi_query_search, submit_result]


# 헬퍼
async def _run_search(
    query: str,
    tool_filters: list,
    vector_db_service: BaseVectorDbService,
    keyword_tokens: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[list[Document], str]:
    """단일 쿼리 하이브리드 검색. 반환값: (검색 결과 docs, 쿼리 문자열).

    summary 생성은 호출자(executor)가 agent_seen_doc_ids를 참조해 수행한다.
    """
    end_dt = datetime.fromisoformat(end_date) if end_date else None
    # date-only 문자열("YYYY-MM-DD")은 자정으로 파싱되어
    # start==end==00:00:00이 되므로 하루 끝으로 보정
    if (
        end_dt
        and end_dt.hour == 0
        and end_dt.minute == 0
        and end_dt.second == 0
        and end_dt.microsecond == 0
    ):
        end_dt = end_dt.replace(hour=23, minute=59, second=59)

    search_query = {
        "query": query,
        "keyword_tokens": keyword_tokens or [],
        "start_date": datetime.fromisoformat(start_date) if start_date else None,
        "end_date": end_dt,
    }
    results = await vector_db_service.hybrid_search_batch(
        queries=[search_query],
        tool_filters=tool_filters or [],
        k=40,
        weights=[0.6, 0.4],
    )
    # 리스트의 리스트를 평탄화하고 중복 제거
    flattened_results = [doc for sublist in results for doc in sublist]
    docs = deduplicate_documents(flattened_results)
    return docs, query


def _dedup_tool_calls(tool_calls: list) -> list[dict]:
    """multi_query_search의 keyword_tokens를 cross-query 중복 제거한 tool_calls 반환."""
    result = []
    for tc in tool_calls:
        if tc["name"] == "multi_query_search":
            raw = tc["args"].get("search_requests", [])
            # Extended thinking + tool use 조합에서 LLM이 list 대신 JSON 문자열로
            # 직렬화해 반환하는 경우 복구를 시도한다.
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                    logger.info(
                        "multi_query_search_requests_recovered",
                        parsed_count=len(raw),
                    )
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(
                        "multi_query_search_requests_parse_failed",
                        raw_payload=raw,
                        parse_error=str(e),
                        raw_len=len(raw),
                    )
                    raw = []
            used: set[str] = set()
            deduped = []
            for req in raw:
                if not isinstance(req, dict):
                    logger.warning("multi_query_search_invalid_request", req=repr(req)[:100])
                    continue
                tokens = req.get("keyword_tokens") or []
                unique = [t for t in tokens if t not in used]
                used.update(unique)
                deduped.append({**req, "keyword_tokens": unique})
            result.append({**tc, "args": {**tc["args"], "search_requests": deduped}})
        else:
            result.append(tc)
    return result


def _build_search_queries(tool_calls: list) -> list[dict]:
    """tool_calls에서 {vector, keyword} 구조로 쿼리 목록을 추출한다."""
    queries = []
    for tc in tool_calls:
        args = tc.get("args", {})
        if tc["name"] == "single_query_search":
            queries.append({
                "vector": args.get("query", ""),
                "keyword": args.get("keyword_tokens") or [],
            })
        elif tc["name"] == "multi_query_search":
            for req in args.get("search_requests", []):
                queries.append({
                    "vector": req.get("query", ""),
                    "keyword": req.get("keyword_tokens") or [],
                })
    return queries


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

    deduped_tool_calls = _dedup_tool_calls(last_message.tool_calls)
    search_queries = _build_search_queries(deduped_tool_calls)
    await adispatch_custom_event(
        "process",
        {
            "status": "in_progress",
            "node": "tool_executor",
            "content": {"queries": search_queries},
        },
    )

    # agent가 ToolMessage로 본 doc ID 집합. 
    # 중복 노출 방지 + 전역 인덱스 계산에 사용.
    seen_ids: set[str] = set(state.get("agent_seen_doc_ids") or [])
    shown_ids: list[str] = []  # 이번 호출에서 노출한 doc ID 목록 (순서 보존)

    tool_messages: list[ToolMessage] = []
    all_docs: list[Document] = []

    def _summarize_hits(query: str, hits: list[Document]) -> str:
        unseen = [d for d in hits if get_document_id(d) not in seen_ids]
        shown = unseen[:_PREVIEW_LIMIT]

        # len(seen_ids)는 이 배치를 추가하기 전 전체 노출 수 → 1-based 시작 인덱스
        start = len(seen_ids) + 1

        for d in shown:
            doc_id = get_document_id(d)
            seen_ids.add(doc_id)
            shown_ids.append(doc_id)

        header = (
            f"Search complete: query='{query}' | "
            f"hits={len(hits)} new={len(unseen)} shown={len(shown)}"
        )
        if not shown:
            return f"{header}\n(no new documents in this search)"
        return f"{header}\n{build_docs_summary(shown, max_docs=_PREVIEW_LIMIT, start_index=start)}"

    for tool_call in deduped_tool_calls:
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
                docs, query_str = await _run_search(
                    query=args["query"],
                    tool_filters=tool_filters,
                    vector_db_service=vector_db_service,
                    keyword_tokens=args.get("keyword_tokens"),
                    start_date=args.get("start_date"),
                    end_date=args.get("end_date"),
                )
                summary = _summarize_hits(query_str, docs)
            elif tool_name == "multi_query_search":
                deduped_requests: list[dict] = args.get("search_requests", [])

                logger.debug(
                    "tool_executing",
                    tool=tool_name,
                    query_count=len(deduped_requests),
                    requests=deduped_requests,
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
                    for req in deduped_requests
                ]
                results_list = await asyncio.gather(*tasks, return_exceptions=True)
                docs = []
                summaries = []
                for req, result in zip(deduped_requests, results_list):
                    q = req.get("query")
                    if isinstance(result, Exception):
                        logger.warning(
                            "multi_query_search_failed", query=q, error=str(result)
                        )
                        summaries.append(f"search_query='{q}': failed")
                    else:
                        d, query_str = result
                        docs.extend(d)
                        summaries.append(_summarize_hits(query_str, d))
                summary = "\n---\n".join(summaries)
            else:
                docs, summary = [], f"unknown tool: {tool_name}"

        except Exception as e:
            logger.warning(
                "tool_executor_failed", tool=tool_name, error=str(e), exc_info=True
            )
            docs, summary = [], f"execution error: {str(e)}"

        all_docs.extend(docs)
        tool_messages.append(ToolMessage(content=summary, tool_call_id=call_id))

    # 기존 누적 문서에 이번 턴 신규 문서를 id 기준 중복 제거 후 통합
    # 최신 검색 결과가 앞에 오도록 all_docs를 앞에 배치
    existing = state.get("accumulated_docs") or []
    merged = deduplicate_documents(all_docs + existing)

    logger.info(
        "tool_executor_completed",
        tool_count=len(last_message.tool_calls),
        new_docs=len(all_docs),
        total_accumulated=len(merged),
        agent_newly_shown=len(shown_ids),
        agent_seen_total=len(seen_ids),
    )

    await adispatch_custom_event(
        "process",
        {
            "status": "completed",
            "node": "tool_executor",
            "reasoning": f"{len(all_docs)}건의 문서를 찾았어요.",
        },
    )

    return {
        "messages": tool_messages,
        "accumulated_docs": merged,
        "agent_seen_doc_ids": (state.get("agent_seen_doc_ids") or []) + shown_ids,
    }
