import psycopg
import structlog

from catchup.configs.config import settings

logger = structlog.get_logger(__name__)

LIGHT_INDICES = [
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
]

HEAVY_INDICES = [
    """
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cmetadata_contextual_bigm_v2
    ON langchain_pg_embedding USING GIN ((lower(cmetadata ->> 'contextual_content')) gin_bigm_ops)
    """,
    """
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cmetadata_title_bigm_v2
    ON langchain_pg_embedding USING GIN ((lower(cmetadata ->> 'title')) gin_bigm_ops)
    """,
]

# document 컬럼 전체에 걸린 인덱스 — PGBigmRetriever는 cmetadata 필드만 검색하므로 미사용
# idx_embedding_hnsw — embedding::vector(1536) 캐스팅 expression index라 쿼리가 타지 않음
#                      컬럼 타입을 vector(1536)으로 ALTER한 뒤 expression 없는 인덱스로 재생성
# idx_cmetadata_title_bigm — title 필드 없는 source가 있어 partial로 만들었다 폐기, full GIN v2로 교체
# idx_cmetadata_contextual_bigm — lower() 없는 버전, ILIKE는 gin_bigm_ops를 타지 않아 v2로 교체
OBSOLETE_INDICES = ["idx_fts_korean_bigm", "idx_embedding_hnsw", "idx_cmetadata_title_bigm", "idx_cmetadata_contextual_bigm"]

KS_LIGHT_INDICES: list[tuple[str, str]] = [
    ("idx_ks_source", "CREATE INDEX IF NOT EXISTS idx_ks_source ON knowledge_store (source)"),
    ("idx_ks_created_at", "CREATE INDEX IF NOT EXISTS idx_ks_created_at ON knowledge_store (created_at)"),
    ("idx_ks_updated_at", "CREATE INDEX IF NOT EXISTS idx_ks_updated_at ON knowledge_store (updated_at)"),
]

KS_HEAVY_INDICES = [
    """
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ks_body_bigm
    ON knowledge_store USING GIN (lower(body) gin_bigm_ops)
    """,
    """
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ks_title_bigm
    ON knowledge_store USING GIN (lower(title) gin_bigm_ops)
    """,
]
KS_HEAVY_INDEX_NAMES = ["idx_ks_body_bigm", "idx_ks_title_bigm"]


