from datetime import datetime
from datetime import time
from datetime import timedelta

from sqlalchemy import and_
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.db.models import ManualSearchHistory


def save_search_query(
    db: Session,
    user_id: int,
    query: str,
) -> ManualSearchHistory:
    record = ManualSearchHistory(user_id=user_id, query=query)
    db.add(record)
    return record


def get_search_queries_by_user(
    db: Session,
    user_id: int,
    period: str = "all",
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[ManualSearchHistory], int]:
    filters = [ManualSearchHistory.user_id == user_id]

    if period == "today":
        filters.append(
            ManualSearchHistory.created_at
            >= datetime.combine(datetime.now().date(), time.min)
        )
    elif period == "7d":
        filters.append(
            ManualSearchHistory.created_at >= datetime.now() - timedelta(days=7)
        )

    condition = and_(*filters)

    total_count = (
        db.scalar(
            select(func.count())
            .select_from(ManualSearchHistory)
            .where(condition)
        )
        or 0
    )

    stmt = (
        select(ManualSearchHistory)
        .where(condition)
        .order_by(ManualSearchHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    items = db.scalars(stmt).all()

    return list(items), total_count
