import json
from datetime import datetime

from langchain_core.documents import Document

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.db.models import SourceType
from catchup.rag.schemas.filters import build_temporal_filters

_VALID_SOURCES = {s.value for s in SourceType}


async def run_search(
    query: str,
    k: int,
    sources: list[str] | None,
    date_from: str | None,
    date_to: str | None,
    vector_db_service: BaseVectorDbService,
) -> list[dict]:
    tool_filters = _parse_sources(sources)
    temporal_filters = build_temporal_filters(
        tool_filters,
        _parse_date(date_from, "date_from"),
        _parse_date(date_to, "date_to"),
    )

    docs: list[Document] = await vector_db_service.hybrid_search(
        query=query,
        k=k,
        weights=[0.6, 0.4],  # [vector, contextual_content]
        tool_filters=tool_filters,
        temporal_filters=temporal_filters or None,
    )
    return _format_docs(docs)


def _parse_sources(sources: list[str] | None) -> list[SourceType] | None:
    if not sources:
        return None
    invalid = [s for s in sources if s not in _VALID_SOURCES]
    if invalid:
        raise ValueError(
            f"유효하지 않은 source: {invalid}. "
            f"허용값: {sorted(_VALID_SOURCES)}"
        )
    return [SourceType(s) for s in sources]


def _parse_date(value: str | None, field: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f"{field}은 ISO8601 형식이어야 합니다 (예: '2025-01-01'). "
            f"받은 값: {value!r}"
        )


def _format_docs(docs: list[Document]) -> list[dict]:
    results = []
    for doc in docs:
        meta = doc.metadata or {}
        results.append({
            "content": doc.page_content,
            "source": meta.get("source"),
            "url": meta.get("url"),
            "created_at": meta.get("created_at"),
            "author": meta.get("author_name") or meta.get("author"),
            "summary": meta.get("summary"),
        })
    return results


def serialize_results(results: list[dict]) -> str:
    return json.dumps(results, ensure_ascii=False, indent=2)
