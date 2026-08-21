"""
Source 변경을 Human Review 직전의 Artifact Proposal까지 처리한다.

각 Stage의 정책과 transaction은 기존 서비스가 소유한다.
이 모듈은 폴링의 부분 실패가 증분 커서를 건너뛰지 않게 막고,
Stage 1부터 Stage 5까지의 실행 순서와 ``observation.ready`` event 정산만 맡는다.
"""

# ruff: noqa: I001

from __future__ import annotations

import asyncio

from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from enum import StrEnum
from time import perf_counter

from sqlalchemy.exc import SQLAlchemyError

from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import KnowledgeMaintenanceUnitOfWork
from catchup.knowledge_maintenance.contracts.extraction import KnowledgeExtractionRequest
from catchup.knowledge_maintenance.contracts.source_change import SourceChangeEnvelope
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRunSpec
from catchup.knowledge_maintenance.domain.observation import StoredObservation
from catchup.knowledge_maintenance.domain.pipeline_event import FailureKind
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEvent
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEventStatus
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEventType
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.temporal import resolve_reference_time
from catchup.knowledge_maintenance.ports.extraction import ExtractionAPIError
from catchup.knowledge_maintenance.ports.extraction import ExtractionContractError
from catchup.knowledge_maintenance.ports.extraction import KnowledgeExtractionPort
from catchup.knowledge_maintenance.ports.identity_judge import IdentityJudge
from catchup.knowledge_maintenance.ports.name_embedder import NameEmbedder
from catchup.knowledge_maintenance.ports.observation_normalizer import ObservationNormalizer
from catchup.knowledge_maintenance.ports.source_poller import SkippedItem
from catchup.knowledge_maintenance.ports.source_poller import SourcePollResult
from catchup.knowledge_maintenance.services.compile_entity_artifacts import ArtifactCompileResult
from catchup.knowledge_maintenance.services.compile_entity_artifacts import (
    compile_definition_artifacts,
)
from catchup.knowledge_maintenance.services.ingest_and_normalize import SourceIntakeResult
from catchup.knowledge_maintenance.services.ingest_and_normalize import ingest_and_normalize
from catchup.knowledge_maintenance.services.resolve_claim_conflicts import ClaimConflictResult
from catchup.knowledge_maintenance.services.resolve_claim_conflicts import resolve_claim_conflicts
from catchup.knowledge_maintenance.services.resolve_entity_candidates import ResolutionResult
from catchup.knowledge_maintenance.services.resolve_entity_candidates import resolve_entity_candidates
from catchup.knowledge_maintenance.services.store_knowledge_candidates import ObservationNodeMissing
from catchup.knowledge_maintenance.services.store_knowledge_candidates import record_failed_extraction
from catchup.knowledge_maintenance.services.store_knowledge_candidates import store_knowledge_candidates
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

UnitOfWorkFactory = Callable[[], KnowledgeMaintenanceUnitOfWork]


class PollWindowTruncatedError(RuntimeError):
    """변경 목록의 끝을 보지 못해 어떤 Envelope도 안전하지 않음을 표시."""


class PreReviewPipelineStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"


@dataclass(frozen=True, slots=True)
class PipelineItemFailure:
    """한 Stage에서 처리하지 못한 원본 또는 event를 기록한다."""

    item_id: str
    error_type: str
    error_message: str
    retry_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ExtractionStageResult:
    """추출 Stage가 Observation batch 단위로 처리한 결과."""

    events_loaded: int = 0
    batches_stored: int = 0
    batches_reused: int = 0
    failures: tuple[PipelineItemFailure, ...] = ()


@dataclass(frozen=True, slots=True)
class PreReviewPipelineResult:
    """Scheduler가 다음 실행과 운영 알림을 결정할 수 있는 전체 결과."""

    status: PreReviewPipelineStatus
    intake_results: tuple[SourceIntakeResult, ...]
    skipped_item_ids: tuple[str, ...]
    held_back_item_ids: tuple[str, ...]
    intake_failure: PipelineItemFailure | None
    extraction: ExtractionStageResult
    resolution: ResolutionResult
    claim_conflicts: ClaimConflictResult
    artifacts: ArtifactCompileResult


