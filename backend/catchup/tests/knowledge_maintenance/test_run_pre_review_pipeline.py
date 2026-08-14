from __future__ import annotations

import asyncio
from datetime import datetime
from datetime import timezone
from types import SimpleNamespace

import pytest

from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRunSpec
from catchup.knowledge_maintenance.ports.source_poller import SourcePollResult
from catchup.knowledge_maintenance.services import run_pre_review_pipeline as pipeline
from catchup.knowledge_maintenance.services.compile_entity_artifacts import (
    ArtifactCompileResult,
)
from catchup.knowledge_maintenance.services.resolve_claim_conflicts import (
    ClaimConflictResult,
)
from catchup.knowledge_maintenance.services.resolve_entity_candidates import (
    ResolutionResult,
)


class _WorkspaceBoundUow:
    workspace_id = 1


@pytest.mark.asyncio
async def test_pipeline_reraises_fatal_stage_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_pipeline(*args: object, **kwargs: object) -> object:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(pipeline, "_execute_pre_review_pipeline", fail_pipeline)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await pipeline.run_pre_review_pipeline(
            SourcePollResult(),
            workspace_id=1,
            normalizer=object(),  # type: ignore[arg-type]
            extractor=object(),  # type: ignore[arg-type]
            extraction_spec=ExtractionRunSpec(
                provider="test",
                extractor_version="1",
                ontology_id="wiki",
                vocabulary=ExtractionVocabulary(snapshot_id="v1"),
            ),
            extraction_contract_version="1",
            judge=None,
            uow_factory=_WorkspaceBoundUow,  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_extraction_audit_failure_escapes_with_raw_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_output = {"answer": "invalid"}
    observation = SimpleNamespace(
        id="observation-1",
        observation=SimpleNamespace(
            occurred_at=None,
            content="원문",
            metadata_entities=(),
        ),
    )
    pending = pipeline._PendingObservation(
        event=SimpleNamespace(id=1),  # type: ignore[arg-type]
        observation=observation,  # type: ignore[arg-type]
        source_type="channel_talk",
        source_updated_at=None,
        observed_at=datetime(2026, 8, 13, tzinfo=timezone.utc),
    )

    class FailingExtractor:
        async def extract(self, request: object) -> object:
            raise pipeline.ExtractionContractError(
                "계약 위반",
                raw_output=raw_output,
            )

    recorded: list[dict | None] = []

    def fail_audit(*args: object, **kwargs: object) -> None:
        recorded.append(kwargs["raw_output"])  # type: ignore[arg-type]
        raise RuntimeError("audit storage unavailable")

    monkeypatch.setattr(
        pipeline,
        "_load_pending_observations",
        lambda **_: (pending,),
    )
    monkeypatch.setattr(pipeline, "record_failed_extraction", fail_audit)

    with pytest.raises(RuntimeError, match="audit storage unavailable"):
        await pipeline._run_extraction(
            workspace_id=1,
            extractor=FailingExtractor(),  # type: ignore[arg-type]
            spec=ExtractionRunSpec(
                provider="test",
                extractor_version="1",
                ontology_id="wiki",
                vocabulary=ExtractionVocabulary(snapshot_id="v1"),
            ),
            contract_version="1",
            uow_factory=lambda: object(),  # type: ignore[arg-type]
            event_limit=None,
            clock=lambda: datetime(2026, 8, 13, tzinfo=timezone.utc),
        )

    assert recorded == [raw_output]


@pytest.mark.asyncio
async def test_missing_audit_node_fails_event_as_invariant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    event = SimpleNamespace(id=1, workspace_id=1, aggregate_id="observation-1")
    observation = SimpleNamespace(
        id="observation-1",
        observation=SimpleNamespace(
            occurred_at=None,
            content="원문",
            metadata_entities=(),
        ),
    )
    pending = pipeline._PendingObservation(
        event=event,  # type: ignore[arg-type]
        observation=observation,  # type: ignore[arg-type]
        source_type="channel_talk",
        source_updated_at=None,
        observed_at=now,
    )

    class FailingExtractor:
        async def extract(self, request: object) -> object:
            raise pipeline.ExtractionContractError("계약 위반")

    class PipelineEvents:
        failure_kind: pipeline.FailureKind | None = None

        def mark_failed(self, **kwargs: object) -> object:
            self.failure_kind = kwargs["kind"]  # type: ignore[assignment]
            return SimpleNamespace(
                status=pipeline.PipelineEventStatus.FAILED,
                available_at=now,
            )

    class Uow:
        pipeline_events = PipelineEvents()

        def __enter__(self) -> Uow:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def commit(self) -> None:
            return None

    uow = Uow()

    def fail_audit(*args: object, **kwargs: object) -> None:
        raise pipeline.ObservationNodeMissing("graph node missing")

    monkeypatch.setattr(
        pipeline,
        "_load_pending_observations",
        lambda **_: (pending,),
    )
    monkeypatch.setattr(pipeline, "record_failed_extraction", fail_audit)

    result = await pipeline._run_extraction(
        workspace_id=1,
        extractor=FailingExtractor(),  # type: ignore[arg-type]
        spec=ExtractionRunSpec(
            provider="test",
            extractor_version="1",
            ontology_id="wiki",
            vocabulary=ExtractionVocabulary(snapshot_id="v1"),
        ),
        contract_version="1",
        uow_factory=lambda: uow,  # type: ignore[arg-type]
        event_limit=None,
        clock=lambda: now,
    )

    assert uow.pipeline_events.failure_kind is pipeline.FailureKind.INVARIANT_VIOLATION
    assert result.failures[0].error_type == "ObservationNodeMissing"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failures", "expected_status"),
    [
        ((), pipeline.PreReviewPipelineStatus.COMPLETED),
        (
            (
                pipeline.PipelineItemFailure(
                    item_id="observation-1",
                    error_type="TimeoutError",
                    error_message="timed out",
                ),
            ),
            pipeline.PreReviewPipelineStatus.PARTIAL_FAILURE,
        ),
    ],
)
async def test_pipeline_reports_partial_failures_and_propagates_clock(
    monkeypatch: pytest.MonkeyPatch,
    failures: tuple[pipeline.PipelineItemFailure, ...],
    expected_status: pipeline.PreReviewPipelineStatus,
) -> None:
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    clock = lambda: now
    received_clocks: list[object] = []

    async def run_extraction(**kwargs: object) -> pipeline.ExtractionStageResult:
        received_clocks.append(kwargs["clock"])
        return pipeline.ExtractionStageResult(failures=failures)

    def resolve_conflicts(**kwargs: object) -> ClaimConflictResult:
        received_clocks.append(kwargs["clock"])
        return ClaimConflictResult()

    def compile_artifacts(*args: object, **kwargs: object) -> ArtifactCompileResult:
        received_clocks.append(kwargs["clock"])
        # 이미 결정된 동일 멱등 키는 정상적인 no-op이며 상태를 낮추지 않는다.
        return ArtifactCompileResult(proposals_conflicted=1)

    def resolve_candidates(**_: object) -> ResolutionResult:
        asyncio.run(asyncio.sleep(0))
        return ResolutionResult()

    monkeypatch.setattr(pipeline, "_run_extraction", run_extraction)
    monkeypatch.setattr(
        pipeline,
        "resolve_entity_candidates",
        resolve_candidates,
    )
    monkeypatch.setattr(pipeline, "resolve_claim_conflicts", resolve_conflicts)
    monkeypatch.setattr(pipeline, "compile_entity_artifacts", compile_artifacts)

    result = await pipeline.run_pre_review_pipeline(
        SourcePollResult(),
        workspace_id=1,
        normalizer=object(),  # type: ignore[arg-type]
        extractor=object(),  # type: ignore[arg-type]
        extraction_spec=ExtractionRunSpec(
            provider="test",
            extractor_version="1",
            ontology_id="wiki",
            vocabulary=ExtractionVocabulary(snapshot_id="v1"),
        ),
        extraction_contract_version="1",
        judge=None,
        uow_factory=_WorkspaceBoundUow,  # type: ignore[arg-type]
        clock=clock,
    )

    assert result.status is expected_status
    assert received_clocks == [clock, clock, clock]


@pytest.mark.parametrize(
    ("skipped", "held_back", "resolution_failures", "expected"),
    [
        (1, 0, 0, pipeline.PreReviewPipelineStatus.PARTIAL_FAILURE),
        (0, 1, 0, pipeline.PreReviewPipelineStatus.PARTIAL_FAILURE),
        (0, 0, 1, pipeline.PreReviewPipelineStatus.PARTIAL_FAILURE),
        (0, 0, 0, pipeline.PreReviewPipelineStatus.COMPLETED),
    ],
)
def test_status_reports_every_incomplete_work_signal(
    skipped: int,
    held_back: int,
    resolution_failures: int,
    expected: pipeline.PreReviewPipelineStatus,
) -> None:
    status = pipeline._derive_status(
        skipped_item_count=skipped,
        held_back_item_count=held_back,
        intake_failure=None,
        extraction=pipeline.ExtractionStageResult(),
        resolution=ResolutionResult(groups_failed=resolution_failures),
    )

    assert status is expected
