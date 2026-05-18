from typing import Any

import structlog
from fastapi import APIRouter
from fastapi import HTTPException
from langchain_core.documents import Document
from pydantic import BaseModel
from pydantic import Field

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.reranker.constants import RerankerProvider
from catchup.components.reranker.factory import get_rerank_service
from catchup.components.vector_db.factory import get_vector_db_service
from catchup.components.vector_db.pgvector.constants import VectorDbProvider
from catchup.configs.config import settings
from catchup.db.models import SourceType
from catchup.observability.langfuse.configs import get_observe
from catchup.rag.nodes.utils import deduplicate_documents
from catchup.rag.nodes.utils import get_document_id

logger = structlog.get_logger()
observe = get_observe()

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])


class SearchQuery(BaseModel):
    query: str
    keyword_tokens: list[str] = Field(default_factory=list)


class SearchProbeRequest(BaseModel):
    rewritten_query: str
    queries: list[SearchQuery] = Field(..., min_length=1)
    weights: list[float] = Field(default=[0.6, 0.4], min_length=2, max_length=2)
    k: int = Field(default=100, ge=1)
    score_threshold: float = Field(default=0.0)
    tool_filters: list[str] = Field(default_factory=list)


class PreRankDocResult(BaseModel):
    doc_id: str
    rrf_score: float
    title: str
    page_content: str
    contextual_content: str | None
    source: str
    created_at: str | None


class PostRankDocResult(BaseModel):
    doc_id: str
    relevance_score: float
    title: str
    page_content: str
    contextual_content: str | None
    source: str
    created_at: str | None


class SearchProbeResponse(BaseModel):
    pre_rerank: list[PreRankDocResult]
    post_rerank: list[PostRankDocResult]
    query_count: int
    pre_rerank_count: int
    post_rerank_count: int


def _to_pre_rank_result(doc: Document) -> PreRankDocResult:
    md = doc.metadata
    return PreRankDocResult(
        doc_id=get_document_id(doc),
        rrf_score=round(float(md.get("score") or 0.0), 6),
        title=md.get("title") or "",
        page_content=doc.page_content,
        contextual_content=md.get("contextual_content"),
        source=md.get("source", "unknown"),
        created_at=str(md["created_at"]) if md.get("created_at") else None,
    )


def _to_post_rank_result(doc: Document) -> PostRankDocResult:
    md = doc.metadata
    return PostRankDocResult(
        doc_id=get_document_id(doc),
        relevance_score=round(float(md.get("relevance_score") or 0.0), 6),
        title=md.get("title") or "",
        page_content=doc.page_content,
        contextual_content=md.get("contextual_content"),
        source=md.get("source", "unknown"),
        created_at=str(md["created_at"]) if md.get("created_at") else None,
    )


@router.post("/search-probe", response_model=SearchProbeResponse)
@observe(name="debug-search-probe")
async def search_probe(body: SearchProbeRequest) -> SearchProbeResponse:
    embeddings = get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
    vector_db_service = get_vector_db_service(VectorDbProvider.PGVECTOR, embeddings)
    rerank_service = get_rerank_service(RerankerProvider.AWS_BEDROCK)

    try:
        tool_filters: list[SourceType] | None = (
            [SourceType(f) for f in body.tool_filters] if body.tool_filters else None
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    query_dicts: list[dict[str, Any]] = [
        {"query": q.query, "keyword_tokens": q.keyword_tokens}
        for q in body.queries
    ]

    async def _run() -> SearchProbeResponse:
        results = await vector_db_service.hybrid_search_batch(
            queries=query_dicts,
            k=body.k,
            weights=body.weights,
            tool_filters=tool_filters,
        )
        flattened = deduplicate_documents(
            [doc for sublist in results for doc in sublist]
        )
        pre_rerank_items = [_to_pre_rank_result(d) for d in flattened]

        reranked = await rerank_service.rerank(
            query=body.rewritten_query,
            documents=flattened,
            top_n=len(flattened),
        )
        post_rerank_items = [_to_post_rank_result(d) for d in reranked]

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

    if settings.ENABLE_LANGFUSE:
        from langfuse import propagate_attributes

        with propagate_attributes(
            metadata={
                "rewritten_query": body.rewritten_query,
                "queries": [q.query for q in body.queries],
                "keyword_tokens": [q.keyword_tokens for q in body.queries],
                "weights": body.weights,
                "tool_filters": body.tool_filters,
            }
        ):
            return await _run()

    return await _run()