@dataclass(frozen=True, slots=True)
class _PendingObservation:
    event: PipelineEvent
    observation: StoredObservation | None
    source_type: str | None
    source_updated_at: datetime | None
    observed_at: datetime | None
    source_identity: SourceIdentity | None = None
    load_error: str | None = None


async def run_pre_review_pipeline(
    poll_result: SourcePollResult,
    *,
    workspace_id: int,
    normalizer: ObservationNormalizer,
    extractor: KnowledgeExtractionPort,
    extraction_spec: ExtractionRunSpec,
    extraction_contract_version: str,
    judge: IdentityJudge | None,
    uow_factory: UnitOfWorkFactory,
    name_embedder: NameEmbedder | None = None,
    event_limit: int | None = None,
    clock: Callable[[], datetime] | None = None,
) -> PreReviewPipelineResult:
    """
    Source Change를 Human Review 이전인 Artifact Proposal까지 처리하는 진입점.

    항목 단위 실패는 `PARTIAL_FAILURE` 결과로 반환하며
    파이프라인 자체를 계속할 수 없는 예외는 `failed`로 처리하여 호출자에게 전달한다.
    """
    started_at = perf_counter()
    pipeline_logger = logger.bind(
        workspace_id=workspace_id,
        pipeline="pre_review",
    )
    try:
        result = await _execute_pre_review_pipeline(
            poll_result,
            workspace_id=workspace_id,
            normalizer=normalizer,
            extractor=extractor,
            extraction_spec=extraction_spec,
            extraction_contract_version=extraction_contract_version,
            judge=judge,
            uow_factory=uow_factory,
            name_embedder=name_embedder,
            event_limit=event_limit,
            clock=clock,
        )
    except Exception as error:
        pipeline_logger.exception(
            "knowledge_maintenance.pre_review_pipeline.failed",
            status="failed",
            duration_ms=round((perf_counter() - started_at) * 1000),
            error_type=type(error).__name__,
        )
        raise

    pipeline_logger.info(
        "knowledge_maintenance.pre_review_pipeline.completed",
        status=result.status.value,
        duration_ms=round((perf_counter() - started_at) * 1000),
        intake_count=len(result.intake_results),
        skipped_item_count=len(result.skipped_item_ids),
        held_back_item_count=len(result.held_back_item_ids),
        intake_failed=result.intake_failure is not None,
        extraction_loaded_count=result.extraction.events_loaded,
        extraction_stored_count=result.extraction.batches_stored,
        extraction_reused_count=result.extraction.batches_reused,
        extraction_failed_count=len(result.extraction.failures),
        artifact_created_count=result.artifacts.proposals_created,
        artifact_revived_count=result.artifacts.proposals_revived,
    )
    return result


