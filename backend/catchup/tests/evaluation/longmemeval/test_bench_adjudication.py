"""무인 판정 규칙과 단계 순서를 고정한다.

승자 선택은 재실행마다 같아야 한다. 그래서 비교 키가 전부 입력에서
온 것인지, 그리고 claim_id처럼 실행마다 새로 생기는 값이 순위를 바꾸지
않는지를 여기서 못박는다. 단계 순서도 마찬가지다 — 병합이 적용되기
전에 모순을 찾으면 아직 하나로 묶이지 않은 후보의 값이 비교 대상에서
빠진다.
"""

from __future__ import annotations

import itertools
import uuid

import pytest

from catchup.evaluation.longmemeval.bench_adjudication import AdjudicationSteps
from catchup.evaluation.longmemeval.bench_adjudication import WinnerCandidate
from catchup.evaluation.longmemeval.bench_adjudication import pick_winner
from catchup.evaluation.longmemeval.bench_adjudication import run_adjudication
from catchup.evaluation.longmemeval.bench_adjudication import select_winner
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    StoredContradictionProposal,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    StoredContradictionValue,
)


def _value(
    *,
    claim_id: uuid.UUID | None = None,
    value: object = "x",
    statement: str | None = "문장",
    observed_at: str | None = "2024-01-01T00:00:00+00:00",
    normalized: str | None = None,
) -> StoredContradictionValue:
    """모순 안건의 값 후보 하나를 만든다."""
    return StoredContradictionValue(
        claim_id=claim_id or uuid.uuid4(),
        value=value,
        normalized=normalized or str(value),
        statement=statement,
        observed_at=observed_at,
    )


def _candidate(
    *,
    claim_id: uuid.UUID | None = None,
    observed_at: str | None = "2024-01-01T00:00:00+00:00",
    external_document_id: str | None = None,
    locator_start: int | None = None,
    statement: str | None = "문장",
    normalized: str | None = "x",
) -> WinnerCandidate:
    """승자 비교에 쓰는 후보 하나를 만든다."""
    return WinnerCandidate(
        claim_id=claim_id or uuid.uuid4(),
        observed_at=observed_at,
        external_document_id=external_document_id,
        locator_start=locator_start,
        statement=statement,
        normalized=normalized,
    )


class TestPickWinner:
    """관찰 시각이 최신인 주장이 이긴다는 규칙을 고정한다."""

    def test_단일_후보는_그대로_승자다(self) -> None:
        only = _value()

        assert pick_winner([only]) == only.claim_id

    def test_관찰_시각이_최신인_후보가_이긴다(self) -> None:
        old = _value(observed_at="2024-01-01T00:00:00+00:00", value="예전")
        new = _value(observed_at="2024-06-01T00:00:00+00:00", value="최신")

        assert pick_winner([old, new]) == new.claim_id
        assert pick_winner([new, old]) == new.claim_id

    def test_관찰_시각이_없는_후보는_가장_오래된_것으로_친다(self) -> None:
        unknown = _value(observed_at=None, value="시각 미상")
        known = _value(observed_at="2020-01-01T00:00:00+00:00", value="옛날")

        assert pick_winner([unknown, known]) == known.claim_id

    def test_빈_후보_목록은_거부한다(self) -> None:
        with pytest.raises(ValueError):
            pick_winner([])


