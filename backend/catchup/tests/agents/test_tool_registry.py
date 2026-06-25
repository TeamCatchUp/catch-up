from __future__ import annotations

import pytest

from catchup.agents.tools.base import BaseTool
from catchup.agents.tools.registry import ToolRegistry


class FakeTool(BaseTool):
    def __init__(self, calls: list[str]) -> None:
        super().__init__(
            name="fake",
            display_name="Fake",
            description="Fake tool for registry tests.",
        )
        self.calls = calls

    def bind_execution_context(
        self,
        *,
        tool_specs,
        global_context,
        trigger_event,
    ) -> None:
        self.calls.append("tool")


def test_bind_execution_context_binds_trigger_context_before_references_and_tools(
    monkeypatch,
) -> None:
    calls: list[str] = []
    trigger_event = object()

    monkeypatch.setattr(
        "catchup.agents.tools.registry.bind_trigger_context",
        lambda event: calls.append("trigger") or assert_event(event, trigger_event),
    )
    monkeypatch.setattr(
        "catchup.agents.tools.registry.bind_tool_references",
        lambda references: calls.append("references"),
    )
    monkeypatch.setattr(ToolRegistry, "_tools", {"fake": FakeTool(calls)})

    ToolRegistry.bind_execution_context(
        ["fake.run"],
        references={},
        global_context=object(),
        trigger_event=trigger_event,
    )

    assert calls == ["trigger", "references", "tool"]


def assert_event(actual, expected) -> None:
    assert actual is expected


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
