"""
Atlassian OAuth Token Repository

atlassian_oauth_tokens 테이블에 대한 CRUD 함수.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from catchup.db.models import AtlassianOAuthToken

def get_token_by_cloud_id(db: Session, cloud_id: str) -> Optional[AtlassianOAuthToken]:
    """cloud_id로 Atlassian OAuth 토큰 조회."""
    stmt = select(AtlassianOAuthToken).where(AtlassianOAuthToken.cloud_id == cloud_id)
    return db.execute(stmt).scalar_one_or_none()


def get_all_tokens(db: Session) -> list[AtlassianOAuthToken]:
    """모든 Atlassian OAuth 토큰 조회 (최신순)."""
    stmt = select(AtlassianOAuthToken).order_by(AtlassianOAuthToken.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def create_or_update_token(
    db: Session,
    atlassian_account_id: str,
    cloud_id: str,
    site_name: str,
    site_url: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
    scopes: str,
) -> AtlassianOAuthToken:
    """Atlassian OAuth 토큰 생성 또는 업데이트."""
    existing = get_token_by_cloud_id(db, cloud_id)

    if existing:
        existing.atlassian_account_id = atlassian_account_id
        existing.site_name = site_name
        existing.site_url = site_url
        existing.access_token = access_token
        existing.refresh_token = refresh_token
        existing.expires_at = expires_at
        existing.scopes = scopes
        db.commit()
        db.refresh(existing)
        return existing

    new_token = AtlassianOAuthToken(
        atlassian_account_id=atlassian_account_id,
        cloud_id=cloud_id,
        site_name=site_name,
        site_url=site_url,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        scopes=scopes,
    )
    db.add(new_token)
    db.commit()
    db.refresh(new_token)
    return new_token


def delete_token(db: Session, cloud_id: str) -> bool:
    """cloud_id로 Atlassian OAuth 토큰 삭제."""
    stmt = delete(AtlassianOAuthToken).where(AtlassianOAuthToken.cloud_id == cloud_id)
    result = db.execute(stmt)
    db.commit()
    return result.rowcount > 0


# ──────────────────────────────────────────
# 클래스 래퍼 (FastAPI DI용)
# ──────────────────────────────────────────

class AtlassianOAuthRepository:
    
    def get_token_by_cloud_id(
        self, db: Session, cloud_id: str
    ) -> Optional[AtlassianOAuthToken]:
        return get_token_by_cloud_id(db, cloud_id)

    def get_all_tokens(self, db: Session) -> list[AtlassianOAuthToken]:
        return get_all_tokens(db)

    def create_or_update_token(
        self,
        db: Session,
        atlassian_account_id: str,
        cloud_id: str,
        site_name: str,
        site_url: str,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
        scopes: str,
    ) -> AtlassianOAuthToken:
        return create_or_update_token(
            db=db,
            atlassian_account_id=atlassian_account_id,
            cloud_id=cloud_id,
            site_name=site_name,
            site_url=site_url,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            scopes=scopes,
        )

    def delete_token(self, db: Session, cloud_id: str) -> bool:
        return delete_token(db, cloud_id)