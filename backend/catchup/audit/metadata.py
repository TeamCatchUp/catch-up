from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from typing import Literal

from pydantic import ConfigDict
from pydantic import Field
from pydantic import model_validator

from catchup.audit.actions import IntegrationAction
from catchup.audit.base import AuditStatus
from catchup.audit.base import BaseAuditMetadata
from catchup.configs.config import settings
from catchup.db.models import SourceType
from catchup.db.models import SyncConnector
from catchup.db.models import UserRole
from catchup.sync.common.schemas import SyncTargetType

if TYPE_CHECKING:
    from catchup.audit.utils import AuditLogMetadataInput
    from catchup.sync.incremental.schemas import IncrementalIngestResult
    from catchup.sync.incremental.schemas import RecordChange


class SystemAuditMetadata(BaseAuditMetadata):
    model_config = ConfigDict(extra="allow")


class AuthAuditMetadata(BaseAuditMetadata):
    pass

class UserAuditMetadata(BaseAuditMetadata):
    user_id: int
    before_role: str | None = None
    after_role: str | None = None
    status: str | None = None
    reason: str | None = None

    @classmethod
    def from_audit(cls, data: "AuditLogMetadataInput") -> "UserAuditMetadata":
        payload = data.arguments.get("payload")
        result = data.result if isinstance(data.result, dict) else {}
        exc = data.exception
        detail = getattr(exc, "detail", {}) if exc else {}
        detail = detail if isinstance(detail, dict) else {}

        return cls(
            user_id=detail.get(
                "user_id",
                result.get("user_id", getattr(payload, "userId", None)),
            ),
            before_role=detail.get("before_role", result.get("before_role")),
            after_role=detail.get("after_role", result.get("after_role")),
            status=detail.get("status", result.get("status")),
            reason=detail.get("reason", result.get("reason", getattr(payload, "reason", None))),
        )


class IntegrationAuditMetadata(BaseAuditMetadata):
    provider: str | None = None
    integration_id: str | None = None
    integration_name: str | None = None
    resource_count: int | None = None
    jira_target_count: int | None = None
    confluence_target_count: int | None = None
    event_name: str | None = None
    installation_action: str | None = None
    result_status: str | None = None

    @classmethod
    def from_audit(
        cls,
        data: "AuditLogMetadataInput",
    ) -> "IntegrationAuditMetadata":
        if data.action == IntegrationAction.HANDLE_INSTALLATION:
            return cls._from_installation_audit(data)

        return cls._from_oauth_callback_audit(data)

    @classmethod
    def _from_oauth_callback_audit(
        cls,
        data: "AuditLogMetadataInput",
    ) -> "IntegrationAuditMetadata":
        provider = data.arguments["provider"]
        context = None
        result = data.result

        if data.status == AuditStatus.FAILURE:
            context = (
                getattr(data.exception, "reason", None)
                or getattr(data.exception, "code", None)
                or "internal_error"
            )

        return cls(
            context=context,
            provider=provider,
            integration_id=getattr(result, "team_id", None),
            integration_name=getattr(result, "team_name", None),
            resource_count=len(getattr(result, "resources", [])) if getattr(result, "resources", None) is not None else None,
            jira_target_count=len(getattr(result, "jira_targets", [])) if getattr(result, "jira_targets", None) is not None else None,
            confluence_target_count=len(getattr(result, "confluence_targets", [])) if getattr(result, "confluence_targets", None) is not None else None,
        )

    @classmethod
    def _from_installation_audit(
        cls,
        data: "AuditLogMetadataInput",
    ) -> "IntegrationAuditMetadata":
        payload = data.arguments["data"]
        result = data.result
        provider = data.arguments.get("provider", "github")
        context = None

        if data.status == AuditStatus.FAILURE:
            context = (
                getattr(data.exception, "reason", None)
                or getattr(data.exception, "code", None)
                or "internal_error"
            )

        return cls(
            context=context,
            provider=provider,
            integration_id=str(payload.installation.id),
            integration_name=payload.installation.account.login,
            event_name="installation",
            installation_action=payload.action,
            result_status=getattr(result, "status", None),
        )


