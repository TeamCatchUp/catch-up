from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from catchup.db.models import ConfluenceSpace, ConfluenceUser

def upsert_spaces_bulk(db:Session, spaces: list[dict]) -> int:
    if not spaces:
        return 0
    
    now = datetime.now(timezone.utc)
    for space in spaces:
        space["synced_at"] = now

    stmt = insert(ConfluenceSpace).values(spaces)
    stmt = stmt.on_conflict_do_update(
        index_elements=["cloud_id", "space_id"],
        set_ = {
            "space_key": stmt.excluded.space_key,
            "space_name": stmt.excluded.space_name,\
            "space_type": stmt.excluded.space_type,
            "status": stmt.excluded.status,
            "homepage_id": stmt.excluded.homepage_id,
            "description": stmt.excluded.description,
            "synced_at": stmt.excluded.synced_at,
        }
    )
    db.execute(stmt)
    db.commit()

    return len(spaces)

def get_spaces_by_cloud_id(db:Session, cloud_id: str)-> list[ConfluenceSpace]:
    stmt = (
        select(ConfluenceSpace)
        .where(ConfluenceSpace.cloud_id == cloud_id)
        .order_by(ConfluenceSpace.space_key)
    )
    return list(db.execute(stmt).scalars().all())

def get_space_by_id(
    db: Session, cloud_id: str, space_id: str
) -> ConfluenceSpace | None:
    stmt = select(ConfluenceSpace).where(
        ConfluenceSpace.cloud_id == cloud_id,
        ConfluenceSpace.space_id == space_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def delete_space(db:Session, cloud_id: str, space_id: str) -> int:
    stmt = delete(ConfluenceSpace).where(
        ConfluenceSpace.cloud_id == cloud_id,
        ConfluenceSpace.space_id == space_id,

    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount

def delete_spaces_by_cloud_id(db: Session, cloud_id: str) -> int:
    stmt = delete(ConfluenceSpace).where(ConfluenceSpace.cloud_id == cloud_id)
    result = db.execute(stmt)
    db.commit()
    return result.rowcount

def get_space_id_map(
        db: Session, cloud_id: str, space_keys: list[str],
) -> dict[str, str]:
    stmt = select(
        ConfluenceSpace.space_key, ConfluenceSpace.space_id,
    ).where(
        ConfluenceSpace.cloud_id == cloud_id,
        ConfluenceSpace.space_key.in_(space_keys)
    )
    return dict(db.execute(stmt).all())


def get_space_name_map(
        db: Session, cloud_id: str, space_keys: list[str],
) -> dict[str, str | None]:
    """space_key → space_name 매핑 반환 (Full Sync에서 캐싱용)."""
    stmt = select(
        ConfluenceSpace.space_key, ConfluenceSpace.space_name,
    ).where(
        ConfluenceSpace.cloud_id == cloud_id,
        ConfluenceSpace.space_key.in_(space_keys)
    )
    return dict(db.execute(stmt).all())


# ------------------------------------------------------------
# Confluence Users
# ------------------------------------------------------------

def upsert_users_bulk(db: Session, users: list[dict]) -> int:
    if not users:
        return 0

    now = datetime.now(timezone.utc)
    for user in users:
        user["synced_at"] = now

    stmt = insert(ConfluenceUser).values(users)
    stmt = stmt.on_conflict_do_update(
        index_elements=["cloud_id", "account_id"],
        set_={
            "account_type": stmt.excluded.account_type,
            "display_name": stmt.excluded.display_name,
            "public_name": stmt.excluded.public_name,
            "email": stmt.excluded.email,
            "time_zone": stmt.excluded.time_zone,
            "locale": stmt.excluded.locale,
            "avatar_url": stmt.excluded.avatar_url,
            "is_external_collaborator": stmt.excluded.is_external_collaborator,
            "synced_at": stmt.excluded.synced_at,
        },
    )
    db.execute(stmt)
    db.commit()
    return len(users)


def get_users_by_cloud_id(db: Session, cloud_id: str) -> list[ConfluenceUser]:
    stmt = (
        select(ConfluenceUser)
        .where(ConfluenceUser.cloud_id == cloud_id)
        .order_by(ConfluenceUser.display_name)
    )
    return list(db.execute(stmt).scalars().all())


def delete_users_by_cloud_id(db: Session, cloud_id: str) -> int:
    stmt = delete(ConfluenceUser).where(ConfluenceUser.cloud_id == cloud_id)
    result = db.execute(stmt)
    db.commit()
    return result.rowcount