class TestTieBreakDeterminism:
    """같은 시각에 놓인 후보의 순위가 실행마다 흔들리지 않게 한다."""

    def test_동시각이면_문서_식별자가_먼저_가른다(self) -> None:
        first = _candidate(external_document_id="doc-a", statement="ㄴ")
        second = _candidate(external_document_id="doc-b", statement="ㄱ")

        assert select_winner([second, first]).claim_id == first.claim_id

    def test_같은_문서면_locator_시작점이_가른다(self) -> None:
        early = _candidate(
            external_document_id="doc-a", locator_start=10, statement="ㄴ"
        )
        late = _candidate(
            external_document_id="doc-a", locator_start=99, statement="ㄱ"
        )

        assert select_winner([late, early]).claim_id == early.claim_id

    def test_문서_정보가_없으면_문장_사전순이_가른다(self) -> None:
        alpha = _candidate(statement="alpha")
        beta = _candidate(statement="beta")

        assert select_winner([beta, alpha]).claim_id == alpha.claim_id

    def test_문장까지_같으면_정규화_값이_가른다(self) -> None:
        low = _candidate(statement=None, normalized="A")
        high = _candidate(statement=None, normalized="B")

        assert select_winner([high, low]).claim_id == low.claim_id

    def test_입력_순서를_뒤섞어도_승자가_같다(self) -> None:
        candidates = [
            _candidate(statement="c", observed_at="2024-03-01T00:00:00+00:00"),
            _candidate(statement="a", observed_at="2024-03-01T00:00:00+00:00"),
            _candidate(statement="b", observed_at="2024-03-01T00:00:00+00:00"),
            _candidate(statement="z", observed_at="2024-01-01T00:00:00+00:00"),
        ]
        expected = select_winner(candidates).claim_id

        winners = {
            select_winner(list(order)).claim_id
            for order in itertools.permutations(candidates)
        }

        assert winners == {expected}

    def test_claim_id는_순위를_바꾸지_않는다(self) -> None:
        # claim_id는 실행마다 새로 생기는 uuid4다. 그것이 순위에 끼면
        # 같은 입력을 다시 넣어도 승자가 달라진다.
        alpha_id = uuid.UUID(int=1)
        beta_id = uuid.UUID(int=2)
        alpha = _candidate(claim_id=alpha_id, statement="alpha")
        beta = _candidate(claim_id=beta_id, statement="beta")
        swapped_alpha = _candidate(claim_id=beta_id, statement="alpha")
        swapped_beta = _candidate(claim_id=alpha_id, statement="beta")

        assert select_winner([alpha, beta]).claim_id == alpha_id
        assert select_winner([swapped_beta, swapped_alpha]).claim_id == beta_id

    def test_동시각_판정에는_tie_break를_썼다고_남긴다(self) -> None:
        tied = [_candidate(statement="a"), _candidate(statement="b")]
        clear = [
            _candidate(observed_at="2024-01-01T00:00:00+00:00"),
            _candidate(observed_at="2024-02-01T00:00:00+00:00"),
        ]

        assert select_winner(tied).tie_break_used is True
        assert select_winner(clear).tie_break_used is False


class _StepRecorder:
    """어느 단계가 어떤 순서로 불렸는지 적는다."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def step(self, name: str, count: int = 0):
        """이름을 적고 건수를 돌려주는 단계 하나를 만든다."""

        def run() -> int:
            self.calls.append(name)
            return count

        return run


class TestRunAdjudication:
    """단계 순서가 스펙에서 정한 대로 고정됐는지 확인한다."""

    def test_단계는_정해진_순서로_불린다(self) -> None:
        recorder = _StepRecorder()
        steps = AdjudicationSteps(
            approve_merges=recorder.step("approve_merges", 3),
            apply_mutations=recorder.step("apply_mutations", 2),
            detect_conflicts=recorder.step("detect_conflicts", 5),
            adjudicate_contradictions=recorder.step("adjudicate", 4),
            compile_artifacts=recorder.step("compile", 7),
            approve_artifacts=recorder.step("approve_artifacts", 6),
        )

        counts = run_adjudication(steps)

        assert recorder.calls == [
            "approve_merges",
            "apply_mutations",
            "detect_conflicts",
            "adjudicate",
            "apply_mutations",
            "compile",
            "approve_artifacts",
        ]
        assert counts.merges_approved == 3
        assert counts.conflicts_found == 5
        assert counts.contradictions_decided == 4
        assert counts.artifacts_compiled == 7
        assert counts.artifacts_approved == 6

    def test_병합_적용이_모순_감지보다_앞선다(self) -> None:
        # 병합이 적용되기 전에 모순을 찾으면 아직 하나로 묶이지 않은
        # 후보의 값이 비교 그룹에서 빠진다.
        recorder = _StepRecorder()
        steps = AdjudicationSteps(
            approve_merges=recorder.step("approve_merges"),
            apply_mutations=recorder.step("apply_mutations"),
            detect_conflicts=recorder.step("detect_conflicts"),
            adjudicate_contradictions=recorder.step("adjudicate"),
            compile_artifacts=recorder.step("compile"),
            approve_artifacts=recorder.step("approve_artifacts"),
        )

        run_adjudication(steps)

        assert recorder.calls.index("apply_mutations") < recorder.calls.index(
            "detect_conflicts"
        )
        assert recorder.calls.index("adjudicate") < recorder.calls.index(
            "compile"
        )


class TestCandidatesFromProposal:
    """안건에 실린 값 후보를 비교 가능한 형태로 옮긴다."""

    def test_안건의_값_후보를_그대로_옮긴다(self) -> None:
        proposal = StoredContradictionProposal(
            id=uuid.uuid4(),
            predicate="status",
            subject_key="node:1",
            summary="값이 갈렸다",
            values=(
                _value(observed_at="2024-01-01T00:00:00+00:00", value="a"),
                _value(observed_at="2024-09-01T00:00:00+00:00", value="b"),
            ),
        )

        assert pick_winner(proposal.values) == proposal.values[1].claim_id
