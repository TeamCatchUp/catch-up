from __future__ import annotations

import asyncio
import time
from datetime import timezone
from typing import Any
from typing import override

import structlog
from langchain_core.documents import Document
from sqlalchemy import TextClause
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.components.vector_db.rank import weighted_reciprocal_rank
from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_TABLE_NAME
from catchup.components.vector_db.v2.vector_store import VectorStore
from catchup.configs.config import settings
from catchup.db.models import SourceType
from catchup.rag.schemas.filters import TemporalFilter
from catchup.rag.schemas.filters import build_temporal_filters

logger = structlog.get_logger(__name__)


class PGBigmRetriever:
    """pg_bigm 기반 키워드 검색기.
    
    body와 title 필드에 각각 LIKE, fuzzy 유사도를 쿼리한다.
    SQL 결과 순위를 RRF 방식으로 누적해 최종 키워드 검색 순위를 결정한다.
    """

    def __init__(
        self,
        *,
        async_session_factory: async_sessionmaker[AsyncSession],
    ):
        self._session_factory = async_session_factory

    def _to_documents(self, rows) -> list[Document]:
        return [
            Document(
                id=row.document_id,
                page_content=row.content,
                metadata={
                    "source": row.source,
                    "entity_type": row.entity_type,
                    "record_id": row.record_id,
                    "scope_type": row.scope_type,
                    "scope_id": row.scope_id,
                    "target_type": row.target_type,
                    "target_id": row.target_id,
                    "target_name": row.target_name,
                    "internal_author_id": row.internal_author_id,
                    "title": row.title,
                    "body": row.body,
                    "data": row.data,
                    "metadata": row.metadata,
                    "url": row.url,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                    "synced_at": row.synced_at,
                },
            )
            for row in rows
        ]

    @staticmethod
    def _build_filter_clauses(
        tool_filters: list[SourceType] | None,
        temporal_filters: list[TemporalFilter] | None,
        params: dict[str, Any],
    ) -> list[str]:
        """tool_filters와 temporal_filters를 SQL WHERE 조건 문자열 목록으로 변환한다.

        temporal_filters가 있으면 (소스 AND 기간) 조건을 OR로 묶어 반환한다.
        tool_filters만 있으면 단순 ANY 조건으로 처리한다.
        params dict를 in-place로 수정해 바인딩 파라미터를 추가한다.
        """
        if not temporal_filters:
            if not tool_filters:
                return []
            params["tools"] = [f.value for f in tool_filters]
            return ["e.source = ANY(:tools)"]

        # TemporalFilter마다 파라미터 이름을 인덱스로 구분해 충돌을 방지한다.
        conditions = []
        for i, tf in enumerate(temporal_filters):
            tools_p = f"tools_{i}"
            start_p = f"start_date_{i}"
            end_p = f"end_date_{i}"
            params[tools_p] = [t.value for t in tf.tools]
            params[start_p] = (
                tf.start_date
                if tf.start_date.tzinfo
                else tf.start_date.replace(tzinfo=timezone.utc)
            )
            params[end_p] = (
                tf.end_date
                if tf.end_date.tzinfo
                else tf.end_date.replace(tzinfo=timezone.utc)
            )
            conditions.append(
                f"(e.source = ANY(:{tools_p})"
                f" AND e.{tf.time_field} BETWEEN :{start_p} AND :{end_p})"
            )
        return [f"({' OR '.join(conditions)})"]

    def _build_base_sql(
        self,
        token: str,
        token_condition: str,
        k: int,
        offset: int,
        tool_filters: list[SourceType] | None,
        temporal_filters: list[TemporalFilter] | None,
        order_by: str = "bigm_similarity(e.title, :token) DESC, e.created_at DESC",
    ) -> tuple[TextClause, dict[str, Any]]:
        """공통 SELECT/WHERE/ORDER BY 골격을 조립한다.

        token_condition과 order_by만 호출부에서 주입받아, body/title 쿼리가
        같은 골격을 재사용할 수 있도록 한다.
        """
        params: dict[str, Any] = {"token": token, "k": k, "offset": offset}
        filter_clauses = self._build_filter_clauses(
            tool_filters, temporal_filters, params
        )
        filter_clauses.append(token_condition)
        sql = text(f"""
            SELECT
                e.document_id, e.content, e.source, e.entity_type,
                e.record_id, e.scope_type, e.scope_id,
                e.target_type, e.target_id, e.target_name,
                e.internal_author_id, e.title, e.body, e.data,
                e.metadata, e.url, e.created_at, e.updated_at, e.synced_at
            FROM {KNOWLEDGE_STORE_TABLE_NAME} e
            WHERE {" AND ".join(filter_clauses)}
            ORDER BY {order_by}
            LIMIT :k OFFSET :offset
        """)
        return sql, params

    def _build_body_query(
        self,
        token: str,
        k: int,
        offset: int,
        tool_filters: list[SourceType] | None,
        temporal_filters: list[TemporalFilter] | None,
    ) -> tuple[TextClause, dict[str, Any]]:
        """body 전문 검색 쿼리를 생성한다.

        likequery()는 pg_bigm이 제공하는 함수로, 토큰을 LIKE 패턴(%token%)으로
        변환한다. body GIN 인덱스를 타기 위해 lower()를 양쪽에 적용한다.
        """
        return self._build_base_sql(
            token,
            "lower(e.body) LIKE lower(likequery(:token))",
            k,
            offset,
            tool_filters,
            temporal_filters,
        )

    def _build_title_query(
        self,
        token: str,
        k: int,
        offset: int,
        tool_filters: list[SourceType] | None,
        temporal_filters: list[TemporalFilter] | None,
    ) -> tuple[TextClause, dict[str, Any]]:
        """title 퍼지 검색 쿼리를 생성한다.

        =% 연산자는 pg_bigm의 유사도 임계값(pg_bigm.similarity_limit, 기본 0.1)
        이상인 title을 매칭한다. ORDER BY는 LIKE 완전 일치를 1순위 tie-breaker로
        두어, "CATDEV-134"처럼 토큰이 title에 그대로 포함된 문서가 퍼지 유사도만
        높은 다른 문서보다 앞에 오도록 보장한다.
        """
        return self._build_base_sql(
            token,
            "lower(e.title) =% lower(:token)",
            k,
            offset,
            tool_filters,
            temporal_filters,
            order_by=(
                # LIKE 완전 일치(1) vs 퍼지만 일치(0) → DESC로 완전 일치 우선
                "(lower(e.title) LIKE lower(likequery(:token))) DESC,"
                " bigm_similarity(e.title, :token) DESC,"
                " e.created_at DESC"
            ),
        )

    async def _execute(
        self,
        session: AsyncSession,
        sql: TextClause,
        params: dict[str, Any],
    ) -> list:
        if settings.ENABLE_QUERY_EXPLAIN:
            try:
                explain_sql = text(
                    "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) " + sql.text
                )
                result = await session.execute(explain_sql, params)
                logger.info(
                    "bigm_query_plan", plan="\n".join(r[0] for r in result.fetchall())
                )
            except Exception as exc:
                logger.warning("bigm_query_plan_failed", error=str(exc))

        t0 = time.perf_counter()
        result = await session.execute(sql, params)
        rows = result.fetchall()
        logger.debug(
            "bigm_query_completed",
            elapsed=round(time.perf_counter() - t0, 3),
            row_count=len(rows),
        )
        return rows

    async def search(
        self,
        tokens: list[str],
        *,
        k: int,
        offset: int = 0,
        tool_filters: list[SourceType] | None = None,
        temporal_filters: list[TemporalFilter] | None = None,
        include_title: bool = False,
    ) -> list[Document]:
        """토큰 목록으로 pg_bigm 키워드 검색을 수행한다.

        각 토큰마다 body 쿼리(필수)와 title 쿼리(include_title=True일 때)를 실행하고,
        SQL 결과 순위를 RRF 점수(1 / (60 + rank))로 변환해 문서별로 누적한다.
        동일 문서가 여러 토큰이나 body/title 양쪽에서 히트하면 점수가 합산되어
        상위로 올라온다. doc_map은 첫 히트 시점의 row를 보존하며(setdefault),
        최종 정렬은 Python에서 누적 점수 기준으로 수행한다.
        """
        doc_map: dict[str, Any] = {}
        rank_scores: dict[str, float] = {}

        async with self._session_factory() as session:
            for token in tokens:
                body_sql, body_params = self._build_body_query(
                    token,
                    k=k,
                    offset=0,
                    tool_filters=tool_filters,
                    temporal_filters=temporal_filters,
                )
                for sql_rank, row in enumerate(
                    await self._execute(session, body_sql, body_params)
                ):
                    doc_id = row.document_id
                    rank_scores[doc_id] = rank_scores.get(doc_id, 0.0) + 1.0 / (
                        60 + sql_rank
                    )
                    doc_map.setdefault(doc_id, row)

                if include_title:
                    title_sql, title_params = self._build_title_query(
                        token,
                        k=k,
                        offset=0,
                        tool_filters=tool_filters,
                        temporal_filters=temporal_filters,
                    )
                    for sql_rank, row in enumerate(
                        await self._execute(session, title_sql, title_params)
                    ):
                        doc_id = row.document_id
                        rank_scores[doc_id] = rank_scores.get(doc_id, 0.0) + 1.0 / (
                            60 + sql_rank
                        )
                        doc_map.setdefault(doc_id, row)

        sorted_rows = sorted(
            doc_map.values(),
            key=lambda r: rank_scores[r.document_id],
            reverse=True,
        )
        return self._to_documents(sorted_rows[offset : offset + k])


