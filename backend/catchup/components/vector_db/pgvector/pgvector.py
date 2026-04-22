import logging
from typing import Optional, Dict, Any, override
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.retrievers import BaseRetriever, RetrieverInput
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnableSerializable
from langchain_postgres import PGVector
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from sqlalchemy import Engine, text

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.components.vector_db.rank import weighted_reciprocal_rank
from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.models import SourceType
from catchup.rag.schemas.filters import TemporalFilter

logger = logging.getLogger(__name__)


class PostgresFTSRetriever(BaseRetriever):
    """PostgreSQL Full Text Search(FTS) 지원"""
    
    # BaseRetriever는 내부적으로 BaseModel을 상속하므로 Pydantic 스타일을 따라야 함
    session_factory: Any  # e.g) sessionmaker (from sqlalchemy.orm)
    collection_name: str = settings.PGVECTOR_COLLECTION_NAME
    k: int = 4
    tool_filters: list[SourceType] | None = None
    temporal_filters: list[TemporalFilter] | None = None

    @override
    def _get_relevant_documents(
        self,
        query: str | list[str],
        *,
        run_manager: CallbackManagerForRetrieverRun,  # BaseRetriever 시그니처
    ) -> list[Document]:
        """
        Hybrid Search를 위한 PostgreSQL Full Text search. 
        """
        
        # 동적 쿼리 필터
        filter_clause = ""
        
        # pg_bigm similarity 정렬을 위한 원본 쿼리 (리스트일 경우 공백으로 병합)
        original_query = " ".join(query) if isinstance(query, list) else query
        tokens = query if isinstance(query, list) else [query]

        params = {
            "collection_name": self.collection_name,
            "query": original_query,
            "k": self.k
        }
        
        if not self.temporal_filters:
            if self.tool_filters:
                filter_clause = " AND e.cmetadata ->> 'source' = ANY(:tools)"
                params["tools"] = [f.value for f in self.tool_filters]
                
        else:
            sql_conditions = []
            for i, tf in enumerate(self.temporal_filters):
                tools_param_name = f"tools_{i}"
                start_param_name = f"start_date_{i}"
                end_param_name   = f"end_date_{i}"
                params[tools_param_name] = [t.value for t in tf.tools]
                params[start_param_name] = tf.start_date
                params[end_param_name]   = tf.end_date

                sql_conditions.append(
                    f"(e.cmetadata ->> 'source' = ANY(:{tools_param_name}) "
                    f"AND (e.cmetadata ->> '{tf.time_field}')::timestamp "
                    f"BETWEEN :{start_param_name} AND :{end_param_name})"
                )
                            
            filter_clause = f" AND ({' OR '.join(sql_conditions)})"

        # keyword_tokens가 있으면 LIKE likequery() 필터 생성
        token_conditions = []
        for idx, token in enumerate(tokens):
            param_name = f"keyword_{idx}"
            token_conditions.append(f"(e.cmetadata ->> 'contextual_content') LIKE likequery(:{param_name})")
            params[param_name] = token

        # 1차 검색 (AND 조건)
        and_filter = f" AND ({' AND '.join(token_conditions)})" if token_conditions else ""
        
        search_sql_template = """
            SELECT e.document, e.cmetadata, e.id
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON e.collection_id = c.uuid
            WHERE c.name = :collection_name
              {filter_clause}
              {keyword_filter}
            ORDER BY bigm_similarity(e.cmetadata ->> 'contextual_content', :query) DESC
            LIMIT :k
        """

        search_sql_and = text(search_sql_template.format(
            filter_clause=filter_clause,
            keyword_filter=and_filter
        ))
        
        results = list(self._do_query(search_sql_and, params))
        
        # 2차 검색 (Fallback: 결과가 k개 미만이면 OR 조건으로 추가 검색)
        if len(results) < self.k and len(tokens) > 1:
            or_filter = f" AND ({' OR '.join(token_conditions)})"
            search_sql_or = text(search_sql_template.format(
                filter_clause=filter_clause,
                keyword_filter=or_filter
            ))
            
            or_results = self._do_query(search_sql_or, params)
            
            # 중복 제거 (이미 AND 결과에 포함된 문서 제외)
            existing_ids = {row[2] for row in results}
            for row in or_results:
                if row[2] not in existing_ids:
                    results.append(row)
                    if len(results) >= self.k:
                        break

        docs = self._get_documents_from_results(results[:self.k])
        return docs

    def _do_query(
        self,
        search_sql: str,
        params: dict
    ):
        with self.session_factory() as session:
            # HNSW 검색 품질 향상을 위해 ef_search 설정 적용
            session.execute(text("SET LOCAL hnsw.ef_search = 80"))
            results = session.execute(search_sql, params)
            return results.fetchall()

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
        weights: list[float] = [0.5, 0.5],
        tool_filters: list[SourceType] | None = None,
        temporal_filters: list[TemporalFilter] | None = None,
        keyword_tokens: list[str] | None = None,
    ) -> list[Document]:
        """
        Langchain 기반 Hybrid Search를 수행한다.
        """
        hybrid_search_chain = self._hybrid_search_chain(
            tool_filters=tool_filters,
            temporal_filters=temporal_filters,
            k=k,
            weights=weights
        )
        
        return hybrid_search_chain.invoke({
            "semantic_query": query,
            "keyword_tokens": keyword_tokens or [query]
        })

    def _hybrid_search_chain(
        self,
        k: int = 4,
        weights: list[float] = [0.5, 0.5],  # [Vector, Keyword]
        tool_filters: list[SourceType] | None = None,
        temporal_filters: list[TemporalFilter] | None = None
    ) -> RunnableSerializable[RetrieverInput, list[Document]]:
        """
        PostgreSQL FTS와 PGVector Similarity Search를 결합하여 
        Hybrid Search Chain을 생성한다.
        """
        
        search_kwargs = {"k": k}
        
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

        keyword_retriever = PostgresFTSRetriever(
            session_factory=self.session_factory,
            collection_name=self.collection_name,
            k=k,
            tool_filters=tool_filters,
            temporal_filters=temporal_filters
        )
        
        retriever_parallel = RunnableParallel(
            vector_docs=RunnableLambda(lambda x: vector_retriever.invoke(x["semantic_query"])),
            keyword_docs=RunnableLambda(lambda x: keyword_retriever.invoke(x["keyword_tokens"]))
        )
        
        def apply_rrf(results):
            return weighted_reciprocal_rank(
                doc_lists=[
                    results["vector_docs"],
                    results["keyword_docs"]
                ],
                weights=weights                
            )
        
        chain = retriever_parallel | RunnableLambda(apply_rrf)
        
        return chain
    
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
