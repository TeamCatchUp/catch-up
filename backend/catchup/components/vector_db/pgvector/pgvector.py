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
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,  # BaseRetriever 시그니처
    ) -> list[Document]:
        """
        Hybrid Search를 위한 PostgreSQL Full Text search. 
        """
        
        # 동적 쿼리 필터
        filter_clause = ""
        
        params = {
            "collection_name": self.collection_name,
            "query": query,
            "like_query": f"%{query}%",
            "k": self.k
        }
        
        if not self.temporal_filters:
            if self.tool_filters:
                filter_clause = " AND e.cmetadata ->> 'source' = ANY(:tools)"
                params["tools"] = [f.value for f in self.tool_filters]
                
        else:
            sql_conditions = []
            for i, tf in enumerate(self.temporal_filters):
                tools_param_name = f"tools_{i}"  # 키 값이 덮어띄워지지 않도록 보장
                params[tools_param_name] = [t.value for t in tf.tools]
                params.update({"start_date": tf.start_date, "end_date": tf.end_date})
                    
                sql_conditions.append(
                    f"(e.cmetadata ->> 'source' = ANY(:{tools_param_name}) "
                    f"AND (e.cmetadata ->> '{tf.time_field}')::timestamp "
                    f"BETWEEN :start_date AND :end_date)"
                )
                            
            filter_clause = f" AND ({' OR '.join(sql_conditions)})"

        search_sql = text(f"""
            SELECT e.document, e.cmetadata
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON e.collection_id = c.uuid
            WHERE c.name = :collection_name
              {filter_clause}
              AND e.document LIKE :like_query
            ORDER BY bigm_similarity(e.document, :query) DESC
            LIMIT :k
        """)
        

        results = self._do_query(search_sql, params)
        docs = self._get_documents_from_results(results)

        return docs

    def _do_query(
        self,
        search_sql: str,
        params: dict
    ):
        with self.session_factory() as session:
            results = session.execute(
                search_sql,
                params
            )
            return results

    def _get_documents_from_results(self, results):
        docs = []

        for row in results:
            docs.append(
                Document(page_content=row[0], metadata=row[1] if row[1] else {})
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
        # self._ensure_index()

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

    # def _ensure_index(self):
    #     """
    #     pg_bigm을 사용하여 한글 부분 일치 검색을 위한 GIN 인덱스를 생성한다.
    #     JSONB 타입의 cmetadata 컬럼의 'source', 'updated_at', 'created_at' 필드를 
    #     필터링 하기 위한 B-Tree 인덱스를 생성한다.
    #     테이블이 존재할 때만 인덱스를 생성하며, 이미 존재하면 건너뛴다.
    #     """
    #     index_query = text("""
    #         CREATE EXTENSION IF NOT EXISTS pg_bigm;
    #         CREATE EXTENSION IF NOT EXISTS vector;
            
    #         CREATE INDEX IF NOT EXISTS idx_fts_korean_bigm
    #         ON langchain_pg_embedding
    #         USING GIN (document gin_bigm_ops);
            
    #         CREATE INDEX IF NOT EXISTS idx_cmetadata_source 
    #         ON langchain_pg_embedding ((cmetadata ->> 'source'));
            
    #         CREATE INDEX IF NOT EXISTS idx_cmetadata_updated_at
    #         ON langchain_pg_embedding ((cmetadata ->> 'updated_at'));
                           
    #         CREATE INDEX IF NOT EXISTS idx_cmetadata_created_at
    #         ON langchain_pg_embedding ((cmetadata ->> 'created_at'));
    #     """)

    #     try:
    #         with self.session_factory() as session:
    #             session.execute(index_query)
    #             session.commit()
    #             logger.info("Created postgresql indices successfully.")
    #     except Exception as e:
    #         logger.warning(f"Failed to create postgresql indices: {e}")
    
    def hybrid_search(
        self,
        query: str,
        k: int = 4,
        weights: list[float] = [0.5, 0.5],
        tool_filters: list[SourceType] | None = None,
        temporal_filters: list[TemporalFilter] | None = None,
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
        
        return hybrid_search_chain.invoke(query)

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
            vector_docs=vector_retriever,
            keyword_docs=keyword_retriever
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
