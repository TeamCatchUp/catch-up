from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from catchup.configs.config import settings

_sync_url = make_url(settings.sqlalchemy_database_url)
_async_url = _sync_url.set(drivername="postgresql+psycopg_async")

# engine.py의 `connect` 이벤트에서 설정하는 세션 파라미터를 connect_args로 대체한다.
# psycopg3 async cursor는 SQLAlchemy 이벤트 핸들러 내에서 동기 호출이 불가능하므로
# connect_args를 통해 커넥션 수립 시점에 동일하게 적용한다.
async_engine = create_async_engine(
    _async_url,
    pool_size=settings.DB_ASYNC_POOL_SIZE,
    max_overflow=settings.DB_ASYNC_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    connect_args={
        "options": "-c pg_bigm.similarity_limit=0.17"
    },
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