class RegisterWebhookAuditMetadata(BaseAuditMetadata):
    provider: str | None = None
    integration_id: str | None = None
    webhook_source: str | None = None
    result_status: str | None = None
    project_key_count: int | None = None
    created_webhook_count: int | None = None
    stored_webhook_count: int | None = None

    @classmethod
    def from_audit(
        cls,
        data: "AuditLogMetadataInput",
    ) -> "RegisterWebhookAuditMetadata":
        result = data.result if isinstance(data.result, dict) else {}
        context = None
        argument_project_keys = data.arguments.get("project_keys")

        if data.status == AuditStatus.FAILURE:
            context = (
                getattr(data.exception, "reason", None)
                or getattr(data.exception, "code", None)
                or "internal_error"
            )

        project_keys = result.get("project_keys")
        created_webhook_ids = result.get("created_webhook_ids")

        return cls(
            context=context,
            provider="jira",
            integration_id=data.arguments["cloud_id"],
            webhook_source=data.arguments["source"],
            result_status=result.get("status"),
            project_key_count=(
                len(project_keys)
                if project_keys is not None
                else len(argument_project_keys)
                if argument_project_keys is not None
                else None
            ),
            created_webhook_count=len(created_webhook_ids) if created_webhook_ids is not None else None,
            stored_webhook_count=result.get("stored_webhook_count"),
        )


class ChannelTalkCredentialAuditMetadata(BaseAuditMetadata):
    provider: Literal["channel_talk"] = "channel_talk"
    credential_type: Literal["channel", "documents"]
    result_status: str | None = None
    channel_id: str | None = None
    channel_name: str | None = None
    space_id: str | None = None
    space_name: str | None = None
    webhook_token_configured: bool | None = None
    association_status: str | None = None
    polling_cycle_hours: int | None = None
    installed: bool | None = None
    removed: bool | None = None
    error_summary: str | None = None

    @classmethod
    def from_channel_credentials_audit(
        cls,
        data: "AuditLogMetadataInput",
    ) -> "ChannelTalkCredentialAuditMetadata":
        return cls._from_audit(data, credential_type="channel")

    @classmethod
    def from_document_credentials_audit(
        cls,
        data: "AuditLogMetadataInput",
    ) -> "ChannelTalkCredentialAuditMetadata":
        return cls._from_audit(data, credential_type="documents")

    @classmethod
    def _from_audit(
        cls,
        data: "AuditLogMetadataInput",
        *,
        credential_type: Literal["channel", "documents"],
    ) -> "ChannelTalkCredentialAuditMetadata":
        result = data.result
        request = data.arguments.get("connect_request")
        association_status = getattr(result, "association_status", None)

        return cls(
            context=cls._failure_context(data),
            credential_type=credential_type,
            result_status=cls._result_status(data),
            channel_id=cls._first_text(
                getattr(result, "channel_id", None),
                data.arguments.get("channel_id"),
            ),
            channel_name=cls._first_text(getattr(result, "channel_name", None)),
            space_id=cls._first_text(
                getattr(result, "space_id", None),
                data.arguments.get("space_id"),
            ),
            space_name=cls._first_text(getattr(result, "space_name", None)),
            webhook_token_configured=cls._webhook_token_configured(
                data=data,
                request=request,
            ),
            association_status=cls._first_text(
                getattr(association_status, "value", None),
                association_status,
            ),
            polling_cycle_hours=getattr(result, "polling_cycle_hours", None)
            or getattr(request, "polling_cycle_hours", None),
            installed=getattr(result, "installed", None),
            removed=getattr(result, "removed", None),
            error_summary=cls._error_summary(data),
        )

    @staticmethod
    def _failure_context(data: "AuditLogMetadataInput") -> str | None:
        if data.status != AuditStatus.FAILURE:
            return None
        return (
            getattr(data.exception, "reason", None)
            or getattr(data.exception, "code", None)
            or "internal_error"
        )

    @staticmethod
    def _error_summary(data: "AuditLogMetadataInput") -> str | None:
        if data.status != AuditStatus.FAILURE or data.exception is None:
            return None
        return str(data.exception)

    @staticmethod
    def _result_status(data: "AuditLogMetadataInput") -> str:
        if data.status == AuditStatus.ATTEMPT:
            return "attempt"
        if data.status == AuditStatus.FAILURE:
            return "failed"
        if getattr(data.result, "removed", None) is False:
            return "not_found"
        return "success"

    @staticmethod
    def _webhook_token_configured(
        *,
        data: "AuditLogMetadataInput",
        request: object | None,
    ) -> bool | None:
        result_value = getattr(data.result, "webhook_token_configured", None)
        if result_value is not None:
            return bool(result_value)
        request_value = getattr(request, "webhook_token", None)
        if request_value is not None:
            return bool(str(request_value).strip())
        return None

    @staticmethod
    def _first_text(*values: object) -> str | None:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None


