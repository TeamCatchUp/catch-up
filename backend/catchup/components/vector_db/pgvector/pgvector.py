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

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.components.vector_db.rank import weighted_reciprocal_rank
from catchup.configs.config import settings
from catchup.db.engine import SessionLocal

logger = logging.getLogger(__name__)


class PostgresFTSRetriever(BaseRetriever):
    """PostgreSQL Full Text Search(FTS) 지원"""
    
    session_factory: Any  # e.g) sessionmaker (from sqlalchemy.orm)
    collection_name: str = settings.PGVECTOR_COLLECTION_NAME
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
              AND e.document LIKE :like_query
            ORDER BY bigm_similarity(e.document, :query) DESC
            LIMIT :k
        """)
        
        like_query = f"%{query}%"

        results = self._do_query(query, like_query, search_sql)
        docs = self._get_documents_from_results(results)

        return docs

    def _do_query(
            self,
            query: str,
            like_query: str,
            search_sql: str
        ):
        with self.session_factory() as session:
            results = session.execute(
                search_sql,
                {
                    "collection_name": self.collection_name,
                    "query": query,
                    "like_query": like_query,
                    "k": self.k
                },
            )
            return results

    def _get_documents_from_results(self, results):
        docs = []

        for row in results:
            docs.append(
                Document(page_content=row[0], metadata=row[1] if row[1] else {})
            )

        return docs


class PGVectorService(BaseVectorDbService):
    def __init__(
        self,
        postgresql_engine: Engine,
        embeddings: Embeddings,
        collection_name: str = settings.PGVECTOR_COLLECTION_NAME,
        session_factory: Any = SessionLocal,
    ):
        logger.info(f"PGVectorService initialized with Collection Name: '{collection_name}'")
        logger.info(f"DB URL Host: {postgresql_engine.url.host}")
        self.session_factory = session_factory
        self.collection_name = collection_name
        self.vector_store = self._create_pgvector(
            postgresql_engine, embeddings, collection_name
        )
        self._ensure_fts_index()

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
        pg_bigm을 사용하여 한글 부분 일치 검색을 위한 GIN 인덱스를 생성한다.
        테이블이 존재할 때만 인덱스를 생성하며, 이미 존재하면 건너뛴다.
        """
        index_query = text("""
            CREATE EXTENSION IF NOT EXISTS pg_bigm;
            CREATE INDEX IF NOT EXISTS idx_fts_korean_bigm
            ON langchain_pg_embedding
            USING GIN (document gin_bigm_ops);
        """)

        try:
            with self.session_factory() as session:
                session.execute(index_query)
                session.commit()
                logger.info("pg_bigm 기반 한글 인덱스 생성 성공")
        except Exception as e:
            logger.warning(f"pg_bigm 인덱스 생성 실패: {e}")

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
    
    def get_documents_by_ids(self, ids: list[str]) -> list[Document]:
        if not ids:
            return []
        return self.vector_store.get_by_ids(ids)
   

# Test용 스크립트
if __name__ == "__main__":
    from langchain_cohere import CohereEmbeddings
    from langchain_core.documents import Document
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from catchup.configs.config import settings

    # DB 연결 및 초기화
    DATABASE_URL = settings.sqlalchemy_database_url
    engine = create_engine(DATABASE_URL)
    SessionFactory = sessionmaker(bind=engine)
    COLLECTION_NAME = settings.PGVECTOR_COLLECTION_NAME

    embeddings = CohereEmbeddings(
        model=settings.COHERE_EMBEDDING_MODEL,
        cohere_api_key=settings.COHERE_API_KEY,
    )

    print(f">>> 컬렉션 '{COLLECTION_NAME}' 초기화 중...")

    with SessionFactory() as session:
        coll_query = text("SELECT uuid FROM langchain_pg_collection WHERE name = :name")
        result = session.execute(coll_query, {"name": COLLECTION_NAME}).fetchone()
        
        if result:
            coll_uuid = result[0]
            session.execute(text("DELETE FROM langchain_pg_embedding WHERE collection_id = :uuid"), {"uuid": coll_uuid})
            session.execute(text("DELETE FROM langchain_pg_collection WHERE uuid = :uuid"), {"uuid": coll_uuid})
            session.commit()
            print(">>> 기존 데이터 삭제 완료.")
        else:
            print(">>> 삭제할 기존 데이터가 없습니다.")

    print("\n>>> 데이터 주입 시작...")
    pg_service = PGVectorService(
        postgresql_engine=engine,
        embeddings=embeddings,
        collection_name=COLLECTION_NAME,
        session_factory=SessionFactory
    )

    mock_docs = [
        Document(
            # d1: LangChain 문서
            id='480e29d9-05ae-4efb-8a84-37b1e9478aad', 
            page_content="LangChain과 PGVector를 결합하면 강력한 검색 시스템을 구축할 수 있습니다.",
            metadata={"source": "tech_blog", "author": "Kim"}
        ),
        Document(
            # d2: PostgreSQL 문서
            id='cd72fa82-37f5-4d94-9f52-8d4347cb88a0',
            page_content="PostgreSQL은 세계에서 가장 진보된 오픈소스 관계형 데이터베이스입니다.",
            metadata={"source": "wiki", "category": "db"}
        ),
        Document(
            # d3: Python 문서
            id='0e2f490d-68f7-484f-8b82-13c98bd54d67',
            page_content="파이썬(Python)은 데이터 사이언스와 AI 분야에서 가장 널리 쓰이는 언어입니다.",
            metadata={"source": "tech_blog", "author": "Lee"}
        ),
        # 아래는 Graph에는 없지만 검색 테스트용으로 추가 (Noise)
        Document(
            id='a05668b6-0767-4189-a5c4-29cd2dfa5097',
            page_content="하이브리드 검색은 키워드 매칭과 시맨틱(의미) 검색의 장점을 모두 활용합니다.",
            metadata={"source": "paper", "year": 2024}
        ),
        Document(
            id='a1b6822a-4774-442c-8cd0-510365f18116',
            page_content="오늘 점심 메뉴는 김치찌개와 계란말이입니다. 맛집을 찾아봅시다.",
            metadata={"source": "chat", "type": "noise"}
        ),
    ]

    # PGVector에 저장
    pg_service.vector_store.add_documents(mock_docs, ids=[doc.id for doc in mock_docs])
    print(f">>> {len(mock_docs)}개의 문서를 Vector DB에 저장했습니다. (Graph DB와 ID 동기화 완료)")

    print("\n>>> [검색 테스트] '파이썬' 검색")
    results = pg_service.hybrid_search("파이썬", k=1)
    for doc in results:
        print(f"ID: {doc.id} | Content: {doc.metadata.get('contextual_content', '')}")
