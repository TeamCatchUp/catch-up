from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationInfo
from pydantic import computed_field
from pydantic import field_validator

from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.connectors.confluence.schemas import ConfluenceBlogPostResponse
from catchup.connectors.confluence.schemas import ConfluencePageResponse
from catchup.connectors.confluence.service import ConfluenceIngestionService
from catchup.db.models import SyncConnector
from catchup.sync.audit import SyncAuditContext
from catchup.sync.ingestion.document_builders.confluence import (
    ConfluenceTransformResult,
)
from catchup.sync.ingestion.schemas import SyncExecutionRequest
from catchup.sync.ingestion.schemas import SyncExecutionResult
from catchup.sync.ingestion.schemas import SyncWindow
from catchup.utils.validation import require_text

ConfluenceRecordType = Literal["page", "blogpost"]
ConfluenceIncrementalEventKind = Literal["created", "updated", "deleted"]
logger = logging.getLogger(__name__)


class ConfluenceSpaceFullSyncExecutionRequest(SyncExecutionRequest):
    model_config = ConfigDict(extra="forbid")

    connector: Literal[SyncConnector.CONFLUENCE] = SyncConnector.CONFLUENCE
    target: Literal["space"] = "space"
    space_key: str
    space_id: str | None = None
    space_name: str | None = None
    record_type: ConfluenceRecordType
    batch_index: int = 0
    records: tuple[dict[str, Any], ...] = ()
    user_name_map: dict[str, str | None] = Field(default_factory=dict)
    sync_from_dt: datetime | None = None
    audit_context: SyncAuditContext | None = None

    @field_validator("space_key")
    @classmethod
    def _validate_space_key(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @field_validator("space_id")
    @classmethod
    def _validate_space_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return require_text(value, "space_id")

    def log_context(self) -> dict[str, object]:
        return {
            "space_key": self.space_key,
            "space_id": self.space_id,
            "record_type": self.record_type,
            "batch_index": self.batch_index,
            "record_count": len(self.records),
            "sync_from_dt_present": self.sync_from_dt is not None,
        }


class ConfluenceSpaceIncrementalSyncExecutionRequest(SyncExecutionRequest):
    connector: Literal[SyncConnector.CONFLUENCE] = SyncConnector.CONFLUENCE
    target: Literal["space"] = "space"
    space_key: str
    record_type: ConfluenceRecordType
    record_id: str
    event_kind: ConfluenceIncrementalEventKind = "updated"
    since: datetime | None = None
    audit_context: SyncAuditContext | None = None

    @field_validator("space_key", "record_id")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @computed_field
    @property
    def is_delete_event(self) -> bool:
        return self.event_kind == "deleted"

    def log_context(self) -> dict[str, object]:
        return {
            "space_key": self.space_key,
            "record_type": self.record_type,
            "record_id": self.record_id,
            "event_kind": self.event_kind,
        }


class ConfluenceSpaceFetchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_count: int = 1
    records: tuple[dict[str, Any], ...] = ()
    delete_prefixes: tuple[str, ...] = ()
    record_type: ConfluenceRecordType | None = None
    space_id: str | None = None
    space_name: str | None = None
    space_key: str | None = None
    user_name_map: dict[str, str | None] = Field(default_factory=dict)
    batch_index: int = 0
    is_last: bool = True
    checkpoint: int | None = None

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "record_type": self.record_type,
            "batch_index": self.batch_index,
            "record_count": len(self.records),
            "is_last": self.is_last,
        }


class ConfluenceSpaceTransformItem(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    content_id: str
    transform_result: ConfluenceTransformResult


class ConfluenceSpaceTransformResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    requested_count: int = 1
    record_type: ConfluenceRecordType | None = None
    items: tuple[ConfluenceSpaceTransformItem, ...] = ()
    delete_prefixes: tuple[str, ...] = ()
    error_count: int = 0
    stop_after_batch: bool = False
    space_key: str | None = None
    space_name: str | None = None

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "record_type": self.record_type,
            "item_count": len(self.items),
            "error_count": self.error_count,
            "stop_after_batch": self.stop_after_batch,
        }


class ConfluenceSpaceSummaryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary_applied: bool = False


class ConfluenceSpacePersistResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted_count: int = 0
    deleted_count: int = 0
    error_count: int = 0
    skipped: bool = False

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "persisted_count": self.persisted_count,
            "deleted_count": self.deleted_count,
            "error_count": self.error_count,
            "skipped": self.skipped,
        }


class ConfluenceSpaceSyncExecutionResult(SyncExecutionResult):
    connector: Literal[SyncConnector.CONFLUENCE] = SyncConnector.CONFLUENCE
    target: Literal["space"] = "space"
    persisted_count: int = 0
    deleted_count: int = 0
    failed_count: int = 0
    skipped: bool = False
    fetched: ConfluenceSpaceFetchResult
    transformed: ConfluenceSpaceTransformResult
    summary: ConfluenceSpaceSummaryResult
    persisted: ConfluenceSpacePersistResult
    record_type: ConfluenceRecordType | None = None
    batch_index: int = 0
    is_last: bool = True
    checkpoint: int | None = None

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "persisted_count": self.persisted_count,
            "deleted_count": self.deleted_count,
            "failed_count": self.failed_count,
            "skipped": self.skipped,
            "record_type": self.record_type,
            "batch_index": self.batch_index,
            "is_last": self.is_last,
        }


class ConfluenceSpaceSyncAdapter:
    """Bounded Confluence space or exact content execution adapter."""

    def __init__(self, *, service: ConfluenceIngestionService) -> None:
        self._service = service
        self._space_context_by_key: dict[
            str,
            tuple[str, str | None, dict[str, str | None]],
        ] = {}
        self._full_iterators: dict[
            tuple[str, ConfluenceRecordType],
            AsyncIterator[list[dict[str, Any]]],
        ] = {}

    async def fetch(
        self,
        *,
        execution: ConfluenceSpaceFullSyncExecutionRequest
        | ConfluenceSpaceIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
    ) -> ConfluenceSpaceFetchResult:
        _ = sync_window
        if isinstance(execution, ConfluenceSpaceFullSyncExecutionRequest):
            return await self._fetch_full_sync_page(execution)
        return await self._fetch_incremental_record(execution)

    async def transform(
        self,
        *,
        execution: ConfluenceSpaceFullSyncExecutionRequest
        | ConfluenceSpaceIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: ConfluenceSpaceFetchResult,
    ) -> ConfluenceSpaceTransformResult:
        _ = sync_window
        if not isinstance(execution, ConfluenceSpaceFullSyncExecutionRequest) and not fetched.records:
            if fetched.delete_prefixes:
                return ConfluenceSpaceTransformResult(
                    requested_count=fetched.requested_count,
                    record_type=fetched.record_type,
                    delete_prefixes=fetched.delete_prefixes,
                    space_key=fetched.space_key,
                    space_name=fetched.space_name,
                )
            return ConfluenceSpaceTransformResult(
                requested_count=fetched.requested_count,
            )

        items: list[ConfluenceSpaceTransformItem] = []
        error_count = 0
        stop_after_batch = False
        record_type = fetched.record_type or execution.record_type
        space_key = fetched.space_key or execution.space_key
        space_name = fetched.space_name or (
            execution.space_name
            if isinstance(execution, ConfluenceSpaceFullSyncExecutionRequest)
            else None
        )
        user_name_map = fetched.user_name_map or (
            execution.user_name_map
            if isinstance(execution, ConfluenceSpaceFullSyncExecutionRequest)
            else {}
        )
        for raw_content in fetched.records:
            try:
                if record_type == "page":
                    content = ConfluencePageResponse.model_validate(raw_content)
                    modified_at = parse_atlassian_datetime(
                        content.version.created_at if content.version else None
                    )
                    sync_from_dt = (
                        execution.sync_from_dt
                        if isinstance(execution, ConfluenceSpaceFullSyncExecutionRequest)
                        else execution.since
                    )
                    if sync_from_dt and modified_at and modified_at < sync_from_dt:
                        stop_after_batch = True
                        continue
                    transform_result = await self._service._process_page(
                        content,
                        space_key=space_key,
                        space_name=space_name,
                        user_name_map=user_name_map,
                    )
                else:
                    content = ConfluenceBlogPostResponse.model_validate(raw_content)
                    modified_at = parse_atlassian_datetime(
                        content.version.created_at if content.version else None
                    )
                    sync_from_dt = (
                        execution.sync_from_dt
                        if isinstance(execution, ConfluenceSpaceFullSyncExecutionRequest)
                        else execution.since
                    )
                    if sync_from_dt and modified_at and modified_at < sync_from_dt:
                        stop_after_batch = True
                        continue
                    transform_result = await self._service._process_blogpost(
                        content,
                        space_key=space_key,
                        space_name=space_name,
                        user_name_map=user_name_map,
                    )

                items.append(
                    ConfluenceSpaceTransformItem(
                        content_id=content.id,
                        transform_result=transform_result,
                    )
                )
            except Exception as exc:
                if self._service._is_retryable_connector_error(exc):
                    raise
                logger.warning(
                    "[CONFLUENCE][FULL SYNC] Failed to transform %s batch item: cloud_id=%s, space_key=%s, content_id=%s, error=%s",
                    record_type,
                    self._service.cloud_id,
                    space_key,
                    raw_content.get("id"),
                    exc,
                )
                error_count += 1

        return ConfluenceSpaceTransformResult(
            requested_count=fetched.requested_count,
            record_type=record_type,
            items=tuple(items),
            error_count=error_count,
            stop_after_batch=stop_after_batch,
            space_key=space_key,
            space_name=space_name,
        )

    async def summarize(
        self,
        *,
        execution: ConfluenceSpaceFullSyncExecutionRequest
        | ConfluenceSpaceIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: ConfluenceSpaceTransformResult,
    ) -> ConfluenceSpaceSummaryResult:
        _ = execution, sync_window, transformed
        return ConfluenceSpaceSummaryResult()

    async def persist(
        self,
        *,
        execution: ConfluenceSpaceFullSyncExecutionRequest
        | ConfluenceSpaceIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: ConfluenceSpaceTransformResult,
        summary: ConfluenceSpaceSummaryResult,
    ) -> ConfluenceSpacePersistResult:
        _ = sync_window, summary
        if isinstance(execution, ConfluenceSpaceFullSyncExecutionRequest):
            error_count = transformed.error_count
            for item in transformed.items:
                try:
                    await self._service._store_transform_result(
                        entity_type=execution.record_type,
                        content_id=item.content_id,
                        space_key=transformed.space_key or execution.space_key,
                        transform_result=item.transform_result,
                        audit_context=execution.audit_context,
                    )
                except Exception as exc:
                    if self._service._is_retryable_connector_error(exc):
                        raise
                    logger.warning(
                        "[CONFLUENCE][FULL SYNC] Failed to persist %s item: cloud_id=%s, space_key=%s, content_id=%s, error=%s",
                        execution.record_type,
                        self._service.cloud_id,
                        execution.space_key,
                        item.content_id,
                        exc,
                    )
                    error_count += 1
            return ConfluenceSpacePersistResult(
                persisted_count=len(transformed.items),
                error_count=error_count,
            )

        if transformed.delete_prefixes:
            for prefix in transformed.delete_prefixes:
                await self._service.repository.delete_by_id_prefix(prefix)
            return ConfluenceSpacePersistResult(
                deleted_count=len(transformed.delete_prefixes),
            )

        error_count = transformed.error_count
        for item in transformed.items:
            await self._service._store_transform_result(
                entity_type=execution.record_type,
                content_id=item.content_id,
                space_key=transformed.space_key or execution.space_key,
                transform_result=item.transform_result,
                audit_context=execution.audit_context,
            )
        return ConfluenceSpacePersistResult(
            persisted_count=len(transformed.items),
            error_count=error_count,
            skipped=not transformed.items and error_count == 0,
        )

    def build_result(
        self,
        *,
        execution: ConfluenceSpaceFullSyncExecutionRequest
        | ConfluenceSpaceIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: ConfluenceSpaceFetchResult,
        transformed: ConfluenceSpaceTransformResult,
        summary: ConfluenceSpaceSummaryResult,
        persisted: ConfluenceSpacePersistResult,
    ) -> ConfluenceSpaceSyncExecutionResult:
        _ = sync_window
        return ConfluenceSpaceSyncExecutionResult(
            tenant_id=execution.tenant_id,
            persisted_count=persisted.persisted_count,
            deleted_count=persisted.deleted_count,
            failed_count=persisted.error_count,
            skipped=persisted.skipped,
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
            record_type=fetched.record_type,
            batch_index=fetched.batch_index,
            is_last=fetched.is_last,
            checkpoint=fetched.checkpoint,
            metadata={
                "record_type": fetched.record_type,
                "batch_index": fetched.batch_index,
                "is_last": fetched.is_last,
                "checkpoint": fetched.checkpoint,
            },
        )

    async def _fetch_full_sync_page(
        self,
        execution: ConfluenceSpaceFullSyncExecutionRequest,
    ) -> ConfluenceSpaceFetchResult:
        if execution.records:
            return ConfluenceSpaceFetchResult(
                requested_count=1,
                records=execution.records,
                record_type=execution.record_type,
                space_id=execution.space_id,
                space_key=execution.space_key,
                space_name=execution.space_name,
                user_name_map=execution.user_name_map,
                batch_index=execution.batch_index,
                is_last=True,
                checkpoint=execution.batch_index,
            )

        space_id, space_name, user_name_map = await self._space_context(execution.space_key)
        key = (execution.space_key, execution.record_type)
        iterator = self._full_iterators.get(key)
        if iterator is None:
            if execution.record_type == "page":
                iterator = self._service.client.iter_pages(
                    space_id=space_id,
                    body_format="storage",
                )
            else:
                iterator = self._service.client.iter_blogposts(
                    space_id=space_id,
                    body_format="storage",
                )
            self._full_iterators[key] = iterator

        try:
            records = await anext(iterator)
        except StopAsyncIteration:
            return ConfluenceSpaceFetchResult(
                requested_count=1,
                record_type=execution.record_type,
                space_id=space_id,
                space_key=execution.space_key,
                space_name=space_name,
                user_name_map=user_name_map,
                batch_index=execution.batch_index,
                is_last=True,
                checkpoint=execution.batch_index,
            )

        return ConfluenceSpaceFetchResult(
            requested_count=1,
            records=tuple(records),
            record_type=execution.record_type,
            space_id=space_id,
            space_key=execution.space_key,
            space_name=space_name,
            user_name_map=user_name_map,
            batch_index=execution.batch_index,
            is_last=False,
            checkpoint=execution.batch_index,
        )

    async def _fetch_incremental_record(
        self,
        execution: ConfluenceSpaceIncrementalSyncExecutionRequest,
    ) -> ConfluenceSpaceFetchResult:
        _space_id, space_name, user_name_map = await self._space_context(execution.space_key)
        if execution.is_delete_event:
            return ConfluenceSpaceFetchResult(
                requested_count=1,
                delete_prefixes=(
                    f"confluence:{execution.record_type}:{execution.record_id}:chunk:",
                ),
                record_type=execution.record_type,
                space_key=execution.space_key,
                space_name=space_name,
                user_name_map=user_name_map,
            )

        if execution.record_type == "page":
            raw_content = await self._service.client.get_page_by_id(
                execution.record_id,
                body_format="storage",
            )
        else:
            raw_content = await self._service.client.get_blogpost_by_id(
                execution.record_id,
                body_format="storage",
            )
        return ConfluenceSpaceFetchResult(
            requested_count=1,
            records=(raw_content,),
            record_type=execution.record_type,
            space_key=execution.space_key,
            space_name=space_name,
            user_name_map=user_name_map,
        )

    async def _space_context(
        self,
        space_key: str,
    ) -> tuple[str, str | None, dict[str, str | None]]:
        cached = self._space_context_by_key.get(space_key)
        if cached is not None:
            return cached

        space_id_map, space_name_map, user_name_map = await self._service._load_space_sync_context(
            [space_key],
        )
        space_id = space_id_map.get(space_key)
        if not space_id:
            raise RuntimeError(
                "[CONFLUENCE][CONNECTOR CORE] Space not found in metadata snapshot: "
                f"cloud_id={self._service.cloud_id}, space_key={space_key}"
            )
        result = (space_id, space_name_map.get(space_key), user_name_map)
        self._space_context_by_key[space_key] = result
        return result
