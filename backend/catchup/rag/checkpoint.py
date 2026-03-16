from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import structlog
from catchup.configs.config import settings

logger = structlog.get_logger(__name__)

_checkpointer = None
_pool = None

async def init_langgraph_checkpointer():
    global _checkpointer, _pool
    
    logger.info(
        "checkpointer_init_started",
        context="checkpointer_initialization",
    )
    
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
        
        logger.info(
            "checkpointer_init_success",
            context="checkpointer_initialization",
        )
        return _checkpointer
        
    except Exception as e:
        logger.error(
            "checkpointer_init_failed",
            context="checkpointer_initialization",
            error=str(e),
        )
        if _pool:
            await _pool.close()
        raise


async def close_langgraph_checkpointer():
    global _checkpointer, _pool
    if _pool:
        await _pool.close()
        _pool = None
        _checkpointer = None
        logger.info(
            "checkpointer_pool_closed",
            context="checkpointer_shutdown",
        )


def get_langgraph_checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None:
        raise RuntimeError("LangGraph checkpointer is not initialized")
    return _checkpointer