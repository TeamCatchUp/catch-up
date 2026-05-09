"""
Jira Dynamic Webhook 상태 저장소
"""

from datetime import datetime
from datetime import timezone

from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from catchup.db.models import JiraWebhookSubscription


def _encode_events(events: list[str] | None) -> str | None:
    if not events:
        return None
    normalized = sorted({event for event in events if event})
    return ",".join(normalized) if normalized else None


def _decode_events(events_csv: str | None) -> list[str]:
    if not events_csv:
        return []
    return [event for event in events_csv.split(",") if event]


def get_webhook(
    db: Session,
    cloud_id: str,
    webhook_id: int,
) -> JiraWebhookSubscription | None:
    stmt = select(JiraWebhookSubscription).where(
        JiraWebhookSubscription.cloud_id == cloud_id,
        JiraWebhookSubscription.webhook_id == webhook_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_webhooks_by_cloud_id(
    db: Session,
    cloud_id: str,
) -> list[JiraWebhookSubscription]:
    stmt = (
        select(JiraWebhookSubscription)
        .where(JiraWebhookSubscription.cloud_id == cloud_id)
        .order_by(JiraWebhookSubscription.webhook_id.asc())
    )
    return list(db.execute(stmt).scalars().all())


def upsert_webhook(
    db: Session,
    cloud_id: str,
    webhook_id: int,
    callback_url: str,
    jql_filter: str | None,
    events: list[str] | None,
    expires_at: datetime | None,
    last_synced_at: datetime | None = None,
) -> JiraWebhookSubscription:
    encoded_events = _encode_events(events)

    stmt = (
        insert(JiraWebhookSubscription)
        .values(
            cloud_id=cloud_id,
            webhook_id=webhook_id,
            callback_url=callback_url,
            jql_filter=jql_filter,
            events_csv=encoded_events,
            expires_at=expires_at,
            last_synced_at=last_synced_at,
        )
        .on_conflict_do_update(
            constraint="uq_jira_webhook_subscriptions_cloud_webhook",
            set_={
                "callback_url": callback_url,
                "jql_filter": jql_filter,
                "events_csv": encoded_events,
                "expires_at": expires_at,
                "last_synced_at": last_synced_at,
                "updated_at": func.now(),
            },
        )
    )
    db.execute(stmt)
    db.flush()
    subscription = get_webhook(db, cloud_id, webhook_id)
    if subscription is None:
        raise RuntimeError("jira webhook upsert did not return a persisted subscription")
    return subscription


def update_webhook_expiration(
    db: Session,
    cloud_id: str,
    webhook_ids: list[int],
    expires_at: datetime | None,
) -> int:
    if not webhook_ids:
        return 0

    subscriptions = (
        db.execute(
            select(JiraWebhookSubscription).where(
                JiraWebhookSubscription.cloud_id == cloud_id,
                JiraWebhookSubscription.webhook_id.in_(webhook_ids),
            )
        )
        .scalars()
        .all()
    )

    now = datetime.now(timezone.utc)
    for subscription in subscriptions:
        subscription.expires_at = expires_at
        subscription.last_synced_at = now

    return len(subscriptions)


def get_expiring_webhooks(
    db: Session,
    cloud_id: str,
    before: datetime,
) -> list[JiraWebhookSubscription]:
    stmt = select(JiraWebhookSubscription).where(
        JiraWebhookSubscription.cloud_id == cloud_id,
        or_(
            JiraWebhookSubscription.expires_at.is_(None),
            JiraWebhookSubscription.expires_at <= before,
        ),
    )
    return list(db.execute(stmt).scalars().all())


def delete_webhooks_not_in_ids(
    db: Session,
    cloud_id: str,
    webhook_ids: list[int],
) -> int:
    stmt = delete(JiraWebhookSubscription).where(
        JiraWebhookSubscription.cloud_id == cloud_id,
    )
    if webhook_ids:
        stmt = stmt.where(~JiraWebhookSubscription.webhook_id.in_(webhook_ids))

    result = db.execute(stmt)
    return result.rowcount


def get_webhook_events(subscription: JiraWebhookSubscription) -> list[str]:
    return _decode_events(subscription.events_csv)