class FullSyncTriggerMetadata(BaseAuditMetadata):
    connector: SyncConnector
    scope_id: str
    targets: list[dict[str, str]]
    sync_days: int
    job_id: str | None = None
    event_ids: list[str] | None = None

    @classmethod
    def from_audit(cls, data: "AuditLogMetadataInput") -> "FullSyncTriggerMetadata":
        sync_request = data.arguments["sync_request"]
        response = data.result
        # Audit metadata도 public request 계약과 같은 typed targets 배열을 기록한다.
        # target_ids는 더 이상 남기지 않아 이후 로그 분석에서도 계약이 한 가지로 보인다.
        resolved_sync_days = (
            sync_request.sync_days
            if sync_request.sync_days is not None
            else settings.DEFAULT_SYNC_DAYS
        )

        return cls(
            connector=sync_request.connector,
            scope_id=sync_request.scope_id or "",
            targets=[
                {
                    "target_type": target.target_type.value,
                    "target_id": target.target_id,
                }
                for target in sync_request.targets
            ],
            sync_days=resolved_sync_days,
            job_id=getattr(response, "job_id", None),
            event_ids=getattr(response, "event_ids", None),
        )


class FullSyncEventAuditMetadata(BaseAuditMetadata):
    connector: SyncConnector
    scope_id: str
    job_id: str
    event_id: str
    target_type: SyncTargetType
    target_id: str
    target_name: str | None = None
    attempt: int
    max_attempts: int
    sync_from_ts: str | None = None
    # requeue
    phase: str = "process"
    is_retry: bool = False
    next_attempt: int | None = None
    retry_at: str | None = None
    error_summary: str | None = None
    synced_count: int | None = None
    error_count: int | None = None
    skipped: bool | None = None

    @classmethod
    def from_audit(cls, data: "AuditLogMetadataInput") -> "FullSyncEventAuditMetadata":
        context = data.arguments["context"]
        result = data.result

        return cls(
            connector=context.connector,
            scope_id=context.scope_id,
            job_id=context.job_id,
            event_id=context.event_id,
            target_type=context.target_type,
            target_id=context.target_id,
            target_name=context.target_name,
            attempt=context.attempt,
            max_attempts=context.max_attempts,
            sync_from_ts=context.sync_from_ts,
            phase="process",
            is_retry=context.attempt > 0,
            synced_count=getattr(result, "synced_count", None),
            error_count=getattr(result, "error_count", None),
            skipped=getattr(result, "skipped", None),
        )

    @classmethod
    def from_requeue(
        cls,
        *,
        context,
        next_attempt: int,
        retry_at: str,
        error_summary: str,
    ) -> "FullSyncEventAuditMetadata":
        return cls(
            connector=context.connector,
            scope_id=context.scope_id,
            job_id=context.job_id,
            event_id=context.event_id,
            target_type=context.target_type,
            target_id=context.target_id,
            target_name=context.target_name,
            attempt=context.attempt,
            max_attempts=context.max_attempts,
            sync_from_ts=context.sync_from_ts,
            phase="requeue",
            is_retry=context.attempt > 0,
            next_attempt=next_attempt,
            retry_at=retry_at,
            error_summary=error_summary,
        )


class FullSyncJobAuditMetadata(BaseAuditMetadata):
    connector: SyncConnector
    scope_id: str
    job_id: str
    total_targets: int
    completed_targets: int | None = None
    failed_targets: int | None = None
    requeued_targets: int | None = None

    @classmethod
    def from_job_start(
        cls,
        *,
        context,
        total_targets: int,
    ) -> "FullSyncJobAuditMetadata":
        return cls(
            connector=context.connector,
            scope_id=context.scope_id,
            job_id=context.job_id,
            total_targets=total_targets,
        )

    @classmethod
    def from_job_result(
        cls,
        *,
        context,
        total_targets: int,
        completed_targets: int,
        failed_targets: int,
        requeued_targets: int,
    ) -> "FullSyncJobAuditMetadata":
        return cls(
            connector=context.connector,
            scope_id=context.scope_id,
            job_id=context.job_id,
            total_targets=total_targets,
            completed_targets=completed_targets,
            failed_targets=failed_targets,
            requeued_targets=requeued_targets,
        )