async def _execute_pre_review_pipeline(
    poll_result: SourcePollResult,
    *,
    workspace_id: int,
    normalizer: ObservationNormalizer,
    extractor: KnowledgeExtractionPort,
    extraction_spec: ExtractionRunSpec,
    extraction_contract_version: str,
    judge: IdentityJudge | None,
    uow_factory: UnitOfWorkFactory,
    name_embedder: NameEmbedder | None = None,
    event_limit: int | None = None,
    clock: Callable[[], datetime] | None = None,
) -> PreReviewPipelineResult:
    """
    Source Change를 Human Review 입력인 Artifact Proposal까지 진행시키는 파이프라인

    ``uow_factory``는 호출마다 새 transaction 경계를 반환해야 하며 Artifact repository가 ``workspace_id``로 고정된 UoW를 만들어야 한다.
    목록이 잘린 poll 결과는 쓰기를 시작하기 전에 거부한다.
    개별 intake 실패는 증분 커서가 실패 항목을 지나가지 않도록 그 뒤 Envelope를 보류한다.
    """
    _validate_inputs(
        poll_result,
        workspace_id=workspace_id,
        extraction_contract_version=extraction_contract_version,
        event_limit=event_limit,
    )
    if poll_result.list_truncated:
        raise PollWindowTruncatedError(
            "source poll result is truncated; no envelope is safe to ingest"
        )

    artifact_uow = _require_workspace_bound_uow(
        uow_factory,
        workspace_id=workspace_id,
    )

    clock = clock or _utcnow

    # 삭제 예정
    ingest_now, barrier_held_back = _split_by_barrier(
        poll_result.envelopes,
        poll_result.skipped,
    )

    intake_results, intake_failure, failure_held_back = _run_intake(
        ingest_now,
        normalizer=normalizer,
        uow_factory=uow_factory,
        clock=clock,
    )

    extraction = await _run_extraction(
        workspace_id=workspace_id,
        extractor=extractor,
        spec=extraction_spec,
        contract_version=extraction_contract_version.strip(),
        uow_factory=uow_factory,
        event_limit=event_limit,
        clock=clock,
    )

    resolution = await asyncio.to_thread(
        resolve_entity_candidates,
        workspace_id=workspace_id,
        judge=judge,
        uow=uow_factory(),
        name_embedder=name_embedder,
    )

    claim_conflicts = resolve_claim_conflicts(
        workspace_id=workspace_id,
        vocabulary=extraction_spec.vocabulary,
        uow=uow_factory(),
        clock=clock,
    )

    artifacts = compile_definition_artifacts(
        artifact_uow,
        workspace_id=workspace_id,
        vocabulary=extraction_spec.vocabulary,
        clock=clock,
    )

    held_back = (*barrier_held_back, *failure_held_back)
    status = _derive_status(
        skipped_item_count=len(poll_result.skipped),
        held_back_item_count=len(held_back),
        intake_failure=intake_failure,
        extraction=extraction,
        resolution=resolution,
        artifacts=artifacts,
    )
    result = PreReviewPipelineResult(
        status=status,
        intake_results=tuple(intake_results),
        skipped_item_ids=tuple(item.item_id for item in poll_result.skipped),
        held_back_item_ids=tuple(
            _item_id(envelope) for envelope in held_back
        ),
        intake_failure=intake_failure,
        extraction=extraction,
        resolution=resolution,
        claim_conflicts=claim_conflicts,
        artifacts=artifacts,
    )
    return result


def _validate_inputs(
    poll_result: SourcePollResult,
    *,
    workspace_id: int,
    extraction_contract_version: str,
    event_limit: int | None,
) -> None:
    if workspace_id <= 0:
        raise ValueError("workspace_id must be greater than 0")
    if not extraction_contract_version.strip():
        raise ValueError("extraction_contract_version must not be blank")
    if event_limit is not None and event_limit <= 0:
        raise ValueError("event_limit must be greater than 0")
    mismatched = [
        _item_id(envelope)
        for envelope in poll_result.envelopes
        if envelope.workspace_id != workspace_id
    ]
    if mismatched:
        raise ValueError(
            f"poll result contains envelopes from another workspace: {mismatched}"
        )


def _item_id(envelope: SourceChangeEnvelope) -> str:
    return envelope.source_identity.external_document_id


