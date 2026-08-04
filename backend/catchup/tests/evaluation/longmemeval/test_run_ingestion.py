"""수집 러너의 workspace 가드를 검증한다.

부트스트랩 세션은 어휘 튜닝용이라 평가 서브셋 밖에서 골라 온 것이다.
이 세션이 평가 workspace에 들어가면 어디서도 오류가 나지 않는다 — 채점은
그대로 돌고 점수만 오염된 지식 위에서 나온다. 그래서 실행 전에 끊는지를
못 박는다.

문항별 workspace를 만드는 자리도 같은 이유로 못 박는다. 행을 만들지
못했는데 그냥 넘어가면 그다음 적재가 FK 오류로 무너지고, 원인이 여기였다는
사실이 로그 어디에도 남지 않는다. 남의 문항이 쓰던 번호를 그대로
재사용하는 것도 같은 종류의 조용한 오염이라 함께 막는다.

manifest 공개 시점도 못 박는다. 적재가 깨졌는데 완성된 manifest가 남으면
QA는 격리가 켜졌다고 판단해 빈 workspace를 조회하고, 그 결과를 정상
점수로 기록한다.

DB도 LLM도 부르지 않는다.
"""

from __future__ import annotations

import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

import pytest

from catchup.evaluation.longmemeval.dataset import OracleQuestion
from catchup.evaluation.longmemeval.dataset import OracleSession
from catchup.evaluation.longmemeval.run_ingestion import EVAL_WORKSPACE_ID
from catchup.evaluation.longmemeval.run_ingestion import check_bootstrap_workspace
from catchup.evaluation.longmemeval.run_ingestion import ensure_workspace
from catchup.evaluation.longmemeval.run_ingestion import ingest_eval_subset
from catchup.evaluation.longmemeval.workspace_manifest import WORKSPACE_NAME_MAX_LENGTH
from catchup.evaluation.longmemeval.workspace_manifest import assign_workspaces
from catchup.evaluation.longmemeval.workspace_manifest import manifest_invalidated_path
from catchup.evaluation.longmemeval.workspace_manifest import write_manifest


def _staged(manifest: Path) -> list[Path]:
    """아직 공개되지 않은 임시 manifest를 모은다.

    임시 경로에는 실행 ID가 붙으므로 이름을 미리 알 수 없다. 같은 경로로
    겹쳐 도는 실행이 서로의 파일을 덮지 않게 하려고 그렇게 만들었다.
    """
    return sorted(manifest.parent.glob(f"{manifest.name}.tmp.*"))


def test_bootstrap_into_the_eval_workspace_is_refused() -> None:
    """bootstrap 모드가 평가 workspace 기본값을 겨냥하면 막는다."""
    with pytest.raises(SystemExit) as excinfo:
        check_bootstrap_workspace("bootstrap", EVAL_WORKSPACE_ID)

    message = str(excinfo.value)
    assert str(EVAL_WORKSPACE_ID) in message
    assert "--workspace-id 901" in message


def test_bootstrap_into_another_workspace_passes() -> None:
    """bootstrap이 평가용이 아닌 workspace면 그대로 통과시킨다."""
    check_bootstrap_workspace("bootstrap", 901)


def test_eval_mode_keeps_using_the_eval_workspace() -> None:
    """eval 모드는 평가 workspace가 정상이므로 막지 않는다."""
    check_bootstrap_workspace("eval", EVAL_WORKSPACE_ID)


class _FakeResult:
    """`execute`가 돌려주는 결과 자리를 흉내 낸다."""

    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self._row = row

    def first(self) -> tuple[Any, ...] | None:
        """첫 행을 돌려준다. 없으면 None이다."""
        return self._row


