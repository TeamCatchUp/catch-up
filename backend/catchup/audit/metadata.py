import uuid
from typing import TYPE_CHECKING

from pydantic import ConfigDict
from pydantic import Field
from pydantic import model_validator

from catchup.audit.base import BaseAuditMetadata
from catchup.db.models import SourceType
from catchup.db.models import SyncConnector
from catchup.db.models import UserRole

if TYPE_CHECKING:
    from catchup.server.sync.schemas import FullSyncRequest
    from catchup.server.sync.schemas import SyncAcceptedResponse
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


class IntegrationAuditMetadata(BaseAuditMetadata):
    provider: str | None = None


class FullSyncTriggerMetadata(BaseAuditMetadata):
    connector: SyncConnector
    scope_id: str
    target_ids: list[str]
    sync_days: int
    job_id: str | None = None
    event_ids: list[str] | None = None

    @classmethod
    def from_full_sync(
        cls,
        *,
        sync_request: "FullSyncRequest",
        default_sync_days: int,
        response: "SyncAcceptedResponse" | None = None,
    ) -> "FullSyncTriggerMetadata":
        resolved_sync_days = (
            sync_request.sync_days
            if sync_request.sync_days is not None
            else default_sync_days
        )
        return cls(
            connector=sync_request.connector,
            scope_id=sync_request.scope_id,
            target_ids=sync_request.target_ids,
            sync_days=resolved_sync_days,
            job_id=response.job_id if response is not None else None,
            event_ids=response.event_ids if response is not None else None,
        )


class IncrementalSyncTriggerMetadata(BaseAuditMetadata):
    connector: SyncConnector
    scope_id: str
    target_id: str
    record_type: str
    record_ids: list[str]
    change_count: int
    record_key_count: int
    blocked_count: int

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
