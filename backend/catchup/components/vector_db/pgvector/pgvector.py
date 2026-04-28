import time
from typing import Any
from typing import Dict
from typing import Literal
from typing import Optional
from typing import override

import structlog
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.retrievers import RetrieverInput
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables import RunnableParallel
from langchain_core.runnables import RunnableSerializable
from langchain_postgres import PGVector
from sqlalchemy import Engine
from sqlalchemy import text

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.components.vector_db.rank import weighted_reciprocal_rank
from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.models import SourceType
from catchup.rag.schemas.filters import TemporalFilter

logger = structlog.get_logger(__name__)


class PostgresFTSRetriever(BaseRetriever):
    """PostgreSQL Full Text Search(FTS) 지원"""

    # BaseRetriever는 내부적으로 BaseModel을 상속하므로 Pydantic 스타일을 따라야 함
    session_factory: Any  # e.g) sessionmaker (from sqlalchemy.orm)
    collection_name: str = settings.PGVECTOR_COLLECTION_NAME
    k: int = 4
    offset: int = 0
    tool_filters: list[SourceType] | None = None
    temporal_filters: list[TemporalFilter] | None = None
    search_mode: Literal["title", "content", "both"] = "both"

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
        search_sql, params = self.build_fts_query(
            collection_name=self.collection_name,
            query=query,
            k=self.k,
            offset=self.offset,
            search_mode=self.search_mode,
            tool_filters=self.tool_filters,
            temporal_filters=self.temporal_filters,
        )

        results = list(self._do_query(search_sql, params))
        return self._get_documents_from_results(results)

    @staticmethod
    def build_fts_query(
        collection_name: str,
        query: str | list[str],
        k: int,
        offset: int = 0,
        search_mode: Literal["title", "content", "both"] = "both",
        tool_filters: list[SourceType] | None = None,
        temporal_filters: list[TemporalFilter] | None = None,
    ) -> tuple[Any, dict]:
        """
        통합 키워드 검색 SQL 및 파라미터 생성.
        """
        if isinstance(query, list):
            tokens = query
        else:
            # 문자열인 경우 공백으로 쪼개서 개별 키워드 리스트 생성
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

        # 토큰 기반 필터 및 스코어링 로직
        # AND 조건을 위해 모든 토큰이 포함되어야 함
        token_filters = []
        exact_match_scores = []
        sim_scores = []

        for i, token in enumerate(tokens):
            p_name = f"token_{i}"
            params[p_name] = token
            
            # Exact Match (완전 일치) 확인 로직
            # Title 가중치 2.0, Content 가중치 1.0 (Both 모드 기준)
            if search_mode in ("title", "both"):
                exact_match_scores.append(f"(CASE WHEN LOWER(e.cmetadata ->> 'title') = LOWER(:{p_name}) THEN 2.0 ELSE 0.0 END)")
                sim_scores.append(f"(bigm_similarity(e.cmetadata ->> 'title', :{p_name}) * 2.0)")
            
            if search_mode in ("content", "both"):
                exact_match_scores.append(f"(CASE WHEN LOWER(e.cmetadata ->> 'contextual_content') = LOWER(:{p_name}) THEN 1.0 ELSE 0.0 END)")
                sim_scores.append(f"bigm_similarity(e.cmetadata ->> 'contextual_content', :{p_name})")

            # AND 필터링: 각 토큰이 제목이나 내용 중 하나에는 반드시 포함되거나 유사해야 함
            token_conds = []
            if search_mode in ("title", "both"):
                token_conds.append(f"((e.cmetadata ->> 'title') =% :{p_name} OR (e.cmetadata ->> 'title') ILIKE likequery(:{p_name}))")
            if search_mode in ("content", "both"):
                token_conds.append(f"((e.cmetadata ->> 'contextual_content') =% :{p_name} OR (e.cmetadata ->> 'contextual_content') ILIKE likequery(:{p_name}))")
            
            if token_conds:
                token_filters.append(f"({' OR '.join(token_conds)})")

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
        params: dict
    ):
        with self.session_factory() as session:
            logger.debug("db_query_started")
            t0 = time.perf_counter()
            
            # pg_bigm 검색을 위해 similarity_limit 설정
            session.execute(text("SET LOCAL pg_bigm.similarity_limit = 0.02"))
            results = session.execute(search_sql, params)
            rows = results.fetchall()
            
            logger.debug(
                "db_query_completed",
                elapsed=round(time.perf_counter() - t0, 3),
                row_count=len(rows)
            )
            return rows

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
    
    def full_text_search(
        self,
        query: str,
    ) -> list[Document]:
        """
        단독 Full Text Search 유틸 함수.
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
    ):
        logger.info(f"PGVectorService initialized with Collection Name: '{collection_name}'")
        self.session_factory = session_factory
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

    def hybrid_search(
        self,
        query: str,
        k: int = 4,
        weights: list[float] = [0.3, 0.5, 0.2],
        tool_filters: list[SourceType] | None = None,
        temporal_filters: list[TemporalFilter] | None = None,
        keyword_tokens: list[str] | None = None,
        offset: int = 0,
        score_threshold: float = 0.4,
    ) -> list[Document]:
        """
        Langchain 기반 Hybrid Search를 수행한다.
        """
        
        logger.debug(
            "hybrid_search_started",
            query_len=len(query)
        )
        t0 = time.perf_counter()
        
        hybrid_search_chain = self._hybrid_search_chain(
            tool_filters=tool_filters,
            temporal_filters=temporal_filters,
            k=k,
            weights=weights,
            keyword_tokens=keyword_tokens,
            offset=offset,
            score_threshold=score_threshold
        )

        
        result = hybrid_search_chain.invoke({
            "semantic_query": query,
            "keyword_tokens": keyword_tokens or [query]
        })
        
        logger.debug(
            "hybrid_search_completed",
            elapsed=round(time.perf_counter() - t0, 3),
            result_count=len(result)
        )
        
        return result

        logger.info("hybrid_search_completed", elapsed=round(time.perf_counter() - t0, 3), result_count=len(result))
        return result

    def _hybrid_search_chain(
        self,
        k: int = 4,
        weights: list[float] = [0.3, 0.5, 0.2],  # [Vector, Title, Content]
        tool_filters: list[SourceType] | None = None,
        temporal_filters: list[TemporalFilter] | None = None,
        keyword_tokens: list[str] | None = None,
        offset: int = 0,
        score_threshold: float = 0.4
    ) -> RunnableSerializable[RetrieverInput, list[Document]]:
        """
        PostgreSQL FTS와 PGVector Similarity Search를 결합하여 
        3-Way Hybrid Search Chain을 생성한다.
        """
        
        def _make_logged_invoker(name: str, fn):
            def invoker(x):
                t0 = time.perf_counter()
                logger.debug(f"{name}_started")
                result = fn(x)
                logger.debug(
                    f"{name}_completed",
                    elapsed=round(time.perf_counter() - t0, 3),
                    count=len(result)
                )
                return result
            return invoker
        
        # Semantic Retriever (HNSW)
        # Recall 확보를 위해 k + offset보다 더 많은 후보(100)를 가져옴
        semantic_k = max(100, k + offset)
        search_kwargs = {"k": semantic_k}
        
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
        
        vector_retriever = self.vector_store.as_retriever(search_kwargs=search_kwargs)

        # Title Keyword Retriever
        title_retriever = PostgresFTSRetriever(
            session_factory=self.session_factory,
            collection_name=self.collection_name,
            k=semantic_k, # Fusion 전까지는 충분한 후보 유지
            offset=offset,
            tool_filters=tool_filters,
            temporal_filters=temporal_filters,
            search_mode="title"
        )
        
        # Content Keyword Retriever
        content_retriever = PostgresFTSRetriever(
            session_factory=self.session_factory,
            collection_name=self.collection_name,
            k=semantic_k,
            offset=offset,
            tool_filters=tool_filters,
            temporal_filters=temporal_filters,
            search_mode="content"
        )
        
        def _invoke_vector(x):
            t = time.perf_counter()
            logger.info("vector_retrieval_started")
            docs = vector_retriever.invoke(x["semantic_query"])
            logger.info("vector_retrieval_completed", elapsed=round(time.perf_counter() - t, 3), count=len(docs))
            return docs

        def _invoke_keyword(x):
            t = time.perf_counter()
            logger.info("keyword_retrieval_started")
            docs = keyword_retriever.invoke(x["keyword_tokens"])
            logger.info("keyword_retrieval_completed", elapsed=round(time.perf_counter() - t, 3), count=len(docs))
            return docs

        retriever_parallel = RunnableParallel(
            # Semantic 결과 필터링 (score_threshold 미만 제거)
            vector_docs=RunnableLambda(_make_logged_invoker(
                "vector_retrieval",
                lambda x: [
                    doc for doc, score in self.vector_store.similarity_search_with_score(
                        query=x["semantic_query"], 
                        k=semantic_k,
                        filter=search_kwargs.get("filter")
                    )[offset:]
                    if score >= score_threshold
                ]
            )),
            title_docs=RunnableLambda(_make_logged_invoker(
                "title_retrieval",
                lambda x: title_retriever.invoke(x["keyword_tokens"])
            )),
            content_docs=RunnableLambda(_make_logged_invoker(
                "content_retrieval",
                lambda x: content_retriever.invoke(x["keyword_tokens"])
            )),
        )
        
        def apply_rrf(results):
            # 3-Way RRF Fusion
            merged_docs = weighted_reciprocal_rank(
                doc_lists=[
                    results["vector_docs"],
                    results["title_docs"],
                    results["content_docs"]
                ],
                weights=weights                
            )
            # 최종 limit (k) 적용
            return merged_docs[:k]
        
        chain = retriever_parallel | RunnableLambda(apply_rrf)
        
        return chain

    def _weighted_keyword_search(
        self,
        query: str,
        k: int = 20,
        tool_filters: list[SourceType] | None = None,
        search_mode: Literal["title", "content", "both"] = "both",
        offset: int = 0,
    ) -> list[Document]:
        """
        가중치 기반 키워드 검색.
        """
        search_sql, params = PostgresFTSRetriever.build_fts_query(
            collection_name=self.collection_name,
            query=query,
            k=k,
            offset=offset,
            search_mode=search_mode,
            tool_filters=tool_filters,
            temporal_filters=None # PGVectorService interface does not yet expose temporal_filters for this method
        )

        with self.session_factory() as session:
            session.execute(text("SET LOCAL pg_bigm.similarity_limit = 0.02"))
            results = session.execute(search_sql, params).fetchall()

        return [
            Document(
                page_content=row[0],
                metadata=row[1] if row[1] else {},
                id=row[2]
            )
            for row in results
        ]

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        search_type: str = "similarity",
        filter: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> list[Document]:
        """
        단독 Similarity Search 유틸 함수.
        Hybrid Search에서는 사용되지 않는다.
        """
        search_kwargs = {"k": k, "filter": filter, **kwargs}
        retriever = self.vector_store.as_retriever(
            search_type=search_type, search_kwargs=search_kwargs
        )
        return retriever.invoke(query)

    
    def get_documents_by_ids(self, ids: list[str]) -> list[Document]:
        """Graph 확장 시 노드를 특정하기 위한 anchor id 리스트를 반환한다."""
        if not ids:
            return []
        return self.vector_store.get_by_ids(ids)
