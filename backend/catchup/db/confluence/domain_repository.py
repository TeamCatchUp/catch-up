from datetime import datetime, timezone

from sqlalchemy import select, delete, func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from catchup.db.models import ConfluenceSpace, ConfluenceUser


def _user_email_update_value(stmt):
    return func.coalesce(stmt.excluded.email, ConfluenceUser.email)

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
    db.flush()

    return len(spaces)

def sync_spaces_snapshot(
    db: Session,
    cloud_id: str,
    spaces: list[dict],
) -> dict[str, int]:
    """
    Cloud 단위 Space 스냅샷 동기화
    """
    now = datetime.now(timezone.utc)

    if not spaces:
        delete_stmt = delete(ConfluenceSpace).where(ConfluenceSpace.cloud_id == cloud_id)
        delete_result = db.execute(delete_stmt)
        db.flush()
        return {
            "upserted": 0,
            "deleted": delete_result.rowcount or 0,
        }

    normalized_spaces: list[dict] = []
    fetched_space_ids: list[str] = []

    for space in spaces:
        space_id = space.get("space_id")
        if not space_id:
            continue

        normalized_spaces.append(
            {
                "cloud_id": cloud_id,
                "space_id": space_id,
                "space_key": space.get("space_key", ""),
                "space_name": space.get("space_name", ""),
                "space_type": space.get("space_type", "global"),
                "status": space.get("status", "current"),
                "homepage_id": space.get("homepage_id"),
                "description": space.get("description"),
                "synced_at": now,
            }
        )
        fetched_space_ids.append(space_id)

    if not normalized_spaces:
        delete_stmt = delete(ConfluenceSpace).where(ConfluenceSpace.cloud_id == cloud_id)
        delete_result = db.execute(delete_stmt)
        db.flush()
        return {
            "upserted": 0,
            "deleted": delete_result.rowcount or 0,
        }

    upsert_stmt = insert(ConfluenceSpace).values(normalized_spaces)
    upsert_stmt = upsert_stmt.on_conflict_do_update(
        index_elements=["cloud_id", "space_id"],
        set_={
            "space_key": upsert_stmt.excluded.space_key,
            "space_name": upsert_stmt.excluded.space_name,
            "space_type": upsert_stmt.excluded.space_type,
            "status": upsert_stmt.excluded.status,
            "homepage_id": upsert_stmt.excluded.homepage_id,
            "description": upsert_stmt.excluded.description,
            "synced_at": upsert_stmt.excluded.synced_at,
        },
    )
    db.execute(upsert_stmt)

    stale_delete_stmt = delete(ConfluenceSpace).where(
        ConfluenceSpace.cloud_id == cloud_id,
        ~ConfluenceSpace.space_id.in_(fetched_space_ids),
    )
    stale_delete_result = db.execute(stale_delete_stmt)

    db.flush()

    return {
        "upserted": len(normalized_spaces),
        "deleted": stale_delete_result.rowcount or 0,
    }

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
    db.flush()
    return result.rowcount

def delete_spaces_by_cloud_id(db: Session, cloud_id: str) -> int:
    stmt = delete(ConfluenceSpace).where(ConfluenceSpace.cloud_id == cloud_id)
    result = db.execute(stmt)
    db.flush()
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

def upsert_users_bulk(
    db: Session,
    users: list[dict],
) -> int:
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
            "email": _user_email_update_value(stmt),
            "time_zone": stmt.excluded.time_zone,
            "locale": stmt.excluded.locale,
            "avatar_url": stmt.excluded.avatar_url,
            "is_external_collaborator": stmt.excluded.is_external_collaborator,
            "synced_at": stmt.excluded.synced_at,
        },
    )
    db.execute(stmt)
    db.flush()
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
    db.flush()
    return result.rowcount
