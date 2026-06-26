from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
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

    body(LIKE 전문)와 title(=% 퍼지)를 독립 메서드로 노출한다.
    RetrievalService가 두 결과를 별도 버킷으로 받아 3-way RRF에 활용한다.
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
        tool_filters: list[SourceType] | None,
        temporal_filters: list[TemporalFilter] | None,
        order_by: str = "e.created_at DESC",
        extra_select: str = "",
    ) -> tuple[TextClause, dict[str, Any]]:
        """공통 SELECT/WHERE/ORDER BY 골격을 조립한다.

        token_condition, order_by, extra_select을 호출부에서 주입받아,
        body/title 쿼리가 같은 골격을 재사용할 수 있도록 한다.
        extra_select는 쉼표를 포함한 추가 컬럼 문자열이다 (예: ", col AS alias").
        extra_select 안에 바인딩 파라미터(:name)를 쓸 경우 해당 키가 params에
        이미 존재해야 한다 — _build_base_sql은 params를 추가로 확장하지 않는다.
        """
        params: dict[str, Any] = {"token": token, "k": k}
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
                e.metadata, e.url, e.created_at, e.updated_at, e.synced_at{extra_select}
            FROM {KNOWLEDGE_STORE_TABLE_NAME} e
            WHERE {" AND ".join(filter_clauses)}
            ORDER BY {order_by}
            LIMIT :k
        """)
        return sql, params

    def _build_body_query(
        self,
        token: str,
        k: int,
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
            tool_filters,
            temporal_filters,
            order_by="e.created_at DESC",
        )

    def _build_title_query(
        self,
        token: str,
        k: int,
        tool_filters: list[SourceType] | None,
        temporal_filters: list[TemporalFilter] | None,
    ) -> tuple[TextClause, dict[str, Any]]:
        """title 퍼지 검색 쿼리를 생성한다.

        =% 연산자는 pg_bigm의 유사도 임계값(pg_bigm.similarity_limit, 현재 0.17)
        이상인 title을 매칭한다. ORDER BY는 LIKE 완전 일치를 1순위 tie-breaker로
        두어, "CATDEV-134"처럼 토큰이 title에 그대로 포함된 문서가 퍼지 유사도만
        높은 다른 문서보다 앞에 오도록 보장한다.
        bigm_score를 SELECT에 포함해 관측성 목적으로 keyword_score 메타데이터에 부착한다.
        노이즈 컷오프는 DB 레벨 pg_bigm.similarity_limit(0.17)에서 처리하므로
        Python 레벨 추가 필터링은 수행하지 않는다.
        """
        return self._build_base_sql(
            token,
            "lower(e.title) =% lower(:token)",
            k,
            tool_filters,
            temporal_filters,
            order_by=(
                "(lower(e.title) LIKE lower(likequery(:token))) DESC,"
                " bigm_score DESC,"
                " e.created_at DESC"
            ),
            extra_select=(
                ", bigm_similarity(lower(e.title), lower(:token)) AS bigm_score"
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

    async def _search(
        self,
        query_builder: Callable[
            [str, int, list[SourceType] | None, list[TemporalFilter] | None],
            tuple[TextClause, dict[str, Any]],
        ],
        tokens: list[str],
        *,
        k: int,
        tool_filters: list[SourceType] | None,
        temporal_filters: list[TemporalFilter] | None,
    ) -> tuple[list[Document], dict[str, float]]:
        """토큰별 쿼리를 단일 세션에서 순차 실행하고 RRF 점수로 병합한다.

        각 토큰의 SQL 결과 순위를 1/(60+rank)로 변환해 누적한다.
        동일 문서가 여러 토큰에서 히트할수록 점수가 쌓여 상위로 올라온다.
        query_builder로 body/title 쿼리를 주입받아 로직을 공유한다.

        extra_scores: SQL 결과 행에 bigm_score 같은 추가 컬럼이 있으면
        doc_id별 max값을 수집해 두 번째 반환값으로 돌려준다. 없으면 빈 dict.
        """
        doc_map: dict[str, Any] = {}
        rank_scores: dict[str, float] = {}
        extra_scores: dict[str, float] = {}

        async with self._session_factory() as session:
            for token in tokens:
                sql, params = query_builder(token, k, tool_filters, temporal_filters)
                for sql_rank, row in enumerate(
                    await self._execute(session, sql, params)
                ):
                    doc_id = row.document_id
                    # 여러 토큰에서 동시에 히트한 문서일수록 더 관련성이 높다는 전제 하에,
                    # 토큰이 여러 개일 때의 검색 결과를 합치기 위해 토큰 단위로 RRF를 적용한다.
                    rank_scores[doc_id] = rank_scores.get(doc_id, 0.0) + 1.0 / (
                        60 + sql_rank
                    )
                    doc_map.setdefault(doc_id, row)
                    if (score := getattr(row, "bigm_score", None)) is not None:
                        extra_scores[doc_id] = max(
                            extra_scores.get(doc_id, 0.0), float(score)
                        )

        sorted_rows = sorted(
            doc_map.values(),
            key=lambda r: rank_scores[r.document_id],
            reverse=True,
        )
        return self._to_documents(sorted_rows[:k]), extra_scores

    async def search_body(
        self,
        tokens: list[str],
        *,
        k: int,
        tool_filters: list[SourceType] | None = None,
        temporal_filters: list[TemporalFilter] | None = None,
    ) -> list[Document]:
        """body 전문 검색(LIKE)을 수행한다."""
        docs, _ = await self._search(
            self._build_body_query,
            tokens,
            k=k,
            tool_filters=tool_filters,
            temporal_filters=temporal_filters,
        )
        return docs

    async def search_title(
        self,
        tokens: list[str],
        *,
        k: int,
        tool_filters: list[SourceType] | None = None,
        temporal_filters: list[TemporalFilter] | None = None,
    ) -> list[Document]:
        """title 퍼지 검색(=%)을 수행한다."""
        docs, keyword_scores = await self._search(
            self._build_title_query,
            tokens,
            k=k,
            tool_filters=tool_filters,
            temporal_filters=temporal_filters,
        )
        for doc in docs:
            if (ks := keyword_scores.get(doc.id)) is not None:
                doc.metadata["keyword_score"] = round(ks, 4)
        return docs


class RetrievalService(BaseVectorDbService):
    """벡터 검색과 키워드 검색을 병합하는 하이브리드 검색 서비스.

    vector: PGVectorStore cosine similarity (HNSW 인덱스)
    body: PGBigmRetriever body LIKE (전문 검색)
    title: PGBigmRetriever title =% (퍼지 검색)

    세 결과를 weighted_reciprocal_rank로 3-way RRF한다.
    weights = [vector, body, title] 순서로 명시적으로 지정한다.
    최종 doc.metadata["score"]가 downstream(RAG, search API)이 읽는 점수다.
    """

    _CANDIDATE_MULTIPLIER = 3

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
        weights: list[float] = [0.5, 0.3, 0.2],  # [vector, body, title]
        tool_filters: list[Any] | None = None,
        temporal_filters: list[Any] | None = None,
        keyword_tokens: list[str] | None = None,
        offset: int = 0,
        score_threshold: float = 0.2,
    ) -> list[Document]:
        """벡터 + body + title 3-way 하이브리드 검색을 수행한다.

        weights = [vector, body, title] 순서다.
        RAG 기본값 [0.5, 0.3, 0.2]: body 신호 우선.
        manual search 권장값 [0.4, 0.2, 0.4]: title 신호 강화.

        score_threshold: cosine distance 컷오프 (1 - threshold 초과 시 vector 결과 제거).
        title의 노이즈 컷오프는 DB 레벨 pg_bigm.similarity_limit(0.17)에서 처리한다.

        keyword_tokens가 없으면 RRF를 건너뛰고 vector 결과를 직접 반환한다.
        세 검색(vector, body, title)은 asyncio.gather로 병렬 실행한다.

        RRF candidate pool: 각 버킷에서 candidate_k개를 수집한 뒤 RRF로 병합하고
        최종 k개를 반환한다. candidate_k = max(k * _CANDIDATE_MULTIPLIER, k + offset).
        """
        if len(weights) != 3:
            raise ValueError("weights must have 3 elements: [vector, body, title]")

        candidate_k = max(k * self._CANDIDATE_MULTIPLIER, k + offset)

        vector_filter = self._build_vector_filter(tool_filters, temporal_filters)
        langchain_store = self._vector_store.get_langchain_vector_store()

        # semantic search는 항상 수행
        vector_coro = langchain_store.asimilarity_search_with_score(
            query, k=candidate_k, filter=vector_filter
        )

        # keyword가 존재하는 경우에만 3-Way 병렬 검색 수행
        if keyword_tokens and self._keyword_retriever:
            body_coro = self._keyword_retriever.search_body(
                keyword_tokens,
                k=candidate_k,
                tool_filters=tool_filters,
                temporal_filters=temporal_filters,
            )
            title_coro = self._keyword_retriever.search_title(
                keyword_tokens,
                k=candidate_k,
                tool_filters=tool_filters,
                temporal_filters=temporal_filters,
            )
            vector_results, body_docs, title_docs = await asyncio.gather(
                vector_coro, body_coro, title_coro
            )
        else:
            # keyword 없으면 RRF 불필요 — vector 결과를 score_threshold만 적용해 반환
            vector_results = await vector_coro
            body_docs = []
            title_docs = []

        # asimilarity_search_with_score는 (Document, cosine_distance) 튜플 반환.
        vector_docs = []
        for doc, dist in vector_results:
            if dist <= 1.0 - score_threshold:
                doc.metadata["similarity_score"] = round(1.0 - dist, 4)
                vector_docs.append(doc)

        # keyword 결과가 없으면(토큰 미제공 또는 bigm 히트 0건) RRF 불필요.
        # cosine similarity 순서를 그대로 보존해 반환한다.
        if not body_docs and not title_docs:
            for doc in vector_docs:
                doc.metadata["hit_types"] = ["vector"]
            return vector_docs[offset : offset + k]

        # [메타데이터 유실 방지]
        # weighted_reciprocal_rank는 버킷 중 가장 먼저 등장한 doc 객체를 보존한다.
        # vector_docs가 항상 첫 번째 버킷이므로, vector & body 동시 히트 문서는
        # merged 후에도 vector의 doc 객체가 채택된다.
        # 이때 title 버킷에만 존재하던 keyword_score가 객체에서 사라지므로,
        # RRF 실행 전에 미리 확보하고 병합 후 다시 부착한다.
        # hit_types도 같은 이유로 — 어느 버킷 객체가 채택됐든 관계없이
        # 모든 버킷 히트 정보를 보존하기 위해 사전 수집한다.
        hit_types: dict[str, list[str]] = {}
        keyword_scores: dict[str, float] = {}
        for label, docs, score_key in [
            ("vector", vector_docs, None),
            ("body", body_docs, None),
            ("title", title_docs, "keyword_score"),
        ]:
            for doc in docs:
                hit_types.setdefault(doc.id, []).append(label)
                if score_key and (s := doc.metadata.get(score_key)) is not None:
                    keyword_scores[doc.id] = s

        # 3-Way RRF 수행
        merged = weighted_reciprocal_rank(
            [vector_docs, body_docs, title_docs], weights
        )
        
        # [메타데이터 유실 방지]
        # RRF 실행 후 미리 모아둔 메타데이터 부착.
        for doc in merged:
            doc.metadata["hit_types"] = hit_types.get(doc.id, [])
            if doc.id in keyword_scores:
                doc.metadata["keyword_score"] = keyword_scores[doc.id]

        return merged[offset : offset + k]

    @override
    async def hybrid_search_batch(
        self,
        queries: list[dict[str, Any]],
        k: int = 10,
        weights: list[float] = [0.5, 0.3, 0.2],  # [vector, body, title]
        tool_filters: list[Any] | None = None,
    ) -> list[list[Document]]:
        """여러 쿼리를 병렬로 hybrid_search한다.

        RAG 에이전트가 multi-query 전략을 쓸 때 호출된다. 쿼리 간 keyword_tokens
        중복을 제거해 동일 토큰이 여러 쿼리에서 반복 검색되지 않도록 한다.
        asyncio.gather로 모든 쿼리를 동시에 실행한다.

        토큰 dedup은 queries 순서에 의존한다 — 앞선 쿼리가 소진한 토큰은
        뒤 쿼리에서 제거되므로, 중요도가 높은 쿼리를 앞에 배치해야 recall 손실을
        최소화할 수 있다. 호출부(RAG 에이전트)가 쿼리 순서를 결정할 책임을 가진다.
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