def _require_workspace_bound_uow(
    uow_factory: UnitOfWorkFactory,
    *,
    workspace_id: int,
) -> KnowledgeMaintenanceUnitOfWork:

    uow = uow_factory()
    if uow.workspace_id != workspace_id:
        raise ValueError(
            "uow_factory must create a UoW bound to the pipeline workspace"
        )
    return uow


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# TODO(review): Poller의 수집 실패를 파이프라인까지 전달하지 않는다.
# Poller가 재시도 후 완전한 결과를 전달하거나 해당 회차를 실패 처리하면
# 이 barrier를 삭제한다.
def _split_by_barrier(
    envelopes: Sequence[SourceChangeEnvelope],
    skipped: Sequence[SkippedItem],
) -> tuple[list[SourceChangeEnvelope], list[SourceChangeEnvelope]]:
    """수집하지 못한 원본보다 최신인 Envelope를 다음 회차로 보류한다."""
    if not skipped:
        return list(envelopes), []

    markers = [item.ordering_marker for item in skipped]
    if any(marker is None for marker in markers):
        return [], list(envelopes)

    barrier = min(marker for marker in markers if marker is not None)
    ingest_now = [
        envelope for envelope in envelopes if _ordering_marker(envelope) < barrier
    ]
    held_back = [
        envelope for envelope in envelopes if _ordering_marker(envelope) >= barrier
    ]
    return ingest_now, held_back


def _ordering_marker(envelope: SourceChangeEnvelope) -> datetime:
    return envelope.source_updated_at or envelope.observed_at


def _run_intake(
    envelopes: Sequence[SourceChangeEnvelope],
    *,
    normalizer: ObservationNormalizer,
    uow_factory: UnitOfWorkFactory,
    clock: Callable[[], datetime],
) -> tuple[
    list[SourceIntakeResult],
    PipelineItemFailure | None,
    list[SourceChangeEnvelope],
]:
    """Stage 1~2를 오래된 순서로 실행하고 첫 실패에서 멈춘다."""
    ordered = sorted(envelopes, key=_ordering_marker)
    completed: list[SourceIntakeResult] = []
    for index, envelope in enumerate(ordered):
        try:
            completed.append(
                ingest_and_normalize(
                    envelope,
                    normalizer=normalizer,
                    uow=uow_factory(),
                    clock=clock,
                )
            )
        except Exception as error:
            failure = PipelineItemFailure(
                item_id=_item_id(envelope),
                error_type=type(error).__name__,
                error_message=str(error),
            )
            logger.bind(
                workspace_id=envelope.workspace_id,
                pipeline="pre_review",
                stage="intake",
            ).exception(
                "knowledge_maintenance.pre_review_pipeline.intake_failed",
                status="failed",
                item_id=failure.item_id,
                error_type=failure.error_type,
            )
            return completed, failure, list(ordered[index + 1 :])
    return completed, None, []


