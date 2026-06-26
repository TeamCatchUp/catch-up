from __future__ import annotations

from typing import Literal

import structlog
from fastapi import APIRouter
from fastapi import HTTPException
from langchain_core.documents import Document
from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.v2.retrieval import PGBigmRetriever
from catchup.components.vector_db.v2.retrieval import RetrievalService
from catchup.components.vector_db.v2.vector_store import VectorStore
from catchup.db.async_engine import AsyncSessionLocal
from catchup.db.models import SourceType

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/debug/retrieval", tags=["debug"])


class RetrievalV2ProbeRequest(BaseModel):
    query: str
    keyword_tokens: list[str] = Field(default_factory=list)
    weights: list[float] = Field(default=[0.5, 0.3, 0.2], min_length=3, max_length=3)
    k: int = Field(default=10, ge=1, le=100)
    score_threshold: float = Field(default=0.2, ge=0.0, le=1.0)
    tool_filters: list[str] = Field(default_factory=list)

    @field_validator("weights")
    @classmethod
    def _weights_sum(cls, v: list[float]) -> list[float]:
        if abs(sum(v) - 1.0) > 0.01:
            raise ValueError("weights must sum to 1.0")
        return v


class DocMetrics(BaseModel):
    rrf_score: float | None
    similarity_score: float | None
    keyword_score: float | None
    hit_types: list[str]


class DocResult(BaseModel):
    doc_id: str
    title: str
    body: str
    source: str
    created_at: str | None
    metrics: DocMetrics


class RetrievalV2ProbeResponse(BaseModel):
    search_mode: Literal["vector_only", "hybrid"]
    vector_hits: list[DocResult]
    body_hits: list[DocResult]
    title_hits: list[DocResult]
    merged: list[DocResult]
    vector_count: int
    body_count: int
    title_count: int
    merged_count: int


def _doc_result(doc: Document) -> DocResult:
    md = doc.metadata
    return DocResult(
        doc_id=doc.id or "",
        title=md.get("title") or "",
        body=(md.get("body") or "")[:500],
        source=md.get("source") or "",
        created_at=str(md["created_at"]) if md.get("created_at") else None,
        metrics=DocMetrics(
            rrf_score=round(float(md["score"]), 6) if md.get("score") is not None else None,
            similarity_score=(
                round(float(md["similarity_score"]), 4)
                if md.get("similarity_score") is not None
                else None
            ),
            keyword_score=(
                round(float(md["keyword_score"]), 4)
                if md.get("keyword_score") is not None
                else None
            ),
            hit_types=md.get("hit_types") or [],
        ),
    )


@router.post("/lcpg-v2", response_model=RetrievalV2ProbeResponse)
async def retrieval_v2_probe(
    body: RetrievalV2ProbeRequest,
) -> RetrievalV2ProbeResponse:
    """v2 retrieval의 vector / body / title / merged 결과를 각각 반환한다."""
    try:
        tool_filters: list[SourceType] | None = (
            [SourceType(f) for f in body.tool_filters] if body.tool_filters else None
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    embeddings = get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
    vs = VectorStore(embeddings=embeddings)
    await vs.initialize()

    retriever = PGBigmRetriever(async_session_factory=AsyncSessionLocal)
    service = RetrievalService(vector_store=vs, keyword_retriever=retriever)

    langchain_store = vs.get_langchain_vector_store()

    # vector 단독 결과 (score_threshold 미적용, 비교용)
    vector_filter = RetrievalService._build_vector_filter(tool_filters, None)
    raw_vector = await langchain_store.asimilarity_search_with_score(
        body.query, k=body.k, filter=vector_filter
    )
    vector_hits: list[DocResult] = []
    for doc, dist in raw_vector:
        doc.metadata["similarity_score"] = round(1.0 - dist, 4)
        vector_hits.append(_doc_result(doc))

    # body / title 단독 결과
    if body.keyword_tokens:
        body_docs = await retriever.search_body(
            body.keyword_tokens, k=body.k, tool_filters=tool_filters
        )
        title_docs = await retriever.search_title(
            body.keyword_tokens, k=body.k, tool_filters=tool_filters
        )
    else:
        body_docs = []
        title_docs = []

    body_hits = [_doc_result(d) for d in body_docs]
    title_hits = [_doc_result(d) for d in title_docs]

    # 3-way merged
    merged = await service.hybrid_search(
        query=body.query,
        k=body.k,
        weights=body.weights,
        tool_filters=tool_filters,
        keyword_tokens=body.keyword_tokens or None,
        score_threshold=body.score_threshold,
    )
    merged_results = [_doc_result(d) for d in merged]
    search_mode: Literal["vector_only", "hybrid"] = (
        "hybrid"
        if any(d.metadata.get("score") is not None for d in merged)
        else "vector_only"
    )

    logger.info(
        "retrieval_v2_probe_completed",
        search_mode=search_mode,
        vector_count=len(vector_hits),
        body_count=len(body_hits),
        title_count=len(title_hits),
        merged_count=len(merged_results),
    )

    return RetrievalV2ProbeResponse(
        search_mode=search_mode,
        vector_hits=vector_hits,
        body_hits=body_hits,
        title_hits=title_hits,
        merged=merged_results,
        vector_count=len(vector_hits),
        body_count=len(body_hits),
        title_count=len(title_hits),
        merged_count=len(merged_results),
    )
