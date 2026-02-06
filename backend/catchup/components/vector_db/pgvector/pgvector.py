import logging
from typing import Optional, Dict, Any, override
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.retrievers import BaseRetriever, RetrieverInput
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnableSerializable
from langchain_postgres import PGVector
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from pydantic import ConfigDict
from sqlalchemy import Engine, text

from catchup.components.vector_db.rank import weighted_reciprocal_rank
from catchup.db.engine import SessionLocal

logger = logging.getLogger(__name__)


class PostgresFTSRetriever(BaseRetriever):
    """PostgreSQL Full Text Search(FTS) 지원"""
    
    session_factory: Any  # e.g) sessionmaker (from sqlalchemy.orm)
    collection_name: str
    language_config: str = "korean"
    k: int = 4

    model_config = ConfigDict(arbitrary_types_allowed=True)
        
    def full_text_search(
        self,
        query: str,
    )->list[Document]:
        return self.invoke(query)
        

    @override
    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,  # BaseRetriever 시그니처
    ) -> list[Document]:
        """PostgreSQL Full Text search."""

        search_sql = text(f"""
            SELECT e.document, e.cmetadata
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON e.collection_id = c.uuid
            WHERE c.name = :collection_name
              AND to_tsvector('{self.language_config}', e.document) @@ websearch_to_tsquery('{self.language_config}', :query)
            ORDER BY ts_rank(to_tsvector('{self.language_config}', e.document), websearch_to_tsquery('{self.language_config}', :query)) DESC
            LIMIT :k
        """)  # TODO: 한국어 형태소 분석기

        results = self._do_query(query, search_sql)

        docs = self._get_documents_from_results(results)

        return docs

    def _do_query(self, query: str, search_sql: str):
        with self.session_factory() as session:
            results = session.execute(
                search_sql,
                {"collection_name": self.collection_name, "query": query, "k": self.k},
            )
            return results

    def _get_documents_from_results(self, results):
        docs = []

        for row in results:
            docs.append(
                Document(page_content=row[0], metadata=row[1] if row[1] else {})
            )

        return docs


