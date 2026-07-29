from catchup.evaluation.eval_identity_judge import HELD_OUT_CASES
from catchup.evaluation.eval_identity_judge import REGRESSION_CASES
from catchup.evaluation.eval_identity_judge import EvalCase
from catchup.evaluation.eval_identity_judge import EvalMetrics
from catchup.evaluation.eval_identity_judge import ExpectedIdentity
from catchup.evaluation.eval_identity_judge import _member_orders


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
    }


def test_security_team_cases_cover_all_expected_relations() -> None:
    """보안팀은 다른 회사·정보 부족·같은 회사의 세 관계를 모두 덮는다."""
    security_cases = {
        case.key: case.expected
        for case in HELD_OUT_CASES
        if case.key.startswith("보안팀")
    }

    assert security_cases == {
        "보안팀(회사 다름)": ExpectedIdentity.DIFFERENT,
        "보안팀(정보 부족)": ExpectedIdentity.INSUFFICIENT,
        "보안팀(같은 회사)": ExpectedIdentity.SAME,
    }


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
