from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from catchup.connectors.slack.client import SlackRateLimitError
from catchup.connectors.slack.factory import create_slack_ingestion_service
from catchup.db.engine import SessionLocal
from catchup.db.incremental import mark_record_keys_recovered
from catchup.db.models import (
    IncrementalRecordState,
    IncrementalRecordStatus,
    SyncConnector,
)
from catchup.server.sync.schemas import (
    SlackIncrementalRecoveryResponse,
)


@dataclass(slots=True, frozen=True)
class SlackRecoveryCandidate:
    channel_id: str
    rehydrate_record_ids: tuple[str, ...] = field(default_factory=tuple)
    delete_record_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True, frozen=True)
class SlackRecoveryPlan:
    team_id: str | None = None
    candidates: tuple[SlackRecoveryCandidate, ...] = field(default_factory=tuple)


@dataclass(slots=True, frozen=True)
class _ChannelRecoveryResult:
    succeeded_records: int = 0
    failed_records: int = 0


class SlackIncrementalRecoveryService:
    _RECOVERY_BATCH_SIZE = 200

    async def _load_candidates(
        self,
    ) -> SlackRecoveryPlan:
        return await run_in_threadpool(
            self._load_candidates_sync,
        )

    def _load_candidates_sync(
        self,
    ) -> SlackRecoveryPlan:
        with SessionLocal() as db:
            stmt = (
                select(
                    IncrementalRecordState.scope_id,
                    IncrementalRecordState.parent_id,
                    IncrementalRecordState.record_id,
                    IncrementalRecordState.event_kind,
                )
                .select_from(IncrementalRecordState)
                .where(
                    IncrementalRecordState.connector == SyncConnector.SLACK,
                    IncrementalRecordState.record_type == "message",
                    IncrementalRecordState.status != IncrementalRecordStatus.RECOVERED,
                )
                .order_by(
                    IncrementalRecordState.updated_at.desc(),
                    IncrementalRecordState.last_event_at.desc(),
                )
            )
            rows = db.execute(stmt).all()

        return self._build_recovery_plan(rows)

    def _build_recovery_plan(
        self,
        rows: Iterable[object],
    ) -> SlackRecoveryPlan:
        team_id: str | None = None
        grouped: dict[str, dict[str, set[str]]] = {}
        seen_record_ids: set[str] = set()

        for row in rows:
            scope_id = str(getattr(row, "scope_id", "") or "").strip()
            channel_id = str(getattr(row, "parent_id", "") or "").strip()
            record_id = str(getattr(row, "record_id", "") or "").strip()
            event_kind = str(getattr(row, "event_kind", "") or "").strip().lower()

            if not scope_id or not channel_id or not record_id:
                continue
            if team_id is None:
                team_id = scope_id
            if scope_id != team_id or record_id in seen_record_ids:
                continue

            seen_record_ids.add(record_id)
            channel_entry = grouped.setdefault(
                channel_id,
                {
                    "rehydrate": set(),
                    "delete": set(),
                },
            )
            if event_kind == "deleted":
                channel_entry["delete"].add(record_id)
                channel_entry["rehydrate"].discard(record_id)
            else:
                channel_entry["rehydrate"].add(record_id)
                channel_entry["delete"].discard(record_id)

        candidates = tuple(
            SlackRecoveryCandidate(
                channel_id=channel_id,
                rehydrate_record_ids=self._sort_record_ids(values["rehydrate"]),
                delete_record_ids=self._sort_record_ids(values["delete"]),
            )
            for channel_id, values in sorted(grouped.items())
        )
        return SlackRecoveryPlan(team_id=team_id, candidates=candidates)

    async def _get_service(self, scope_id: str):
        return await create_slack_ingestion_service(scope_id)

    @staticmethod
    def _sort_record_ids(record_ids: Iterable[str]) -> tuple[str, ...]:
        def _key(value: str) -> tuple[int, float | str]:
            try:
                return (0, float(value))
            except ValueError:
                return (1, value)

        return tuple(sorted({record_id for record_id in record_ids if record_id}, key=_key))

    @staticmethod
    def _chunk_record_ids(record_ids: tuple[str, ...], batch_size: int) -> list[list[str]]:
        if not record_ids:
            return []
        return [
            list(record_ids[index : index + batch_size])
            for index in range(0, len(record_ids), batch_size)
        ]

    @staticmethod
    def _build_record_keys(
        *,
        scope_id: str,
        channel_id: str,
        record_ids: Iterable[str],
    ) -> list[str]:
        return [
            f"{SyncConnector.SLACK.value}:{scope_id}:channel:{channel_id}:message:{record_id}"
            for record_id in record_ids
            if str(record_id).strip()
        ]

    @staticmethod
    def _mark_record_keys_recovered_sync(record_keys: list[str]) -> int:
        with SessionLocal() as db:
            return mark_record_keys_recovered(
                db,
                record_keys=record_keys,
            )

    @staticmethod
    def _build_document_ids(
        *,
        scope_id: str,
        channel_id: str,
        record_ids: Iterable[str],
    ) -> list[str]:
        return [
            f"slack:message:{scope_id}:{channel_id}:{record_id}"
            for record_id in record_ids
            if str(record_id).strip()
        ]

    async def _mark_record_ids_recovered(
        self,
        *,
        team_id: str,
        channel_id: str,
        record_ids: Iterable[str],
    ) -> None:
        record_keys = self._build_record_keys(
            scope_id=team_id,
            channel_id=channel_id,
            record_ids=record_ids,
        )
        if not record_keys:
            return
        await run_in_threadpool(
            self._mark_record_keys_recovered_sync,
            record_keys,
        )

    async def _recover_deleted_records(
        self,
        *,
        team_id: str,
        candidate: SlackRecoveryCandidate,
        slack_service: object,
    ) -> _ChannelRecoveryResult:
        if not candidate.delete_record_ids:
            return _ChannelRecoveryResult()

        try:
            await slack_service.repository.delete_documents(
                self._build_document_ids(
                    scope_id=team_id,
                    channel_id=candidate.channel_id,
                    record_ids=candidate.delete_record_ids,
                )
            )
            await self._mark_record_ids_recovered(
                team_id=team_id,
                channel_id=candidate.channel_id,
                record_ids=candidate.delete_record_ids,
            )
            return _ChannelRecoveryResult(
                succeeded_records=len(candidate.delete_record_ids),
            )
        except SlackRateLimitError:
            raise
        except Exception:
            return _ChannelRecoveryResult(
                failed_records=len(candidate.delete_record_ids),
            )

    async def _recover_rehydrate_batch(
        self,
        *,
        team_id: str,
        candidate: SlackRecoveryCandidate,
        slack_service: object,
        record_id_batch: list[str],
    ) -> _ChannelRecoveryResult:
        try:
            retry_result = await slack_service.retry_missing_records(
                channel_id=candidate.channel_id,
                channel_name=candidate.channel_id,
                message_ids=record_id_batch,
            )
            if not retry_result.records:
                return _ChannelRecoveryResult(
                    failed_records=len(record_id_batch),
                )

            retry_item = retry_result.records[0]
            failed_id_set = set(retry_item.failed_ids)
            succeeded_ids = [
                record_id
                for record_id in record_id_batch
                if record_id not in failed_id_set
            ]

            if succeeded_ids:
                await self._mark_record_ids_recovered(
                    team_id=team_id,
                    channel_id=candidate.channel_id,
                    record_ids=succeeded_ids,
                )

            return _ChannelRecoveryResult(
                succeeded_records=len(succeeded_ids),
                failed_records=len(failed_id_set),
            )
        except SlackRateLimitError:
            raise
        except Exception:
            return _ChannelRecoveryResult(
                failed_records=len(record_id_batch),
            )

    async def _get_or_create_service(self, team_id: str) -> object | None:
        try:
            return await self._get_service(team_id)
        except SlackRateLimitError:
            raise
        except Exception:
            return None

    async def _recover_scope_candidates(
        self,
        *,
        team_id: str,
        candidates: list[SlackRecoveryCandidate],
        slack_service: object | None,
    ) -> _ChannelRecoveryResult:
        if slack_service is None:
            failed_records = sum(
                len(candidate.rehydrate_record_ids) + len(candidate.delete_record_ids)
                for candidate in candidates
            )
            return _ChannelRecoveryResult(failed_records=failed_records)

        succeeded_records = 0
        failed_records = 0

        for candidate in candidates:
            delete_result = await self._recover_deleted_records(
                team_id=team_id,
                candidate=candidate,
                slack_service=slack_service,
            )
            succeeded_records += delete_result.succeeded_records
            failed_records += delete_result.failed_records

            for record_id_batch in self._chunk_record_ids(
                candidate.rehydrate_record_ids,
                self._RECOVERY_BATCH_SIZE,
            ):
                batch_result = await self._recover_rehydrate_batch(
                    team_id=team_id,
                    candidate=candidate,
                    slack_service=slack_service,
                    record_id_batch=record_id_batch,
                )
                succeeded_records += batch_result.succeeded_records
                failed_records += batch_result.failed_records

        return _ChannelRecoveryResult(
            succeeded_records=succeeded_records,
            failed_records=failed_records,
        )

    async def recover(self) -> SlackIncrementalRecoveryResponse:
        recovery_plan = await self._load_candidates()

        total_incremental_records_before_recovery = sum(
            len(candidate.rehydrate_record_ids) + len(candidate.delete_record_ids)
            for candidate in recovery_plan.candidates
        )
        if recovery_plan.team_id is None:
            return SlackIncrementalRecoveryResponse(
                total_incremental_records_before_recovery=0,
                succeeded_records=0,
                failed_records=0,
            )

        slack_service = await self._get_or_create_service(recovery_plan.team_id)
        recovery_result = await self._recover_scope_candidates(
            team_id=recovery_plan.team_id,
            candidates=list(recovery_plan.candidates),
            slack_service=slack_service,
        )

        return SlackIncrementalRecoveryResponse(
            total_incremental_records_before_recovery=total_incremental_records_before_recovery,
            succeeded_records=recovery_result.succeeded_records,
            failed_records=recovery_result.failed_records,
        )


@lru_cache(maxsize=1)
def get_slack_incremental_recovery_service() -> SlackIncrementalRecoveryService:
    return SlackIncrementalRecoveryService()