class RetrievalService(BaseVectorDbService):
    """벡터 검색과 키워드 검색을 병합하는 하이브리드 검색 서비스.

    vector: PGVectorStore cosine similarity (HNSW 인덱스)
    keyword: PGBigmRetriever (pg_bigm GIN 인덱스)
    병합: weighted_reciprocal_rank — 두 결과 리스트에 가중치를 적용한 RRF.
          최종 doc.metadata["score"]가 downstream(RAG, search API)이 읽는 점수다.
    """

    def __init__(
        self,
        *,
        vector_store: VectorStore,
        keyword_retriever: PGBigmRetriever | None = None,
    ):
        self._vector_store = vector_store
        self._keyword_retriever = keyword_retriever

    @staticmethod
    def _build_vector_filter(
        tool_filters: list[SourceType] | None,
        temporal_filters: list[TemporalFilter] | None,
    ) -> dict | None:
        """PGVectorStore filter 문법으로 변환한다.

        temporal_filters가 있으면 각 (소스, 기간) 조건을 $and로 묶고
        여러 개는 $or로 연결한다. datetime은 isoformat 문자열이 아닌 객체로
        전달해야 PGVectorStore가 TIMESTAMPTZ 비교를 올바르게 처리한다.
        """
        if not temporal_filters:
            if not tool_filters:
                return None
            return {"source": {"$in": [f.value for f in tool_filters]}}

        or_conditions = []
        for tf in temporal_filters:
            start = (
                tf.start_date
                if tf.start_date.tzinfo
                else tf.start_date.replace(tzinfo=timezone.utc)
            )
            end = (
                tf.end_date
                if tf.end_date.tzinfo
                else tf.end_date.replace(tzinfo=timezone.utc)
            )
            or_conditions.append(
                {
                    "$and": [
                        {"source": {"$in": [t.value for t in tf.tools]}},
                        {tf.time_field: {"$gte": start}},
                        {tf.time_field: {"$lte": end}},
                    ]
                }
            )
        return {"$or": or_conditions} if len(or_conditions) > 1 else or_conditions[0]

    @override
    async def hybrid_search(
        self,
        query: str,
        k: int = 10,
        weights: list[float] = [0.6, 0.4],
        tool_filters: list[Any] | None = None,
        temporal_filters: list[Any] | None = None,
        keyword_tokens: list[str] | None = None,
        offset: int = 0,
        score_threshold: float = 0.4,
    ) -> list[Document]:
        """벡터 + 키워드 하이브리드 검색을 수행한다.

        score_threshold: cosine distance가 (1 - threshold)를 초과하는 벡터 결과는
            제거한다. 식별자 쿼리("CATDEV-134")처럼 임베딩 품질이 낮은 경우 약한
            벡터 결과가 키워드 결과를 밀어내지 않도록 하기 위한 컷오프다.

        similarity_score: 통과한 벡터 결과에만 부여(1 - distance). 높을수록 좋다.
        score: weighted_reciprocal_rank가 최종적으로 부여하는 RRF 점수.
            downstream이 랭킹 기준으로 읽는 값이다.

        query와 keyword_tokens는 역할이 다르다:
            query — 임베딩되어 벡터 유사도 검색에 사용. 시맨틱 문장이어야 한다.
            keyword_tokens — pg_bigm LIKE/=% 검색에 사용. 식별자나 고유명사에 적합하다.
        """
        vector_filter = self._build_vector_filter(tool_filters, temporal_filters)
        langchain_store = self._vector_store.get_langchain_vector_store()

        # asimilarity_search_with_score는 (Document, cosine_distance) 튜플을 반환한다.
        vector_results: list[
            tuple[Document, float]
        ] = await langchain_store.asimilarity_search_with_score(
            query, k=k, filter=vector_filter
        )
        vector_docs = []
        for doc, dist in vector_results:
            if dist <= 1.0 - score_threshold:
                doc.metadata["similarity_score"] = round(1.0 - dist, 4)
                vector_docs.append(doc)

        keyword_results: list[Document] = []
        if keyword_tokens and self._keyword_retriever:
            keyword_results = await self._keyword_retriever.search(
                keyword_tokens,
                k=k,
                tool_filters=tool_filters,
                temporal_filters=temporal_filters,
                include_title=True,
            )

        merged = weighted_reciprocal_rank([vector_docs, keyword_results], weights)
        return merged[offset : offset + k]

    @override
    async def hybrid_search_batch(
        self,
        queries: list[dict[str, Any]],
        k: int = 10,
        weights: list[float] = [0.6, 0.4],
        tool_filters: list[Any] | None = None,
    ) -> list[list[Document]]:
        """여러 쿼리를 병렬로 hybrid_search한다.

        RAG 에이전트가 multi-query 전략을 쓸 때 호출된다. 쿼리 간 keyword_tokens
        중복을 제거해 동일 토큰이 여러 쿼리에서 반복 검색되지 않도록 한다.
        (쿼리 A가 "토큰"을 소진하면 쿼리 B는 해당 토큰 없이 실행된다.)
        asyncio.gather로 모든 쿼리를 동시에 실행한다.
        """
        # 앞선 쿼리가 사용한 토큰은 뒤 쿼리에서 제거해 pg_bigm 중복 히트를 줄인다.
        used_keywords: set[str] = set()
        deduped_queries: list[dict[str, Any]] = []
        for q in queries:
            tokens = q.get("keyword_tokens") or []
            unique_tokens = [t for t in tokens if t not in used_keywords]
            used_keywords.update(unique_tokens)
            deduped_queries.append({**q, "keyword_tokens": unique_tokens})

        tasks = []
        for q in deduped_queries:
            temporal_filters = build_temporal_filters(
                tool_filters=tool_filters,
                start_date=q.get("start_date"),
                end_date=q.get("end_date"),
            )
            tasks.append(
                self.hybrid_search(
                    query=q["query"],
                    k=k,
                    weights=weights,
                    tool_filters=tool_filters,
                    temporal_filters=temporal_filters,
                    keyword_tokens=q.get("keyword_tokens"),
                )
            )

        t0 = time.perf_counter()
        results = await asyncio.gather(*tasks)
        logger.debug(
            "hybrid_search_batch_completed",
            elapsed=round(time.perf_counter() - t0, 3),
            task_count=len(tasks),
        )
        return list(results)

    @override
    async def fetch_by_ids(self, ids: list[str]) -> list[Document]:
        if not ids:
            return []
        langchain_store = self._vector_store.get_langchain_vector_store()
        return await langchain_store.aget_by_ids(ids)

