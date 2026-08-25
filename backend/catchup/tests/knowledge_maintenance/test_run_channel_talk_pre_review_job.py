from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime
from datetime import timezone
from types import SimpleNamespace

import pytest

from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.ports.source_poller import SkippedItem
from catchup.knowledge_maintenance.ports.source_poller import SourcePollResult
from catchup.knowledge_maintenance.services import (
    run_channel_talk_pre_review_job as job,
)
from catchup.knowledge_maintenance.services.run_pre_review_pipeline import (
    PreReviewPipelineStatus,
)


class _FakePoller:
    result = SourcePollResult()
    calls: list[dict] = []

    def __init__(self, **kwargs) -> None:
        self.constructor_kwargs = kwargs

    async def poll(self, **kwargs) -> SourcePollResult:
        self.__class__.calls.append(kwargs)
        return self.__class__.result


class _FakeLlm:
    def with_structured_output(self, *_args, **_kwargs):
        return object()


class _FakeLlmService:
    def get_llm(self):
        return _FakeLlm()


@pytest.fixture(autouse=True)
def _reset_poller() -> None:
    _FakePoller.result = SourcePollResult()
    _FakePoller.calls = []


def _patch_dependencies(monkeypatch) -> None:
    setting = SimpleNamespace(
        id=3,
        workspace_id=11,
        channel_talk_credential_id=5,
        enabled=True,
    )
    credential = SimpleNamespace(
        channel_id="channel-1",
        access_key="key",
        access_secret="secret",
    )
    monkeypatch.setattr(job, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(
        job,
        "get_test_knowledge_maintenance_setting",
        lambda _db, setting_id: setting,
    )
    monkeypatch.setattr(
        job,
        "load_channel_talk_connection_by_id",
        lambda _credential_id: credential,
    )
    monkeypatch.setattr(
        job,
        "_derive_lookback_start",
        lambda *_args, **_kwargs: datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(job, "ChannelTalkUserChatPoller", _FakePoller)
    monkeypatch.setattr(
        job,
        "BedrockIdentityJudge",
        lambda *_args, **_kwargs: "judge",
    )
    monkeypatch.setattr(
        job,
        "_load_published_vocabulary",
        lambda *_args, **_kwargs: ExtractionVocabulary(snapshot_id="v1"),
    )
    monkeypatch.setattr(job, "get_llm_service", lambda **_kwargs: _FakeLlmService())


@pytest.mark.asyncio
async def test_job_polls_then_calls_pre_review_pipeline(monkeypatch) -> None:
    _patch_dependencies(monkeypatch)
    pipeline_calls = []

    async def _run_pipeline(poll_result, **kwargs):
        pipeline_calls.append((poll_result, kwargs))
        return SimpleNamespace(status=PreReviewPipelineStatus.COMPLETED)

    monkeypatch.setattr(job, "run_pre_review_pipeline", _run_pipeline)

    result = await job.run_channel_talk_pre_review_job(3)

    assert result.status is PreReviewPipelineStatus.COMPLETED
    assert _FakePoller.calls[0]["workspace_id"] == 11
    assert len(pipeline_calls) == 1
    assert pipeline_calls[0][0] is _FakePoller.result
    assert pipeline_calls[0][1]["workspace_id"] == 11
    assert pipeline_calls[0][1]["judge"] == "judge"


@pytest.mark.asyncio
async def test_job_rejects_incomplete_poll_before_pipeline(monkeypatch) -> None:
    _patch_dependencies(monkeypatch)
    _FakePoller.result = SourcePollResult(
        skipped=[
            SkippedItem(
                item_id="chat-1",
                ordering_marker=datetime(2026, 8, 1, tzinfo=timezone.utc),
                reason="fetch_failed",
            )
        ]
    )

    async def _unexpected_pipeline(*_args, **_kwargs):
        raise AssertionError("pipeline must not run")

    monkeypatch.setattr(job, "run_pre_review_pipeline", _unexpected_pipeline)

    with pytest.raises(RuntimeError, match="incomplete"):
        await job.run_channel_talk_pre_review_job(3)


@pytest.mark.asyncio
@pytest.mark.parametrize("auto_merge_enabled", [True, False])
async def test_job_passes_auto_merge_kill_switch_to_pipeline(
    monkeypatch, auto_merge_enabled: bool
) -> None:
    _patch_dependencies(monkeypatch)
    monkeypatch.setattr(
        job.settings,
        "KNOWLEDGE_AUTO_MERGE_ENABLED",
        auto_merge_enabled,
    )
    pipeline_calls = []

    async def _run_pipeline(poll_result, **kwargs):
        pipeline_calls.append(kwargs)
        return SimpleNamespace(status=PreReviewPipelineStatus.COMPLETED)

    monkeypatch.setattr(job, "run_pre_review_pipeline", _run_pipeline)

    await job.run_channel_talk_pre_review_job(3)

    assert pipeline_calls[0]["auto_merge_enabled"] is auto_merge_enabled


@pytest.mark.asyncio
async def test_job_passes_narrator_to_pipeline(monkeypatch) -> None:
    _patch_dependencies(monkeypatch)
    llm_service_kwargs: list[dict] = []
    monkeypatch.setattr(
        job,
        "get_llm_service",
        lambda **kwargs: llm_service_kwargs.append(kwargs) or _FakeLlmService(),
    )
    pipeline_calls = []

    async def _run_pipeline(poll_result, **kwargs):
        pipeline_calls.append(kwargs)
        return SimpleNamespace(status=PreReviewPipelineStatus.COMPLETED)

    monkeypatch.setattr(job, "run_pre_review_pipeline", _run_pipeline)

    await job.run_channel_talk_pre_review_job(3)

    assert isinstance(pipeline_calls[0]["narrator"], job.LlmBlockNarrator)
    assert llm_service_kwargs[0]["read_timeout"] == 120
