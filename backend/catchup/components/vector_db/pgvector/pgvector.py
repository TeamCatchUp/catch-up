import asyncio
import time
from typing import Any
from typing import override

import structlog
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_postgres import PGVector
from sqlalchemy import Engine
from sqlalchemy import text

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.components.vector_db.rank import weighted_reciprocal_rank
from catchup.configs.config import settings
from catchup.db.async_engine import AsyncSessionLocal
from catchup.db.engine import SessionLocal
from catchup.db.engine import parse_plan
from catchup.db.models import SourceType
from catchup.rag.executors import rag_executors
from catchup.rag.schemas.filters import TemporalFilter
from catchup.rag.schemas.filters import build_temporal_filters

logger = structlog.get_logger(__name__)


def _timed(name: str, fn):
    def wrapper(*args, **kwargs):
        t = time.perf_counter()
        logger.debug(f"{name}_started")
        result = fn(*args, **kwargs)
        logger.debug(f"{name}_completed", elapsed=round(time.perf_counter() - t, 3), count=len(result))
        return result
    return wrapper


class PGBigmRetriever(BaseRetriever):
    """pg_bigm 유사도 기반 키워드 검색 지원"""

    # BaseRetriever는 내부적으로 BaseModel을 상속하므로 Pydantic 스타일을 따라야 함
    session_factory: Any  # e.g) sessionmaker (from sqlalchemy.orm)
    async_session_factory: Any = None  # async_sessionmaker (from sqlalchemy.ext.asyncio)
    collection_name: str = settings.PGVECTOR_COLLECTION_NAME
    k: int = 4
    offset: int = 0
    tool_filters: list[SourceType] | None = None
    temporal_filters: list[TemporalFilter] | None = None
    search_mode: str = "fuzzy"  # "exact": ILIKE likequery (RAG), "fuzzy": =% similarity (keyword search)
    @override
    def _get_relevant_documents(
        self,
        query: str | list[str],
        *,
        run_manager: CallbackManagerForRetrieverRun,  # BaseRetriever Signature
    ) -> list[Document]:
        """
        pg_bigm 유사도 기반 키워드 검색.
        """
        search_sql, params = self.build_bigm_query(
            collection_name=self.collection_name,
            query=query,
            k=self.k,
            offset=self.offset,
            tool_filters=self.tool_filters,
            temporal_filters=self.temporal_filters,
            search_mode=self.search_mode,
        )

        results = list(self._do_query(search_sql, params))
        return self._get_documents_from_results(results)

    @staticmethod
    def build_bigm_query(
        collection_name: str,
        query: str | list[str],
        k: int,
        offset: int = 0,
        tool_filters: list[SourceType] | None = None,
        temporal_filters: list[TemporalFilter] | None = None,
        search_mode: str = "fuzzy",
    ) -> tuple[Any, dict]:
        """
        contextual_content 기반 키워드 검색 SQL 및 파라미터 생성.
        """
        if isinstance(query, list):
            tokens = query
        else:
            tokens = query.split()

        # 빈 토큰 제외 및 중복 제거
        tokens = list(set([t.strip() for t in tokens if t.strip()]))

        params = {
            "collection_name": collection_name,
            "k": k,
            "offset": offset,
        }

        # 기본 필터 (Collection)
        filter_clauses = ["c.name = :collection_name"]

        # 협업 툴 & 시간 필터
        if not temporal_filters:
            if tool_filters:
                filter_clauses.append("e.cmetadata ->> 'source' = ANY(:tools)")
                params["tools"] = [f.value for f in tool_filters]
        else:
            sql_conditions = []
            for i, tf in enumerate(temporal_filters):
                tools_p = f"tools_{i}"
                start_p = f"start_date_{i}"
                end_p = f"end_date_{i}"
                params[tools_p] = [t.value for t in tf.tools]
                # ISO 문자열로 전달하여 텍스트 인덱스 활용 (ISO 8601은 문자열 비교가 시간 비교와 일치함)
                params[start_p] = tf.start_date.isoformat()
                params[end_p] = tf.end_date.isoformat()

                sql_conditions.append(
                    f"(e.cmetadata ->> 'source' = ANY(:{tools_p}) "
                    f"AND (e.cmetadata ->> '{tf.time_field}') "
                    f"BETWEEN :{start_p} AND :{end_p})"
                )
            filter_clauses.append(f"({' OR '.join(sql_conditions)})")

        token_filters = []
        exact_match_scores = []
        sim_scores = []

        for i, token in enumerate(tokens):
            p_name = f"token_{i}"
            params[p_name] = token

            exact_match_scores.append(f"(CASE WHEN LOWER(e.cmetadata ->> 'contextual_content') = LOWER(:{p_name}) THEN 1.0 ELSE 0.0 END)")
            if search_mode == "exact":
                token_filters.append(
                    f"lower(e.cmetadata ->> 'contextual_content') LIKE lower(likequery(:{p_name}))"
                )
            else:
                token_filters.append(
                    f"lower(e.cmetadata ->> 'contextual_content') =% lower(:{p_name})"
                )
                sim_scores.append(f"bigm_similarity(e.cmetadata ->> 'contextual_content', :{p_name})")

        if token_filters:
            filter_clauses.append(f"({' AND '.join(token_filters)})")

        # 필터 조립
        where_clause = " AND ".join(filter_clauses)
        
        # 스코어 조립 (토큰별 점수 합산)
        exact_boost_sql = " + ".join(exact_match_scores) if exact_match_scores else "0.0"
        similarity_sql = " + ".join(sim_scores) if sim_scores else "0.0"

        search_sql = text(f"""
            SELECT e.document, e.cmetadata, e.id,
                ({exact_boost_sql}) as exact_match_boost,
                ({similarity_sql}) as similarity_score
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON e.collection_id = c.uuid
            WHERE {where_clause}
            ORDER BY 
                exact_match_boost DESC,
                similarity_score DESC,
                (e.cmetadata ->> 'created_at') DESC
            LIMIT :k OFFSET :offset
        """)

        return search_sql, params

    def _do_query(
        self,
        search_sql: Any,
        params: dict,
        label: str = "bigm",
    ):
        with self.session_factory() as session:
            logger.debug("keyword_query_started", label=label)
            t0 = time.perf_counter()

            if settings.ENABLE_QUERY_EXPLAIN:
                try:
                    explain_sql = text(
                        "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) " + search_sql.text
                    )
                    plan_rows = session.execute(explain_sql, params).fetchall()
                    metrics = parse_plan([row[0] for row in plan_rows])
                    logger.info("db_query_plan", label=label, **metrics)
                except Exception as e:
                    logger.warning("db_query_plan_failed", label=label, error=str(e))

            results = session.execute(search_sql, params)
            rows = results.fetchall()

            logger.debug(
                "keyword_query_completed",
                label=label,
                elapsed=round(time.perf_counter() - t0, 3),
                row_count=len(rows)
            )
            return rows

    async def _async_do_query(
        self,
        search_sql: Any,
        params: dict,
        label: str = "bigm",
    ):
        """
        async session으로 쿼리를 실행한다.
        thread pool 없이 asyncio event loop에서 직접 수행.
        """
        session_factory = self.async_session_factory or AsyncSessionLocal
        async with session_factory() as session:
            logger.debug("keyword_query_started", label=label)
            t0 = time.perf_counter()

            if settings.ENABLE_QUERY_EXPLAIN:
                try:
                    explain_sql = text(
                        "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) " + search_sql.text
                    )
                    result = await session.execute(explain_sql, params)
                    plan_rows = result.fetchall()
                    metrics = parse_plan([row[0] for row in plan_rows])
                    logger.info("db_query_plan", label=label, **metrics)
                except Exception as e:
                    logger.warning("db_query_plan_failed", label=label, error=str(e))

            result = await session.execute(search_sql, params)
            rows = result.fetchall()

            logger.debug(
                "keyword_query_completed",
                label=label,
                elapsed=round(time.perf_counter() - t0, 3),
                row_count=len(rows),
            )
            return rows

    async def async_invoke(
        self,
        query: str | list[str],
        label: str = "bigm",
    ) -> list[Document]:
        """
        async session 기반 키워드 검색.
        hybrid_search에서 run_in_executor 없이 직접 await.
        """
        search_sql, params = self.build_bigm_query(
            collection_name=self.collection_name,
            query=query,
            k=self.k,
            offset=self.offset,
            tool_filters=self.tool_filters,
            temporal_filters=self.temporal_filters,
            search_mode=self.search_mode,
        )
        rows = await self._async_do_query(search_sql, params, label=label)
        return self._get_documents_from_results(rows)

    def _get_documents_from_results(self, results):
        docs = []

        for row in results:
            docs.append(
                Document(
                    page_content=row[0],
                    metadata=row[1] if row[1] else {},
                    id=row[2]
                )
            )

        return docs
    
    def bigm_search(
        self,
        query: str,
    ) -> list[Document]:
        """
        단독 pg_bigm 키워드 검색 유틸 함수.
        Hybrid Search에서는 사용되지 않는다.
        """
        return self.invoke(query)


