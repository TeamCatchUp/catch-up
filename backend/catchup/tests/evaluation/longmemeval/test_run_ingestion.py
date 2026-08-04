"""수집 러너의 workspace 가드를 검증한다.

부트스트랩 세션은 어휘 튜닝용이라 평가 서브셋 밖에서 골라 온 것이다.
이 세션이 평가 workspace에 들어가면 어디서도 오류가 나지 않는다 — 채점은
그대로 돌고 점수만 오염된 지식 위에서 나온다. 그래서 실행 전에 끊는지를
못 박는다.

문항별 workspace를 만드는 자리도 같은 이유로 못 박는다. 행을 만들지
못했는데 그냥 넘어가면 그다음 적재가 FK 오류로 무너지고, 원인이 여기였다는
사실이 로그 어디에도 남지 않는다.

DB도 LLM도 부르지 않는다.
"""

from __future__ import annotations

from typing import Any

import pytest

from catchup.evaluation.longmemeval.run_ingestion import EVAL_WORKSPACE_ID
from catchup.evaluation.longmemeval.run_ingestion import check_bootstrap_workspace
from catchup.evaluation.longmemeval.run_ingestion import ensure_workspace


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
    """workspace 행이 있는지 없는지만 흉내 내는 fake session이다.

    실제 DB의 `ON CONFLICT DO NOTHING`처럼, 기준 workspace가 없으면 INSERT가
    아무 행도 만들지 않고 조용히 끝나는 상황을 재현한다.
    """

    def __init__(self, *, existing: set[int]) -> None:
        self.existing = existing
        self.template_exists = True
        self.statements: list[str] = []
        self.commits = 0

    def execute(self, statement: Any, params: dict[str, Any]) -> _FakeResult:
        """INSERT면 행을 만들고, SELECT면 존재 여부를 돌려준다."""
        text = str(statement)
        self.statements.append(text)
        if "INSERT" in text:
            if self.template_exists:
                self.existing.add(params["workspace_id"])
            return _FakeResult(None)
        return _FakeResult(
            (1,) if params["workspace_id"] in self.existing else None
        )

    def commit(self) -> None:
        """커밋 횟수만 센다."""
        self.commits += 1


def test_ensure_workspace_creates_a_missing_row() -> None:
    """없는 workspace는 만들고 커밋한다."""
    session = _FakeSession(existing=set())

    ensure_workspace(session, workspace_id=910000, name="bench-lme-q-q-a")

    assert 910000 in session.existing
    assert session.commits == 1


def test_ensure_workspace_leaves_an_existing_row_alone() -> None:
    """이미 있는 workspace는 그대로 두고 통과시킨다."""
    session = _FakeSession(existing={910000})

    ensure_workspace(session, workspace_id=910000, name="다른-이름")

    assert session.existing == {910000}


def test_ensure_workspace_stops_when_the_template_is_missing() -> None:
    """기준 workspace가 없어 행을 못 만들면 조용히 넘어가지 않는다."""
    session = _FakeSession(existing=set())
    session.template_exists = False

    with pytest.raises(SystemExit) as excinfo:
        ensure_workspace(session, workspace_id=910000, name="bench-lme-q-q-a")

    assert "910000" in str(excinfo.value)
