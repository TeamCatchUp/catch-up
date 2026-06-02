from datetime import datetime

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.db.models import SlackOAuthToken


def get_slack_token_by_team_id(
    db: Session, team_id: str
) -> SlackOAuthToken | None:
    """Team ID로 Token 조회"""
    stmt = select(SlackOAuthToken).where(SlackOAuthToken.team_id == team_id)
    return db.execute(stmt).scalar_one_or_none()


def get_slack_token_by_id(
    db: Session,
    credential_id: int,
) -> SlackOAuthToken | None:
    """Credential row ID로 Token 조회"""
    return db.get(SlackOAuthToken, credential_id)


def get_all_slack_tokens(db: Session) -> list[SlackOAuthToken]:
    """모든 Slack Token 조회"""
    stmt = select(SlackOAuthToken).order_by(SlackOAuthToken.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def create_or_update_slack_token(
    db: Session,
    team_id: str,
    team_name: str | None,
    bot_user_id: str,
    bot_access_token: str,
    bot_scopes: str,
    authed_user_id: str | None = None,
    bot_refresh_token: str | None = None,
    bot_token_expires_at: datetime | None = None,
    incoming_webhook_url: str | None = None,
    incoming_webhook_channel: str | None = None,
) -> SlackOAuthToken:
    token_data = {
        "team_id": team_id,
        "team_name": team_name,
        "bot_user_id": bot_user_id,
        "bot_access_token": bot_access_token,
        "bot_scopes": bot_scopes,
        "authed_user_id": authed_user_id,
        "bot_refresh_token": bot_refresh_token,
        "bot_token_expires_at": bot_token_expires_at,
        "incoming_webhook_url": incoming_webhook_url,
        "incoming_webhook_channel": incoming_webhook_channel,
    }

    existing = get_slack_token_by_team_id(db, team_id)

    if existing:
        for key, value in token_data.items():
            if key != "team_id":
                setattr(existing, key, value)
        db.flush()
        return existing

    new_token = SlackOAuthToken(**token_data)
    db.add(new_token)
    db.flush()
    return new_token


def delete_slack_token(db: Session, team_id: str) -> bool:
    stmt = delete(SlackOAuthToken).where(SlackOAuthToken.team_id == team_id)
    result = db.execute(stmt)
    return result.rowcount > 0
