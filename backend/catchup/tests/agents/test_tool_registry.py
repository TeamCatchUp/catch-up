from __future__ import annotations

import pytest

from catchup.agents.tools.registry import ToolRegistry


def test_bind_execution_context_reports_unregistered_tool() -> None:
    with pytest.raises(KeyError, match="Tool 'missing_tool' is not registered"):
        ToolRegistry.bind_execution_context(
            ["missing_tool.run"],
            global_context=object(),
            trigger_event=object(),
        )


def test_get_action_spec_reports_unregistered_tool() -> None:
    with pytest.raises(KeyError, match="Tool 'missing_tool' is not registered"):
        ToolRegistry.get_action_spec("missing_tool.run")
