from collections import Counter

import structlog

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.rag.nodes.utils import deduplicate_documents
from catchup.rag.nodes.utils import get_document_id
from catchup.rag.schemas.structures import SearchTurnMeta
from catchup.rag.state import AgentState

logger = structlog.get_logger()

# multi-turn reuse 시 merged docs 상한. complex pipeline K(20)와 동일.
_REUSE_MAX_DOCS = 20


async def merge_cache_node(state: AgentState):
    """검색 파이프라인의 rerank 결과(retrieved_docs)로 doc_cache를 교체하고
    search_turn_history에 경량 메타데이터를 누적한다.

    doc_cache는 직전 검색 턴의 결과만 보존한다(hot cache).
    search_turn_history는 모든 검색 턴의 doc_ids + 메타데이터를 누적한다.
    reuse 턴에서는 호출되지 않는다.
    """
    new_docs = state.get("retrieved_docs", [])
    turn_number = state.get("turn_number", 0)
    rewritten_query = state.get("rewritten_query", "")
    query_topic = state.get("query_topic")

    source_distribution = dict(
        Counter(d.metadata.get("source", "unknown") for d in new_docs)
    )
    doc_ids = [get_document_id(d) for d in new_docs]

    new_snapshot = SearchTurnMeta(
        turn_number=turn_number,
        rewritten_query=rewritten_query,
        query_topic=query_topic,
        doc_ids=doc_ids,
        source_distribution=source_distribution,
    )

    existing_history = list(state.get("search_turn_history", []))
    updated_history = existing_history + [new_snapshot]

    logger.info(
        "doc_cache_updated",
        doc_count=len(new_docs),
        search_history_len=len(updated_history),
    )
    return {
        "doc_cache": new_docs,
        "search_turn_history": updated_history,
    }


async def prepare_cache_node(
    state: AgentState,
    vector_db_service: BaseVectorDbService,
):
    """prepare_cache_node 진입 시 retrieved_docs를 구성한다.

    항상 doc_cache(hot cache)를 포함하고, supervisor가 cache_turn_numbers를
    지정한 경우 해당 검색 턴의 docs를 DB에서 lazy fetch하여 병합한다.
    """
    hot_docs = state.get("doc_cache", [])
    search_turn_history = state.get("search_turn_history", [])

    pipeline_plan = state.get("pipeline_plan")
    fetch_indices = (
        pipeline_plan.cache_turn_numbers
        if pipeline_plan and pipeline_plan.cache_turn_numbers
        else None
    )

    if fetch_indices and search_turn_history:
        # supervisor가 명시한 턴만 사용. hot cache는 자동 포함 안 함.
        # hot cache의 search_turn_history 내 인덱스(1-based)가 fetch_indices에 포함된 경우에만 hot_docs 사용.
        hot_cache_idx = len(search_turn_history)
        include_hot = hot_cache_idx in fetch_indices

        ids_to_fetch: list[str] = []
        for i in fetch_indices:
            if i == hot_cache_idx or not (1 <= i <= len(search_turn_history)):
                continue
            raw = search_turn_history[i - 1]
            snap = SearchTurnMeta.model_validate(raw) if isinstance(raw, dict) else raw
            ids_to_fetch.extend(snap.doc_ids)

        all_docs = list(hot_docs) if include_hot else []
        if ids_to_fetch:
            past_docs = await vector_db_service.fetch_by_ids(ids_to_fetch)
            all_docs.extend(past_docs)

        merged = deduplicate_documents(all_docs)[:_REUSE_MAX_DOCS]
        if not merged:
            merged = hot_docs  # 안전 fallback
    else:
        merged = hot_docs

    logger.info(
        "prepare_cache",
        hot_doc_count=len(hot_docs),
        fetch_indices=fetch_indices,
        merged_doc_count=len(merged),
    )
    return {"retrieved_docs": merged}
