from unittest.mock import patch

import pytest

from catchup.audit.actions import McpAction
from catchup.audit.base import AuditStatus
from catchup.mcp.tools.decorators import mcp_tool


@pytest.mark.asyncio
async def test_mcp_tool_no_args_passthrough():
    """action/observe_name 없으면 함수를 그대로 반환한다."""
    @mcp_tool()
    async def fn(x: int) -> int:
        return x * 2

    result = await fn(3)
    assert result == 6
    assert fn.__name__ == "fn"


@pytest.mark.asyncio
async def test_mcp_tool_preserves_name_with_observe():
    """observe_name 지정 시 __name__ 이 보존된다."""
    @mcp_tool(observe_name="test-observe")
    async def my_tool(query: str) -> str:
        return query

    assert my_tool.__name__ == "my_tool"
    result = await my_tool("hello")
    assert result == "hello"


@pytest.mark.asyncio
async def test_mcp_tool_audit_log_called_on_success():
    """action 지정 시 audit_log 래핑이 적용된다 — SUCCESS emit 확인."""
    @mcp_tool(action=McpAction.SEARCH_KNOWLEDGE_BASE, emit_attempt=False)
    async def fn() -> str:
        return "ok"

    with patch(
        "catchup.audit.utils.emit_audit_event"
    ) as mock_emit:
        await fn()
        mock_emit.assert_called_once()
        call_kwargs = mock_emit.call_args.kwargs
        assert call_kwargs["status"] == AuditStatus.SUCCESS
        assert call_kwargs["action"] == McpAction.SEARCH_KNOWLEDGE_BASE


@pytest.mark.asyncio
async def test_mcp_tool_emit_attempt_flag():
    """emit_attempt=True 이면 ATTEMPT + SUCCESS 총 2회 emit 된다."""
    @mcp_tool(action=McpAction.SEARCH_KNOWLEDGE_BASE, emit_attempt=True)
    async def fn() -> str:
        return "ok"

    with patch(
        "catchup.audit.utils.emit_audit_event"
    ) as mock_emit:
        await fn()
        assert mock_emit.call_count == 2
        statuses = [c.kwargs["status"] for c in mock_emit.call_args_list]
        assert AuditStatus.ATTEMPT in statuses
        assert AuditStatus.SUCCESS in statuses