async def _ks_table_exists(conn) -> bool:
    """knowledge_store 테이블 존재 여부를 확인한다."""
    row = await (await conn.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'knowledge_store'
        )
    """)).fetchone()
    return bool(row and row[0])


async def ensure_ks_indices() -> None:
    """knowledge_store 테이블의 B-tree 및 GIN bigm 인덱스를 생성한다.

    테이블이 존재하지 않으면 아무 작업도 수행하지 않는다.
    """
    conn_string = settings.sqlalchemy_database_url.replace("+psycopg", "")

    async with await psycopg.AsyncConnection.connect(conn_string) as conn:
        if not await _ks_table_exists(conn):
            logger.info("ks_indices_skipped", reason="knowledge_store table not found")
            return
        for index_name, sql in KS_LIGHT_INDICES:
            await conn.execute(sql)
            logger.info(
                "ks_light_index_created",
                context="server_startup",
                index_name=index_name,
            )

    async with await psycopg.AsyncConnection.connect(conn_string, autocommit=True) as conn:
        for index_name, sql in zip(KS_HEAVY_INDEX_NAMES, KS_HEAVY_INDICES):
            row = await (await conn.execute(f"""
                SELECT indisvalid FROM pg_index
                JOIN pg_class ON pg_index.indexrelid = pg_class.oid
                WHERE relname = '{index_name}'
            """)).fetchone()

            if row is not None and not row[0]:
                logger.warning(
                    "ks_heavy_index_invalid_dropping",
                    context="server_startup",
                    index_name=index_name,
                )
                await conn.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}")

            logger.info(
                "ks_heavy_index_creation_started",
                context="server_startup",
                index_name=index_name,
            )
            try:
                await conn.execute(sql)
                final_check = await (await conn.execute(f"""
                    SELECT pg_get_indexdef(pg_class.oid), pg_index.indisvalid
                    FROM pg_class
                    JOIN pg_index ON pg_class.oid = pg_index.indexrelid
                    WHERE relname = '{index_name}'
                """)).fetchone()

                if final_check and final_check[1]:
                    logger.info(
                        "ks_heavy_index_creation_completed",
                        context="server_startup",
                        index_name=index_name,
                        status="valid",
                        index_definition=final_check[0],
                    )
                else:
                    logger.error(
                        "ks_heavy_index_creation_failed_verification",
                        context="server_startup",
                        index_name=index_name,
                        status="invalid_or_missing",
                    )
            except Exception as e:
                logger.error(
                    "ks_heavy_index_creation_failed",
                    context="server_startup",
                    index_name=index_name,
                    error=str(e),
                )


async def ensure_ks_vector_index() -> None:
    """knowledge_store 테이블의 HNSW 인덱스를 생성한다.

    테이블이 존재하지 않으면 아무 작업도 수행하지 않는다.
    embedding 컬럼이 차원 없는 vector이면 vector(N)으로 ALTER한 뒤 인덱스를 생성한다.
    """
    conn_string = settings.sqlalchemy_database_url.replace("+psycopg", "")
    index_name = "idx_ks_embedding_hnsw"
    try:
        async with await psycopg.AsyncConnection.connect(
            conn_string, autocommit=True
        ) as conn:
            if not await _ks_table_exists(conn):
                logger.info(
                    "ks_vector_index_skipped",
                    reason="knowledge_store table not found",
                )
                return

            col_row = await (await conn.execute("""
                SELECT pg_catalog.format_type(a.atttypid, a.atttypmod)
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                WHERE c.relname = 'knowledge_store'
                  AND a.attname = 'embedding'
            """)).fetchone()

            if col_row and col_row[0] == "vector":
                logger.info(
                    "ks_embedding_column_type_altering",
                    context="server_startup",
                    from_type="vector",
                    to_type=f"vector({settings.PGVECTOR_EMBEDDING_DIMENSIONS})",
                )
                await conn.execute(f"""
                    ALTER TABLE knowledge_store
                    ALTER COLUMN embedding TYPE vector({settings.PGVECTOR_EMBEDDING_DIMENSIONS})
                """)
                logger.info("ks_embedding_column_type_altered", context="server_startup")

            row = await (await conn.execute(f"""
                SELECT indisvalid FROM pg_index
                JOIN pg_class ON pg_index.indexrelid = pg_class.oid
                WHERE relname = '{index_name}'
            """)).fetchone()

            if row is not None and not row[0]:
                logger.warning(
                    "ks_vector_index_invalid_dropping",
                    context="server_startup",
                    index_name=index_name,
                )
                await conn.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}")

            logger.info(
                "ks_vector_index_creation_started",
                context="server_startup",
                index_name=index_name,
            )
            await conn.execute(f"""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name}
                ON knowledge_store
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 128)
            """)

            final_check = await (await conn.execute(f"""
                SELECT pg_get_indexdef(pg_class.oid), pg_index.indisvalid
                FROM pg_class
                JOIN pg_index ON pg_class.oid = pg_index.indexrelid
                WHERE relname = '{index_name}'
            """)).fetchone()

            if final_check and final_check[1]:
                logger.info(
                    "ks_vector_index_creation_completed",
                    context="server_startup",
                    index_name=index_name,
                    status="valid",
                    index_definition=final_check[0],
                )
            else:
                logger.error(
                    "ks_vector_index_creation_failed_verification",
                    context="server_startup",
                    index_name=index_name,
                    status="invalid_or_missing",
                )

            await conn.execute("SET enable_seqscan = off")
            explain_rows = await (await conn.execute(f"""
                EXPLAIN (ANALYZE, FORMAT TEXT)
                SELECT document_id FROM knowledge_store
                ORDER BY embedding <=> (array_fill(0, ARRAY[{settings.PGVECTOR_EMBEDDING_DIMENSIONS}])::vector)
                LIMIT 10
            """)).fetchall()
            plan_text = "\n".join(row[0] for row in explain_rows)
            if index_name in plan_text:
                logger.info(
                    "ks_vector_index_usage_verified",
                    context="server_startup",
                    index_name=index_name,
                )
            else:
                logger.error(
                    "ks_vector_index_usage_not_verified",
                    context="server_startup",
                    index_name=index_name,
                    plan=plan_text[:500],
                )

    except Exception as e:
        logger.error(
            "ks_vector_index_creation_failed",
            context="server_startup",
            index_name=index_name,
            error=str(e),
        )


async def ensure_ks_all_indices() -> None:
    """knowledge_store 인덱스를 순차 실행한다.

    GIN과 HNSW 모두 CREATE INDEX CONCURRENTLY를 사용하므로
    동시에 실행하면 같은 테이블에서 ShareUpdateExclusiveLock 경합으로 deadlock이 발생한다.
    GIN(bigm) → HNSW 순서로 직렬 실행해 이를 방지한다.
    """
    await ensure_ks_indices()
    await ensure_ks_vector_index()


async def ensure_pg_indices() -> None:
    conn_string = settings.sqlalchemy_database_url.replace("+psycopg", "")
    
    # B-tree는 일반 트랜잭션에서 빠르게 처리
    async with await psycopg.AsyncConnection.connect(conn_string) as conn:
        # pg_bigm 익스텐션 활성화 (이미 활성화되어 있으면 no-op)
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_bigm")
        
        for sql in LIGHT_INDICES:
            await conn.execute(sql)
            
    # GIN은 autocommit 모드에서 Non-blocking으로 처리
    async with await psycopg.AsyncConnection.connect(conn_string, autocommit=True) as conn:
        for index_name in OBSOLETE_INDICES:
            await conn.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}")
            logger.info("obsolete_index_dropped", index_name=index_name)

        heavy_index_names = ["idx_cmetadata_contextual_bigm_v2", "idx_cmetadata_title_bigm_v2"]
        for index_name in heavy_index_names:
            row = await (await conn.execute(f"""
                SELECT indisvalid FROM pg_index
                JOIN pg_class ON pg_index.indexrelid = pg_class.oid
                WHERE relname = '{index_name}'
            """)).fetchone()

            if row is not None and not row[0]:
                logger.warning(
                    "heavy_index_invalid_dropping",
                    context="server_startup",
                    index_name=index_name,
                )
                await conn.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}")
                logger.info(
                    "heavy_index_invalid_dropped",
                    context="server_startup",
                    index_name=index_name,
                )

        for index_name, sql in zip(heavy_index_names, HEAVY_INDICES):
            logger.info(
                "heavy_index_creation_started",
                context="server_startup",
                index_name=index_name,
            )
            try:
                await conn.execute(sql)
                
                final_check = await (await conn.execute(f"""
                    SELECT pg_get_indexdef(pg_class.oid), pg_index.indisvalid 
                    FROM pg_class 
                    JOIN pg_index ON pg_class.oid = pg_index.indexrelid
                    WHERE relname = '{index_name}'
                """)).fetchone()

                if final_check and final_check[1]:
                    logger.info(
                        "heavy_index_creation_completed",
                        context="server_startup",
                        index_name=index_name,
                        status="valid",
                        index_definition=final_check[0]
                    )
                else:
                    logger.error(
                        "heavy_index_creation_failed_verification",
                        context="server_startup",
                        index_name=index_name,
                        status="invalid_or_missing"
                    )
            except Exception as e:
                logger.error(
                    "heavy_index_creation_failed",
                    context="server_startup",
                    index_name=index_name,
                    error=str(e),
                )


async def ensure_vector_index() -> None:
    """
    langchain_pg_embedding.embedding 컬럼 타입을 보정하고 HNSW 인덱스를 생성한다.

    langchain-postgres는 embedding 컬럼을 차원 없는 vector로 생성한다.
    HNSW 인덱스는 차원 정보를 필요로 하므로 컬럼이 vector(N)이 아닌 경우 ALTER한다.
    컬럼이 이미 vector(N)이면 no-op.

    CREATE INDEX CONCURRENTLY는 트랜잭션 블록 내에서 실행 불가하므로
    autocommit=True 커넥션을 별도로 생성한다.
    """
    conn_string = settings.sqlalchemy_database_url.replace("+psycopg", "")
    index_name = "idx_embedding_hnsw_v2"
    try:
        async with await psycopg.AsyncConnection.connect(
            conn_string, autocommit=True
        ) as conn:
            # embedding 컬럼이 차원 없는 vector이면 vector(N)으로 ALTER (idempotent)
            col_row = await (await conn.execute("""
                SELECT pg_catalog.format_type(a.atttypid, a.atttypmod)
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                WHERE c.relname = 'langchain_pg_embedding'
                  AND a.attname = 'embedding'
            """)).fetchone()

            if col_row and col_row[0] == 'vector':
                logger.info(
                    "embedding_column_type_altering",
                    context="server_startup",
                    from_type="vector",
                    to_type=f"vector({settings.PGVECTOR_EMBEDDING_DIMENSIONS})",
                )
                await conn.execute(f"""
                    ALTER TABLE langchain_pg_embedding
                    ALTER COLUMN embedding TYPE vector({settings.PGVECTOR_EMBEDDING_DIMENSIONS})
                """)
                logger.info(
                    "embedding_column_type_altered",
                    context="server_startup",
                )

            # 중단된 CONCURRENTLY 빌드가 남긴 INVALID 인덱스 처리
            row = await (await conn.execute(f"""
                SELECT indisvalid FROM pg_index
                JOIN pg_class ON pg_index.indexrelid = pg_class.oid
                WHERE relname = '{index_name}'
            """)).fetchone()

            if row is not None and not row[0]:
                logger.warning(
                    "vector_index_invalid_dropping",
                    context="server_startup",
                    index_name=index_name,
                )
                await conn.execute(
                    f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}"
                )

            logger.info(
                "vector_index_creation_started",
                context="server_startup",
                index_name=index_name,
            )
            await conn.execute(f"""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name}
                ON langchain_pg_embedding
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 128)
            """)
            
            # 최종 상태 및 파라미터 재검증
            final_check = await (await conn.execute(f"""
                SELECT pg_get_indexdef(pg_class.oid), pg_index.indisvalid 
                FROM pg_class 
                JOIN pg_index ON pg_class.oid = pg_index.indexrelid
                WHERE relname = '{index_name}'
            """)).fetchone()

            if final_check and final_check[1]:
                logger.info(
                    "vector_index_creation_completed",
                    context="server_startup",
                    index_name=index_name,
                    status="valid",
                    index_definition=final_check[0]
                )
            else:
                logger.error(
                    "vector_index_creation_failed_verification",
                    context="server_startup",
                    index_name=index_name,
                    status="invalid_or_missing"
                )

            # HNSW 인덱스가 실제 쿼리에서 사용되는지 검증
            await conn.execute("SET enable_seqscan = off")
            explain_rows = await (await conn.execute(f"""
                EXPLAIN (ANALYZE, FORMAT TEXT)
                SELECT id FROM langchain_pg_embedding
                ORDER BY embedding <=> (array_fill(0, ARRAY[{settings.PGVECTOR_EMBEDDING_DIMENSIONS}])::vector)
                LIMIT 10
            """)).fetchall()
            plan_text = "\n".join(row[0] for row in explain_rows)
            uses_hnsw = index_name in plan_text
            if uses_hnsw:
                logger.info(
                    "vector_index_usage_verified",
                    context="server_startup",
                    index_name=index_name,
                )
            else:
                logger.error(
                    "vector_index_usage_not_verified",
                    context="server_startup",
                    index_name=index_name,
                    plan=plan_text[:500],
                )

    except Exception as e:
        logger.error(
            "vector_index_creation_failed",
            context="server_startup",
            index_name=index_name,
            error=str(e),
        )