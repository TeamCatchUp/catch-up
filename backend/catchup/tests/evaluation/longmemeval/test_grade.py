"""채점기의 판정 파싱·프롬프트 분기·비용 산식을 검증한다.

채점기가 틀리면 파이프라인이 아니라 자로 잰 값이 틀린다. 그래서 세
지점을 못 박는다. 하나, 판정 파싱은 yes/no만 점수로 세고 나머지는
error로 드러낸다 — 못 읽은 응답을 조용히 오답으로 세면 정답률이
낮아지는 이유가 파이프라인인지 채점기인지 알 수 없다. 둘, 유형별
규칙 분기는 abstention이 유형보다 먼저다. 셋, 비용은 토큰 × 단가라는
한 줄 산식이다.

넷, 리포트 본문이 귀속의 근사 한계를 스스로 밝히는지도 못 박는다.
리포트만 읽는 사람은 이 파일들을 열어 보지 않으므로, 한계가 코드
주석에만 있으면 그 사람은 분포를 실제보다 낙관적으로 읽는다.

DB도 LLM도 부르지 않는다.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest

from catchup.evaluation.longmemeval.dataset import OracleQuestion
from catchup.evaluation.longmemeval.diagnosis import ANSWER_GENERATION
from catchup.evaluation.longmemeval.diagnosis import EvidenceStats
from catchup.evaluation.longmemeval.diagnosis import FailureAttribution
from catchup.evaluation.longmemeval.grade import ABSTENTION_RULE
from catchup.evaluation.longmemeval.grade import DEFAULT_RULE
from catchup.evaluation.longmemeval.grade import JUDGE_PROMPT_VERSION
from catchup.evaluation.longmemeval.grade import KNOWLEDGE_UPDATE_RULE
from catchup.evaluation.longmemeval.grade import TEMPORAL_RULE
from catchup.evaluation.longmemeval.grade import VERDICT_ERROR
from catchup.evaluation.longmemeval.grade import VERDICT_NO
from catchup.evaluation.longmemeval.grade import VERDICT_YES
from catchup.evaluation.longmemeval.grade import GradeRow
from catchup.evaluation.longmemeval.grade import JudgeResult
from catchup.evaluation.longmemeval.grade import ReportInputs
from catchup.evaluation.longmemeval.grade import build_judge_prompt
from catchup.evaluation.longmemeval.grade import check_question_coverage
from catchup.evaluation.longmemeval.grade import estimate_cost
from catchup.evaluation.longmemeval.grade import grade_questions
from catchup.evaluation.longmemeval.grade import judge_rule
from catchup.evaluation.longmemeval.grade import parse_verdict
from catchup.evaluation.longmemeval.grade import render_report
from catchup.evaluation.longmemeval.usage import UsageTotals


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("yes", VERDICT_YES),
        ("no", VERDICT_NO),
        ("YES", VERDICT_YES),
        ("NO", VERDICT_NO),
        ("  Yes  ", VERDICT_YES),
        ("no.", VERDICT_NO),
        ("Yes, the response matches the reference.", VERDICT_YES),
        ("**no**", VERDICT_NO),
        ("maybe", VERDICT_ERROR),
        ("", VERDICT_ERROR),
        ("   ", VERDICT_ERROR),
        ("I cannot judge this.", VERDICT_ERROR),
        ("nope", VERDICT_ERROR),
    ],
)
def test_parse_verdict_reads_only_the_first_word(
    raw: str,
    expected: str,
) -> None:
    """첫 단어만 판정으로 읽고 나머지는 error로 드러낸다."""
    assert parse_verdict(raw) == expected


def test_judge_rule_branches_by_question_type() -> None:
    """유형마다 다른 채점 규칙을 고른다."""
    assert judge_rule("multi-session", is_abstention=False) == DEFAULT_RULE
    assert (
        judge_rule("temporal-reasoning", is_abstention=False) == TEMPORAL_RULE
    )
    assert (
        judge_rule("knowledge-update", is_abstention=False)
        == KNOWLEDGE_UPDATE_RULE
    )


def test_abstention_rule_overrides_the_question_type() -> None:
    """abstention 문항은 유형과 무관하게 거절 규칙으로 잰다.

    `_abs` 문항에는 정답 정보가 haystack에 아예 없다. 유형별 규칙으로
    재면 "모른다"가 정답과 다르다는 이유로 전부 오답이 된다.
    """
    for question_type in (
        "multi-session",
        "temporal-reasoning",
        "knowledge-update",
    ):
        assert judge_rule(question_type, is_abstention=True) == ABSTENTION_RULE


def test_judge_prompt_carries_question_answer_and_hypothesis() -> None:
    """프롬프트에 질문·정답·모델 답과 유형 규칙이 함께 실린다."""
    prompt = build_judge_prompt(
        question="Where does Alice work now?",
        answer="Acme",
        hypothesis="She works at Acme.",
        question_type="knowledge-update",
        is_abstention=False,
    )

    assert "Where does Alice work now?" in prompt
    assert "Acme" in prompt
    assert "She works at Acme." in prompt
    assert KNOWLEDGE_UPDATE_RULE in prompt
    assert ABSTENTION_RULE not in prompt


def test_abstention_prompt_hides_the_reference_answer() -> None:
    """거절 문항 프롬프트는 정답 자리를 규칙으로 대체한다.

    haystack에 없는 정답을 채점자에게 보여주면 "정답과 같은가"라는
    질문이 성립해 버려서, 재려던 것(모른다고 말했는가)이 아닌 값을
    재게 된다.
    """
    prompt = build_judge_prompt(
        question="What is Alice's phone number?",
        answer="(not present in the conversation)",
        hypothesis="I don't have information about that.",
        question_type="knowledge-update",
        is_abstention=True,
    )

    assert ABSTENTION_RULE in prompt
    assert KNOWLEDGE_UPDATE_RULE not in prompt
    assert "I don't have information about that." in prompt


def test_judge_prompt_version_is_declared() -> None:
    """리포트에 적을 프롬프트 버전 문자열이 존재한다."""
    assert JUDGE_PROMPT_VERSION


def test_estimate_cost_multiplies_tokens_by_unit_price() -> None:
    """비용은 백만 토큰 단가 × 토큰 수다."""
    usage = UsageTotals(
        calls=3,
        input_tokens=1_000_000,
        output_tokens=500_000,
    )

    cost = estimate_cost(usage, input_price=3.0, output_price=15.0)

    assert cost == pytest.approx(3.0 + 7.5)


def test_estimate_cost_is_zero_without_tokens() -> None:
    """토큰이 없으면 비용도 0이다."""
    cost = estimate_cost(UsageTotals(), input_price=3.0, output_price=15.0)

    assert cost == pytest.approx(0.0)


def _report_inputs(
    *,
    skipped_question_ids: tuple[str, ...] = (),
) -> ReportInputs:
    """오답 한 건짜리 최소 리포트 입력을 만든다."""
    row = GradeRow(
        question_id="q1",
        question_type="knowledge-update",
        is_abstention=False,
        verdict=VERDICT_NO,
        hypothesis="She works at Globex.",
        judge_raw="no",
        abstained=False,
        subject_miss=False,
        evidence_stats=EvidenceStats(
            extracted_claims=4,
            contradictions_detected=1,
            contradictions_decided=1,
        ),
        attribution=FailureAttribution(
            cause=ANSWER_GENERATION,
            evidence={"context_claims": 5, "extracted_claims": 4},
        ),
        usage=UsageTotals(calls=1, input_tokens=10, output_tokens=1),
    )
    return ReportInputs(
        workspace_id=902,
        results_dir=Path("/tmp/results"),
        rows=(row,),
        qa_usage=UsageTotals(calls=2, input_tokens=100, output_tokens=20),
        qa_elapsed_ms=1200.0,
        grade_elapsed_ms=300.0,
        contradiction_total=3,
        contradiction_decided=1,
        vocabulary_snapshots=(("ont-1", "v1", 40),),
        skipped_question_ids=skipped_question_ids,
    )


def test_report_states_the_attribution_limits() -> None:
    """리포트 본문이 귀속 근사의 한계 넷을 스스로 밝힌다.

    리포트만 읽는 사람에게 이 한계가 안 보이면, 넷 다 실패를 적게 세는
    쪽으로 기운 분포를 있는 그대로의 인과로 읽게 된다.
    """
    report = render_report(_report_inputs())

    assert "## 진단 한계" in report
    assert "conflict_missed" in report
    assert "위음성" in report
    assert "claim_not_extracted" in report
    assert "has_answer" in report
    assert "adjudication_wrong" in report
    assert "승자 claim" in report
    assert "relation" in report
    assert "subject" in report


def test_report_warns_about_rows_dropped_from_grading() -> None:
    """채점 서브셋 밖이라 버린 결과 행을 리포트가 드러낸다.

    버린 행은 정답률 분모에 안 들어간다. 조용히 사라지면 결과 파일과
    서브셋이 어긋났을 때도 분모만 작아진 정답률이 정상처럼 보인다.
    """
    report = render_report(_report_inputs(skipped_question_ids=("q9", "q8")))

    assert "2건" in report
    assert "`q8`" in report
    assert "`q9`" in report


def test_report_omits_the_drop_warning_when_nothing_was_dropped() -> None:
    """버린 행이 없으면 경고 문구를 넣지 않는다."""
    report = render_report(_report_inputs())

    assert "버린 문항" not in report


def _question(question_id: str) -> OracleQuestion:
    """채점에 필요한 최소 필드만 채운 문항을 만든다."""
    return OracleQuestion(
        question_id=question_id,
        question_type="knowledge-update",
        question="Where does she work?",
        answer="Globex",
        question_date=datetime(2023, 5, 1, tzinfo=timezone.utc),
        sessions=(),
        answer_session_ids=frozenset(),
    )


def test_grade_questions_reports_rows_outside_the_subset() -> None:
    """서브셋에 없는 결과 행을 건너뛰되 그 사실을 `on_skip`으로 알린다."""
    dropped: list[str] = []

    rows = grade_questions(
        [{"question_id": "q1"}, {"question_id": "ghost"}],
        questions={"q1": _question("q1")},
        traces={},
        evidence={},
        judge=lambda **_: JudgeResult(
            verdict=VERDICT_YES,
            raw="yes",
            usage=UsageTotals(),
        ),
        on_skip=dropped.append,
    )

    assert [row.question_id for row in rows] == ["q1"]
    assert dropped == ["ghost"]


def test_coverage_passes_when_every_question_appears_once() -> None:
    """대상 문항이 정확히 한 번씩 있으면 그대로 통과한다."""
    check_question_coverage(["q1", "q2"], ["q2", "q1"], label="QA 결과")


def test_coverage_rejects_a_missing_result() -> None:
    """결과 하나가 빠지면 판정 전에 멈춘다.

    부분 결과를 채점하면 분모가 남은 문항 수로 줄어, 중간에 깨진 실행이
    오히려 높은 정답률로 보인다.
    """
    with pytest.raises(SystemExit) as excinfo:
        check_question_coverage(["q1", "q2"], ["q1"], label="QA 결과")

    message = str(excinfo.value)
    assert "누락 1건" in message
    assert "q2" in message


def test_coverage_rejects_a_duplicated_question_id() -> None:
    """같은 문항이 두 번 있으면 분모가 부풀므로 멈춘다."""
    with pytest.raises(SystemExit) as excinfo:
        check_question_coverage(["q1"], ["q1", "q1"], label="QA 결과")

    assert "중복 1건" in str(excinfo.value)


def test_coverage_rejects_a_question_outside_the_subset() -> None:
    """채점 대상 밖의 결과가 섞여 있어도 멈춘다."""
    with pytest.raises(SystemExit) as excinfo:
        check_question_coverage(["q1"], ["q1", "ghost"], label="QA 결과")

    message = str(excinfo.value)
    assert "대상 밖 1건" in message
    assert "ghost" in message
