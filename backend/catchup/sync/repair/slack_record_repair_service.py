from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from functools import lru_cache

from fastapi.concurrency import run_in_threadpool

from catchup.db.engine import SessionLocal
from catchup.db.models import SyncConnector
from catchup.db.slack import domain_repository as slack_entities
from catchup.server.sync.schemas import SyncRecordGapItem
from catchup.server.sync.schemas import SyncRecordGapResponse
from catchup.server.sync.schemas import SyncRecordRetryItemRequest
from catchup.server.sync.schemas import SyncRecordRetryItemResponse
from catchup.server.sync.schemas import SyncRecordRetryRequest
from catchup.server.sync.schemas import SyncRecordRetryResponse
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.ingestion.factories.slack import create_slack_ingestion_service
from catchup.sync.repair.context import RecordRepairContext


@dataclass(slots=True, frozen=True)
class SlackTargetRef:
    team_id: str
    channel_id: str
    channel_name: str


@dataclass(slots=True, frozen=True)
class SlackRetryRecords:
    message_ids: list[str] = field(default_factory=list)


def _load_slack_target_ref(
    scope_id: str,
    target_id: str,
) -> SlackTargetRef:
    team_id = scope_id.strip()
    channel_id = target_id.strip()

    if not team_id:
        raise SyncRequestException("scope_id is required", code="invalid_scope_id")
    if not channel_id:
        raise SyncRequestException("target_id is required", code="invalid_target_id")

    with SessionLocal() as db:
        channel = slack_entities.get_channel(db, channel_id)

    if channel is None or channel.team_id != team_id:
        raise SyncRequestException(
            "slack channel not found in workspace",
            code="target_not_found",
            metadata={
                "scope_id": scope_id,
                "target_id": target_id,
            },
        )

    return SlackTargetRef(
        team_id=team_id,
        channel_id=channel_id,
        channel_name=channel.name,
    )


def _index_retry_records(
    records: list[SyncRecordRetryItemRequest],
) -> SlackRetryRecords:
    message_ids: list[str] = []

    for item in records:
        if item.record_type != "message":
            raise SyncRequestException(
                "unsupported slack record_type",
                code="unsupported_record_type",
                metadata={"record_type": item.record_type},
            )
        message_ids = list(item.record_ids)

    return SlackRetryRecords(message_ids=message_ids)


class SlackRecordRepairService:
    async def _get_target_ref(
        self,
        *,
        scope_id: str,
        target_id: str,
    ) -> SlackTargetRef:
        return await run_in_threadpool(
            _load_slack_target_ref,
            scope_id,
            target_id,
        )

    async def _get_slack_service(
        self,
        *,
        team_id: str,
    ):
        return await create_slack_ingestion_service(team_id=team_id)

    async def get_record_gaps(
        self,
        *,
        repair_context: RecordRepairContext,
    ) -> SyncRecordGapResponse:
        target = await self._get_target_ref(
            scope_id=repair_context.scope_id,
            target_id=repair_context.target_id,
        )
        service = await self._get_slack_service(team_id=target.team_id)
        gap_report = await service.build_record_gap_report(
            channel_id=target.channel_id,
            channel_name=target.channel_name,
            sync_from_ts=repair_context.sync_from_ts,
        )

        return SyncRecordGapResponse(
            connector=SyncConnector.SLACK,
            scope_id=repair_context.scope_id,
            target_id=repair_context.target_id,
            target_name=target.channel_name,
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
        service = await self._get_slack_service(team_id=target.team_id)
        retry_records = _index_retry_records(request.records)
        retry_result = await service.retry_missing_records(
            channel_id=target.channel_id,
            channel_name=target.channel_name,
            sync_from_ts=repair_context.sync_from_ts,
            message_ids=retry_records.message_ids,
        )

        return SyncRecordRetryResponse(
            connector=SyncConnector.SLACK,
            scope_id=repair_context.scope_id,
            target_id=repair_context.target_id,
            target_name=target.channel_name,
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
def get_slack_record_repair_service() -> SlackRecordRepairService:
    return SlackRecordRepairService()
