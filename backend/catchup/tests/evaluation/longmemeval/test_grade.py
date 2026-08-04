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

다섯, 채점 대상 선택이 검사보다 먼저인지를 main 수준에서 못 박는다.
완주 산출물에 `--limit`으로 앞 N문항만 채점하는 것은 광고된 비용 제어
수단이라, 나머지 행을 오류로 보면 그 길이 통째로 막힌다.

실제 DB와 Bedrock은 fake로 대신한다.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from datetime import datetime
from datetime import timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from catchup.evaluation.longmemeval import grade
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
from catchup.evaluation.longmemeval.grade import select_rows_to_grade
from catchup.evaluation.longmemeval.run_qa import RESULTS_FILENAME
from catchup.evaluation.longmemeval.run_qa import TRACE_FILENAME
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
    excluded_question_ids: tuple[str, ...] = (),
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
        excluded_question_ids=excluded_question_ids,
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


def test_report_counts_rows_left_out_of_grading() -> None:
    """채점 대상 밖이라 판정하지 않은 행을 리포트가 집계로 드러낸다.

    제외한 행은 정답률 분모에 안 들어간다. 조용히 사라지면 결과 파일과
    서브셋이 어긋났을 때도 분모만 작아진 정답률이 정상처럼 보인다.
    """
    report = render_report(_report_inputs(excluded_question_ids=("q9", "q8")))

    assert "채점 제외 2건" in report
    assert "`q8`" in report
    assert "`q9`" in report


def test_report_omits_the_exclusion_note_when_nothing_was_excluded() -> None:
    """제외한 행이 없으면 집계 문구를 넣지 않는다."""
    report = render_report(_report_inputs())

    assert "채점 제외" not in report


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


def test_grade_row_reads_subject_miss_with_the_diagnosis_rule() -> None:
    """빈 후보를 miss로 읽는 판단이 채점 행에서도 같다.

    규칙을 채점기에 다시 쓰면 한쪽만 고친 순간 리포트의 subject_miss 열과
    귀속 분포가 같은 실행을 다르게 설명한다.
    """
    rows = grade_questions(
        [{"question_id": "q1"}],
        questions={"q1": _question("q1")},
        traces={"q1": {"subjects_tried": []}},
        evidence={},
        judge=lambda **_: JudgeResult(
            verdict=VERDICT_YES,
            raw="yes",
            usage=UsageTotals(),
        ),
    )

    assert rows[0].subject_miss is True


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


def test_coverage_rejects_a_question_outside_the_selected_set() -> None:
    """고른 집합에 대상 밖 문항이 남아 있으면 멈춘다.

    `select_rows_to_grade`가 먼저 걸러 내므로 보통은 일어나지 않지만,
    거르지 않고 부르는 호출자를 위한 마지막 방어선으로 남겨 둔다.
    """
    with pytest.raises(SystemExit) as excinfo:
        check_question_coverage(["q1"], ["q1", "ghost"], label="QA 결과")

    message = str(excinfo.value)
    assert "대상 밖 1건" in message
    assert "ghost" in message


def test_selection_keeps_only_the_rows_in_the_target_set() -> None:
    """완주 산출물에서 채점 대상 문항의 행만 골라낸다.

    `--limit`으로 앞 문항만 채점하는 것은 정상 사용이다. 나머지 행을
    오류로 보면 40문항을 완주한 뒤 한 문항만 채점하는 길이 막힌다.
    """
    selection = select_rows_to_grade(
        [{"question_id": "q1"}, {"question_id": "q2"}],
        ["q1"],
        label="QA 결과",
    )

    assert [row["question_id"] for row in selection.rows] == ["q1"]
    assert selection.excluded_ids == ("q2",)


def test_selection_rejects_a_missing_row_inside_the_target_set() -> None:
    """고른 집합 안에 빠진 문항이 있으면 여전히 거절한다."""
    with pytest.raises(SystemExit) as excinfo:
        select_rows_to_grade(
            [{"question_id": "q1"}],
            ["q1", "q2"],
            label="QA 결과",
        )

    assert "누락 1건" in str(excinfo.value)


def test_selection_rejects_a_duplicate_inside_the_target_set() -> None:
    """고른 집합 안의 중복도 거절한다. 분모가 부풀기 때문이다."""
    with pytest.raises(SystemExit) as excinfo:
        select_rows_to_grade(
            [{"question_id": "q1"}, {"question_id": "q1"}],
            ["q1"],
            label="QA 결과",
        )

    assert "중복 1건" in str(excinfo.value)


def _oracle_payload(question_id: str) -> dict[str, object]:
    """oracle 파일에 실릴 질문 하나의 원본 dict를 만든다."""
    return {
        "question_id": question_id,
        "question_type": "knowledge-update",
        "question": "Where does she work?",
        "answer": "Globex",
        "question_date": "2023/05/01 10:00",
        "haystack_session_ids": ["s1"],
        "haystack_dates": ["2023/04/01 10:00"],
        "haystack_sessions": [
            [
                {
                    "role": "user",
                    "content": "I joined Globex.",
                    "has_answer": True,
                }
            ]
        ],
        "answer_session_ids": ["s1"],
    }


