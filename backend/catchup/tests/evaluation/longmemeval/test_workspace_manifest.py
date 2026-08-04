"""문항별 workspace 격리가 실제로 조회를 갈라놓는지 검증한다.

지키는 선은 셋이다.

하나, 문항 A의 haystack에서 나온 지식이 문항 B의 조회에 걸리면 안 된다.
전 문항을 한 workspace에 부었을 때는 같은 이름의 대상이 두 문항에 나오면
B가 "모른다"고 답해야 하는 자리에서 A의 사실로 답한다. 어디서도 오류가
나지 않고 점수만 올라가므로, 조회 함수가 실제로 받은 workspace_id를
기록해 문항마다 다른 곳을 봤는지 못 박는다.

둘, workspace 번호는 결정론이어야 한다. 재실행이 다른 번호를 쓰면 같은
문항의 지식이 두 곳에 나뉘어 앞선 수집이 통째로 버려진다.

셋, manifest가 없어 격리 없이 도는 실행은 조용히 지나가면 안 된다. 그
실행은 오류 하나 없이 돌면서 점수만 부풀리므로, 경고가 사라지면 그
결과를 격리 실행의 점수와 나란히 놓게 된다.

DB도 LLM도 부르지 않는다.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest
import structlog.testing

from catchup.evaluation.longmemeval import grade
from catchup.evaluation.longmemeval import run_qa
from catchup.evaluation.longmemeval.dataset import OracleQuestion
from catchup.evaluation.longmemeval.dataset import OracleSession
from catchup.evaluation.longmemeval.qa_service import ABSTENTION_ANSWER
from catchup.evaluation.longmemeval.qa_service import AnswerResult
from catchup.evaluation.longmemeval.qa_service import KnowledgeLookup
from catchup.evaluation.longmemeval.qa_service import SubjectResult
from catchup.evaluation.longmemeval.qa_service import UsageTotals
from catchup.evaluation.longmemeval.qa_service import answer_questions
from catchup.evaluation.longmemeval.workspace_manifest import DEFAULT_WORKSPACE_BASE
from catchup.evaluation.longmemeval.workspace_manifest import WORKSPACE_NAME_MAX_LENGTH
from catchup.evaluation.longmemeval.workspace_manifest import WorkspaceAssignment
from catchup.evaluation.longmemeval.workspace_manifest import assign_workspaces
from catchup.evaluation.longmemeval.workspace_manifest import check_manifest_covers
from catchup.evaluation.longmemeval.workspace_manifest import invalidate_manifest
from catchup.evaluation.longmemeval.workspace_manifest import load_manifest
from catchup.evaluation.longmemeval.workspace_manifest import manifest_invalidated_path
from catchup.evaluation.longmemeval.workspace_manifest import publish_manifest
from catchup.evaluation.longmemeval.workspace_manifest import stage_manifest
from catchup.evaluation.longmemeval.workspace_manifest import workspace_by_question
from catchup.evaluation.longmemeval.workspace_manifest import workspace_name
from catchup.evaluation.longmemeval.workspace_manifest import write_manifest
from catchup.knowledge_maintenance.ports.knowledge_candidates import AsOfClaim
from catchup.knowledge_maintenance.services.query_knowledge_as_of import AsOfQueryResult
from catchup.knowledge_maintenance.services.query_knowledge_as_of import MatchedSubject

QUESTION_DATE = datetime(2023, 6, 1, tzinfo=timezone.utc)
SUBJECT = "Alice"


def _session(session_id: str) -> OracleSession:
    """세션 하나를 만든다."""
    return OracleSession(
        session_id=session_id,
        timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc),
        turns=(),
    )


def _question(
    question_id: str,
    *,
    session_ids: tuple[str, ...] = (),
) -> OracleQuestion:
    """평가 문항 하나를 만든다."""
    return OracleQuestion(
        question_id=question_id,
        question_type="knowledge-update",
        question="Where does Alice work now?",
        answer="Acme",
        question_date=QUESTION_DATE,
        sessions=tuple(_session(sid) for sid in session_ids),
        answer_session_ids=frozenset(session_ids),
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


def _miss() -> AsOfQueryResult:
    """아무것도 걸리지 않은 조회 결과를 만든다."""
    return AsOfQueryResult(subject=None, as_of=QUESTION_DATE, claims=())


class _WorkspaceScopedLookups:
    """workspace마다 다른 지식을 가진 fake 조회 묶음이다.

    실제 as-of 조회가 workspace_id로 격리되는 것을 그대로 흉내 낸다.
    없는 workspace를 물으면 빈 결과가 나온다 — 여기서 기본 workspace로
    되돌리면 검증하려던 격리가 fake 안에서 무너진다.
    """

    def __init__(self, claims_in: int) -> None:
        self.claims_in = claims_in
        self.seen: list[tuple[str, int]] = []

    def lookup_for_workspace(self, workspace_id: int) -> KnowledgeLookup:
        """workspace 하나를 읽는 조회 경로를 만든다."""

        def as_of(subject: str, at: datetime) -> AsOfQueryResult:
            self.seen.append((subject, workspace_id))
            if workspace_id == self.claims_in:
                return _hit()
            return _miss()

        def history(subject: str) -> AsOfQueryResult:
            if workspace_id == self.claims_in:
                return _hit()
            return _miss()

        return KnowledgeLookup(as_of=as_of, history=history)


def _extract(question: str) -> SubjectResult:
    """늘 같은 subject 하나를 내는 fake 추출기다."""
    return SubjectResult(subjects=(SUBJECT,), usage=UsageTotals(calls=1))


def _answer(
    *,
    question: str,
    question_date: datetime,
    claims_context: str,
) -> AnswerResult:
    """컨텍스트가 있으면 답을 쓰는 fake 답변기다."""
    return AnswerResult(answer="Acme.", usage=UsageTotals(calls=1))


def test_shared_subject_does_not_leak_across_questions() -> None:
    """A에만 있는 지식이 B의 조회에 걸리지 않고 B는 거절한다."""
    first = _question("q-a", session_ids=("s1", "s2"))
    second = _question("q-b", session_ids=("s2", "s3"))
    assignments = assign_workspaces([first, second], base=910000)
    workspace_for = workspace_by_question(assignments)
    lookups = _WorkspaceScopedLookups(claims_in=910000)

    outcomes = answer_questions(
        [first, second],
        lookup=lambda question: lookups.lookup_for_workspace(
            workspace_for[question.question_id]
        ),
        extract_subjects=_extract,
        answer=_answer,
    )

    # 같은 subject를 물었지만 문항마다 다른 workspace를 봤다.
    assert lookups.seen == [(SUBJECT, 910000), (SUBJECT, 910001)]
    assert outcomes[0].abstained is False
    assert outcomes[1].abstained is True
    assert outcomes[1].hypothesis == ABSTENTION_ANSWER
    assert outcomes[1].as_of_claims == 0


def test_single_lookup_still_shared_by_every_question() -> None:
    """조회 경로를 하나만 넘기면 옛 단일 workspace 동작 그대로다."""
    first = _question("q-a")
    second = _question("q-b")
    lookups = _WorkspaceScopedLookups(claims_in=902)

    outcomes = answer_questions(
        [first, second],
        lookup=lookups.lookup_for_workspace(902),
        extract_subjects=_extract,
        answer=_answer,
    )

    assert lookups.seen == [(SUBJECT, 902), (SUBJECT, 902)]
    assert [outcome.abstained for outcome in outcomes] == [False, False]


def test_workspace_ids_follow_subset_order() -> None:
    """번호는 base + 서브셋 인덱스라 같은 입력이면 같은 값이 나온다."""
    questions = [_question(f"q{index}") for index in range(3)]

    first_run = assign_workspaces(questions)
    second_run = assign_workspaces(questions)

    assert first_run == second_run
    assert [item.workspace_id for item in first_run] == [
        DEFAULT_WORKSPACE_BASE,
        DEFAULT_WORKSPACE_BASE + 1,
        DEFAULT_WORKSPACE_BASE + 2,
    ]


def test_assignment_keeps_the_sessions_of_its_own_question() -> None:
    """겹치는 세션도 각 문항의 workspace 목록에 그대로 남는다."""
    first = _question("q-a", session_ids=("s1", "s2"))
    second = _question("q-b", session_ids=("s2", "s3"))

    assignments = assign_workspaces([first, second], base=910000)

    assert assignments[0].session_ids == ("s1", "s2")
    assert assignments[1].session_ids == ("s2", "s3")


def test_manifest_round_trips_through_the_file(tmp_path: Path) -> None:
    """쓴 manifest를 그대로 다시 읽는다."""
    assignments = assign_workspaces(
        [_question("q-a", session_ids=("s1",)), _question("q-b")],
        base=910000,
    )
    path = tmp_path / "nested" / "workspace_manifest.json"

    write_manifest(path, assignments)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload[0] == {
        "question_id": "q-a",
        "workspace_id": 910000,
        "session_ids": ["s1"],
    }
    assert load_manifest(path) == assignments


def test_manifest_rejects_a_non_array_file(tmp_path: Path) -> None:
    """배열이 아닌 manifest는 조용히 빈 목록으로 접지 않는다."""
    path = tmp_path / "workspace_manifest.json"
    path.write_text('{"question_id": "q-a"}', encoding="utf-8")

    with pytest.raises(ValueError):
        load_manifest(path)


def test_missing_question_in_the_manifest_stops_the_run() -> None:
    """manifest에 없는 문항이 있으면 옛 workspace로 되돌리지 않고 멈춘다."""
    workspace_for = {"q-a": 910000}

    with pytest.raises(SystemExit) as excinfo:
        check_manifest_covers(["q-a", "q-b"], workspace_for)

    assert "q-b" in str(excinfo.value)


def test_covered_questions_pass_the_check() -> None:
    """문항이 전부 적혀 있으면 그대로 통과시킨다."""
    check_manifest_covers(["q-a"], {"q-a": 910000, "q-b": 910001})


def test_workspace_name_fits_the_column() -> None:
    """긴 question_id도 name 칸 길이 안으로 잘린다."""
    name = workspace_name("q" * 80)

    assert name.startswith("bench-lme-q-")
    assert len(name) == WORKSPACE_NAME_MAX_LENGTH


def test_diagnostics_count_each_question_in_its_own_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """진단 집계도 문항마다 자기 workspace에서만 센다.

    한 workspace에서 전부 읽으면 다른 문항의 세션에서 나온 claim이 이
    문항의 `extracted_claims`로 잡혀 실패 귀속이 통째로 어긋난다.
    """
    first = _question("q-a", session_ids=("s1", "s2"))
    second = _question("q-b", session_ids=("s2", "s3"))
    workspace_for = {"q-a": 910000, "q-b": 910001}

    claim_id = uuid.uuid4()
    claims_by_workspace = {910000: {claim_id: {"s1", "s2"}}, 910001: {}}
    proposal = grade.ContradictionProposal(
        proposal_id=uuid.uuid4(),
        status="applied",
        claim_candidate_ids=frozenset({claim_id}),
    )
    proposals_by_workspace = {910000: [proposal], 910001: []}
    snapshots_by_workspace = {
        910000: [("longmemeval", "2", 3)],
        910001: [("longmemeval", "2", 5)],
    }

    monkeypatch.setattr(
        grade,
        "load_claim_sessions",
        lambda session, *, workspace_id: claims_by_workspace[workspace_id],
    )
    monkeypatch.setattr(
        grade,
        "load_contradiction_proposals",
        lambda session, *, workspace_id: proposals_by_workspace[workspace_id],
    )
    monkeypatch.setattr(
        grade,
        "load_vocabulary_snapshots",
        lambda session, *, workspace_id: snapshots_by_workspace[workspace_id],
    )

    diagnostics = grade.collect_diagnostics(
        object(),
        [first, second],
        workspace_id=902,
        workspace_for=workspace_for,
    )

    # s2는 두 문항에 겹치지만 그 claim은 q-a의 workspace에만 있다.
    assert diagnostics.evidence["q-a"].extracted_claims == 1
    assert diagnostics.evidence["q-b"].extracted_claims == 0
    assert diagnostics.evidence["q-a"].contradictions_decided == 1
    assert diagnostics.evidence["q-b"].contradictions_detected == 0
    assert diagnostics.contradiction_total == 1
    assert diagnostics.contradiction_decided == 1
    # 어휘 스냅샷은 실행 전체에 대한 질문이라 workspace를 가로질러 합친다.
    assert diagnostics.vocabulary_snapshots == (("longmemeval", "2", 8),)


def test_diagnostics_without_a_manifest_read_one_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """manifest가 없으면 옛 단일 workspace에서 그대로 읽는다."""
    questions = [_question("q-a", session_ids=("s1",))]
    asked: list[int] = []

    def _claims(session: object, *, workspace_id: int) -> dict:
        asked.append(workspace_id)
        return {}

    monkeypatch.setattr(grade, "load_claim_sessions", _claims)
    monkeypatch.setattr(
        grade,
        "load_contradiction_proposals",
        lambda session, *, workspace_id: [],
    )
    monkeypatch.setattr(
        grade,
        "load_vocabulary_snapshots",
        lambda session, *, workspace_id: [],
    )

    diagnostics = grade.collect_diagnostics(
        object(),
        questions,
        workspace_id=902,
    )

    assert asked == [902]
    assert diagnostics.evidence["q-a"].extracted_claims == 0


def test_assignment_exposes_its_workspace_name() -> None:
    """대응표 항목이 자기 workspace 이름을 알려준다."""
    assignment = WorkspaceAssignment(
        question_id="q-a",
        workspace_id=910000,
        session_ids=(),
    )

    assert assignment.workspace_name == "bench-lme-q-q-a"


def test_run_qa_shouts_when_the_manifest_is_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """QA 러너가 공용 workspace로 떨어질 때 경고를 찍는다.

    격리 없는 실행은 오류 하나 없이 돌면서 abstention 점수만 부풀린다.
    경고가 사라지면 그 결과를 격리 실행과 나란히 놓게 되므로 못 박는다.
    """
    missing = tmp_path / "workspace_manifest.json"

    with structlog.testing.capture_logs() as logs:
        workspace_for = run_qa.resolve_workspace_for(missing, ["q-a"])

    captured = capsys.readouterr()
    assert workspace_for is None
    assert "문항 간 기억 격리 없음" in captured.out
    assert "문항 간 기억 격리 없음" in captured.err
    assert str(missing) in captured.out
    assert [entry["event"] for entry in logs] == ["bench_qa_shared_workspace"]


def test_grade_shouts_when_the_manifest_is_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """채점기가 공용 workspace에서 진단할 때 경고를 찍는다."""
    missing = tmp_path / "workspace_manifest.json"

    with structlog.testing.capture_logs() as logs:
        workspace_for = grade.resolve_workspace_for(missing, ["q-a"])

    captured = capsys.readouterr()
    assert workspace_for is None
    assert "문항 간 기억 격리 없음" in captured.out
    assert "문항 간 기억 격리 없음" in captured.err
    assert str(missing) in captured.err
    assert [entry["event"] for entry in logs] == ["bench_grade_shared_workspace"]


def test_invalidate_manifest_moves_the_published_file(tmp_path: Path) -> None:
    """공개된 manifest는 지우지 않고 옆으로 치운다."""
    manifest = tmp_path / "workspace_manifest.json"
    write_manifest(
        manifest,
        (
            WorkspaceAssignment(
                question_id="q-a",
                workspace_id=910000,
                session_ids=("s1",),
            ),
        ),
    )

    moved = invalidate_manifest(manifest)

    assert moved == manifest_invalidated_path(manifest)
    assert not manifest.exists()
    assert [item.question_id for item in load_manifest(moved)] == ["q-a"]


def test_invalidate_manifest_ignores_a_missing_file(tmp_path: Path) -> None:
    """공개된 manifest가 없으면 아무 일도 하지 않는다."""
    manifest = tmp_path / "workspace_manifest.json"

    assert invalidate_manifest(manifest) is None
    assert not manifest_invalidated_path(manifest).exists()


def test_two_writers_never_publish_each_others_manifest(
    tmp_path: Path,
) -> None:
    """같은 경로로 겹쳐 도는 두 수집이 서로의 임시 파일을 건드리지 않는다.

    고정된 `.tmp` 하나를 나눠 쓰면 B의 stage가 A의 임시 파일을 덮는다.
    그러면 A의 publish가 아직 적재 중인 B의 대응표를 최종 경로에
    공개하고, 뒤이은 B의 publish는 임시 파일이 이미 사라져
    `FileNotFoundError`로 끝난다. 그 사이 QA는 B의 부분 workspace를
    완료 실행으로 읽는다.

    그래서 stage와 publish를 교차시켜 각자 자기 내용만 공개하는지 본다.
    최종 승자는 마지막 publish다.
    """
    manifest = tmp_path / "workspace_manifest.json"
    first = assign_workspaces([_question("q-a")], base=910000)
    second = assign_workspaces([_question("q-b")], base=920000)

    first_staged = stage_manifest(manifest, first)
    second_staged = stage_manifest(manifest, second)

    assert first_staged != second_staged
    assert [item.question_id for item in load_manifest(first_staged)] == ["q-a"]

    publish_manifest(manifest, first_staged)
    assert [item.question_id for item in load_manifest(manifest)] == ["q-a"]

    publish_manifest(manifest, second_staged)
    assert [item.question_id for item in load_manifest(manifest)] == ["q-b"]
    assert sorted(tmp_path.glob(f"{manifest.name}.tmp.*")) == []
