"""
BaseTool / @action 데코레이터 — ActionSpec 정책 기본값 테스트.

검증 대상:
  - @action에 선언된 default_failure_policy / default_max_retry /
    default_confirmation_gate가 ActionSpec에 저장된다.
  - BaseTool.schema()가 action별 기본값을 노출한다.
"""
from pydantic import BaseModel

from catchup.agents.enums import ActionType
from catchup.agents.enums import FailurePolicy
from catchup.agents.tools.base import BaseTool
from catchup.agents.tools.base import action


class _Input(BaseModel):
    query: str


def _make_tool(
    failure_policy: FailurePolicy,
    max_retry: int | None = None,
) -> BaseTool:
    class _Tool(BaseTool):
        @action(
            input_model=_Input,
            output_model=None,
            description="테스트 액션",
            type=ActionType.READ,
            default_failure_policy=failure_policy,
            default_max_retry=max_retry,
        )
        async def my_action(self, inputs: _Input) -> dict:
            return {}

    return _Tool(name="test_tool", display_name="Test Tool", description="test")


def test_action_spec_stores_default_failure_policy():
    """@action이 default_failure_policy를 ActionSpec에 저장한다."""
    tool = _make_tool(failure_policy=FailurePolicy.SILENT_SKIP)
    spec = tool.get_action_spec("my_action")
    assert spec.default_failure_policy == FailurePolicy.SILENT_SKIP


def test_action_spec_default_max_retry_is_none_when_omitted():
    """default_max_retry를 명시하지 않으면 ActionSpec에 None으로 저장된다."""
    tool = _make_tool(failure_policy=FailurePolicy.SILENT_SKIP)
    spec = tool.get_action_spec("my_action")
    assert spec.default_max_retry is None


def test_action_spec_stores_explicit_default_max_retry():
    """@action에 명시한 default_max_retry가 ActionSpec에 저장된다."""
    tool = _make_tool(failure_policy=FailurePolicy.RETRY_THEN_NOTIFY, max_retry=3)
    spec = tool.get_action_spec("my_action")
    assert spec.default_max_retry == 3


def test_action_spec_default_confirmation_gate_is_auto_when_omitted():
    """default_confirmation_gate를 명시하지 않으면 AUTO로 저장된다."""
    tool = _make_tool(failure_policy=FailurePolicy.SILENT_SKIP)
    spec = tool.get_action_spec("my_action")
    assert spec.default_confirmation_gate == "auto"


def test_base_tool_schema_exposes_default_policies():
    """BaseTool.schema()가 action별 기본 정책값을 포함한다."""
    tool = _make_tool(failure_policy=FailurePolicy.NOTIFY_AND_STOP, max_retry=2)
    schema = tool.schema()

    action_schema = schema["actions"]["my_action"]
    assert action_schema["default_failure_policy"] == "notify_and_stop"
    assert action_schema["default_max_retry"] == 2
    assert action_schema["default_confirmation_gate"] == "auto"
