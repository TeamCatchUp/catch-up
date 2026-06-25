from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field

from catchup.agents.enums import ActionType
from catchup.agents.enums import FailurePolicy
from catchup.agents.harness.prompt_renderer import _build_tool_context
from catchup.agents.schemas import ToolReferenceSpec
from catchup.agents.tools.base import ActionSpec
from catchup.agents.tools.registry import ToolRegistry


class _Input(BaseModel):
    channel_name: str = Field(description="Configured channel reference key.")


def test_build_tool_context_renders_scalar_reference_keys(monkeypatch) -> None:
    action_spec = ActionSpec(
        name="send_message",
        description="Send a message.",
        input_model=_Input,
        output_model=None,
        type=ActionType.WRITE,
        default_failure_policy=FailurePolicy.CONTINUE,
    )
    monkeypatch.setattr(
        ToolRegistry,
        "get_action_spec",
        lambda qualified_name: action_spec,
    )

    context = _build_tool_context(
        "slack.send_message",
        [
            ToolReferenceSpec(
                argument="channel_name",
                kind="slack_channel",
                key="고객지원",
                value="C123",
            ),
            ToolReferenceSpec(
                argument="channel_name",
                kind="slack_channel",
                key="운영",
                value="C456",
            ),
        ],
    )

    field = context.input_fields["channel_name"]
    assert field.reference_kind == "slack_channel"
    assert field.allowed_values == ["고객지원", "운영"]
