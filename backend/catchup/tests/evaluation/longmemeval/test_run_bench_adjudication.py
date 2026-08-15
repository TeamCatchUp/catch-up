"""무인 판정 러너가 건별 실패를 종료 코드까지 실어 나르는지 못 박는다.

이 러너는 사람이 큐를 다시 보지 않는 자리에서 돈다. 승인 하나가 실패해도
그 안건은 계류로 남고 그만큼 지식이 빠진 채 점수가 나오는데, 경고만 남기고
exit 0으로 끝내면 오케스트레이터는 exit code만 보므로 그 workspace를 완료로
기록한다. 그래서 실패를 세는 곳과 그 수가 종료 코드로 이어지는 곳을 함께
고정한다.

DB도 LLM도 부르지 않는다.
"""

from __future__ import annotations

import uuid

import pytest

from catchup.evaluation.longmemeval import run_bench_adjudication
from catchup.evaluation.longmemeval.bench_adjudication import AdjudicationCounts
from catchup.evaluation.longmemeval.bench_adjudication import AdjudicationSteps
from catchup.evaluation.longmemeval.bench_adjudication import StepOutcome
from catchup.evaluation.longmemeval.bench_adjudication import run_adjudication
from catchup.knowledge_maintenance.ports.mutation_proposals import StoredMergeProposal
from catchup.knowledge_maintenance.services.compile_entity_artifacts import (
    ArtifactCompileResult,
)
from catchup.knowledge_maintenance.services.review_merge_proposal import (
    MergeReviewError,
)


def _counts(**overrides: int) -> AdjudicationCounts:
    """실패 수만 바꿔 끼운 결과 하나를 만든다."""
    base = {
        "merges_approved": 1,
        "merges_applied": 1,
        "conflicts_found": 1,
        "contradictions_decided": 1,
        "supersedes_applied": 1,
        "artifacts_compiled": 1,
        "artifacts_approved": 1,
    }
    return AdjudicationCounts(**{**base, **overrides})


def test_report_counts_returns_zero_without_failures(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """남은 안건이 없으면 정상 종료한다."""
    assert run_bench_adjudication.report_counts(_counts()) == 0
    assert "처리하지 못한 안건" not in capsys.readouterr().out


def test_report_counts_fails_when_a_single_item_is_left(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """한 건이라도 남으면 exit 1로 끝내고 무엇이 남았는지 적는다."""
    code = run_bench_adjudication.report_counts(_counts(merges_failed=1))

    assert code == 1
    output = capsys.readouterr().out
    assert "병합 승인 실패 1" in output
    assert "합계 1건" in output


def test_report_counts_fails_on_an_apply_failure() -> None:
    """적용 실패도 종료 코드에 실린다."""
    assert run_bench_adjudication.report_counts(_counts(mutations_failed=2)) == 1


def test_report_counts_fails_on_a_compile_conflict(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """카드 컴파일 충돌 한 건도 exit 1로 이어진다."""
    code = run_bench_adjudication.report_counts(_counts(compilations_failed=1))

    assert code == 1
    assert "카드 컴파일 충돌 1" in capsys.readouterr().out


def test_compile_artifacts_counts_a_conflict_as_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """멱등 키 충돌로 건너뛴 entity를 실패로 올려 보낸다.

    충돌한 노드의 새 카드는 만들어지지 않는다. 로그에만 남기면
    `counts.failures`가 0이라 exit 0으로 끝나고, 오케스트레이터는 카드가
    빠진 workspace를 완료로 기록한다.
    """
    monkeypatch.setattr(
        run_bench_adjudication,
        "compile_definition_artifacts",
        lambda uow, *, workspace_id, vocabulary: ArtifactCompileResult(
            definitions_considered=1,
            nodes_considered=3,
            proposals_created=1,
            proposals_revived=0,
            unchanged_skipped=1,
            proposals_conflicted=1,
        ),
    )

    outcome = run_bench_adjudication._compile_artifacts(
        _FakeUow(()),
        workspace_id=910000,
        vocabulary=object(),
    )

    assert outcome.done == 1
    assert outcome.failed == 1


def test_compile_artifacts_fails_when_no_definition_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """정의가 하나도 없으면 그 자체를 실패로 올려 보낸다.

    무엇을 문서로 만들지는 정의가 정한다. 정의가 없으면 카드가 한 장도
    서지 않는데, 0건을 정상으로 넘기면 exit 0으로 끝나 오케스트레이터가
    지식이 빠진 workspace를 완료로 기록한다.
    """
    monkeypatch.setattr(
        run_bench_adjudication,
        "compile_definition_artifacts",
        lambda uow, *, workspace_id, vocabulary: ArtifactCompileResult(),
    )

    outcome = run_bench_adjudication._compile_artifacts(
        _FakeUow(()),
        workspace_id=910000,
        vocabulary=object(),
    )

    assert outcome.done == 0
    assert outcome.failed == 1


def test_run_adjudication_carries_a_compile_conflict_to_the_counts() -> None:
    """컴파일 충돌이 회차 집계의 실패 합계까지 이어진다."""
    counts = run_adjudication(
        AdjudicationSteps(
            approve_merges=lambda: StepOutcome(done=0),
            apply_mutations=lambda: StepOutcome(done=0),
            detect_conflicts=lambda: StepOutcome(done=0),
            adjudicate_contradictions=lambda: StepOutcome(done=0),
            compile_artifacts=lambda: StepOutcome(done=0, failed=1),
            approve_artifacts=lambda: StepOutcome(done=0),
        )
    )

    assert counts.compilations_failed == 1
    assert counts.failures == 1


class _FakeMutationProposals:
    """계류 병합 안건 목록만 흉내 내는 fake repository다."""

    def __init__(self, proposals: tuple[StoredMergeProposal, ...]) -> None:
        self.proposals = proposals

    def list_pending_duplicates(
        self,
        *,
        workspace_id: int,
    ) -> list[StoredMergeProposal]:
        return list(self.proposals)


class _FakeUow:
    """병합 안건 조회만 하는 fake unit of work다."""

    def __init__(self, proposals: tuple[StoredMergeProposal, ...]) -> None:
        self.mutation_proposals = _FakeMutationProposals(proposals)

    def __enter__(self) -> _FakeUow:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _proposal() -> StoredMergeProposal:
    return StoredMergeProposal(
        id=uuid.uuid4(),
        summary="같은 대상이다",
        resolver_metadata={},
        candidates=(),
    )


def test_approve_merges_counts_a_review_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """승인 하나가 실패하면 그 사실이 결과에 남는다.

    실패한 안건은 계류로 남는다. 건수를 0으로 접으면 병합되지 않은 후보가
    남은 workspace가 완료로 기록되고, 그 뒤의 모순 감지도 갈라진 후보를
    따로 본다.
    """
    first, second = _proposal(), _proposal()
    calls: list[uuid.UUID] = []

    def _review(uow, *, workspace_id, proposal_id, verdict, reviewer):
        calls.append(proposal_id)
        if proposal_id == first.id:
            raise MergeReviewError("이미 결정된 안건이다")

    monkeypatch.setattr(
        run_bench_adjudication,
        "review_merge_proposal",
        _review,
    )

    outcome = run_bench_adjudication._approve_merges(
        _FakeUow((first, second)),
        workspace_id=910000,
    )

    assert outcome.done == 1
    assert outcome.failed == 1
    # 실패해도 남은 안건은 계속 시도한다. 전 건을 본 뒤에 보고하는 것이
    # 이 러너의 규칙이다.
    assert calls == [first.id, second.id]