def _write_qa_outputs(results_dir: Path, question_ids: Sequence[str]) -> None:
    """완주한 QA 실행의 결과·trace 산출물을 흉내 내 쓴다."""
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / RESULTS_FILENAME).write_text(
        "".join(
            json.dumps({"question_id": qid, "hypothesis": "Globex."}) + "\n"
            for qid in question_ids
        ),
        encoding="utf-8",
    )
    (results_dir / TRACE_FILENAME).write_text(
        "".join(
            json.dumps(
                {
                    "question_id": qid,
                    "elapsed_ms": 1.0,
                    "subjects_tried": ["she"],
                }
            )
            + "\n"
            for qid in question_ids
        ),
        encoding="utf-8",
    )


class _FakeSession:
    """진단 조회에 쓰이지 않는 자리표시자 session이다."""

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *_: object) -> bool:
        return False


class _FakeEngine:
    """dispose만 받는 자리표시자 engine이다."""

    def dispose(self) -> None:
        return None


def _stub_grade_dependencies(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """DB·Bedrock 의존을 fake로 바꾸고 judge 호출 목록을 돌려준다."""
    judged: list[str] = []

    def _judge(**kwargs: object) -> JudgeResult:
        judged.append(str(kwargs["hypothesis"]))
        return JudgeResult(
            verdict=VERDICT_YES,
            raw="yes",
            usage=UsageTotals(calls=1),
        )

    monkeypatch.setattr(
        grade,
        "create_engine",
        lambda *_a, **_k: _FakeEngine(),
    )
    monkeypatch.setattr(
        grade,
        "sessionmaker",
        lambda *_a, **_k: (lambda: _FakeSession()),
    )
    monkeypatch.setattr(
        grade,
        "collect_diagnostics",
        lambda *_a, **_k: grade.Diagnostics(
            evidence={},
            contradiction_total=0,
            contradiction_decided=0,
            vocabulary_snapshots=(),
        ),
    )
    monkeypatch.setattr(
        grade,
        "get_llm_service",
        lambda **_k: SimpleNamespace(get_llm=lambda: object()),
    )
    monkeypatch.setattr(grade, "bedrock_judge", lambda _llm: _judge)
    return judged


def test_main_grades_the_first_n_questions_of_a_finished_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """완주 산출물에 `--limit`을 걸면 앞 N문항만 판정하고 나머지는 제외한다.

    judge 비용을 아끼려고 전체 완주본의 앞 한 문항만 채점하는 것은 광고된
    사용법이다. 이것이 막히면 40문항 실행마다 전액 judge 비용을 내야 한다.
    """
    oracle_path = tmp_path / "oracle.json"
    oracle_path.write_text(
        json.dumps([_oracle_payload("q1"), _oracle_payload("q2")]),
        encoding="utf-8",
    )
    results_dir = tmp_path / "results"
    _write_qa_outputs(results_dir, ["q1", "q2"])
    judged = _stub_grade_dependencies(monkeypatch)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "grade",
            "--results-dir",
            str(results_dir),
            "--oracle-path",
            str(oracle_path),
            "--manifest",
            str(tmp_path / "missing-manifest.json"),
            "--limit",
            "1",
        ],
    )

    assert grade.main() == 0

    assert len(judged) == 1
    graded_ids = [
        json.loads(line)["question_id"]
        for line in (results_dir / "grades.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert graded_ids == ["q1"]
    report = (results_dir / "report.md").read_text(encoding="utf-8")
    assert "채점 제외 1건" in report
    assert "`q2`" in report
    assert "채점 제외 1건" in capsys.readouterr().out


def test_main_still_rejects_a_run_that_missed_a_target_question(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--limit` 없이 대상 문항 하나가 빠지면 판정 전에 멈춘다.

    부분 결과에 점수를 매기면 분모가 줄어 깨진 실행이 오히려 높은
    정답률로 보인다.
    """
    oracle_path = tmp_path / "oracle.json"
    oracle_path.write_text(
        json.dumps([_oracle_payload("q1"), _oracle_payload("q2")]),
        encoding="utf-8",
    )
    results_dir = tmp_path / "results"
    _write_qa_outputs(results_dir, ["q1"])
    judged = _stub_grade_dependencies(monkeypatch)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "grade",
            "--results-dir",
            str(results_dir),
            "--oracle-path",
            str(oracle_path),
            "--manifest",
            str(tmp_path / "missing-manifest.json"),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        grade.main()

    assert "누락 1건" in str(excinfo.value)
    assert judged == []


def test_main_rejects_a_duplicate_inside_the_graded_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """고른 집합 안에 같은 문항이 두 번 있으면 멈춘다."""
    oracle_path = tmp_path / "oracle.json"
    oracle_path.write_text(
        json.dumps([_oracle_payload("q1"), _oracle_payload("q2")]),
        encoding="utf-8",
    )
    results_dir = tmp_path / "results"
    _write_qa_outputs(results_dir, ["q1", "q1", "q2"])
    judged = _stub_grade_dependencies(monkeypatch)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "grade",
            "--results-dir",
            str(results_dir),
            "--oracle-path",
            str(oracle_path),
            "--manifest",
            str(tmp_path / "missing-manifest.json"),
            "--limit",
            "1",
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        grade.main()

    assert "중복 1건" in str(excinfo.value)
    assert judged == []
