from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime
from datetime import timezone
from types import SimpleNamespace

import pytest

from catchup.utils import scheduler


class _FakeCronTrigger:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


class _FakeScheduler:
    instances: list["_FakeScheduler"] = []

    def __init__(self, *, timezone) -> None:
        self.timezone = timezone
        self.jobs: list[dict] = []
        self.started = False
        self.shutdown_wait: bool | None = None
        self.__class__.instances.append(self)

    def add_job(self, func, **kwargs) -> None:
        self.jobs.append({"func": func, **kwargs})

    def get_job(self, job_id: str):
        return next((job for job in self.jobs if job["id"] == job_id), None)

    def reschedule_job(self, job_id: str, **kwargs):
        job = self.get_job(job_id)
        if job is None:
            raise LookupError(job_id)
        job["rescheduled"] = kwargs
        return job

    def remove_job(self, job_id: str) -> None:
        self.jobs = [job for job in self.jobs if job["id"] != job_id]

    def start(self) -> None:
        self.started = True

    def shutdown(self, *, wait: bool) -> None:
        self.shutdown_wait = wait


@pytest.fixture(autouse=True)
def _reset_scheduler(monkeypatch):
    _FakeScheduler.instances.clear()
    monkeypatch.setattr(scheduler, "_scheduler", None)
    monkeypatch.setattr(scheduler, "AsyncIOScheduler", _FakeScheduler)
    monkeypatch.setattr(scheduler, "CronTrigger", _FakeCronTrigger)
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(
        scheduler,
        "list_test_knowledge_maintenance_settings",
        lambda _db, workspace_id=None: [],
    )
    yield
    monkeypatch.setattr(scheduler, "_scheduler", None)
    _FakeScheduler.instances.clear()


def test_scheduler_registers_one_sequential_v2_backfill_job(monkeypatch) -> None:
    monkeypatch.setattr(
        scheduler.settings,
        "VECTOR_STORE_V2_BACKFILL_SCHEDULE_ENABLED",
        True,
    )
    monkeypatch.setattr(scheduler.settings, "VECTOR_STORE_V2_BACKFILL_CRON_HOUR", 0)
    monkeypatch.setattr(scheduler.settings, "VECTOR_STORE_V2_BACKFILL_CRON_MINUTE", 0)

    scheduler.init_scheduler()

    fake_scheduler = _FakeScheduler.instances[0]
    job_ids = {job["id"] for job in fake_scheduler.jobs}
    assert "vector_store_v2_sequential_backfill" in job_ids
    assert "github_pr_v2_backfill" not in job_ids
    assert "github_issue_v2_backfill" not in job_ids
    assert "slack_message_v2_backfill" not in job_ids
    assert "jira_issue_v2_backfill" not in job_ids

    backfill_jobs = [
        job
        for job in fake_scheduler.jobs
        if job["id"] == "vector_store_v2_sequential_backfill"
    ]
    assert len(backfill_jobs) == 1
    backfill_job = backfill_jobs[0]
    assert backfill_job["func"] is scheduler.run_vector_store_v2_sequential_backfill_job
    assert backfill_job["name"] == "Vector Store v2 Sequential Backfill"
    assert backfill_job["replace_existing"] is True
    assert backfill_job["misfire_grace_time"] == 900
    assert backfill_job["max_instances"] == 1
    assert backfill_job["trigger"].kwargs == {
        "hour": 0,
        "minute": 0,
        "timezone": scheduler.SEOUL_TZ,
    }


def test_vector_store_v2_backfill_sequence_orders_providers() -> None:
    assert [spec.key for spec in scheduler.VECTOR_STORE_V2_BACKFILL_SEQUENCE] == [
        "confluence/page",
        "confluence/blogpost",
    ]


def test_scheduler_registers_enabled_knowledge_maintenance_setting(
    monkeypatch,
) -> None:
    setting = SimpleNamespace(
        id=7,
        enabled=True,
        execution_anchor_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
        interval_minutes=30,
    )
    monkeypatch.setattr(
        scheduler,
        "list_test_knowledge_maintenance_settings",
        lambda _db, workspace_id=None: [setting],
    )

    scheduler.init_scheduler()

    job = _FakeScheduler.instances[0].get_job("test-knowledge-maintenance:7")
    assert job is not None
    assert job["func"] is scheduler.run_channel_talk_pre_review_job
    assert job["trigger"] == "interval"
    assert job["minutes"] == 30
    assert job["start_date"] == setting.execution_anchor_at
    assert job["max_instances"] == 1
    assert job["coalesce"] is True


def test_apply_knowledge_maintenance_schedule_updates_and_removes_job() -> None:
    fake_scheduler = _FakeScheduler(timezone=scheduler.SEOUL_TZ)
    scheduler._scheduler = fake_scheduler
    setting = SimpleNamespace(
        id=9,
        enabled=True,
        execution_anchor_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
        interval_minutes=15,
    )

    scheduler.apply_test_knowledge_maintenance_schedule(setting)
    setting.interval_minutes = 45
    scheduler.apply_test_knowledge_maintenance_schedule(setting)

    job = fake_scheduler.get_job("test-knowledge-maintenance:9")
    assert job["rescheduled"]["minutes"] == 45

    setting.enabled = False
    scheduler.apply_test_knowledge_maintenance_schedule(setting)
    assert fake_scheduler.get_job("test-knowledge-maintenance:9") is None


def test_scheduler_skips_v2_backfill_job_when_flag_is_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        scheduler.settings,
        "VECTOR_STORE_V2_BACKFILL_SCHEDULE_ENABLED",
        False,
    )

    scheduler.init_scheduler()

    fake_scheduler = _FakeScheduler.instances[0]
    job_ids = {job["id"] for job in fake_scheduler.jobs}
    assert "vector_store_v2_sequential_backfill" not in job_ids
    assert all("v2_backfill" not in job_id for job_id in job_ids)
