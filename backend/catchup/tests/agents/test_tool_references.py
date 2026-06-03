from __future__ import annotations

import pytest

from catchup.agents.schemas import ToolReferenceSpec
from catchup.agents.tools.references import bind_tool_references
from catchup.agents.tools.references import resolve_tool_reference


def test_resolve_tool_reference_returns_scalar_value() -> None:
    bind_tool_references(
        {
            "slack.send_thread_message": [
                ToolReferenceSpec(
                    argument="credential_id",
                    kind="slack_credential",
                    key="Slack Bot 인증",
                    value=7,
                )
            ]
        }
    )

    assert (
        resolve_tool_reference(
            tool_name="slack.send_thread_message",
            argument="credential_id",
            input_value="Slack Bot 인증",
            kind="slack_credential",
        )
        == 7
    )


def test_resolve_tool_reference_rejects_wrong_kind() -> None:
    bind_tool_references(
        {
            "slack.send_thread_message": [
                ToolReferenceSpec(
                    argument="credential_id",
                    kind="slack_credential",
                    key="Slack Bot 인증",
                    value=7,
                )
            ]
        }
    )

    with pytest.raises(RuntimeError, match="kind mismatch"):
        resolve_tool_reference(
            tool_name="slack.send_thread_message",
            argument="credential_id",
            input_value="Slack Bot 인증",
            kind="slack_channel",
        )


def test_resolve_tool_reference_rejects_unallowed_key() -> None:
    bind_tool_references(
        {
            "slack.send_thread_message": [
                ToolReferenceSpec(
                    argument="channel_name",
                    kind="slack_channel",
                    key="고객지원",
                    value="C123",
                )
            ]
        }
    )

    with pytest.raises(RuntimeError, match="not allowed"):
        resolve_tool_reference(
            tool_name="slack.send_thread_message",
            argument="channel_name",
            input_value="미허용 채널",
            kind="slack_channel",
        )