class _FakeSession:
    """workspace 행의 id와 이름만 흉내 내는 fake session이다.

    실제 DB를 두 군데서 따라 한다. 하나는 `ON CONFLICT DO NOTHING`이라
    기준 workspace가 없으면 INSERT가 아무 행도 만들지 않고 조용히 끝나는
    것, 다른 하나는 이미 있는 행의 이름을 덮어쓰지 않는 것이다. 이름을
    덮어쓰는 fake를 쓰면 소유 검증이 무엇을 막는지 드러나지 않는다.

    `workspaces.name`은 varchar(50)이라 넘치는 이름은 잘라서 저장한다.
    """

    def __init__(self, *, existing: dict[int, str] | None = None) -> None:
        self.existing: dict[int, str] = dict(existing or {})
        self.template_exists = True
        self.statements: list[str] = []
        self.commits = 0

    def execute(self, statement: Any, params: dict[str, Any]) -> _FakeResult:
        """INSERT면 행을 만들고, SELECT면 저장된 이름을 돌려준다."""
        text = str(statement)
        self.statements.append(text)
        workspace_id = params["workspace_id"]
        if "INSERT" in text:
            if self.template_exists and workspace_id not in self.existing:
                self.existing[workspace_id] = params["name"][
                    :WORKSPACE_NAME_MAX_LENGTH
                ]
            return _FakeResult(None)
        if workspace_id not in self.existing:
            return _FakeResult(None)
        return _FakeResult((self.existing[workspace_id],))

    def commit(self) -> None:
        """커밋 횟수만 센다."""
        self.commits += 1


def test_ensure_workspace_creates_a_missing_row() -> None:
    """없는 workspace는 만들고 커밋한다."""
    session = _FakeSession()

    ensure_workspace(session, workspace_id=910000, name="bench-lme-q-q-a")

    assert session.existing == {910000: "bench-lme-q-q-a"}
    assert session.commits == 1


def test_ensure_workspace_reuses_a_row_with_the_same_name() -> None:
    """같은 문항의 workspace면 그대로 재사용하고 INSERT도 하지 않는다."""
    session = _FakeSession(existing={910000: "bench-lme-q-q-a"})

    ensure_workspace(session, workspace_id=910000, name="bench-lme-q-q-a")

    assert session.existing == {910000: "bench-lme-q-q-a"}
    assert not any("INSERT" in text for text in session.statements)
    assert session.commits == 0


def test_ensure_workspace_refuses_a_row_owned_by_another_question() -> None:
    """번호가 다른 문항에 재배정되면 적재 전에 멈춘다."""
    session = _FakeSession(existing={910001: "bench-lme-q-08f4fc43"})

    with pytest.raises(SystemExit) as excinfo:
        ensure_workspace(
            session,
            workspace_id=910001,
            name="bench-lme-q-031748ae",
        )

    message = str(excinfo.value)
    assert "910001" in message
    assert "bench-lme-q-08f4fc43" in message
    assert "bench-lme-q-031748ae" in message
    assert "--workspace-base" in message
    assert not any("INSERT" in text for text in session.statements)


def test_ensure_workspace_refuses_a_human_workspace() -> None:
    """사람이 쓰던 workspace를 겨냥해도 조용히 얹지 않는다."""
    session = _FakeSession(existing={902: "bench-longmemeval-eval"})

    with pytest.raises(SystemExit) as excinfo:
        ensure_workspace(session, workspace_id=902, name="bench-lme-q-q-a")

    assert "bench-longmemeval-eval" in str(excinfo.value)


def test_ensure_workspace_compares_truncated_names() -> None:
    """50자에서 잘려 저장된 이름도 같은 문항이면 통과시킨다."""
    long_id = "q" * 60
    name = f"bench-lme-q-{long_id}"
    session = _FakeSession(
        existing={910000: name[:WORKSPACE_NAME_MAX_LENGTH]}
    )

    ensure_workspace(session, workspace_id=910000, name=name)

    assert session.commits == 0


def test_ensure_workspace_stops_when_the_template_is_missing() -> None:
    """기준 workspace가 없어 행을 못 만들면 조용히 넘어가지 않는다."""
    session = _FakeSession()
    session.template_exists = False

    with pytest.raises(SystemExit) as excinfo:
        ensure_workspace(session, workspace_id=910000, name="bench-lme-q-q-a")

    assert "910000" in str(excinfo.value)


def _question(question_id: str, session_ids: tuple[str, ...]) -> OracleQuestion:
    """세션 몇 개만 달린 최소 문항을 만든다."""
    when = datetime(2026, 5, 1, tzinfo=timezone.utc)
    return OracleQuestion(
        question_id=question_id,
        question_type="single-session-user",
        question="q",
        answer="a",
        question_date=when,
        sessions=tuple(
            OracleSession(session_id=session_id, timestamp=when, turns=())
            for session_id in session_ids
        ),
        answer_session_ids=frozenset(),
    )


