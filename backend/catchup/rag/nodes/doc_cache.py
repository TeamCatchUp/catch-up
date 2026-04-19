import structlog
from langchain_core.documents import Document

from catchup.rag.state import AgentState

logger = structlog.get_logger()

_DOC_CACHE_WINDOW = 50


async def merge_cache_node(state: AgentState):
    """rerank 결과(retrieved_docs)를 doc_cache에 병합한다.

    신규 문서를 앞에 두고 기존 캐시에서 중복 없는 항목을 window cap까지 채운다.
    오래된 문서는 자연스럽게 cap 밖으로 밀려난다.
    """
    existing = state.get("doc_cache", [])
    new_docs = state.get("retrieved_docs", [])
    merged = _merge_docs(existing, new_docs)
    logger.info(
        "doc_cache_merged",
        new_docs=len(new_docs),
        existing=len(existing),
        merged=len(merged),
    )
    return {"doc_cache": merged}


async def prepare_cache_node(state: AgentState):
    """reuse 파이프라인 진입 시 doc_cache를 retrieved_docs로 복사한다.

    reuse subgraph의 rerank_node가 현재 쿼리 기준으로 재정렬할 수 있도록
    캐시 전체를 retrieved_docs에 노출한다.
    """
    doc_cache = state.get("doc_cache", [])
    logger.info("prepare_cache", doc_cache_size=len(doc_cache))
    return {"retrieved_docs": doc_cache}


def _merge_docs(existing: list[Document], new_docs: list[Document]) -> list[Document]:
    seen_ids = {doc.id for doc in new_docs}
    merged = list(new_docs)
    for doc in existing:
        if len(merged) >= _DOC_CACHE_WINDOW:
            break
        if doc.id not in seen_ids:
            merged.append(doc)
            seen_ids.add(doc.id)
    return merged
