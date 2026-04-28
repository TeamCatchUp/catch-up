import logging

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.sqlalchemy_database_url,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
)


@event.listens_for(engine, "connect")
def set_pg_bigm_limit(dbapi_connection, connection_record):
    """
    pg_bigm 유사도 검색 임계값을 커넥션 수립 시점에 설정한다.
    매 쿼리마다 SET LOCAL을 실행하는 오버헤드를 방지한다.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SET pg_bigm.similarity_limit = 0.02")
    except Exception as e:
        logger.warning(f"Failed to set pg_bigm.similarity_limit: {e}")
    finally:
        cursor.close()


SessionLocal = sessionmaker(bind=engine)
