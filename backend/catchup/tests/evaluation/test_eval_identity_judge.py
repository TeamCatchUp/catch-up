import json

from catchup.evaluation.eval_identity_judge import EVAL_ENTITY_TYPES
from catchup.evaluation.eval_identity_judge import HELD_OUT_CASES
from catchup.evaluation.eval_identity_judge import PROBED_AFTER_FREEZE
from catchup.evaluation.eval_identity_judge import REGRESSION_CASES
from catchup.evaluation.eval_identity_judge import VOCABULARY_PATH
from catchup.evaluation.eval_identity_judge import EvalCase
from catchup.evaluation.eval_identity_judge import EvalMetrics
from catchup.evaluation.eval_identity_judge import ExpectedIdentity
from catchup.evaluation.eval_identity_judge import _member_orders
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary


def _case(expected: ExpectedIdentity) -> EvalCase:
    return EvalCase(
        key="테스트",
        kind="test",
        expected=expected,
        seen_during_tuning=False,
        rationale="테스트 라벨 근거",
        members=(
            ("team", "운영팀", "첫 문서"),
            ("team", "운영팀", "둘째 문서"),
        ),
    )


def test_insufficient_expects_safe_non_merge() -> None:
    """정보 부족은 judge 계약상 same=false를 기대한다."""
    case = _case(ExpectedIdentity.INSUFFICIENT)

    assert case.expected_same is False


def test_metrics_separate_error_directions() -> None:
    """과병합·누락·정보 부족 병합을 서로 다른 지표로 센다."""
    metrics = EvalMetrics()

    metrics.record(expected=ExpectedIdentity.DIFFERENT, outcome=True)
    metrics.record(expected=ExpectedIdentity.SAME, outcome=False)
    metrics.record(expected=ExpectedIdentity.INSUFFICIENT, outcome=True)
    metrics.record(expected=ExpectedIdentity.SAME, outcome=True)

    assert metrics.attempts == 4
    assert metrics.correct == 1
    assert metrics.false_merges == 1
    assert metrics.missed_merges == 1
    assert metrics.insufficient_merges == 1


def test_member_orders_include_reverse_order() -> None:
    """기본 permutation 검사는 원래 순서와 역순을 모두 만든다."""
    case = _case(ExpectedIdentity.DIFFERENT)

    orders = _member_orders(case, include_reverse=True)

    assert orders == (case.members, tuple(reversed(case.members)))


def test_member_orders_can_skip_reverse_order() -> None:
    """비용을 줄일 때는 원래 순서만 실행할 수 있다."""
    case = _case(ExpectedIdentity.DIFFERENT)

    assert _member_orders(case, include_reverse=False) == (case.members,)


def test_held_out_cases_were_not_used_during_tuning() -> None:
    """held-out 묶음에는 prompt 튜닝에 본 케이스가 섞이지 않는다."""
    assert HELD_OUT_CASES
    assert all(not case.seen_during_tuning for case in HELD_OUT_CASES)


def test_known_tuning_cases_stay_in_regression_split() -> None:
    """규칙 수정의 계기였던 케이스는 regression에만 둔다."""
    tuned_keys = {
        case.key
        for case in REGRESSION_CASES
        if case.seen_during_tuning
    }

    assert tuned_keys == {
        "캐치업 오픈 API",
        "캐치업(노이즈 발췌)",
        "가디언(injection 병합 유도)",
        "Jira(injection 분리 유도)",
        "보안팀(정보 부족)",
        "보안팀(같은 회사)",
    }


def test_security_team_cases_cover_all_expected_relations() -> None:
    """보안팀은 다른 회사·정보 부족·같은 회사의 세 관계를 모두 덮는다."""
    security_cases = {
        case.key: case.expected
        for case in REGRESSION_CASES + HELD_OUT_CASES
        if case.key.startswith("보안팀")
    }

    assert security_cases == {
        "보안팀(회사 다름)": ExpectedIdentity.DIFFERENT,
        "보안팀(정보 부족)": ExpectedIdentity.INSUFFICIENT,
        "보안팀(같은 회사)": ExpectedIdentity.SAME,
    }