class IncrementalSyncTriggerMetadata(BaseAuditMetadata):
    connector: SyncConnector
    scope_id: str
    target_id: str
    record_type: str
    record_ids: list[str]
    change_count: int
    record_key_count: int | None = None
    blocked_count: int | None = None

    @classmethod
    def from_audit(cls, data: "AuditLogMetadataInput") -> "IncrementalSyncTriggerMetadata" | None:
        changes = data.arguments["changes"]
        if not changes:
            return None

        first_change = changes[0]
        result = data.result
        record_keys = getattr(result, "record_keys", None)

        return cls(
            connector=first_change.connector,
            scope_id=first_change.scope_id,
            target_id=first_change.parent_id,
            record_type=first_change.record_type,
            record_ids=[change.record_id for change in changes],
            change_count=len(changes),
            record_key_count=len(record_keys) if record_keys is not None else None,
            blocked_count=getattr(result, "blocked_count", None),
        )

    @classmethod
    def from_incremental_sync(
        cls,
        *,
        changes: list["RecordChange"],
        result: "IncrementalIngestResult",
    ) -> "IncrementalSyncTriggerMetadata":
        first_change = changes[0]
        return cls(
            connector=first_change.connector,
            scope_id=first_change.scope_id,
            target_id=first_change.parent_id,
            record_type=first_change.record_type,
            record_ids=[change.record_id for change in changes],
            change_count=len(changes),
            record_key_count=len(result.record_keys),
            blocked_count=result.blocked_count,
        )


class IncrementalRecordAuditMetadata(BaseAuditMetadata):
    connector: SyncConnector
    scope_id: str
    target_id: str
    record_key: str
    record_type: str | None = None
    phase: str = "process"
    attempt: int
    next_attempt: int | None = None
    retry_at: str | None = None
    skipped: bool | None = None

    @classmethod
    def from_audit(cls, data: "AuditLogMetadataInput") -> "IncrementalRecordAuditMetadata":
        context = data.arguments["context"]
        result = data.result

        return cls(
            connector=context.connector,
            scope_id=context.scope_id,
            target_id=context.target_id,
            record_key=context.record_key,
            record_type=context.record_type,
            phase="process",
            attempt=context.attempt,
            skipped=getattr(result, "skipped", None),
        )

    @classmethod
    def from_requeue(
        cls,
        *,
        context,
        next_attempt: int,
        retry_at: str,
    ) -> "IncrementalRecordAuditMetadata":
        return cls(
            connector=context.connector,
            scope_id=context.scope_id,
            target_id=context.target_id,
            record_key=context.record_key,
            record_type=context.record_type,
            phase="requeue",
            attempt=context.attempt,
            next_attempt=next_attempt,
            retry_at=retry_at,
        )


class SyncAuditMetadata(BaseAuditMetadata):
    connector: SyncConnector | None = None
    scope_id: str | None = None
    target_id: str | None = None
    job_id: str | None = None
    task_id: str | None = None
    token_usage: int | None = None


class ChatAuditMetadata(BaseAuditMetadata):
    session_id: uuid.UUID
    query: str | None = None
    tool_filters: list[SourceType] | None = Field(default=None)
    
    # 검색 관련
    retrieved_docs_count: int | None = None
    retrieved_doc_ids: list[str] | None = Field(default_factory=list)
    
    # 출처 제공 관련
    provided_sources_count: int | None = None
    provided_source_ids: list[str] | None = Field(default_factory=list)
    
    def _sync_count_and_ids(self, count_field: str, ids_field: str):
        """리스트 길이와 카운트 필드 사이의 정합성을 맞추는 내부 헬퍼"""
        ids_value = getattr(self, ids_field)
        
        if not ids_value:
            setattr(self, ids_field, None)
            setattr(self, count_field, None)
            return
        
        actual_count = len(ids_value)
        count_value = getattr(self, count_field)
        
        if count_value is None:
            # 카운트가 없으면 실제 리스트 길이로 채움
            setattr(self, count_field, actual_count)
        elif count_value != actual_count:
            # 카운트가 명시되었으나 리스트 길이와 다르면 에러
            raise ValueError(
                f"{count_field}({count_value}) does not match "
                f"actual {ids_field} count({actual_count})"
            )
    
    @model_validator(mode="after")
    def validate_sync_all(self) -> "ChatAuditMetadata":
        self._sync_count_and_ids("retrieved_docs_count", "retrieved_doc_ids")
        self._sync_count_and_ids("provided_sources_count", "provided_source_ids")
        return self
    
    
class AwsS3AuditMetadata(BaseAuditMetadata):
    file_name: str
    s3_key: str


class AdminOAuthAuditMetadata(BaseAuditMetadata):
    pass


class UserOnboardingAuditMetadata(BaseAuditMetadata):
    role: UserRole
