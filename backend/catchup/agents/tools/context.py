from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from catchup.agents.triggers.events import AgentWebhookEvent


@dataclass(frozen=True)
class TriggerContext:
    event: AgentWebhookEvent


_trigger_context_var: ContextVar[TriggerContext | None] = ContextVar(
    "agent_tool_trigger_context",
    default=None,
)


def bind_trigger_context(event: AgentWebhookEvent) -> None:
    _trigger_context_var.set(TriggerContext(event=event))


def get_trigger_context() -> TriggerContext:
    context = _trigger_context_var.get()
    if context is None:
        raise RuntimeError("Trigger execution context is missing for this agent run.")
    return context