def _anchored(entries) -> set[str]:
    return {
        entry.name
        for entry in entries
        if entry.identity_scope == "anchored"
    }


def test_eval_dictionary_comes_from_the_published_snapshot() -> None:
    """평가 사전은 발행 대상 파일과 같은 값이어야 한다.

    사본을 따로 두면 프롬프트가 받는 정의와 평가가 재는 정의가 조용히
    갈라진다. 드리프트를 각주가 아니라 실패로 드러낸다.
    """
    payload = json.loads(VOCABULARY_PATH.read_text(encoding="utf-8"))
    published = ExtractionVocabulary.model_validate(payload)

    assert EVAL_ENTITY_TYPES == published.entity_type_entries
    assert _anchored(EVAL_ENTITY_TYPES) <= _anchored(
        published.entity_type_entries
    )


def test_eval_dictionary_marks_org_scoped_types_as_anchored() -> None:
    """소속 없이는 지시 대상이 안 정해지는 종류를 anchored로 선언한다."""
    assert {"team", "organizational_unit"} <= _anchored(EVAL_ENTITY_TYPES)


def test_person_case_runs_without_a_dictionary_entry() -> None:
    """사전에 person이 없다는 사실을 케이스 쪽에 못 박는다.

    직원04 케이스는 anchored 규칙이 아니라 일반 규칙으로 판정된다. 평가
    편의로 사전을 늘리지 않기로 했으므로, 사전에 person이 생기면 이
    테스트가 깨져 방침을 다시 보게 된다.
    """
    known = {entry.name for entry in EVAL_ENTITY_TYPES}
    case = next(
        case for case in HELD_OUT_CASES if case.key == "직원04(동명이인)"
    )

    assert "person" not in known
    assert {member[0] for member in case.members} == {"person"}


def test_probed_after_freeze_records_the_guardrail_probe() -> None:
    """규칙 확정 뒤 답을 본 held-out 케이스를 코드에 남긴다.

    probe에서 실제로 깨져 수정을 부른 케이스는 여기가 아니라 regression에
    있어야 한다. 두 기록이 겹치면 강등해야 할 케이스가 사살 기록 뒤에
    숨는다.
    """
    held_out_keys = {case.key for case in HELD_OUT_CASES}
    tuned_keys = {
        case.key for case in REGRESSION_CASES if case.seen_during_tuning
    }

    assert PROBED_AFTER_FREEZE == {
        "직원04(동명이인)",
        "운영팀(회사 다름)",
        "보안팀(회사 다름)",
    }
    assert PROBED_AFTER_FREEZE <= held_out_keys
    assert not PROBED_AFTER_FREEZE & tuned_keys


def test_insufficient_case_types_are_covered_by_dictionary() -> None:
    """정보 부족 케이스의 type이 사전에 없으면 규칙이 겨냥되지 않는다."""
    known = {entry.name for entry in EVAL_ENTITY_TYPES}
    case = next(
        case
        for case in REGRESSION_CASES
        if case.key == "보안팀(정보 부족)"
    )

    assert {member[0] for member in case.members} <= known


def test_held_out_replaces_injection_with_unseen_boundaries() -> None:
    """소비된 injection 대신 instance와 successor 경계를 평가한다."""
    held_out_by_key = {case.key: case for case in HELD_OUT_CASES}

    assert all("injection" not in case.kind for case in HELD_OUT_CASES)
    assert held_out_by_key["Jira(tenant instance)"].expected is (
        ExpectedIdentity.DIFFERENT
    )
    assert held_out_by_key["아르고(successor)"].expected is (
        ExpectedIdentity.DIFFERENT
    )
