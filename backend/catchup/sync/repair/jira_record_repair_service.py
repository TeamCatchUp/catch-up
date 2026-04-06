from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from fastapi.concurrency import run_in_threadpool

from catchup.connectors.jira.factory import create_jira_ingestion_service
from catchup.db.engine import SessionLocal
from catchup.db.jira import domain_repository as jira_entities
from catchup.db.models import SyncConnector
from catchup.server.sync.schemas import (
    SyncRecordGapItem,
    SyncRecordGapResponse,
    SyncRecordRetryItemRequest,
    SyncRecordRetryItemResponse,
    SyncRecordRetryRequest,
    SyncRecordRetryResponse,
)
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.repair.context import RecordRepairContext


@dataclass(slots=True, frozen=True)
class JiraTargetRef:
    cloud_id: str
    project_key: str
    project_name: str


@dataclass(slots=True, frozen=True)
class JiraRetryRecords:
    issue_ids: list[str] = field(default_factory=list)
    epic_ids: list[str] = field(default_factory=list)


def _load_jira_target_ref(
    scope_id: str,
    target_id: str,
) -> JiraTargetRef:
    cloud_id = scope_id.strip()
    project_key = target_id.strip()

    if not cloud_id:
        raise SyncRequestException("scope_id is required", code="invalid_scope_id")
    if not project_key:
        raise SyncRequestException("target_id is required", code="invalid_target_id")

    with SessionLocal() as db:
        project = jira_entities.get_project(db, cloud_id, project_key)

    if project is None:
        raise SyncRequestException(
            "jira project not found in cloud",
            code="target_not_found",
            metadata={
                "scope_id": scope_id,
                "target_id": target_id,
            },
        )

    return JiraTargetRef(
        cloud_id=cloud_id,
        project_key=project_key,
        project_name=project.project_name or project_key,
    )


def _index_retry_records(
    records: list[SyncRecordRetryItemRequest],
) -> JiraRetryRecords:
    issue_ids: list[str] = []
    epic_ids: list[str] = []

    for item in records:
        if item.record_type == "issue":
            issue_ids = list(item.record_ids)
        elif item.record_type == "epic":
            epic_ids = list(item.record_ids)
        else:
            raise SyncRequestException(
                "unsupported jira record_type",
                code="unsupported_record_type",
                metadata={"record_type": item.record_type},
            )

    return JiraRetryRecords(
        issue_ids=issue_ids,
        epic_ids=epic_ids,
    )


class JiraRecordRepairService:
    async def _get_target_ref(
        self,
        *,
        scope_id: str,
        target_id: str,
    ) -> JiraTargetRef:
        return await run_in_threadpool(
            _load_jira_target_ref,
            scope_id,
            target_id,
        )

    async def _get_jira_service(
        self,
        *,
        cloud_id: str,
    ):
        return await create_jira_ingestion_service(cloud_id=cloud_id)

    async def get_record_gaps(
        self,
        *,
        repair_context: RecordRepairContext,
    ) -> SyncRecordGapResponse:
        target = await self._get_target_ref(
            scope_id=repair_context.scope_id,
            target_id=repair_context.target_id,
        )
        service = await self._get_jira_service(cloud_id=target.cloud_id)
        gap_report = await service.build_record_gap_report(
            project_key=target.project_key,
            sync_from_dt=repair_context.sync_from_dt,
        )

        return SyncRecordGapResponse(
            connector=SyncConnector.JIRA,
            scope_id=repair_context.scope_id,
            target_id=repair_context.target_id,
            target_name=target.project_name,
            records=[
                SyncRecordGapItem(
                    record_type=item.record_type,
                    expected_count=item.expected_count,
                    stored_count=item.stored_count,
                    missing_count=item.missing_count,
                    missing_ids=item.missing_ids,
                )
                for item in gap_report.records
            ],
        )

    async def retry_records(
        self,
        *,
        request: SyncRecordRetryRequest,
        repair_context: RecordRepairContext,
    ) -> SyncRecordRetryResponse:
        target = await self._get_target_ref(
            scope_id=repair_context.scope_id,
            target_id=repair_context.target_id,
        )
        service = await self._get_jira_service(cloud_id=target.cloud_id)
        retry_records = _index_retry_records(request.records)
        retry_result = await service.retry_missing_records(
            project_key=target.project_key,
            sync_from_dt=repair_context.sync_from_dt,
            issue_ids=retry_records.issue_ids,
            epic_ids=retry_records.epic_ids,
        )

        return SyncRecordRetryResponse(
            connector=SyncConnector.JIRA,
            scope_id=repair_context.scope_id,
            target_id=repair_context.target_id,
            target_name=target.project_name,
            records=[
                SyncRecordRetryItemResponse(
                    record_type=item.record_type,
                    requested_ids=item.requested_ids,
                    retried_count=item.retried_count,
                    succeeded_count=item.succeeded_count,
                    failed_ids=item.failed_ids,
                    remaining_missing_ids=item.remaining_missing_ids,
                )
                for item in retry_result.records
            ],
        )


@lru_cache(maxsize=1)
def get_jira_record_repair_service() -> JiraRecordRepairService:
    return JiraRecordRepairService()
