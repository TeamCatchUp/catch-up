from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest import TestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catchup.db.models import IncrementalRecordState
from catchup.db.models import IncrementalRecordStatus
from catchup.db.models import SyncConnector
from catchup.sync.incremental.dead_record_recovery import (
    recover_exhausted_dead_incremental_records,
)


class IncrementalDeadRecordRecoveryTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        IncrementalRecordState.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self) -> None:
        IncrementalRecordState.__table__.drop(self.engine)
        self.engine.dispose()

    def test_requeues_dead_record_with_attempt_within_max_attempts(self) -> None:
        now = datetime(2026, 5, 16, 1, 0, tzinfo=timezone.utc)
        with self.Session() as db:
            db.add_all(
                [
                    self._record(
                        record_key="jira:cloud:project:GRT:issue:GRT-1",
                        status=IncrementalRecordStatus.DEAD,
                        attempt=1,
                        last_error="Connection was closed before valid response",
                    ),
                    self._record(
                        record_key="jira:cloud:project:GRT:issue:GRT-2",
                        status=IncrementalRecordStatus.DEAD,
                        attempt=0,
                        last_error="invalid dead attempt",
                    ),
                    self._record(
                        record_key="jira:cloud:project:GRT:issue:GRT-3",
                        status=IncrementalRecordStatus.DEAD,
                        attempt=4,
                        last_error="already recovered once and failed again",
                    ),
                    self._record(
                        record_key="jira:cloud:project:GRT:issue:GRT-4",
                        status=IncrementalRecordStatus.QUEUED,
                        attempt=3,
                    ),
                ]
            )
            db.commit()

            result = recover_exhausted_dead_incremental_records(
                db,
                max_attempts=3,
                now=now,
            )
            records = {
                record.record_key: record
                for record in db.query(IncrementalRecordState).all()
            }

        requeued_record = records["jira:cloud:project:GRT:issue:GRT-1"]
        self.assertEqual(result.scanned, 1)
        self.assertEqual(result.requeued, 1)
        self.assertEqual(
            requeued_record.status,
            IncrementalRecordStatus.DEBOUNCING,
        )
        self.assertEqual(requeued_record.attempt, 1)
        self.assertIsNone(requeued_record.last_error)
        self.assertEqual(
            requeued_record.debounce_until.replace(tzinfo=timezone.utc),
            now,
        )
        self.assertEqual(
            records["jira:cloud:project:GRT:issue:GRT-2"].status,
            IncrementalRecordStatus.DEAD,
        )
        self.assertEqual(
            records["jira:cloud:project:GRT:issue:GRT-3"].status,
            IncrementalRecordStatus.DEAD,
        )
        self.assertEqual(
            records["jira:cloud:project:GRT:issue:GRT-4"].status,
            IncrementalRecordStatus.QUEUED,
        )

    def test_respects_batch_limit(self) -> None:
        now = datetime(2026, 5, 16, 1, 0, tzinfo=timezone.utc)
        with self.Session() as db:
            db.add_all(
                [
                    self._record(
                        record_key="jira:cloud:project:GRT:issue:GRT-1",
                        status=IncrementalRecordStatus.DEAD,
                        attempt=3,
                    ),
                    self._record(
                        record_key="jira:cloud:project:GRT:issue:GRT-2",
                        status=IncrementalRecordStatus.DEAD,
                        attempt=3,
                    ),
                ]
            )
            db.commit()

            result = recover_exhausted_dead_incremental_records(
                db,
                max_attempts=3,
                limit=1,
                now=now,
            )
            debouncing_count = (
                db.query(IncrementalRecordState)
                .filter(
                    IncrementalRecordState.status
                    == IncrementalRecordStatus.DEBOUNCING
                )
                .count()
            )

        self.assertEqual(result.scanned, 1)
        self.assertEqual(result.requeued, 1)
        self.assertEqual(debouncing_count, 1)

    @staticmethod
    def _record(
        *,
        record_key: str,
        status: IncrementalRecordStatus,
        attempt: int,
        last_error: str | None = None,
    ) -> IncrementalRecordState:
        now = datetime(2026, 5, 16, 0, 0, tzinfo=timezone.utc)
        return IncrementalRecordState(
            record_key=record_key,
            connector=SyncConnector.JIRA,
            scope_id="scope",
            record_type="issue",
            record_id=record_key.rsplit(":", 1)[-1],
            parent_type="project",
            parent_id="GRT",
            event_kind="updated",
            status=status,
            generation=1,
            attempt=attempt,
            last_event_at=now,
            debounce_until=now,
            updated_at=now,
            last_error=last_error,
        )
