from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import cast

import pytest
from apscheduler.job import Job

from catchup.utils.rescheduler import reschedule_interval_job
from catchup.utils.rescheduler import reschedule_one_shot_job


class _FakeScheduler:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.job = cast(Job, object())

    def reschedule_job(self, job_id: str, **kwargs) -> Job:
        self.calls.append((job_id, kwargs))
        return self.job


def test_reschedule_one_shot_job_uses_date_trigger() -> None:
    scheduler = _FakeScheduler()
    next_run_at = datetime(2026, 8, 10, 15, tzinfo=timezone.utc)

    result = reschedule_one_shot_job(
        scheduler,
        job_id="llm-wiki:workspace:1",
        next_run_at=next_run_at,
    )

    assert result is scheduler.job
    assert scheduler.calls == [
        (
            "llm-wiki:workspace:1",
            {"trigger": "date", "run_date": next_run_at},
        )
    ]


def test_reschedule_one_shot_job_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone"):
        reschedule_one_shot_job(
            _FakeScheduler(),
            job_id="llm-wiki:workspace:1",
            next_run_at=datetime(2026, 8, 10, 15),
        )


def test_reschedule_interval_job_uses_anchor_and_minutes() -> None:
    scheduler = _FakeScheduler()
    anchor_at = datetime(2026, 8, 10, 15, tzinfo=timezone.utc)

    result = reschedule_interval_job(
        scheduler,
        job_id="test-knowledge-maintenance:1",
        anchor_at=anchor_at,
        interval_minutes=30,
    )

    assert result is scheduler.job
    assert scheduler.calls == [
        (
            "test-knowledge-maintenance:1",
            {
                "trigger": "interval",
                "minutes": 30,
                "start_date": anchor_at,
            },
        )
    ]


@pytest.mark.parametrize("interval_minutes", [0, -1])
def test_reschedule_interval_job_rejects_non_positive_interval(
    interval_minutes: int,
) -> None:
    with pytest.raises(ValueError, match="positive"):
        reschedule_interval_job(
            _FakeScheduler(),
            job_id="test-knowledge-maintenance:1",
            anchor_at=datetime(2026, 8, 10, 15, tzinfo=timezone.utc),
            interval_minutes=interval_minutes,
        )
