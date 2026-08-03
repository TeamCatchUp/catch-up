"""수집 러너의 workspace 가드를 검증한다.

부트스트랩 세션은 어휘 튜닝용이라 평가 서브셋 밖에서 골라 온 것이다.
이 세션이 평가 workspace에 들어가면 어디서도 오류가 나지 않는다 — 채점은
그대로 돌고 점수만 오염된 지식 위에서 나온다. 그래서 실행 전에 끊는지를
못 박는다.

DB도 LLM도 부르지 않는다.
"""

from __future__ import annotations

import pytest

from catchup.evaluation.longmemeval.run_ingestion import EVAL_WORKSPACE_ID
from catchup.evaluation.longmemeval.run_ingestion import check_bootstrap_workspace


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
