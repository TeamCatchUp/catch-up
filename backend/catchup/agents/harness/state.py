from typing import Annotated
from typing import TypedDict

from langgraph.graph.message import add_messages


class ExecutionState(TypedDict):
    # LangGraph add_messages reducer: tool_calls/ToolMessage 누적에 사용된다.
    messages: Annotated[list, add_messages]
    # spec.tools[*].name 목록. tool_gate allowlist 검증에 사용된다.
    allowed_tool_names: list[str]
    # STOP 정책 발동 시 사유를 기록한다. tool_gate가 END로 라우팅한다.
    stop_reason: str | None
