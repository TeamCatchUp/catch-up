import psycopg

from catchup.configs.config import settings


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