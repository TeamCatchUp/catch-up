"""QA 러너가 완주하지 못한 실행을 결과로 남기지 않는지 못 박는다.

문항 하나에서 Bedrock이나 DB가 깨지면 앞 문항들의 답은 이미 나와 있다.
그것이 완주본으로 읽히면 채점기는 남은 문항 수를 분모로 점수를 낸다 —
못 푼 문항이 뒤쪽에 몰린 실행일수록 점수가 높아진다. 그래서 "전 문항
성공 뒤에만 포인터가 이 run을 가리킨다"를 러너 수준에서 고정한다.

전 문항을 답했더라도 더 최신 실행이 포인터를 가져갔으면 이 run은 현재가
아니다. 그때 CLI가 exit 0과 "포인터가 이 run을 가리킨다"를 내면 그 출력을
믿은 사람이나 자동화가 남의 run을 채점한다. 그 경로도 여기서 막는다.

DB도 LLM도 부르지 않는다.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest

from catchup.evaluation.longmemeval import run_qa
from catchup.evaluation.longmemeval.atomic_publish import RUN_STATUS_RUNNING
from catchup.evaluation.longmemeval.atomic_publish import current_run_directory
from catchup.evaluation.longmemeval.atomic_publish import read_pointer
from catchup.evaluation.longmemeval.atomic_publish import write_pointer
from catchup.evaluation.longmemeval.dataset import OracleQuestion
from catchup.evaluation.longmemeval.qa_service import AnswerResult
from catchup.evaluation.longmemeval.qa_service import KnowledgeLookup
from catchup.evaluation.longmemeval.qa_service import SubjectResult
from catchup.evaluation.longmemeval.run_qa import RESULTS_FILENAME
from catchup.evaluation.longmemeval.run_qa import TRACE_FILENAME
from catchup.evaluation.longmemeval.run_qa import USAGE_FILENAME
from catchup.evaluation.longmemeval.run_qa import QaRunSummary
from catchup.evaluation.longmemeval.run_qa import run_and_publish
from catchup.evaluation.longmemeval.usage import UsageTotals
from catchup.knowledge_maintenance.ports.knowledge_candidates import AsOfClaim
from catchup.knowledge_maintenance.services.query_knowledge_as_of import AsOfQueryResult
from catchup.knowledge_maintenance.services.query_knowledge_as_of import MatchedSubject

QUESTION_DATE = datetime(2023, 6, 1, tzinfo=timezone.utc)
SUBJECT = "Alice"


def _question(question_id: str) -> OracleQuestion:
    """평가 문항 하나를 만든다."""
    return OracleQuestion(
        question_id=question_id,
        question_type="knowledge-update",
        question="Where does Alice work now?",
        answer="Acme",
        question_date=QUESTION_DATE,
        sessions=(),
        answer_session_ids=frozenset(),
    )


def _hit() -> AsOfQueryResult:
    """claim 한 건이 걸린 조회 결과를 만든다."""
    return AsOfQueryResult(
        subject=MatchedSubject(
            node_id=uuid.uuid4(),
            entity_type="person",
            display_name=SUBJECT,
            matched_by="canonical_key",
        ),
        as_of=QUESTION_DATE,
        claims=(
            AsOfClaim(
                claim_id=uuid.uuid4(),
                predicate="employer",
                value_type="text",
                value="Acme",
                statement="Alice works at Acme.",
                valid_from=datetime(2023, 1, 1, tzinfo=timezone.utc),
                valid_to=None,
            ),
        ),
    )


def _lookup() -> KnowledgeLookup:
    """늘 같은 claim을 돌려주는 fake 조회 경로다."""
    return KnowledgeLookup(
        as_of=lambda subject, at: _hit(),
        history=lambda subject: _hit(),
    )


def _extract(question: str) -> SubjectResult:
    """늘 같은 subject 하나를 내는 fake 추출기다."""
    return SubjectResult(subjects=(SUBJECT,), usage=UsageTotals(calls=1))


def _run(directory: Path, answer) -> object:
    """공통 인자를 채워 러너 본체를 부른다."""
    return run_and_publish(
        [_question("q-a"), _question("q-b")],
        lookup=_lookup(),
        extract_subjects=_extract,
        answer=answer,
        output=directory,
        workspace_id=902,
        manifest=None,
        capacity="large",
    )


def test_every_question_publishes_all_three_files(tmp_path: Path) -> None:
    """전 문항이 성공하면 결과·trace·비용이 한 run으로 함께 나타난다."""

    def _answer(*, question, question_date, claims_context) -> AnswerResult:
        return AnswerResult(answer="Acme.", usage=UsageTotals(calls=1))

    summary = _run(tmp_path, _answer)

    directory = current_run_directory(tmp_path)
    assert directory == summary.run_directory
    results = (
        (directory / RESULTS_FILENAME).read_text(encoding="utf-8").splitlines()
    )
    traces = (
        (directory / TRACE_FILENAME).read_text(encoding="utf-8").splitlines()
    )
    usage = json.loads(
        (directory / USAGE_FILENAME).read_text(encoding="utf-8")
    )

    assert summary.questions == 2
    assert [json.loads(line)["question_id"] for line in results] == [
        "q-a",
        "q-b",
    ]
    assert [json.loads(line)["question_id"] for line in traces] == [
        "q-a",
        "q-b",
    ]
    assert usage["questions"] == 2


def test_a_failed_question_publishes_nothing(tmp_path: Path) -> None:
    """두 번째 문항이 깨지면 첫 문항의 답도 완주본으로 읽히지 않는다."""
    answered: list[str] = []

    def _answer(*, question, question_date, claims_context) -> AnswerResult:
        answered.append(question)
        if len(answered) == 2:
            raise RuntimeError("Bedrock 호출이 깨졌다")
        return AnswerResult(answer="Acme.", usage=UsageTotals(calls=1))

    with pytest.raises(RuntimeError):
        _run(tmp_path, _answer)

    # 첫 문항은 실제로 답까지 갔다. 그런데도 완주한 run은 없어야 한다 —
    # 있으면 그 부분 결과가 완주 결과로 채점된다.
    assert len(answered) == 2
    with pytest.raises(SystemExit):
        current_run_directory(tmp_path)


def test_a_run_that_lost_the_pointer_reports_it_to_its_caller(
    tmp_path: Path,
) -> None:
    """포인터를 빼앗긴 run은 요약에서 공개 실패를 말한다.

    경고 출력만으로는 부족하다. 호출한 쪽이 읽을 값이 없으면 러너는
    성공으로 돌아가고, 그 출력을 믿은 채점기가 남의 run을 읽는다.
    """

    def _answer(*, question, question_date, claims_context) -> AnswerResult:
        # 첫 문항을 답하는 사이에 더 최신 실행이 포인터를 가져간다.
        write_pointer(tmp_path, run_id="newer", status=RUN_STATUS_RUNNING)
        return AnswerResult(answer="Acme.", usage=UsageTotals(calls=1))

    summary = _run(tmp_path, _answer)

    assert summary.published is False
    assert read_pointer(tmp_path) == {
        "run_id": "newer",
        "status": RUN_STATUS_RUNNING,
    }
    # 이 run의 산출물 자체는 자기 디렉토리에 그대로 남는다.
    assert (summary.run_directory / RESULTS_FILENAME).exists()


class _FakeLlmService:
    """모델을 부르지 않는 LLM 서비스 대역이다."""

    def get_llm(self) -> object:
        """모델 자리에 놓을 아무 객체나 돌려준다."""
        return object()


class _FakeEngine:
    """dispose만 받는 엔진 대역이다."""

    def dispose(self) -> None:
        """정리할 것이 없다."""


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    published: bool,
    extra_args: tuple[str, ...] = (),
    captured_kwargs: dict | None = None,
) -> int:
    """DB·LLM을 대역으로 갈아 끼운 채 CLI 진입점을 부른다."""
    oracle = tmp_path / "oracle.json"
    oracle.write_text("[]", encoding="utf-8")
    output = tmp_path / "out"
    summary = QaRunSummary(
        questions=2,
        abstained=0,
        usage=UsageTotals(calls=2),
        run_directory=output / "runs" / "A",
        published=published,
    )
    monkeypatch.setattr(run_qa, "load_oracle", lambda path: ())
    monkeypatch.setattr(
        run_qa,
        "select_subset",
        lambda questions, per_type: [_question("q-a")],
    )
    monkeypatch.setattr(
        run_qa,
        "get_llm_service",
        lambda **kwargs: _FakeLlmService(),
    )
    monkeypatch.setattr(
        run_qa,
        "bedrock_extract_subjects",
        lambda llm: _extract,
    )
    monkeypatch.setattr(run_qa, "bedrock_answer", lambda llm: None)
    monkeypatch.setattr(run_qa, "create_engine", lambda url: _FakeEngine())
    monkeypatch.setattr(run_qa, "sessionmaker", lambda **kwargs: None)
    def _publish(*args, **kwargs) -> QaRunSummary:
        if captured_kwargs is not None:
            captured_kwargs.update(kwargs)
        return summary

    monkeypatch.setattr(run_qa, "run_and_publish", _publish)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_qa",
            "--output",
            str(output),
            "--manifest",
            str(tmp_path / "no-manifest.json"),
            "--oracle-path",
            str(oracle),
            *extra_args,
        ],
    )
    return run_qa.main()


def test_similarity_fallback_is_on_unless_the_flag_turns_it_off(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """유사 후보 되짚기는 기본이 on이고 플래그로만 꺼진다."""
    default: dict = {}
    _run_main(monkeypatch, tmp_path, published=True, captured_kwargs=default)
    assert default["use_similarity_fallback"] is True

    baseline: dict = {}
    _run_main(
        monkeypatch,
        tmp_path,
        published=True,
        extra_args=("--similarity-fallback", "off"),
        captured_kwargs=baseline,
    )
    assert baseline["use_similarity_fallback"] is False


def test_usage_payload_records_the_similarity_switch() -> None:
    """비용 파일에 되짚기 on/off를 남겨 두 실행을 구분할 수 있게 한다."""
    payload = json.loads(
        run_qa.usage_payload(
            workspace_id=902,
            manifest=None,
            capacity="large",
            questions=2,
            abstained=1,
            total=UsageTotals(calls=2),
            similarity_fallback=False,
        )
    )

    assert payload["similarity_fallback"] is False


def test_the_cli_fails_loudly_when_the_pointer_was_taken_over(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """포인터를 빼앗기면 exit 1로 끝나고 채점 안내를 내지 않는다."""
    code = _run_main(monkeypatch, tmp_path, published=False)

    captured = capsys.readouterr()
    assert code == 1
    assert "현재로 공개되지 않았다" in captured.out
    assert "채점 대상은 다른 run이다" in captured.out
    assert "포인터가 이 run을 가리킨다" not in captured.out


def test_the_cli_still_points_at_a_published_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """정상 완주는 그대로 exit 0과 채점 안내로 끝난다."""
    code = _run_main(monkeypatch, tmp_path, published=True)

    captured = capsys.readouterr()
    assert code == 0
    assert "포인터가 이 run을 가리킨다" in captured.out
    assert "현재로 공개되지 않았다" not in captured.out
