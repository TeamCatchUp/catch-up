from datetime import datetime
from gettext import install
from re import S
from typing import Optional

from catchup.auth.github.schemas import InstallationWebhookPayload
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.db.models import GithubInstallation

def get_installation_info_by_id(db: Session, installation_id: int) -> Optional[GithubInstallation]:
    stmt = select(GithubInstallation).where(GithubInstallation.id == installation_id)
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
    Installation 일시 중지 상태 업데이트
    """
    installation = get_installation_info_by_id(db, installation_id)
    if installation:
        installation.suspended_at = suspended_at
        db.commit()
        db.refresh(installation)
    return installation

def delete_installation(
        db: Session,
        installation_id: int) -> bool:
    """
    Installation 삭제
    """
    installation = get_installation_info_by_id(db, installation_id)
    if installation:
        db.delete(installation)
        db.commit()
        return True
    return False
