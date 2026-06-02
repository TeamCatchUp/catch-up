from langchain_core.tools import StructuredTool

from catchup.agents.schemas import ToolReferenceSpec
from catchup.agents.schemas import ToolSpec
from catchup.agents.tools.base import ActionSpec
from catchup.agents.tools.base import BaseTool
from catchup.agents.tools.context import bind_trigger_context
from catchup.agents.tools.references import bind_tool_references


class ToolRegistry:
    _tools: dict[str, BaseTool] = {}

    @classmethod
    def register(cls, tool: BaseTool) -> None:
        """도구를 레지스트리에 등록한다.

        앱 시작 시 각 BaseTool 구현체가 스스로를 등록한다.
        """
        cls._tools[tool.name] = tool

    @classmethod
    def get_langchain_tools(cls, names: list[str]) -> list[StructuredTool]:
        """spec.tools[*].name 기준으로 LangChain tool 리스트를 반환한다.

        Execution Agent의 llm.bind_tools()에 사용된다.
        names는 "slack.send_message" 형식의 qualified name 리스트다.
        """
        result = []
        for qualified_name in names:
            tool_name = qualified_name.split(".", 1)[0]
            lc_name = qualified_name.replace(".", "__", 1)
            tool = cls._get_tool(tool_name)
            result.extend(
                t for t in tool.to_langchain_tools()
                if t.name == lc_name
            )
        return result

    @classmethod
    def bind_execution_context(
        cls,
        tools: list[ToolSpec],
        *,
        references: dict[str, list[ToolReferenceSpec]] | None = None,
        global_context,
        trigger_event,
    ) -> None:
        """spec.tools[*].name에 포함된 tool에만 실행 컨텍스트를 바인딩한다."""
        bind_trigger_context(trigger_event)
        bind_tool_references(references)

        tool_specs_by_name: dict[str, list[ToolSpec]] = {}
        for tool_spec in tools:
            qualified_name = tool_spec if isinstance(tool_spec, str) else tool_spec.name
            tool_name = qualified_name.split(".", 1)[0]
            tool_specs_by_name.setdefault(tool_name, []).append(tool_spec)

        for tool_name, tool_specs in tool_specs_by_name.items():
            tool = cls._get_tool(tool_name)
            tool.bind_execution_context(
                tool_specs=tool_specs,
                global_context=global_context,
                trigger_event=trigger_event,
            )

    @classmethod
    def get_action_spec(cls, qualified_name: str) -> ActionSpec:
        """tool_gate에서 type(read|write) 조회에 사용된다."""
        tool_name, action_name = qualified_name.split(".", 1)
        return cls._get_tool(tool_name).get_action_spec(action_name)

    @classmethod
    def schema(cls) -> dict:
        """Builder Agent가 사용 가능한 도구 목록 전체를 반환한다.

        Builder Agent는 이 스키마를 보고 spec.tools와
        execution_guidelines를 안전하게 생성한다.
        """
        return {
            name: tool.schema()
            for name, tool in cls._tools.items()
        }

    @classmethod
    def _get_tool(cls, tool_name: str) -> BaseTool:
        tool = cls._tools.get(tool_name)
        if tool is None:
            raise KeyError(f"Tool '{tool_name}' is not registered in the ToolRegistry.")
        return tool
