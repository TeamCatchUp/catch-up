from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from catchup.db.models import Company, PreMappingBuffer


def has_admin_ever_onboarded(db: Session) -> bool:
    stmt = select(
        exists()
        .where(Company.id.isnot(None))
    )
    
    return bool(db.scalar(stmt))


def has_csv_file_ever_been_uploaded(db: Session) -> bool:
    stmt = select(
        exists()
        .where(PreMappingBuffer.id.isnot(None))
    )

    return bool(db.scalar(stmt))