class PGVectorService(BaseVectorDbService):
    def __init__(
        self,
        postgresql_engine: Engine,
        embeddings: Embeddings,
        collection_name: str = settings.PGVECTOR_COLLECTION_NAME,
        session_factory: Any = SessionLocal,
        async_session_factory: Any = AsyncSessionLocal,
    ):
        logger.info(f"PGVectorService initialized with Collection Name: '{collection_name}'")
        self.session_factory = session_factory
        self.async_session_factory = async_session_factory
        self.collection_name = collection_name
        self.vector_store = self._create_pgvector(
            postgresql_engine=postgresql_engine,
            embeddings=embeddings,
            collection_name=collection_name
        )

    def _create_pgvector(
        self,
        postgresql_engine: Engine,
        embeddings: Embeddings,
        collection_name: str
    ) -> PGVector:
        return PGVector(
            embeddings=embeddings,
            collection_name=collection_name,
            connection=postgresql_engine,
            use_jsonb=True,
        )

    @override
    async def hybrid_search(
        self,
        query: str,
        k: int = 4,
        weights: list[float] = [0.6, 0.4],  # [vector, content]
        tool_filters: list[SourceType] | None = None,
        temporal_filters: list[TemporalFilter] | None = None,
        keyword_tokens: list[str] | None = None,
        offset: int = 0,
        score_threshold: float = 0.4,
    ) -> list[Document]:
        """
        Langchain 기반 Hybrid Search를 수행한다.
        """
        logger.debug("hybrid_search_started", query_len=len(query))
        t0 = time.perf_counter()

        loop = asyncio.get_running_loop()
        executor = rag_executors.vector_search_executor

        # langchain PGVector는 sync API이므로 vector 검색은 thread pool 유지
        _run_vector_sync = _timed("vector_retrieval", lambda x: [
            doc for doc, score in self.vector_store.similarity_search_with_score(
                query=x["semantic_query"],
                k=max(100, k + offset),
                filter=x.get("filter")
            )[offset:]
            if score >= score_threshold
        ])

        search_kwargs = self._build_search_kwargs(tool_filters, temporal_filters)
        payload = {
            "semantic_query": query,
            "keyword_tokens": keyword_tokens or [],
            "filter": search_kwargs.get("filter"),
        }

        vector_task = loop.run_in_executor(executor, _run_vector_sync, payload)

        if keyword_tokens:
            # keyword 검색은 async session으로 직접 실행 — thread pool slot 점유 없음
            t_content = time.perf_counter()
            content_retriever = PGBigmRetriever(
                session_factory=self.session_factory,
                async_session_factory=self.async_session_factory,
                collection_name=self.collection_name,
                k=max(100, k + offset),
                offset=offset,
                tool_filters=tool_filters,
                temporal_filters=temporal_filters,
                search_mode="exact",
            )
            content_task = content_retriever.async_invoke(payload["keyword_tokens"])
            vector_docs, content_docs = await asyncio.gather(
                vector_task, content_task
            )
            logger.debug(
                "content_retrieval_completed",
                elapsed=round(time.perf_counter() - t_content, 3),
                count=len(content_docs),
            )
            result = weighted_reciprocal_rank(
                doc_lists=[vector_docs, content_docs],
                weights=weights
            )[:k]
        else:
            vector_docs = await vector_task
            result = vector_docs[:k]

        logger.debug("hybrid_search_completed", elapsed=round(time.perf_counter() - t0, 3), result_count=len(result))

        return result

    @override
    async def hybrid_search_batch(
        self,
        queries: list[dict[str, Any]],
        k: int = 10,
        weights: list[float] = [0.6, 0.4],
        tool_filters: list[SourceType] | None = None,
    ) -> list[list[Document]]:
        """
        여러 쿼리에 대해 병렬로 hybrid_search를 수행한다.
        queries 요소는 'query', 'start_date', 'end_date', 'keyword_tokens' 등을 포함할 수 있다.
        """
        # Deduplicate keywords across queries: first-come-first-served per keyword
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
                end_date=q.get("end_date")
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
    
    def _build_search_kwargs(
        self,
        tool_filters: list[SourceType] | None,
        temporal_filters: list[TemporalFilter] | None,
    ) -> dict:
        search_kwargs = {}
        if not temporal_filters:
            if tool_filters:
                search_kwargs["filter"] = {"source": {"$in": [f.value for f in tool_filters]}}
        else:
            or_conditions = []
            for tf in temporal_filters:
                or_conditions.append({
                    "$and": [
                        {"source": {"$in": [t.value for t in tf.tools]}},
                        {tf.time_field: {"$gte": tf.start_date.isoformat()}},
                        {tf.time_field: {"$lte": tf.end_date.isoformat()}}
                    ]
                })
            search_kwargs["filter"] = {"$or": or_conditions} if len(or_conditions) > 1 else or_conditions[0]
        return search_kwargs

    def _weighted_keyword_search(
        self,
        query: str,
        k: int = 20,
        tool_filters: list[SourceType] | None = None,
        offset: int = 0,
    ) -> list[Document]:
        """
        가중치 기반 키워드 검색.
        """
        search_sql, params = PGBigmRetriever.build_bigm_query(
            collection_name=self.collection_name,
            query=query,
            k=k,
            offset=offset,
            tool_filters=tool_filters,
            temporal_filters=None
        )

        with self.session_factory() as session:
            results = session.execute(search_sql, params).fetchall()

        return [
            Document(
                page_content=row[0],
                metadata=row[1] if row[1] else {},
                id=row[2]
            )
            for row in results
        ]

    @override
    async def fetch_by_ids(self, ids: list[str]) -> list[Document]:
        """과거 검색 턴 doc_ids를 DB에서 lazy fetch한다 (reuse 파이프라인용)."""
        if not ids:
            return []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            rag_executors.vector_search_executor,
            self.vector_store.get_by_ids,
            ids,
        )
