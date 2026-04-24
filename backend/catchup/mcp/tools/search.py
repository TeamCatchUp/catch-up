import asyncio
import json
from datetime import datetime

from langchain_core.documents import Document

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.db.models import SourceType
from catchup.rag.schemas.filters import build_temporal_filters


async def run_search(
    query: str,
    k: int,
    sources: list[str] | None,
    date_from: str | None,
    date_to: str | None,
    vector_db_service: BaseVectorDbService,
) -> list[dict]:
    tool_filters = [SourceType(s) for s in sources] if sources else None

    start_date = datetime.fromisoformat(date_from) if date_from else None
    end_date = datetime.fromisoformat(date_to) if date_to else None
    temporal_filters = build_temporal_filters(tool_filters, start_date, end_date)

    loop = asyncio.get_running_loop()
    docs: list[Document] = await loop.run_in_executor(
        None,
        lambda: vector_db_service.hybrid_search(
            query=query,
            k=k,
            weights=[0.5, 0.3, 0.2],  # [vector, title, contextual_content]
            tool_filters=tool_filters,
            temporal_filters=temporal_filters or None,
        ),
    )
    return _format_docs(docs)


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
