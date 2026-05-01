import logging

from sqlalchemy import create_engine
from sqlalchemy import event
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
def set_session_params(dbapi_connection, connection_record):
    """
    pg_bigm 유사도 임계값과 HNSW ef_search를 커넥션 수립 시점에 설정한다.
    매 쿼리마다 SET LOCAL을 실행하는 오버헤드를 방지하고,
    set_config(...)를 단일 SELECT로 묶어 RTT를 1회로 유지한다.

    hnsw.ef_search=200: hybrid_search가 k=100을 요청하므로 ef_search >= k 보장 필요.
    측정상 ef_search=40에서 K=100 recall이 0.4로 깨지고, 200에서 0.99+로 수렴.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute(
            "SELECT set_config('pg_bigm.similarity_limit', '0.02', false), "
            "       set_config('hnsw.ef_search', '200', false)"
        )
    except Exception as e:
        logger.warning(f"Failed to set session params: {e}")
    finally:
        cursor.close()


SessionLocal = sessionmaker(bind=engine)
