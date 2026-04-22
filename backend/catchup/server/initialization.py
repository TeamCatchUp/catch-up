import psycopg
import structlog

from catchup.configs.config import settings

logger = structlog.get_logger(__name__)

INDICES = [
    """
    CREATE INDEX IF NOT EXISTS idx_cmetadata_source
    ON langchain_pg_embedding ((cmetadata ->> 'source'))
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_cmetadata_updated_at
    ON langchain_pg_embedding ((cmetadata ->> 'updated_at'))
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_cmetadata_created_at
    ON langchain_pg_embedding ((cmetadata ->> 'created_at'))
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_fts_korean_bigm
    ON langchain_pg_embedding USING GIN (document gin_bigm_ops)
    """,
]

async def ensure_pg_indices() -> None:
    conn_string = settings.sqlalchemy_database_url.replace("+psycopg", "")
    async with await psycopg.AsyncConnection.connect(conn_string) as conn:
        for sql in INDICES:
            await conn.execute(sql)


async def ensure_vector_index() -> None:
    """
    langchain_pg_embedding.embedding 컬럼에 HNSW 인덱스를 생성한다.
    인덱스가 이미 존재하면 no-op.
    CONCURRENTLY로 실행하므로 테이블 락 없이 백그라운드에서 빌드됨.

    CREATE INDEX CONCURRENTLY는 트랜잭션 블록 내에서 실행 불가하므로
    autocommit=True 커넥션을 별도로 생성한다.
    """
    conn_string = settings.sqlalchemy_database_url.replace("+psycopg", "")
    try:
        async with await psycopg.AsyncConnection.connect(
            conn_string, autocommit=True
        ) as conn:
            # 중단된 CONCURRENTLY 빌드가 남긴 INVALID 인덱스 처리
            row = await (await conn.execute("""
                SELECT indisvalid FROM pg_index
                JOIN pg_class ON pg_index.indexrelid = pg_class.oid
                WHERE relname = 'idx_embedding_hnsw'
            """)).fetchone()

            if row is not None and not row[0]:
                logger.warning(
                    "vector_index_invalid_dropping",
                    context="server_startup",
                )
                await conn.execute(
                    "DROP INDEX CONCURRENTLY IF EXISTS idx_embedding_hnsw"
                )

            logger.info("vector_index_creation_started", context="server_startup")
            # langchain-postgres가 embedding 컬럼을 차원 없는 vector 타입으로 생성하므로
            # HNSW 인덱스 생성 시 명시적으로 차원을 캐스팅해야 함
            await conn.execute(f"""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_embedding_hnsw
                ON langchain_pg_embedding
                USING hnsw ((embedding::vector({settings.PGVECTOR_EMBEDDING_DIMENSIONS})) vector_cosine_ops)
                WITH (m = 16, ef_construction = 128)
            """)
            
            # 최종 상태 및 파라미터 재검증
            final_check = await (await conn.execute("""
                SELECT pg_get_indexdef(pg_class.oid), pg_index.indisvalid 
                FROM pg_class 
                JOIN pg_index ON pg_class.oid = pg_index.indexrelid
                WHERE relname = 'idx_embedding_hnsw'
            """)).fetchone()

            if final_check and final_check[1]:
                logger.info(
                    "vector_index_creation_completed",
                    context="server_startup",
                    status="valid",
                    index_definition=final_check[0]
                )
            else:
                logger.error(
                    "vector_index_creation_failed_verification",
                    context="server_startup",
                    status="invalid_or_missing"
                )

    except Exception as e:
        logger.error(
            "vector_index_creation_failed",
            context="server_startup",
            error=str(e),
        )