def test_manifest_is_published_only_after_every_session_lands(
    tmp_path: Path,
) -> None:
    """모든 세션 적재가 끝나야 최종 경로에 manifest가 나타난다."""
    questions = [_question("q-a", ("s1", "s2")), _question("q-b", ("s3",))]
    assignments = assign_workspaces(questions, base=910000)
    manifest = tmp_path / "workspace_manifest.json"
    seen: list[str] = []

    def _ingest(session: OracleSession, assignment: Any) -> None:
        # 적재 도중에는 최종 manifest가 아직 없어야 한다. 있으면 QA가
        # 부분 workspace를 격리 실행으로 오인할 창이 열린다.
        assert not manifest.exists()
        seen.append(session.session_id)

    total = ingest_eval_subset(
        assignments,
        questions,
        manifest_out=manifest,
        ingest=_ingest,
    )

    assert total == 3
    assert seen == ["s1", "s2", "s3"]
    assert manifest.exists()
    assert _staged(manifest) == []
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert [item["question_id"] for item in payload] == ["q-a", "q-b"]


def test_a_failed_ingestion_leaves_no_published_manifest(
    tmp_path: Path,
) -> None:
    """중간에 깨지면 임시 파일만 남고 최종 manifest는 없다."""
    questions = [_question("q-a", ("s1", "s2")), _question("q-b", ("s3",))]
    assignments = assign_workspaces(questions, base=910000)
    manifest = tmp_path / "workspace_manifest.json"

    def _ingest(session: OracleSession, assignment: Any) -> None:
        if session.session_id == "s2":
            raise RuntimeError("적재 실패")

    with pytest.raises(RuntimeError):
        ingest_eval_subset(
            assignments,
            questions,
            manifest_out=manifest,
            ingest=_ingest,
        )

    assert not manifest.exists()
    # 임시 파일은 남는다. workspace는 만들어졌는데 적재가 끝나지 않았다는
    # 사실이 그 자체로 진단 재료다.
    assert len(_staged(manifest)) == 1


def test_a_failed_reingestion_removes_the_previous_manifest(
    tmp_path: Path,
) -> None:
    """옛 manifest가 있던 자리에서 재수집이 깨지면 최종 경로가 빈다.

    한 번 성공한 경로 위에서 다시 도는 것이 정상 재실행이다. 그때 옛
    manifest가 최종 경로에 남으면, 두 번째 수집이 깨져도 QA·채점은 옛
    대응표를 완성본으로 읽는다 — workspace 일부는 이미 새 데이터로 바뀐
    상태라 점수가 조용히 어긋난다.
    """
    old = [_question("q-old", ("s0",))]
    manifest = tmp_path / "workspace_manifest.json"
    write_manifest(manifest, assign_workspaces(old, base=910000))
    assert manifest.exists()

    questions = [_question("q-a", ("s1", "s2"))]
    assignments = assign_workspaces(questions, base=910000)

    def _ingest(session: OracleSession, assignment: Any) -> None:
        if session.session_id == "s2":
            raise RuntimeError("적재 실패")

    with pytest.raises(RuntimeError):
        ingest_eval_subset(
            assignments,
            questions,
            manifest_out=manifest,
            ingest=_ingest,
        )

    assert not manifest.exists()
    # 옛 대응표는 지우지 않고 옆으로 치운다. 어느 문항이 어느 workspace에
    # 있었는지는 실패 뒤 정리에 필요한 정보다.
    moved = json.loads(
        manifest_invalidated_path(manifest).read_text(encoding="utf-8")
    )
    assert [item["question_id"] for item in moved] == ["q-old"]


def test_a_successful_reingestion_publishes_the_new_manifest(
    tmp_path: Path,
) -> None:
    """무효화한 뒤 성공하면 새 대응표가 최종 경로에 나타난다."""
    old = [_question("q-old", ("s0",))]
    manifest = tmp_path / "workspace_manifest.json"
    write_manifest(manifest, assign_workspaces(old, base=910000))

    questions = [_question("q-a", ("s1", "s2"))]
    assignments = assign_workspaces(questions, base=910000)

    total = ingest_eval_subset(
        assignments,
        questions,
        manifest_out=manifest,
        ingest=lambda session, assignment: None,
    )

    assert total == 2
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert [item["question_id"] for item in payload] == ["q-a"]
