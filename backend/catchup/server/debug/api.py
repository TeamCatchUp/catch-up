from typing import Any

import structlog
from fastapi import APIRouter
from fastapi import HTTPException
from langchain_core.documents import Document
from pydantic import BaseModel
from pydantic import Field

from catchup.components.reranker.constants import RerankerProvider
from catchup.components.reranker.factory import get_rerank_service
from catchup.components.vector_db.factory import get_vector_db_service
from catchup.components.vector_db.pgvector.constants import VectorDbProvider
from catchup.db.models import SourceType
from catchup.rag.nodes.utils import deduplicate_documents
from catchup.rag.nodes.utils import get_document_id

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])


class SearchProbeRequest(BaseModel):
    rewritten_query: str
    queries: list[str] = Field(..., min_length=1)
    weights: list[float] = Field(default=[0.6, 0.4])
    k: int = Field(default=100, ge=1)
    score_threshold: float = Field(default=0.0)
    tool_filters: list[str] = Field(default_factory=list)


class DocResult(BaseModel):
    doc_id: str
    score: float
    title: str
    content_preview: str
    source: str
    created_at: str | None


class SearchProbeResponse(BaseModel):
    pre_rerank: list[DocResult]
    post_rerank: list[DocResult]
    query_count: int
    pre_rerank_count: int
    post_rerank_count: int


def _to_doc_result(doc: Document, score_key: str) -> DocResult:
    md = doc.metadata
    return DocResult(
        doc_id=get_document_id(doc),
        score=round(float(md.get(score_key) or 0.0), 6),
        title=md.get("title") or "",
        content_preview=doc.page_content[:300],
        source=md.get("source", "unknown"),
        created_at=str(md["created_at"]) if md.get("created_at") else None,
    )


@router.post("/search-probe", response_model=SearchProbeResponse)
async def search_probe(body: SearchProbeRequest) -> SearchProbeResponse:
    vector_db_service = get_vector_db_service(VectorDbProvider.PGVECTOR)
    rerank_service = get_rerank_service(RerankerProvider.AWS_BEDROCK)

    try:
        tool_filters: list[SourceType] | None = (
            [SourceType(f) for f in body.tool_filters] if body.tool_filters else None
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    query_dicts: list[dict[str, Any]] = [{"query": q} for q in body.queries]

    results = await vector_db_service.hybrid_search_batch(
        queries=query_dicts,
        k=body.k,
        weights=body.weights,
        tool_filters=tool_filters,
    )

    flattened = deduplicate_documents([doc for sublist in results for doc in sublist])

    pre_rerank_items = [_to_doc_result(d, "score") for d in flattened]

    reranked = await rerank_service.rerank(
        query=body.rewritten_query,
        documents=flattened,
        top_n=len(flattened),
    )

    post_rerank_items = [_to_doc_result(d, "relevance_score") for d in reranked]

    logger.info(
        "search_probe_completed",
        query_count=len(body.queries),
        pre_rerank_count=len(pre_rerank_items),
        post_rerank_count=len(post_rerank_items),
    )

    return SearchProbeResponse(
        pre_rerank=pre_rerank_items,
        post_rerank=post_rerank_items,
        query_count=len(body.queries),
        pre_rerank_count=len(pre_rerank_items),
        post_rerank_count=len(post_rerank_items),
    )
