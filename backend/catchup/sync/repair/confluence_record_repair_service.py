from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from fastapi.concurrency import run_in_threadpool

from catchup.connectors.confluence.factory import create_confluence_ingestion_service
from catchup.db.confluence import domain_repository as confluence_entities
from catchup.db.engine import SessionLocal
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
class ConfluenceTargetRef:
    cloud_id: str
    space_key: str
    space_name: str


@dataclass(slots=True, frozen=True)
class ConfluenceRetryRecords:
    page_ids: list[str] = field(default_factory=list)
    blogpost_ids: list[str] = field(default_factory=list)


def _load_confluence_target_ref(
    scope_id: str,
    target_id: str,
) -> ConfluenceTargetRef:
    cloud_id = scope_id.strip()
    space_key = target_id.strip()

    if not cloud_id:
        raise SyncRequestError("scope_id is required", code="invalid_scope_id")
    if not space_key:
        raise SyncRequestError("target_id is required", code="invalid_target_id")

    with SessionLocal() as db:
        space_id_map = confluence_entities.get_space_id_map(db, cloud_id, [space_key])
        space_name_map = confluence_entities.get_space_name_map(db, cloud_id, [space_key])

    if space_key not in space_id_map:
        raise SyncRequestError(
            "confluence space not found in cloud",
            code="target_not_found",
            metadata={
                "scope_id": scope_id,
                "target_id": target_id,
            },
        )

    return ConfluenceTargetRef(
        cloud_id=cloud_id,
        space_key=space_key,
        space_name=space_name_map.get(space_key) or space_key,
    )


def _index_retry_records(
    records: list[SyncRecordRetryItemRequest],
) -> ConfluenceRetryRecords:
    page_ids: list[str] = []
    blogpost_ids: list[str] = []

    for item in records:
        if item.record_type == "page":
            page_ids = list(item.record_ids)
        elif item.record_type == "blogpost":
            blogpost_ids = list(item.record_ids)
        else:
            raise SyncRequestError(
                "unsupported confluence record_type",
                code="unsupported_record_type",
                metadata={"record_type": item.record_type},
            )

    return ConfluenceRetryRecords(
        page_ids=page_ids,
        blogpost_ids=blogpost_ids,
    )


class ConfluenceRecordRepairService:
    async def _get_target_ref(
        self,
        *,
        scope_id: str,
        target_id: str,
    ) -> ConfluenceTargetRef:
        return await run_in_threadpool(
            _load_confluence_target_ref,
            scope_id,
            target_id,
        )

    async def _get_confluence_service(
        self,
        *,
        cloud_id: str,
    ):
        return await create_confluence_ingestion_service(cloud_id=cloud_id)

    async def get_record_gaps(
        self,
        *,
        repair_context: RecordRepairContext,
    ) -> SyncRecordGapResponse:
        target = await self._get_target_ref(
            scope_id=repair_context.scope_id,
            target_id=repair_context.target_id,
        )
        service = await self._get_confluence_service(cloud_id=target.cloud_id)
        gap_report = await service.build_record_gap_report(
            space_key=target.space_key,
            sync_from_dt=repair_context.sync_from_dt,
        )

        return SyncRecordGapResponse(
            connector=SyncConnector.CONFLUENCE,
            scope_id=repair_context.scope_id,
            target_id=repair_context.target_id,
            target_name=target.space_name,
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
        service = await self._get_confluence_service(cloud_id=target.cloud_id)
        retry_records = _index_retry_records(request.records)
        retry_result = await service.retry_missing_records(
            space_key=target.space_key,
            sync_from_dt=repair_context.sync_from_dt,
            page_ids=retry_records.page_ids,
            blogpost_ids=retry_records.blogpost_ids,
        )

        return SyncRecordRetryResponse(
            connector=SyncConnector.CONFLUENCE,
            scope_id=repair_context.scope_id,
            target_id=repair_context.target_id,
            target_name=target.space_name,
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
def get_confluence_record_repair_service() -> ConfluenceRecordRepairService:
    return ConfluenceRecordRepairService()
