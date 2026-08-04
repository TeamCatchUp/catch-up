"""벤치마크가 사람 대신 내리는 판정의 규칙과 단계 순서를 정의한다.

LongMemEval은 사람이 검토 큐를 비워 줄 수 없다. 그래서 벤치마크는
"가장 최근 관찰이 참이다"라는 규칙 하나로 모순을 판정하고, 병합과 문서
변경안은 전부 승인한다. 규칙이 하나뿐이어야 점수가 판정 품질이 아니라
파이프라인 성능을 재는 값이 된다.

승자 비교 키는 전부 입력에서 온 것만 쓴다. claim_id는 실행마다 새로
생기는 uuid4이므로 순위에 끼면 같은 데이터를 다시 넣어도 승자가
달라진다 — 재실행 결정론이 깨진다.

이 모듈은 DB도 LLM도 부르지 않는다. 실제 서비스 호출은
`run_bench_adjudication.py`가 맡는다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass

from catchup.knowledge_maintenance.ports.mutation_proposals import (
    StoredContradictionValue,
)

REVIEWER_AUTO_ACCEPT = "bench:longmemeval:auto-accept"
REVIEWER_RECENCY_RULE = "bench:longmemeval:recency-rule"


@dataclass(frozen=True, slots=True)
class WinnerCandidate:
    """승자 비교에 쓰는 값 후보 하나를 표현한다.

    Attributes:
        claim_id: 이 값을 주장한 claim 후보를 가리킨다. 결과로 돌려줄
            뿐 비교 키로는 쓰지 않는다.
        observed_at: 주장이 놓인 시각이다. 최신이 이긴다.
        external_document_id: 근거 원문을 식별한다. 동시각 tie를 가장
            먼저 가르는 키다. 안건이 이 정보를 싣지 않으면 None이다.
        locator_start: 근거 인용이 원문에서 시작하는 위치다. 같은
            문서 안에서 앞선 인용이 이긴다.
        statement: 주장을 사람이 읽는 문장이다. 사전순으로 가른다.
        normalized: 비교에 쓴 정규화 값이다. 마지막 tie-break 키다.
            모순 안건에는 서로 다른 정규화 값이 최소 둘 있지만, 같은
            정규화 값을 가진 claim이 여럿 섞여 들어올 수 있으므로
            이것으로도 전순서가 보장되지는 않는다.
    """

    claim_id: uuid.UUID
    observed_at: str | None
    external_document_id: str | None
    locator_start: int | None
    statement: str | None
    normalized: str | None


@dataclass(frozen=True, slots=True)
class WinnerSelection:
    """승자 선택 한 번의 결과를 표현한다.

    Attributes:
        claim_id: 참으로 정해진 주장을 가리킨다.
        tie_break_used: 관찰 시각만으로 가리지 못해 입력 유래 보조
            키까지 내려갔는지 나타낸다. 감사 로그에 남는다.
        tie_exhausted: 보조 키를 끝까지 써도 최상위 후보와 키가 완전히
            같은 후보가 더 있었는지 나타낸다. 입력 유래 정보로는 더
            가를 수 없었다는 뜻이라 감사 로그에 따로 남긴다.
    """

    claim_id: uuid.UUID
    tie_break_used: bool
    tie_exhausted: bool


@dataclass(frozen=True, slots=True)
class StepOutcome:
    """단계 하나가 무엇을 처리했고 무엇을 놓쳤는지 담는다.

    건수만 돌려주면 건별 실패가 결과에서 사라진다. 무인 판정은 사람이
    큐를 다시 보지 않는 자리라, 승인 하나가 실패해도 그 안건은 영영
    계류로 남고 그만큼 지식이 빠진 채 점수가 나온다. 그래서 처리한 수와
    실패한 수를 함께 들고 다닌다.

    Attributes:
        done: 끝까지 처리한 건수를 나타낸다.
        failed: 오류로 건너뛴 건수를 나타낸다.
    """

    done: int
    failed: int = 0


@dataclass(frozen=True, slots=True)
class AdjudicationSteps:
    """무인 판정 한 회차가 밟을 단계들을 담는다.

    각 단계는 처리 건수와 실패 건수를 돌려준다. 호출자가 진짜 서비스를
    묶어 넣고, 테스트는 순서를 적는 가짜를 넣는다.
    """

    approve_merges: Callable[[], StepOutcome]
    apply_mutations: Callable[[], StepOutcome]
    detect_conflicts: Callable[[], StepOutcome]
    adjudicate_contradictions: Callable[[], StepOutcome]
    compile_artifacts: Callable[[], StepOutcome]
    approve_artifacts: Callable[[], StepOutcome]


@dataclass(frozen=True, slots=True)
class AdjudicationCounts:
    """무인 판정 한 회차의 단계별 건수를 표현한다.

    Attributes:
        merges_approved: 자동 승인한 병합 안건 수다.
        merges_applied: 병합 결정을 적용한 안건 수다.
        conflicts_found: 감지한 모순 그룹 수다.
        contradictions_decided: 규칙으로 판정한 모순 안건 수다.
        supersedes_applied: 판정 결정을 적용한 안건 수다.
        artifacts_compiled: 새로 올라간 문서 변경안 수다.
        artifacts_approved: 자동 승인한 문서 변경안 수다.
        merges_failed: 승인에 실패해 계류로 남은 병합 안건 수다.
        mutations_failed: 적용에 실패해 approved로 남은 안건 수다. 병합
            적용과 판정 적용 두 번을 합친 값이다.
        contradictions_failed: 판정에 실패해 계류로 남은 모순 안건 수다.
        artifacts_failed: 승인에 실패해 계류로 남은 문서 변경안 수다.
    """

    merges_approved: int
    merges_applied: int
    conflicts_found: int
    contradictions_decided: int
    supersedes_applied: int
    artifacts_compiled: int
    artifacts_approved: int
    merges_failed: int = 0
    mutations_failed: int = 0
    contradictions_failed: int = 0
    artifacts_failed: int = 0

    @property
    def failures(self) -> int:
        """이 회차가 처리하지 못하고 남긴 안건 수를 나타낸다.

        하나라도 남으면 그 workspace의 지식은 미완성이다. 러너는 이
        값으로 종료 코드를 정한다 — 건별 실패를 경고로만 남기고 exit 0으로
        끝내면 오케스트레이터가 그 workspace를 완료로 기록한다.
        """
        return (
            self.merges_failed
            + self.mutations_failed
            + self.contradictions_failed
            + self.artifacts_failed
        )


def _observed_at_key(candidate: WinnerCandidate) -> tuple[int, str]:
    """관찰 시각을 비교 가능한 키로 만든다.

    시각을 모르는 주장은 가장 오래된 것으로 친다. 모른다는 것이 최신을
    이기면 시각 정보가 없는 쪽이 늘 이기기 때문이다.
    """
    if candidate.observed_at is None:
        return (0, "")
    return (1, candidate.observed_at)


def _tie_break_key(
    candidate: WinnerCandidate,
) -> tuple[int, str, int, int, int, str, int, str]:
    """동시각 후보를 가를 보조 키를 만든다.

    전부 입력에서 온 값이다. 값이 없는 자리는 뒤로 보내되 순위 자체는
    결정되게, 있음/없음을 앞자리에 둔다. 작은 쪽이 이긴다.
    """
    document = candidate.external_document_id
    start = candidate.locator_start
    statement = candidate.statement
    normalized = candidate.normalized
    return (
        0 if document is not None else 1,
        document or "",
        0 if start is not None else 1,
        start if start is not None else 0,
        0 if statement is not None else 1,
        statement or "",
        0 if normalized is not None else 1,
        normalized or "",
    )


def select_winner(candidates: Sequence[WinnerCandidate]) -> WinnerSelection:
    """가장 최근에 관찰된 주장을 승자로 고른다.

    입력 유래 키 하나(관찰 시각 내림차순 → external_document_id →
    locator start → statement → normalized)로 후보를 줄 세우고 맨 앞을
    고른다. 시각으로 이미 갈리면 보조 키는 쓰이지 않는다.

    이 키는 전순서가 아니다. 한 모순 안건 안에 normalized·statement·
    observed_at이 완전히 같은 claim 쌍이 실제로 들어올 수 있다
    (`resolve_claim_conflicts`가 그런 중복을 세어 둔다). 그때는 정렬
    결과의 맨 앞이 입력 리스트 순서에 좌우된다.

    그래도 판정 자체는 유효하다. 키가 완전히 같은 후보들은 입력 유래
    정보로는 구분할 수 없고, 승자로 확정되는 값도 그로 인해 닫히는
    구간도 서로 같다. 즉 어느 쪽이 승자가 되든 뒤따르는 지식 결과가
    같다 — 전순서가 보장되는 것이 아니라, 남은 tie가 의미 동치라서
    무해한 것이다. 다만 그런 tie가 있었다는 사실은 `tie_exhausted`로
    드러내 감사 로그가 적을 수 있게 한다.

    Raises:
        ValueError: 후보가 하나도 없을 때 던진다.
    """
    if not candidates:
        raise ValueError("승자를 고를 값 후보가 없다")

    latest = max(_observed_at_key(candidate) for candidate in candidates)
    pool = [
        candidate
        for candidate in candidates
        if _observed_at_key(candidate) == latest
    ]
    ordered = sorted(pool, key=_tie_break_key)
    winner = ordered[0]
    winner_key = _tie_break_key(winner)
    same_key = sum(
        1 for candidate in ordered if _tie_break_key(candidate) == winner_key
    )
    return WinnerSelection(
        claim_id=winner.claim_id,
        tie_break_used=len(pool) > 1,
        tie_exhausted=same_key > 1,
    )


def candidate_from_value(value: StoredContradictionValue) -> WinnerCandidate:
    """안건에 실린 값 후보를 비교 가능한 형태로 옮긴다.

    안건은 근거 문서와 locator를 싣지 않는다. 그 자리는 비워 두고 문장과
    정규화 값으로 가른다 — 어느 쪽이든 입력에서 온 값이다.
    """
    normalized = value.normalized
    if normalized is None:
        normalized = str(value.value)
    return WinnerCandidate(
        claim_id=value.claim_id,
        observed_at=value.observed_at,
        external_document_id=None,
        locator_start=None,
        statement=value.statement,
        normalized=normalized,
    )


def pick_winner(values: Sequence[StoredContradictionValue]) -> uuid.UUID:
    """모순 안건의 값 후보에서 승자 claim_id를 고른다.

    Raises:
        ValueError: 값 후보가 하나도 없을 때 던진다.
    """
    return select_winner([candidate_from_value(v) for v in values]).claim_id


def run_adjudication(steps: AdjudicationSteps) -> AdjudicationCounts:
    """무인 판정 한 회차를 정해진 순서로 돌린다.

    순서가 규칙이다. 병합 결정을 적용하기 전에 모순을 찾으면 아직 하나로
    묶이지 않은 후보의 주장이 비교 그룹에서 빠져 모순을 놓친다. 판정을
    적용하기 전에 문서를 컴파일하면 이미 진 값이 카드에 실린다.

    건별 실패가 있어도 남은 단계를 계속 돌린다. 첫 실패에서 멈추면 그
    뒤의 실패가 드러나지 않아 사람이 같은 실행을 여러 번 반복하게 된다.
    대신 실패 수를 전부 모아 결과에 싣는다 — 멈추지 않는 것과 조용히
    지나가는 것은 다르다.
    """
    merges = steps.approve_merges()
    merge_apply = steps.apply_mutations()
    conflicts = steps.detect_conflicts()
    contradictions = steps.adjudicate_contradictions()
    supersede_apply = steps.apply_mutations()
    compiled = steps.compile_artifacts()
    approved = steps.approve_artifacts()
    return AdjudicationCounts(
        merges_approved=merges.done,
        merges_applied=merge_apply.done,
        conflicts_found=conflicts.done,
        contradictions_decided=contradictions.done,
        supersedes_applied=supersede_apply.done,
        artifacts_compiled=compiled.done,
        artifacts_approved=approved.done,
        merges_failed=merges.failed,
        mutations_failed=merge_apply.failed + supersede_apply.failed,
        contradictions_failed=contradictions.failed,
        artifacts_failed=approved.failed,
    )
