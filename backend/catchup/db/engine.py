import logging

from sqlalchemy import create_engine
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

SessionLocal = sessionmaker(bind=engine)
