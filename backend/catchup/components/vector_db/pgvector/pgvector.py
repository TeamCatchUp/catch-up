import asyncio
import time
from typing import Any
from typing import Literal
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
from catchup.schemas.filters import TemporalFilter
from catchup.schemas.filters import build_temporal_filters

logger = structlog.get_logger(__name__)


def _timed(name: str, fn):
    def wrapper(*args, **kwargs):
        t = time.perf_counter()
        logger.debug(f"{name}_started")
        result = fn(*args, **kwargs)
        logger.debug(
            f"{name}_completed",
            elapsed=round(time.perf_counter() - t, 3),
            count=len(result),
        )
        return result

    return wrapper


class PGBigmRetriever(BaseRetriever):
    """pg_bigm 유사도 기반 키워드 검색 지원"""

    # BaseRetriever는 내부적으로 BaseModel을 상속하므로 Pydantic 스타일을 따라야 함
    session_factory: Any  # e.g) sessionmaker (from sqlalchemy.orm)
    async_session_factory: Any = (
        None  # async_sessionmaker (from sqlalchemy.ext.asyncio)
    )
    collection_name: str = settings.PGVECTOR_COLLECTION_NAME
    k: int = 4
    offset: int = 0
    tool_filters: list[SourceType] | None = None
    temporal_filters: list[TemporalFilter] | None = None
    search_mode: Literal["fuzzy", "exact"] = "fuzzy"  # "exact": ILIKE likequery (RAG), "fuzzy": =% similarity (keyword search)
    title_only: bool = (
        False  # True면 title =% 조건으로만 검색 (manual search 3-way RRF 전용)
    )

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
            title_only=self.title_only,
        )

        results = list(self._do_query(search_sql, params))
        return self._get_documents_from_results(results)

    @staticmethod
    def _parse_tokens(query: str | list[str]) -> list[str]:
        """토큰을 파싱하고 정규화한다."""
        tokens = query if isinstance(query, list) else query.split()
        return list(set(t.strip() for t in tokens if t.strip()))

    @staticmethod
    def _build_source_clauses(
        tool_filters: list[SourceType] | None,
        temporal_filters: list[TemporalFilter] | None,
        params: dict,
    ) -> list[str]:
        """협업 툴 & 시간 필터 SQL 조건을 생성한다."""
        if not temporal_filters:
            if not tool_filters:
                return []
            params["tools"] = [f.value for f in tool_filters]
            return ["e.cmetadata ->> 'source' = ANY(:tools)"]

        sql_conditions = []
        for i, tf in enumerate(temporal_filters):
            tools_p = f"tools_{i}"
            start_p = f"start_date_{i}"
            end_p = f"end_date_{i}"
            params[tools_p] = [t.value for t in tf.tools]
            params[start_p] = tf.start_date.isoformat()
            params[end_p] = tf.end_date.isoformat()
            sql_conditions.append(
                f"(e.cmetadata ->> 'source' = ANY(:{tools_p}) "
                f"AND (e.cmetadata ->> '{tf.time_field}') "
                f"BETWEEN :{start_p} AND :{end_p})"
            )
        return [f"({' OR '.join(sql_conditions)})"]

    @staticmethod
    def _build_token_expressions(
        tokens: list[str],
        search_mode: Literal["fuzzy", "exact"],
        title_only: bool,
        params: dict,
    ) -> tuple[list[str], list[str], list[str], list[str]]:
        """토큰 필터 및 스코어 SQL 표현식을 생성한다."""
        token_filters: list[str] = []
        exact_scores: list[str] = []
        sim_scores: list[str] = []
        title_scores: list[str] = []

        for i, token in enumerate(tokens):
            p = f"token_{i}"
            params[p] = token
            if title_only:
                title_scores.append(
                    f"bigm_similarity(COALESCE(e.cmetadata ->> 'title', ''), :{p})"
                )
                token_filters.append(
                    f"lower(e.cmetadata ->> 'title') =% lower(:{p})"
                )
            elif search_mode == "exact":
                # exact 모드: 토큰 매칭 수 + title 유사도 스코어링.
                # Confluence/Jira/GitHub PR은 title이 채워져 있어 유효한 신호.
                # Slack 등 title=''인 문서는 bigm_similarity('', token)=0으로 영향 없음.
                token_filters.append(
                    f"lower(e.cmetadata ->> 'contextual_content') LIKE lower(likequery(:{p}))"
                )
                exact_scores.append(
                    f"(CASE WHEN lower(e.cmetadata ->> 'contextual_content') LIKE lower(likequery(:{p})) THEN 1 ELSE 0 END)"
                )
                title_scores.append(
                    f"bigm_similarity(COALESCE(e.cmetadata ->> 'title', ''), :{p})"
                )
            else:
                # fuzzy 모드: Confluence/Jira 등 title이 있는 문서에서 유효
                title_scores.append(
                    f"bigm_similarity(COALESCE(e.cmetadata ->> 'title', ''), :{p})"
                )
                exact_scores.append(
                    f"(CASE WHEN LOWER(e.cmetadata ->> 'contextual_content') = LOWER(:{p}) THEN 1.0 ELSE 0.0 END)"
                )
                token_filters.append(
                    f"lower(e.cmetadata ->> 'contextual_content') =% lower(:{p})"
                )
                sim_scores.append(
                    f"bigm_similarity(e.cmetadata ->> 'contextual_content', :{p})"
                )

        return token_filters, exact_scores, sim_scores, title_scores

    @staticmethod
    def _log_plan(plan_rows: list, label: str) -> None:
        """계획 로그를 기록한다."""
        metrics = parse_plan([row[0] for row in plan_rows])
        logger.info("db_query_plan", label=label, **metrics)

    @staticmethod
    def build_bigm_query(
        collection_name: str,
        query: str | list[str],
        k: int,
        offset: int = 0,
        tool_filters: list[SourceType] | None = None,
        temporal_filters: list[TemporalFilter] | None = None,
        search_mode: Literal["fuzzy", "exact"] = "fuzzy",
        title_only: bool = False,
    ) -> tuple[Any, dict]:
        """
        contextual_content 기반 키워드 검색 SQL 및 파라미터 생성.
        """
        tokens = PGBigmRetriever._parse_tokens(query)

        params = {
            "collection_name": collection_name,
            "k": k,
            "offset": offset,
        }

        # 기본 필터 (Collection)
        filter_clauses = ["c.name = :collection_name"]

        # 협업 툴 & 시간 필터
        filter_clauses.extend(
            PGBigmRetriever._build_source_clauses(
                tool_filters, temporal_filters, params
            )
        )

        token_filters, exact_match_scores, sim_scores, title_sim_scores = (
            PGBigmRetriever._build_token_expressions(
                tokens, search_mode, title_only, params
            )
        )

        if token_filters:
            filter_clauses.append(f"({' OR '.join(token_filters)})")

        # 필터 조립
        where_clause = " AND ".join(filter_clauses)

        # 스코어 조립 (토큰별 점수 합산)
        exact_boost_sql = (
            " + ".join(exact_match_scores) if exact_match_scores else "0.0"
        )
        similarity_sql = " + ".join(sim_scores) if sim_scores else "0.0"
        # title이 있는 source(Confluence, Jira)에만 가산점.
        # ORDER BY에 float literal (0.0)은 PostgreSQL SyntaxError이므로 cast 사용.
        title_sim_sql = " + ".join(title_sim_scores) if title_sim_scores else "0::float"

        search_sql = text(f"""
            SELECT e.document, e.cmetadata, e.id,
                ({exact_boost_sql}) as exact_match_boost,
                ({similarity_sql}) as similarity_score
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON e.collection_id = c.uuid
            WHERE {where_clause}
            ORDER BY
                ({title_sim_sql}) DESC,
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
                    self._log_plan(plan_rows, label)
                except Exception as e:
                    logger.warning("db_query_plan_failed", label=label, error=str(e))

            results = session.execute(search_sql, params)
            rows = results.fetchall()

            logger.debug(
                "keyword_query_completed",
                label=label,
                elapsed=round(time.perf_counter() - t0, 3),
                row_count=len(rows),
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
                    self._log_plan(plan_rows, label)
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
        다중 토큰은 1 세션에서 토큰별 단일 쿼리를 순차 실행 후 Python merge.
        단일 토큰은 기존 경로(_async_do_query) 사용.
        """
        tokens = self._parse_tokens(query)
        if not tokens:
            return []

        if len(tokens) == 1:
            search_sql, params = self.build_bigm_query(
                collection_name=self.collection_name,
                query=tokens,
                k=self.k,
                offset=self.offset,
                tool_filters=self.tool_filters,
                temporal_filters=self.temporal_filters,
                search_mode=self.search_mode,
                title_only=self.title_only,
            )
            rows = await self._async_do_query(search_sql, params, label=label)
            return self._get_documents_from_results(rows)

        return await self._async_invoke_per_token(tokens, label)

    async def _async_invoke_per_token(
        self,
        tokens: list[str],
        label: str,
    ) -> list[Document]:
        """토큰별 단일 쿼리를 1 세션에서 순차 실행, match count 기준으로 merge한다.

        OR 단일 쿼리 대비 heap scan 범위가 줄어 성능이 개선된다.
        match count가 높은 문서(여러 토큰에 걸친 문서)가 상위에 위치한다.
        """
        session_factory = self.async_session_factory or AsyncSessionLocal
        t0 = time.perf_counter()

        match_count: dict[str, int] = {}
        doc_map: dict[str, Document] = {}

        async with session_factory() as session:
            for token in tokens:
                search_sql, params = self.build_bigm_query(
                    collection_name=self.collection_name,
                    query=[token],
                    k=self.k,
                    offset=0,
                    tool_filters=self.tool_filters,
                    temporal_filters=self.temporal_filters,
                    search_mode=self.search_mode,
                    title_only=self.title_only,
                )
                result = await session.execute(search_sql, params)
                for row in result.fetchall():
                    doc_id = row[2]
                    match_count[doc_id] = match_count.get(doc_id, 0) + 1
                    if doc_id not in doc_map:
                        doc_map[doc_id] = Document(
                            page_content=row[0],
                            metadata=row[1] if row[1] else {},
                            id=doc_id,
                        )

        # match_count DESC, created_at DESC (ISO 문자열은 lexicographic 정렬 동일)
        sorted_ids = sorted(
            doc_map,
            key=lambda d: (match_count[d], doc_map[d].metadata.get("created_at", "")),
            reverse=True,
        )[self.offset : self.offset + self.k]

        logger.debug(
            "keyword_multi_query_completed",
            label=label,
            token_count=len(tokens),
            elapsed=round(time.perf_counter() - t0, 3),
            result_count=len(sorted_ids),
        )
        return [doc_map[d] for d in sorted_ids]

    def _get_documents_from_results(self, results):
        docs = []

        for row in results:
            docs.append(
                Document(
                    page_content=row[0], metadata=row[1] if row[1] else {}, id=row[2]
                )
            )

        return docs


class PGVectorService(BaseVectorDbService):
    def __init__(
        self,
        postgresql_engine: Engine,
        embeddings: Embeddings,
        collection_name: str = settings.PGVECTOR_COLLECTION_NAME,
        session_factory: Any = SessionLocal,
        async_session_factory: Any = AsyncSessionLocal,
    ):
        logger.info(
            f"PGVectorService initialized with Collection Name: '{collection_name}'"
        )
        self.session_factory = session_factory
        self.async_session_factory = async_session_factory
        self.collection_name = collection_name
        self.vector_store = self._create_pgvector(
            postgresql_engine=postgresql_engine,
            embeddings=embeddings,
            collection_name=collection_name,
        )

    def _create_pgvector(
        self, postgresql_engine: Engine, embeddings: Embeddings, collection_name: str
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
        score_threshold: float = 0.2,
        use_title_filter: bool = False,
    ) -> list[Document]:
        """
        Langchain 기반 Hybrid Search를 수행한다.
        """
        logger.debug("hybrid_search_started", query_len=len(query))
        t0 = time.perf_counter()

        if not query and not keyword_tokens:
            logger.warning(
                "hybrid_search_skipped", reason="empty query and no keyword_tokens"
            )
            return []

        loop = asyncio.get_running_loop()
        executor = rag_executors.vector_search_executor

        # langchain PGVector는 sync API이므로 vector 검색은 thread pool 유지
        def _vector_search(x):
            results = []
            for doc, score in self.vector_store.similarity_search_with_score(
                query=x["semantic_query"],
                k=max(100, k + offset),
                filter=x.get("filter"),
            )[offset:]:
                similarity = 1 - score  # cosine distance → similarity (높을수록 유사)
                if similarity >= score_threshold:
                    doc.metadata["score"] = similarity
                    results.append(doc)
            return results

        _run_vector_sync = _timed("vector_retrieval", _vector_search)

        search_kwargs = self._build_search_kwargs(tool_filters, temporal_filters)
        payload = {
            "semantic_query": query,
            "keyword_tokens": keyword_tokens or [],
            "filter": search_kwargs.get("filter"),
        }

        vector_task = (
            loop.run_in_executor(executor, _run_vector_sync, payload) if query else None
        )

        if keyword_tokens:
            # keyword 검색은 async session으로 직접 실행 — thread pool slot 점유 없음
            t_content = time.perf_counter()
            _bigm_k = max(100, k + offset)
            content_retriever = self._make_bigm_retriever(
                k=_bigm_k,
                offset=offset,
                tool_filters=tool_filters,
                temporal_filters=temporal_filters,
                search_mode="exact",
            )
            content_task = content_retriever.async_invoke(payload["keyword_tokens"])

            if use_title_filter:
                title_retriever = self._make_bigm_retriever(
                    k=_bigm_k,
                    offset=offset,
                    tool_filters=tool_filters,
                    temporal_filters=temporal_filters,
                    title_only=True,
                )
                title_task = title_retriever.async_invoke(payload["keyword_tokens"])
            else:
                title_task = None

            vector_docs, content_docs, title_docs = await self._gather_keyword_docs(
                vector_task, content_task, title_task
            )

            if use_title_filter:
                logger.debug(
                    "content_retrieval_completed",
                    elapsed=round(time.perf_counter() - t_content, 3),
                    content_count=len(content_docs),
                    title_count=len(title_docs),
                )
                result = weighted_reciprocal_rank(
                    doc_lists=[vector_docs, content_docs, title_docs],
                    weights=[0.5, 0.2, 0.3],
                )[:k]
            else:
                logger.debug(
                    "content_retrieval_completed",
                    elapsed=round(time.perf_counter() - t_content, 3),
                    count=len(content_docs),
                )
                result = weighted_reciprocal_rank(
                    doc_lists=[vector_docs, content_docs],
                    weights=weights,
                )[:k]
        else:
            vector_docs = await vector_task
            result = vector_docs[:k]

        logger.debug(
            "hybrid_search_completed",
            elapsed=round(time.perf_counter() - t0, 3),
            result_count=len(result),
        )

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

    def _make_bigm_retriever(
        self,
        k: int,
        offset: int,
        tool_filters: list[SourceType] | None,
        temporal_filters: list[TemporalFilter] | None,
        **kwargs,
    ) -> PGBigmRetriever:
        """PGBigmRetriever를 생성한다."""
        return PGBigmRetriever(
            session_factory=self.session_factory,
            async_session_factory=self.async_session_factory,
            collection_name=self.collection_name,
            k=k,
            offset=offset,
            tool_filters=tool_filters,
            temporal_filters=temporal_filters,
            **kwargs,
        )

    async def _gather_keyword_docs(
        self,
        vector_task: asyncio.Task | None,
        content_task,
        title_task,
    ) -> tuple[list[Document], list[Document], list[Document]]:
        """keyword 검색을 위해 vector/content/title 태스크를 조합한다."""
        if title_task is not None:
            if vector_task is not None:
                vector_docs, content_docs, title_docs = await asyncio.gather(
                    vector_task, content_task, title_task
                )
            else:
                content_docs, title_docs = await asyncio.gather(
                    content_task, title_task
                )
                vector_docs = []
        else:
            if vector_task is not None:
                vector_docs, content_docs = await asyncio.gather(
                    vector_task, content_task
                )
            else:
                vector_docs, content_docs = [], await content_task
            title_docs = []
        return vector_docs, content_docs, title_docs

    def _build_search_kwargs(
        self,
        tool_filters: list[SourceType] | None,
        temporal_filters: list[TemporalFilter] | None,
    ) -> dict:
        search_kwargs = {}
        if not temporal_filters:
            if tool_filters:
                search_kwargs["filter"] = {
                    "source": {"$in": [f.value for f in tool_filters]}
                }
        else:
            or_conditions = []
            for tf in temporal_filters:
                or_conditions.append(
                    {
                        "$and": [
                            {"source": {"$in": [t.value for t in tf.tools]}},
                            {tf.time_field: {"$gte": tf.start_date.isoformat()}},
                            {tf.time_field: {"$lte": tf.end_date.isoformat()}},
                        ]
                    }
                )
            search_kwargs["filter"] = (
                {"$or": or_conditions} if len(or_conditions) > 1 else or_conditions[0]
            )
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
            temporal_filters=None,
        )

        with self.session_factory() as session:
            results = session.execute(search_sql, params).fetchall()

        return [
            Document(page_content=row[0], metadata=row[1] if row[1] else {}, id=row[2])
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
