from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from fastapi.concurrency import run_in_threadpool

from catchup.connectors.github.factory import create_github_ingestion_service
from catchup.db.engine import SessionLocal
from catchup.db.github import domain_repository as github_entities
from catchup.db.models import SyncConnector
from catchup.server.sync.schemas import (
    SyncRecordGapItem,
    SyncRecordGapResponse,
    SyncRecordRetryItemRequest,
    SyncRecordRetryItemResponse,
    SyncRecordRetryRequest,
    SyncRecordRetryResponse,
)
from catchup.sync.common.exceptions import SyncRequestError
from catchup.sync.repair.context import RecordRepairContext


@dataclass(slots=True, frozen=True)
class GithubTargetRef:
    installation_id: int
    repo_id: int
    full_name: str


@dataclass(slots=True, frozen=True)
class GithubRetryRecords:
    issue_ids: list[str] = field(default_factory=list)
    pull_request_ids: list[str] = field(default_factory=list)


def _load_github_target_ref(
    scope_id: str,
    target_id: str,
) -> GithubTargetRef:
    normalized_scope_id = scope_id.strip()
    normalized_target_id = target_id.strip()

    if not normalized_scope_id:
        raise SyncRequestError("scope_id is required", code="invalid_scope_id")
    if not normalized_target_id:
        raise SyncRequestError("target_id is required", code="invalid_target_id")

    try:
        installation_id = int(normalized_scope_id)
    except ValueError as exc:
        raise SyncRequestError(
            "scope_id must be a github installation_id",
            code="invalid_scope_id",
            metadata={"scope_id": scope_id},
        ) from exc

    try:
        repo_id = int(normalized_target_id)
    except ValueError as exc:
        raise SyncRequestError(
            "target_id must be a github repository_id",
            code="invalid_target_id",
            metadata={"target_id": target_id},
        ) from exc

    with SessionLocal() as db:
        repositories = github_entities.get_repositories_by_installation(
            db,
            installation_id,
        )

    for repo in repositories:
        if repo.repo_id == repo_id:
            return GithubTargetRef(
                installation_id=installation_id,
                repo_id=repo_id,
                full_name=repo.full_name,
            )

    raise SyncRequestError(
        "github repository not found in installation",
        code="target_not_found",
        metadata={
            "scope_id": scope_id,
            "target_id": target_id,
        },
    )


def _index_retry_records(
    records: list[SyncRecordRetryItemRequest],
) -> GithubRetryRecords:
    issue_ids: list[str] = []
    pull_request_ids: list[str] = []

    for item in records:
        if item.record_type == "issue":
            issue_ids = list(item.record_ids)
        elif item.record_type == "pull_request":
            pull_request_ids = list(item.record_ids)
        else:
            raise SyncRequestError(
                "unsupported github record_type",
                code="unsupported_record_type",
                metadata={"record_type": item.record_type},
            )

    return GithubRetryRecords(
        issue_ids=issue_ids,
        pull_request_ids=pull_request_ids,
    )


class GithubRecordRepairService:
    async def _get_target_ref(
        self,
        *,
        scope_id: str,
        target_id: str,
    ) -> GithubTargetRef:
        return await run_in_threadpool(
            _load_github_target_ref,
            scope_id,
            target_id,
        )

    async def _get_github_service(
        self,
        *,
        installation_id: int,
    ):
        return await create_github_ingestion_service(
            db=None,
            installation_id=installation_id,
        )

    async def get_record_gaps(
        self,
        *,
        repair_context: RecordRepairContext,
    ) -> SyncRecordGapResponse:
        target = await self._get_target_ref(
            scope_id=repair_context.scope_id,
            target_id=repair_context.target_id,
        )
        service = await self._get_github_service(
            installation_id=target.installation_id,
        )

        gap_report = await service.build_record_gap_report(
            repo_id=target.repo_id,
            sync_from_dt=repair_context.sync_from_dt,
        )

        return SyncRecordGapResponse(
            connector=SyncConnector.GITHUB,
            scope_id=repair_context.scope_id,
            target_id=repair_context.target_id,
            target_name=target.full_name,
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
        service = await self._get_github_service(
            installation_id=target.installation_id,
        )
        retry_records = _index_retry_records(request.records)

        retry_result = await service.retry_missing_records(
            repo_id=target.repo_id,
            sync_from_dt=repair_context.sync_from_dt,
            issue_ids=retry_records.issue_ids,
            pull_request_ids=retry_records.pull_request_ids,
        )

        return SyncRecordRetryResponse(
            connector=SyncConnector.GITHUB,
            scope_id=repair_context.scope_id,
            target_id=repair_context.target_id,
            target_name=target.full_name,
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
def get_github_record_repair_service() -> GithubRecordRepairService:
    return GithubRecordRepairService()
