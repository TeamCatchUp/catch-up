"""
Jira Dynamic Webhook 관리 서비스

- Jira API에 webhook 등록/갱신
- DB에 webhook ID/만료 시각 상태 저장
"""

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy.orm import Session

from catchup.audit.enums import AuditEventStatus, AuditLevel
from catchup.audit.metadata import IntegrationAuditMetadata
from catchup.audit.service import emit_audit_event
from catchup.configs.config import settings
from catchup.connectors.atlassian.exceptions import (
    AtlassianTokenExpiredError,
    AtlassianTokenNotFoundError,
)
from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.connectors.jira.client import JiraApiClient
from catchup.db.atlassian import oauth_repository as atlassian_oauth
from catchup.db.jira import webhook_repository as jira_webhook
from catchup.db.jira import domain_repository as jira_domain
from catchup.events.enums import EventType, IntegrationEventAction

logger = logging.getLogger(__name__)


DEFAULT_JIRA_WEBHOOK_EVENTS = [
    "jira:issue_created",
    "jira:issue_updated",
    "jira:issue_deleted",
    "comment_created",
    "comment_updated",
    "comment_deleted",
]


class JiraDynamicWebhookService:
    async def _create_client(self, db: Session, cloud_id: str) -> JiraApiClient:
        token_manager = AtlassianTokenManager(
            oauth_client=AtlassianOAuthClient(),
            oauth_repository=atlassian_oauth,
        )
        try:
            access_token = await token_manager.resolve_access_token_by_cloud_id(db, cloud_id)
        except AtlassianTokenNotFoundError:
            raise HTTPException(status_code=404, detail=f"Jira token not found: {cloud_id}")
        except AtlassianTokenExpiredError:
            raise HTTPException(status_code=401, detail=f"Jira token expired: {cloud_id}")
        return JiraApiClient(cloud_id=cloud_id, access_token=access_token)

    def _build_callback_url(self, cloud_id: str) -> str:
        configured_base_url = settings.ATLASSIAN_WEBHOOK_CALLBACK_BASE_URL.strip()

        if configured_base_url:
            base_url = configured_base_url.rstrip("/")
        else:
            parsed = urlparse(settings.ATLASSIAN_REDIRECT_URI)
            if not parsed.scheme or not parsed.netloc:
                raise RuntimeError(
                    "Invalid ATLASSIAN_REDIRECT_URI for webhook callback URL fallback"
                )
            base_url = f"{parsed.scheme}://{parsed.netloc}"

        return f"{base_url}/api/v1/jira/webhooks/{cloud_id}"

    def _resolve_project_keys(
        self,
        db: Session,
        cloud_id: str,
        project_keys: list[str] | None,
    ) -> list[str]:
        # 1) 로컬 메타데이터(jira_projects) 기준으로 허용 가능한 프로젝트 키 확보
        stored_projects = jira_domain.get_projects_by_cloud_id(db, cloud_id)
        stored_project_keys = sorted(
            {
                project.project_key.strip()
                for project in stored_projects
                if project.project_key and project.project_key.strip()
            }
        )
        if not stored_project_keys:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No projects found in jira_projects. "
                    "Run Jira metadata sync before dynamic webhook registration."
                ),
            )

        # 2) project_keys 미지정이면 jira_projects 전체를 webhook JQL 대상으로 사용
        if project_keys is None:
            return stored_project_keys

        # 3) project_keys가 지정된 경우, jira_projects에 존재하는 키만 허용
        normalized_keys = sorted(
            {
                project_key.strip()
                for project_key in project_keys
                if project_key and project_key.strip()
            }
        )
        if not normalized_keys:
            raise HTTPException(
                status_code=400,
                detail="project_keys is empty",
            )

        allowed_key_set = set(stored_project_keys)
        invalid_keys = sorted(
            project_key for project_key in normalized_keys if project_key not in allowed_key_set
        )
        if invalid_keys:
            raise HTTPException(
                status_code=400,
                detail=(
                    "project_keys must exist in jira_projects for this cloud_id. "
                    f"invalid_keys={invalid_keys}"
                ),
            )

        return normalized_keys

    def _build_jql_filter(self, project_keys: list[str]) -> str:
        # Jira Dynamic Webhook JQL에서 project 필드는 IN 연산으로 등록
        quoted_keys = ", ".join(f'"{project_key}"' for project_key in project_keys)
        return f"project IN ({quoted_keys})"

    async def sync_webhook_state(self, db: Session, cloud_id: str) -> list:
        """
        Jira API 상태를 DB에 동기화
        """
        client = await self._create_client(db, cloud_id)
        callback_url = self._build_callback_url(cloud_id)

        webhooks = await client.list_all_dynamic_webhooks()
        own_webhooks = [
            webhook for webhook in webhooks
            if webhook.get("url") == callback_url
        ]

        now = datetime.now(timezone.utc)
        observed_webhook_ids: list[int] = []

        for webhook in own_webhooks:
            webhook_id = webhook.get("id")
            if webhook_id is None:
                continue

            webhook_id = int(webhook_id)
            observed_webhook_ids.append(webhook_id)

            jira_webhook.upsert_webhook(
                db=db,
                cloud_id=cloud_id,
                webhook_id=webhook_id,
                callback_url=callback_url,
                jql_filter=webhook.get("jqlFilter"),
                events=webhook.get("events") or [],
                expires_at=parse_atlassian_datetime(webhook.get("expirationDate")),
                last_synced_at=now,
            )

        jira_webhook.delete_webhooks_not_in_ids(db, cloud_id, observed_webhook_ids)
        return jira_webhook.get_webhooks_by_cloud_id(db, cloud_id)

    async def register_webhook(
        self,
        db: Session,
        cloud_id: str,
        project_keys: list[str] | None = None,
    ) -> dict:
        """
        Dynamic webhook 등록
        """
        metadata = IntegrationAuditMetadata(
            context=f"jira_webhook_register:cloud_id={cloud_id}",
            provider="jira",
        )
        emit_audit_event(
            event_type=EventType.INTEGRATION,
            event_action=IntegrationEventAction.WEBHOOK_REGISTER,
            event_status=AuditEventStatus.ATTEMPT,
            level=AuditLevel.INFO,
            metadata=metadata,
            immediate=True,
        )

        client = await self._create_client(db, cloud_id)
        callback_url = self._build_callback_url(cloud_id)
        resolved_project_keys = self._resolve_project_keys(db, cloud_id, project_keys)
        jql_filter = self._build_jql_filter(resolved_project_keys)
        events = DEFAULT_JIRA_WEBHOOK_EVENTS
        try:
            response = await client.register_dynamic_webhook(
                callback_url=callback_url,
                jql_filter=jql_filter,
                events=events,
            )

            registration_results = response.get("webhookRegistrationResult") or []
            created_webhook_ids = [
                int(item["createdWebhookId"])
                for item in registration_results
                if item.get("createdWebhookId") is not None
            ]

            subscriptions = await self.sync_webhook_state(db, cloud_id)
        except Exception:
            emit_audit_event(
                event_type=EventType.INTEGRATION,
                event_action=IntegrationEventAction.WEBHOOK_REGISTER,
                event_status=AuditEventStatus.FAIL,
                level=AuditLevel.ERROR,
                metadata=metadata,
                immediate=True,
            )
            raise

        emit_audit_event(
            event_type=EventType.INTEGRATION,
            event_action=IntegrationEventAction.WEBHOOK_REGISTER,
            event_status=AuditEventStatus.SUCCESS,
            level=AuditLevel.INFO,
            metadata=metadata,
            immediate=True,
        )

        logger.info(
            f"[JIRA][WEBHOOK][DYNAMIC] Registered webhook: "
            f"cloud_id={cloud_id}, callback_url={callback_url}, "
            f"project_keys={resolved_project_keys}, created_ids={created_webhook_ids}"
        )

        return {
            "status": "registered",
            "cloud_id": cloud_id,
            "callback_url": callback_url,
            "project_keys": resolved_project_keys,
            "created_webhook_ids": created_webhook_ids,
            "registration_result": registration_results,
            "stored_webhook_count": len(subscriptions),
        }

    async def refresh_webhooks(
        self,
        db: Session,
        cloud_id: str,
        force: bool = False,
    ) -> dict:
        """
        Dynamic webhook 만료 시각 연장
        """
        client = await self._create_client(db, cloud_id)
        await self.sync_webhook_state(db, cloud_id)

        subscriptions = jira_webhook.get_webhooks_by_cloud_id(db, cloud_id)
        if not subscriptions:
            return {"status": "skipped", "reason": "no_registered_webhooks", "cloud_id": cloud_id}

        if force:
            target_ids = [subscription.webhook_id for subscription in subscriptions]
        else:
            threshold_at = datetime.now(timezone.utc) + timedelta(
                hours=settings.JIRA_WEBHOOK_REFRESH_THRESHOLD_HOURS
            )
            expiring = jira_webhook.get_expiring_webhooks(db, cloud_id, threshold_at)
            target_ids = [subscription.webhook_id for subscription in expiring]

        if not target_ids:
            return {"status": "skipped", "reason": "no_expiring_webhooks", "cloud_id": cloud_id}

        response = await client.refresh_dynamic_webhook_life(target_ids)
        expiration_date = parse_atlassian_datetime(response.get("expirationDate"))
        updated_count = jira_webhook.update_webhook_expiration(
            db,
            cloud_id=cloud_id,
            webhook_ids=target_ids,
            expires_at=expiration_date,
        )

        if expiration_date is None:
            await self.sync_webhook_state(db, cloud_id)

        logger.info(
            f"[JIRA][WEBHOOK][DYNAMIC] Refreshed webhooks: "
            f"cloud_id={cloud_id}, refreshed_ids={target_ids}, expiration={response.get('expirationDate')}"
        )

        return {
            "status": "refreshed",
            "cloud_id": cloud_id,
            "refreshed_webhook_ids": target_ids,
            "expiration_date": response.get("expirationDate"),
            "updated_rows": updated_count,
        }

    async def ensure_registered(
        self,
        db: Session,
        cloud_id: str,
        project_keys: list[str] | None = None,
    ) -> dict:
        """
        webhook 등록 보장 + 필요 시 만료 갱신
        """
        subscriptions = await self.sync_webhook_state(db, cloud_id)
        if not subscriptions:
            register_result = await self.register_webhook(
                db=db,
                cloud_id=cloud_id,
                project_keys=project_keys,
            )
            return {
                "status": "registered",
                "cloud_id": cloud_id,
                "register": register_result,
            }

        refresh_result = await self.refresh_webhooks(db=db, cloud_id=cloud_id, force=False)
        return {
            "status": "exists",
            "cloud_id": cloud_id,
            "webhook_count": len(subscriptions),
            "refresh": refresh_result,
        }


def get_jira_dynamic_webhook_service() -> JiraDynamicWebhookService:
    return JiraDynamicWebhookService()
