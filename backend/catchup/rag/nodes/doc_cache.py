import structlog

from catchup.rag.state import AgentState

logger = structlog.get_logger()


async def merge_cache_node(state: AgentState):
    """검색 파이프라인의 rerank 결과(retrieved_docs)로 doc_cache를 교체한다.

    doc_cache는 직전 검색 턴의 결과만 보존한다. reuse 턴에서는 호출되지 않는다.
    """
    new_docs = state.get("retrieved_docs", [])
    logger.info("doc_cache_updated", doc_count=len(new_docs))
    return {"doc_cache": new_docs}


async def prepare_cache_node(state: AgentState):
    """reuse 파이프라인 진입 시 doc_cache를 retrieved_docs로 복사한다."""
    doc_cache = state.get("doc_cache", [])
    logger.info("prepare_cache", doc_cache_size=len(doc_cache))
    return {"retrieved_docs": doc_cache}
