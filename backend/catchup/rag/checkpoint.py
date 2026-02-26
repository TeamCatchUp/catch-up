import logging
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from catchup.configs.config import settings

logger = logging.getLogger(__name__)

_checkpointer = None
_pool = None

async def init_langgraph_checkpointer():
    global _checkpointer, _pool
    
    logger.info("[DB][CHECKPOINTER][INIT] Initializing Async Postgres checkpointer")
    
    try:
        conn_string = settings.sqlalchemy_database_url.replace("+psycopg", "")
        
        _pool = AsyncConnectionPool(
            conn_string,
            min_size=2,
            max_size=10,
            kwargs={"autocommit": True},
            open=False,
        )
        await _pool.open()
        
        _checkpointer = AsyncPostgresSaver(conn=_pool)
        await _checkpointer.setup()
        
        logger.info("[DB][CHECKPOINTER][INIT] Async Postgres checkpointer initialized successfully")
        return _checkpointer
        
    except Exception as e:
        logger.error(f"[DB][CHECKPOINTER][INIT] Failed: {str(e)}")
        if _pool:
            await _pool.close()
        raise


async def close_langgraph_checkpointer():
    global _checkpointer, _pool
    if _pool:
        await _pool.close()
        _pool = None
        _checkpointer = None
        logger.info("[DB][CHECKPOINTER][CLOSE] Connection pool closed")


def get_langgraph_checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None:
        raise RuntimeError("LangGraph checkpointer is not initialized")
    return _checkpointer