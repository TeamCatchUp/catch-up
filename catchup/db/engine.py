from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings

engine = create_engine(
    f"{settings.DB_DIALECT}+{settings.DB_DRIVER}://"
    f"{settings.DB_USERNAME}:{settings.DB_PASSWORD}@"
    f"{settings.DB_HOST}:{settings.DB_PORT}/"
    f"{settings.DB_DATABASE}"
)

SessionLocal = sessionmaker(bind=engine)
