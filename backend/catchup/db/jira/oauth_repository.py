from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from catchup.db.models import JiraOAuthToken

def get_jira_token_by_cloud_id(db:Session, cloud_id:str) -> Optional[JiraOAuthToken]:
    stmt = select(JiraOAuthToken).where(JiraOAuthToken.cloud_id == cloud_id)
    return db.execute(stmt).scalar_one_or_none()

def get_all_jira_tokens(db: Session) -> list[JiraOAuthToken]:
    stmt = select(JiraOAuthToken).order_by(JiraOAuthToken.created_at.desc())
    return list(db.execute(stmt).scalars().all())

# TODO : 파라미터 -> 스키마
def create_or_update_jira_token(
    db: Session,
    atlassian_account_id: str,
    cloud_id: str,
    site_name: str,
    site_url: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
    scopes: str,
) -> JiraOAuthToken:
    existing = get_jira_token_by_cloud_id(db, cloud_id)

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

    new_token = JiraOAuthToken(
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


def delete_jira_token(db: Session, cloud_id: str) -> bool:
    stmt = delete(JiraOAuthToken).where(JiraOAuthToken.cloud_id == cloud_id)
    result = db.execute(stmt)
    db.commit()
    return result.rowcount > 0