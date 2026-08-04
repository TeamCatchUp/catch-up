"""QA 러너가 완주하지 못한 실행을 결과로 남기지 않는지 못 박는다.

문항 하나에서 Bedrock이나 DB가 깨지면 앞 문항들의 답은 이미 나와 있다.
그것이 `qa_results.jsonl`이라는 정상 이름으로 남으면 채점기는 완주
결과로 읽고 남은 문항 수를 분모로 점수를 낸다 — 못 푼 문항이 뒤쪽에
몰린 실행일수록 점수가 높아진다. 그래서 "전 문항 성공 뒤에만 공개"를
러너 수준에서 고정한다.

DB도 LLM도 부르지 않는다.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest

from catchup.evaluation.longmemeval.dataset import OracleQuestion
from catchup.evaluation.longmemeval.draft_vocabulary import UsageTotals
from catchup.evaluation.longmemeval.qa_service import AnswerResult
from catchup.evaluation.longmemeval.qa_service import KnowledgeLookup
from catchup.evaluation.longmemeval.qa_service import SubjectResult
from catchup.evaluation.longmemeval.run_qa import RESULTS_FILENAME
from catchup.evaluation.longmemeval.run_qa import TRACE_FILENAME
from catchup.evaluation.longmemeval.run_qa import USAGE_FILENAME
from catchup.evaluation.longmemeval.run_qa import run_and_publish
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


def _paths(directory: Path) -> dict[str, Path]:
    """러너가 쓸 세 산출물 경로를 만든다."""
    return {
        "results_path": directory / RESULTS_FILENAME,
        "trace_path": directory / TRACE_FILENAME,
        "usage_path": directory / USAGE_FILENAME,
    }


def _run(directory: Path, answer) -> object:
    """공통 인자를 채워 러너 본체를 부른다."""
    return run_and_publish(
        [_question("q-a"), _question("q-b")],
        lookup=_lookup(),
        extract_subjects=_extract,
        answer=answer,
        workspace_id=902,
        manifest=None,
        capacity="large",
        **_paths(directory),
    )


def test_every_question_publishes_all_three_files(tmp_path: Path) -> None:
    """전 문항이 성공하면 결과·trace·비용이 함께 나타난다."""

    def _answer(*, question, question_date, claims_context) -> AnswerResult:
        return AnswerResult(answer="Acme.", usage=UsageTotals(calls=1))

    summary = _run(tmp_path, _answer)

    paths = _paths(tmp_path)
    results = paths["results_path"].read_text(encoding="utf-8").splitlines()
    traces = paths["trace_path"].read_text(encoding="utf-8").splitlines()
    usage = json.loads(paths["usage_path"].read_text(encoding="utf-8"))

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
    """두 번째 문항이 깨지면 첫 문항의 답도 최종 경로에 남지 않는다."""
    answered: list[str] = []

    def _answer(*, question, question_date, claims_context) -> AnswerResult:
        answered.append(question)
        if len(answered) == 2:
            raise RuntimeError("Bedrock 호출이 깨졌다")
        return AnswerResult(answer="Acme.", usage=UsageTotals(calls=1))

    with pytest.raises(RuntimeError):
        _run(tmp_path, _answer)

    # 첫 문항은 실제로 답까지 갔다. 그런데도 최종 경로는 비어 있어야
    # 한다 — 남으면 그것이 완주 결과로 채점된다.
    assert len(answered) == 2
    for path in _paths(tmp_path).values():
        assert not path.exists()
    assert list(tmp_path.iterdir()) == []
