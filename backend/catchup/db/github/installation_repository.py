from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.connectors.github.schemas import InstallationWebhookPayload
from catchup.db.models import GithubInstallation


def get_installation_info_by_id(db: Session, id: int) -> Optional[GithubInstallation]:
    """내부 ID로 Installation 조회"""
    stmt = select(GithubInstallation).where(GithubInstallation.id == id)
    return db.execute(stmt).scalar_one_or_none()


def get_installation_by_installation_id(db: Session, installation_id: int) -> Optional[GithubInstallation]:
    """GitHub Installation ID로 조회 (Webhook, API에서 사용)"""
    stmt = select(GithubInstallation).where(GithubInstallation.installation_id == installation_id)
    return db.execute(stmt).scalar_one_or_none()


def get_all_installations(db: Session) -> list[GithubInstallation]:
    stmt = select(GithubInstallation).order_by(GithubInstallation.created_at.desc())
    return list(db.execute(stmt).scalars().all())

def create_installation(
        db: Session,
        payload: InstallationWebhookPayload) -> GithubInstallation:
    installation = GithubInstallation.from_webhook_payload(payload)
    db.add(installation)
    db.commit()
    db.refresh(installation)
    return installation

def update_installation_suspended(
        db: Session,
        installation_id: int,
        suspended_at: Optional[datetime]) -> Optional[GithubInstallation]:
    """
    Installation 일시 중지 상태 업데이트 (GitHub installation_id 사용)
    """
    installation = get_installation_by_installation_id(db, installation_id)
    if installation:
        installation.suspended_at = suspended_at
        db.commit()
        db.refresh(installation)
    return installation


def delete_installation(
        db: Session,
        id: int) -> bool:
    """
    내부 ID로 Installation 삭제
    """
    installation = get_installation_info_by_id(db, id)
    if installation:
        db.delete(installation)
        db.commit()
        return True
    return False


def delete_installation_by_installation_id(
        db: Session,
        installation_id: int) -> bool:
    """
    GitHub Installation ID로 삭제 (Webhook에서 사용)
    """
    installation = get_installation_by_installation_id(db, installation_id)
    if installation:
        db.delete(installation)
        db.commit()
        return True
    return False
