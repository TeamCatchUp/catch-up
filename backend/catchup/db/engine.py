import logging
from sqlalchemy import create_engine, make_url
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(settings.sqlalchemy_database_url)

SessionLocal = sessionmaker(bind=engine)
