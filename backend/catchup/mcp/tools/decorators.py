from collections.abc import Callable
from typing import Any

from catchup.audit.actions import McpAction
from catchup.audit.metadata import McpAuditMetadata
from catchup.audit.utils import audit_log
from catchup.observability.langfuse.configs import get_observe

_observe = get_observe()


def mcp_tool(
    action: McpAction | None = None,
    observe_name: str | None = None,
    emit_attempt: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """MCP 툴 함수에 observe와 audit_log를 적용하는 팩토리 데코레이터를 반환한다."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        wrapped = fn
        if action is not None:
            wrapped = audit_log(
                action,
                emit_attempt=emit_attempt,
                metadata_factory=McpAuditMetadata.from_audit,
            )(wrapped)
        if observe_name is not None:
            wrapped = _observe(name=observe_name)(wrapped)
        return wrapped

    return decorator
