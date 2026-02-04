from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings

engine = create_engine(settings.sqlalchemy_database_url)

SessionLocal = sessionmaker(bind=engine)
