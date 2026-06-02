from __future__ import annotations

"""
references는 Agent가 Tool의 Input Model에 넘길 수 있는 Key의 Allowlist
Tool은 내부적으로 이 모듈을 통해 key를 API Call / DB Query에 필요한 Identifier으로 변환하여 사용
"""

from contextvars import ContextVar
from typing import Any

from catchup.agents.schemas import ToolReferenceSpec

# Tool은 Registry에 등록되어, 싱글톤으로 유지되기에 전역 변수 대신 ContextVar로 실행 컨텍스트에 바인딩
_references_var: ContextVar[dict[str, list[ToolReferenceSpec]]] = ContextVar(
    "agent_tool_references",
    default={},
)


def bind_tool_references(
    references: dict[str, list[ToolReferenceSpec]] | None,
) -> None:
    """
    현재 Agent run에서 사용할 Tool references를 바인딩

    Runtime 시작 시 AgentSpec.references 전체를 한 번 주입
    """
    _references_var.set(references or {})


def resolve_tool_reference(
    *,
    tool_name: str,
    argument: str,
    input_value: str,
    kind: str | None = None,
) -> dict[str, Any]:
    """
    Agent가 주입한 reference key를 AgentSpec.references의 resolved value으로 변환
    """
    references = _references_var.get()
    tool_references = references.get(tool_name)
    if not tool_references:
        raise RuntimeError(f"Tool reference not configured: {tool_name}.{argument}")

    matching_argument = [
        reference
        for reference in tool_references
        if reference.argument == argument
    ]
    if not matching_argument:
        raise RuntimeError(f"Tool reference argument not configured: {tool_name}.{argument}")

    if kind is not None:
        matching_kind = [
            reference
            for reference in matching_argument
            if reference.kind == kind
        ]
        if not matching_kind:
            raise RuntimeError(
                f"Tool reference kind mismatch: {tool_name}.{argument} expected {kind}"
            )
        matching_argument = matching_kind

    key = str(input_value or "").strip()
    for reference in matching_argument:
        if key in reference.values:
            value = reference.values[key]
            if not isinstance(value, dict):
                raise RuntimeError(
                    f"Tool reference value must be an object: {tool_name}.{argument}"
                )
            return value

    raise RuntimeError(f"Tool reference value not allowed: {tool_name}.{argument}={key}")