async def _run_extraction(
    *,
    workspace_id: int,
    extractor: KnowledgeExtractionPort,
    spec: ExtractionRunSpec,
    contract_version: str,
    uow_factory: UnitOfWorkFactory,
    event_limit: int | None,
    clock: Callable[[], datetime],
) -> ExtractionStageResult:
    extraction_logger = logger.bind(
        workspace_id=workspace_id,
        pipeline="pre_review",
        stage="extraction",
    )
    pending = _load_pending_observations(
        workspace_id=workspace_id,
        uow_factory=uow_factory,
        limit=event_limit,
        now=clock(),
    )
    stored_batches = 0
    reused_batches = 0
    failures: list[PipelineItemFailure] = []

    # ponytail: sequential extraction bounds LLM load; add bounded gather only
    # when measured scheduler throughput requires it.
    for item in pending:
        if item.load_error is not None:
            failures.append(
                _fail_event(
                    item.event,
                    RuntimeError(item.load_error),
                    kind=FailureKind.INVARIANT_VIOLATION,
                    uow_factory=uow_factory,
                    clock=clock,
                )
            )
            continue

        observation = item.observation
        if observation is None or item.observed_at is None or item.source_type is None:
            failures.append(
                _fail_event(
                    item.event,
                    RuntimeError("pending observation is incomplete"),
                    kind=FailureKind.INVARIANT_VIOLATION,
                    uow_factory=uow_factory,
                    clock=clock,
                )
            )
            continue

        reference_time, reference_time_source = resolve_reference_time(
            occurred_at=observation.observation.occurred_at,
            source_updated_at=item.source_updated_at,
            observed_at=item.observed_at,
        )
        extraction_logger.info(
            "knowledge_maintenance.pre_review_pipeline.extraction_reference_time_resolved",
            event_id=item.event.id,
            observation_id=str(observation.id),
            reference_time=reference_time.isoformat(),
            reference_time_source=reference_time_source,
        )
        content = observation.observation.content
        if content is None:
            failures.append(
                _fail_event(
                    item.event,
                    RuntimeError("pending observation has no content"),
                    kind=FailureKind.INVARIANT_VIOLATION,
                    uow_factory=uow_factory,
                    clock=clock,
                )
            )
            continue

        request = KnowledgeExtractionRequest(
            content=content,
            source_type=item.source_type,
            metadata_entities=observation.observation.metadata_entities,
            vocabulary=spec.vocabulary,
            reference_time=reference_time,
            contract_version=contract_version,
            workspace_id=workspace_id,
            external_document_id=(
                item.source_identity.external_document_id
                if item.source_identity is not None
                else None
            ),
        )
        try:
            batch = await extractor.extract(request)
        except (ExtractionContractError, ExtractionAPIError) as error:
            # 실패 기록까지 잃으면 재시도 대상은 남아도 운영자가 원인을
            # 추적할 수 없다. 감사 기록 저장 실패는 부분 실패가 아니라
            # 파이프라인 자체의 저장 실패로 호출자까지 전파한다.
            try:
                record_failed_extraction(
                    observation,
                    spec=spec,
                    error=f"{type(error).__name__}: {error}",
                    uow=uow_factory(),
                    raw_output=(
                        error.raw_output
                        if isinstance(error, ExtractionContractError)
                        else None
                    ),
                    clock=clock,
                )
            except ObservationNodeMissing as audit_error:
                # graph node 부재는 같은 입력을 다시 추출해도 복구되지 않는다.
                # 원래 추출 오류 대신 이 불변식 위반으로 event를 종결한다.
                failures.append(
                    _fail_event(
                        item.event,
                        audit_error,
                        kind=FailureKind.INVARIANT_VIOLATION,
                        uow_factory=uow_factory,
                        clock=clock,
                    )
                )
                continue
            failures.append(
                _fail_event(
                    item.event,
                    error,
                    kind=(
                        FailureKind.CONTRACT_VIOLATION
                        if isinstance(error, ExtractionContractError)
                        else FailureKind.API_ERROR
                    ),
                    uow_factory=uow_factory,
                    clock=clock,
                )
            )
            continue

        try:
            candidate_result = store_knowledge_candidates(
                observation,
                batch,
                spec=spec,
                uow=uow_factory(),
                clock=clock,
            )
        except (ObservationNodeMissing, SQLAlchemyError) as error:
            failures.append(
                _fail_event(
                    item.event,
                    error,
                    kind=(
                        FailureKind.INVARIANT_VIOLATION
                        if isinstance(error, ObservationNodeMissing)
                        else FailureKind.STORAGE_ERROR
                    ),
                    uow_factory=uow_factory,
                    clock=clock,
                )
            )
            continue

        # 후보 저장과 event 완료는 별도 transaction이다. 완료 기록이 실패해
        # 재실행돼도 저장 단계의 멱등 키가 같은 추출 batch를 재사용한다.
        _mark_event_processed(item.event, uow_factory=uow_factory, clock=clock)
        if candidate_result.reused:
            reused_batches += 1
        else:
            stored_batches += 1

    return ExtractionStageResult(
        events_loaded=len(pending),
        batches_stored=stored_batches,
        batches_reused=reused_batches,
        failures=tuple(failures),
    )