class PGVectorService:
    def __init__(
        self,
        postgresql_engine: Engine,
        embeddings: Embeddings,
        collection_name: str,
        session_factory: Any = SessionLocal,
    ):
        self.session_factory = session_factory
        self.collection_name = collection_name
        self.vector_store = self._create_pgvector(
            postgresql_engine, embeddings, collection_name
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

    def _ensure_fts_index(self):
        """
        한국어 Full Text Search를 위한 GIN 인덱스를 생성한다.
        테이블이 존재할 때만 인덱스를 생성하며, 이미 존재하면 건너뛴다.
        """
        index_query = text("""
            CREATE INDEX IF NOT EXISTS idx_fts_korean_document
            ON langchain_pg_embedding 
            USING GIN (to_tsvector('korean', document));
        """)

        try:
            with self.session_factory() as session:
                session.execute(index_query)
                session.commit()
                logger.info("Korean FTS 인덱스 생성 성공")
        except Exception as e:
            logger.warning(f"pgvector 인덱스 생성 실패: {e}")

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        search_type: str = "similarity",
        filter: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> list[Document]:
        search_kwargs = {"k": k, "filter": filter, **kwargs}
        retriever = self.vector_store.as_retriever(
            search_type=search_type, search_kwargs=search_kwargs
        )
        return retriever.invoke(query)
    
    
    def hybrid_search(
            self,
            query: str,
            k: int = 4,
            weights: list[float] = [0.5, 0.5]
    ) -> list[Document]:
        hybrid_search_chain = self._hybrid_search_chain(
            k=k,
            weights=weights
        )
        
        return hybrid_search_chain.invoke(query)

    def _hybrid_search_chain(
        self,
        k: int = 4,
        weights: list[float] = [0.5, 0.5]  # [Vector, Keyword]
    ) -> RunnableSerializable[RetrieverInput, list[Document]]:
        vector_retriever = self.vector_store.as_retriever(search_kwargs={"k": k})

        keyword_retriever = PostgresFTSRetriever(
            session_factory=self.session_factory,
            collection_name=self.collection_name,
            k=k,
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
   

# Test용 스크립트
if __name__ == "__main__":
    from langchain_core.embeddings import Embeddings
    from langchain_core.documents import Document
    from sqlalchemy import create_engine, text
    import numpy as np
    from catchup.configs.config import settings

    # 가짜 임베딩 (테스트용)
    class FakeEmbeddings(Embeddings):
        def __init__(self, size: int = 1536):
            self.size = size

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [np.random.rand(self.size).tolist() for _ in texts]

        def embed_query(self, text: str) -> list[float]:
            return np.random.rand(self.size).tolist()
    
    # DB 연결 설정
    DATABASE_URL = settings.sqlalchemy_database_url
    engine = create_engine(DATABASE_URL)
    
    from sqlalchemy.orm import sessionmaker
    SessionFactory = sessionmaker(bind=engine)

    COLLECTION_NAME = "test_hybrid_collection"
    embeddings = FakeEmbeddings(size=1536)

    # 기존 데이터 초기화
    print(f">>> 컬렉션 '{COLLECTION_NAME}' 초기화 중...")
    
    with SessionFactory() as session:
        coll_query = text("SELECT uuid FROM langchain_pg_collection WHERE name = :name")
        result = session.execute(coll_query, {"name": COLLECTION_NAME}).fetchone()
        
        if result:
            coll_uuid = result[0]
            del_embed = text("DELETE FROM langchain_pg_embedding WHERE collection_id = :uuid")
            session.execute(del_embed, {"uuid": coll_uuid})
            del_coll = text("DELETE FROM langchain_pg_collection WHERE uuid = :uuid")
            session.execute(del_coll, {"uuid": coll_uuid})
            session.commit()
            print(">>> 기존 데이터 삭제 완료.")
        else:
            print(">>> 삭제할 기존 데이터가 없습니다.")

    # 서비스 초기화
    print("\n>>> 서비스 초기화 및 데이터 주입...")
    pg_service = PGVectorService(
        postgresql_engine=engine,
        embeddings=embeddings,
        collection_name=COLLECTION_NAME,
        session_factory=SessionFactory
    )
    
    mock_docs = [
        Document(
            page_content="LangChain과 PGVector를 결합하면 강력한 검색 시스템을 구축할 수 있습니다.",
            metadata={"source": "tech_blog", "author": "Kim"}
        ),
        Document(
            page_content="PostgreSQL은 세계에서 가장 진보된 오픈소스 관계형 데이터베이스입니다.",
            metadata={"source": "wiki", "category": "db"}
        ),
        Document(
            page_content="하이브리드 검색은 키워드 매칭과 시맨틱(의미) 검색의 장점을 모두 활용합니다.",
            metadata={"source": "paper", "year": 2024}
        ),
        Document(
            page_content="오늘 점심 메뉴는 김치찌개와 계란말이입니다. 맛집을 찾아봅시다.",
            metadata={"source": "chat", "type": "noise"}
        ),
        Document(
            page_content="파이썬(Python)은 데이터 사이언스와 AI 분야에서 가장 널리 쓰이는 언어입니다.",
            metadata={"source": "tech_blog", "author": "Lee"}
        ),
    ]

    pg_service.vector_store.add_documents(mock_docs)
    print(f">>> {len(mock_docs)}개의 문서를 DB에 저장했습니다.")

    # 인덱스 생성
    pg_service._ensure_fts_index()

    # 검색 테스트
    query_lunch = "언어"
    print(f"\n>>> [TEST] 검색 쿼리: '{query_lunch}' (키워드 100%)")
    
    # FakeEmbedding이라 벡터 성능이 무작위이므로 키워드 검색(FTS)만 테스트
    results_lunch = pg_service.hybrid_search(query_lunch, k=3, weights=[0.0, 1.0])
    
    print(">>> 검색 결과:")
    for i, doc in enumerate(results_lunch):
        print(f"[{i+1}] {doc.page_content}")