import structlog
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg_pool import AsyncConnectionPool

from catchup.configs.config import settings

logger = structlog.get_logger(__name__)

# langgraph-checkpoint v4 보안 정책으로 인해
# AgentState 내 커스텀 타입을 allowlist 등록해야 함.
_ALLOWED_MSGPACK_MODULES: list[tuple[str, str]] = [
    ("catchup.schemas.sources", "SourceType"),
    ("catchup.schemas.sources", "EntityType"),
    ("catchup.schemas.sources", "ConfluenceSource"),
    ("catchup.schemas.sources", "SlackSource"),
    ("catchup.schemas.sources", "GithubSource"),
    ("catchup.schemas.sources", "JiraSource"),
    ("catchup.schemas.sources", "ChannelTalkSource"),
    ("catchup.schemas.context", "GlobalContext"),
    ("catchup.schemas.structures", "VectorDbSearchQuery"),
    ("catchup.schemas.structures", "ManualSearchQuery"),
    ("catchup.search.planner.state", "CachedSearch"),
    ("catchup.schemas.structures", "PipelinePlan"),
    ("catchup.schemas.structures", "SearchStep"),
    ("catchup.schemas.structures", "SearchPlan"),
    ("catchup.schemas.structures", "SearchTurnMeta"),
    ("catchup.schemas.prompt_settings", "PromptSettings"),
    ("catchup.db.models", "SourceType"),
]

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

        serde = JsonPlusSerializer(allowed_msgpack_modules=_ALLOWED_MSGPACK_MODULES)
        _checkpointer = AsyncPostgresSaver(conn=_pool, serde=serde)
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