def _load_pending_observations(
    *,
    workspace_id: int,
    uow_factory: UnitOfWorkFactory,
    limit: int | None,
    now: datetime,
) -> tuple[_PendingObservation, ...]:
    """pending event와 Observation·SourceVersion의 시간 재료를 함께 읽는다."""
    pending: list[_PendingObservation] = []
    with uow_factory() as uow:
        # 현재 Scheduler는 한 workspace의 파이프라인을 직렬 실행하므로 조회만
        # 한다. 병렬 worker를 열 때는 이 경계에 lease 기반 claim을 추가한다.
        events = uow.pipeline_events.list_pending(
            workspace_id=workspace_id,
            event_type=PipelineEventType.OBSERVATION_READY,
            now=now,
            limit=limit,
        )
        for event in events:
            observation = uow.observations.get_by_id(
                workspace_id=workspace_id,
                observation_id=event.aggregate_id,
            )
            if observation is None:
                pending.append(
                    _missing_pending(event, "observation does not exist in workspace")
                )
                continue
            version = uow.source_versions.get_by_id(
                workspace_id=workspace_id,
                source_version_id=observation.source_version_id,
            )
            if version is None:
                pending.append(
                    _missing_pending(
                        event, "source version does not exist in workspace"
                    )
                )
                continue
            pending.append(
                _PendingObservation(
                    event=event,
                    observation=observation,
                    source_type=version.source_type,
                    source_updated_at=version.source_updated_at,
                    observed_at=version.observed_at,
                    source_identity=version.source_identity,
                )
            )
    return tuple(pending)


def _missing_pending(event: PipelineEvent, message: str) -> _PendingObservation:
    return _PendingObservation(
        event=event,
        observation=None,
        source_type=None,
        source_updated_at=None,
        observed_at=None,
        load_error=message,
    )


def _fail_event(
    event: PipelineEvent,
    error: Exception,
    *,
    kind: FailureKind,
    uow_factory: UnitOfWorkFactory,
    clock: Callable[[], datetime],
) -> PipelineItemFailure:
    message = str(error)
    with uow_factory() as uow:
        settled = uow.pipeline_events.mark_failed(
            event_id=event.id,
            kind=kind,
            error=f"{type(error).__name__}: {message}",
            now=clock(),
        )
        uow.commit()
    retry_at = (
        settled.available_at if settled.status is PipelineEventStatus.PENDING else None
    )
    logger.bind(
        workspace_id=event.workspace_id,
        pipeline="pre_review",
        stage="extraction",
    ).warning(
        "knowledge_maintenance.pre_review_pipeline.extraction_failed",
        status="failed",
        event_id=event.id,
        observation_id=str(event.aggregate_id),
        error_type=type(error).__name__,
        retry_at=retry_at.isoformat() if retry_at is not None else None,
    )
    return PipelineItemFailure(
        item_id=str(event.aggregate_id),
        error_type=type(error).__name__,
        error_message=message,
        retry_at=retry_at,
    )


def _mark_event_processed(
    event: PipelineEvent,
    *,
    uow_factory: UnitOfWorkFactory,
    clock: Callable[[], datetime],
) -> None:
    with uow_factory() as uow:
        uow.pipeline_events.mark_processed(event_id=event.id, now=clock())
        uow.commit()


def _derive_status(
    *,
    skipped_item_count: int,
    held_back_item_count: int,
    intake_failure: PipelineItemFailure | None,
    extraction: ExtractionStageResult,
    resolution: ResolutionResult,
    artifacts: ArtifactCompileResult,
) -> PreReviewPipelineStatus:
    """Scheduler가 재시도·알림에 쓸 한 회차의 상태를 계산한다.

    Artifact의 ``proposals_conflicted``는 이미 결정된 동일 멱등 키를 다시
    쓰지 않은 정상적인 동시성 결과이므로 부분 실패에 포함하지 않는다.
    반면 ``nodes_failed``는 카드를 세우지 못해 비워 둔 노드 수이므로 부분
    실패로 센다.
    """
    has_incomplete_work = any(
        (
            skipped_item_count,
            held_back_item_count,
            intake_failure is not None,
            extraction.failures,
            resolution.groups_failed,
            artifacts.nodes_failed,
        )
    )
    return (
        PreReviewPipelineStatus.PARTIAL_FAILURE
        if has_incomplete_work
        else PreReviewPipelineStatus.COMPLETED
    )
