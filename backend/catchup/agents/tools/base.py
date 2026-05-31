"""
Tool Registry: Execution Agent가 사용할 수 있는 도구와 그 명세를 관리한다.

구현자 인터페이스:
  1. BaseTool을 상속한다.
  2. action 메서드에 @action 데코레이터를 붙인다.
  3. ToolRegistry.register()로 등록한다.

@action 데코레이터는 메서드에 ActionSpec을 부착한다.
BaseTool.to_langchain_tools()가 이를 읽어 LangChain StructuredTool 리스트로 변환한다.
"""
from typing import Any
from typing import Callable

from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from catchup.agents.enums import ActionType
from catchup.agents.enums import FailurePolicy


class ActionSpec(BaseModel):
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel] | None
    type: ActionType

    default_failure_policy: FailurePolicy
    default_max_retry: int | None = None

    model_config = {"arbitrary_types_allowed": True}


_ACTION_SPEC_ATTR = "__action_spec__"


def action(
    *,
    input_model: type[BaseModel],
    output_model: type[BaseModel] | None,
    description: str,
    type: ActionType,
    default_failure_policy: FailurePolicy,
    default_max_retry: int | None = None,
) -> Callable:
    """action 메서드에 ActionSpec을 부착하는 데코레이터."""
    def decorator(fn: Callable) -> Callable:
        spec = ActionSpec(
            name=fn.__name__,
            description=description,
            input_model=input_model,
            output_model=output_model,
            type=type,
            default_failure_policy=default_failure_policy,
            default_max_retry=default_max_retry,
        )
        setattr(fn, _ACTION_SPEC_ATTR, spec)
        return fn
    return decorator


class BaseTool:
    def __init__(self, name: str, display_name: str, description: str) -> None:
        self.name = name
        self.display_name = display_name
        self.description = description

    def _action_specs(self) -> dict[str, ActionSpec]:
        """@action이 붙은 메서드의 ActionSpec을 모두 반환한다."""
        specs = {}
        for attr_name in dir(self):
            method = getattr(type(self), attr_name, None)
            if method and hasattr(method, _ACTION_SPEC_ATTR):
                specs[attr_name] = getattr(method, _ACTION_SPEC_ATTR)
        return specs

    def get_action_spec(self, action_name: str) -> ActionSpec:
        """action_name에 해당하는 ActionSpec을 반환한다.

        ToolRegistry.get_action_spec()에서 type(read|write) 조회에 사용된다.
        """
        specs = self._action_specs()
        if action_name not in specs:
            raise KeyError(f"Unknown action: {action_name}")
        return specs[action_name]

    def bind_execution_context(
        self,
        *,
        global_context: Any,
        trigger_event: Any,
    ) -> None:
        """Agent 실행 직전, spec에 포함된 tool에만 실행 컨텍스트를 바인딩한다."""
        return None

    def to_langchain_tools(self) -> list[StructuredTool]:
        """@action 메서드를 LangChain StructuredTool 리스트로 변환한다.

        Execution Agent의 llm.bind_tools()에 사용된다.
        의존성(API 클라이언트 등)은 생성자에서 주입받아 클로저로 캡처된다.
        """
        tools = []
        for action_name, spec in self._action_specs().items():
            method = getattr(self, action_name)
            tools.append(
                StructuredTool(
                    name=f"{self.name}__{action_name}",
                    description=spec.description,
                    args_schema=spec.input_model,
                    coroutine=method,
                    metadata={"type": spec.type},
                )
            )
        return tools

    def schema(self) -> dict[str, Any]:
        """ToolRegistry.schema()에서 호출된다."""
        return {
            "display_name": self.display_name,
            "description": self.description,
            "actions": {
                name: {
                    "description": spec.description,
                    "type": spec.type,
                    "default_failure_policy": spec.default_failure_policy,
                    "default_max_retry": spec.default_max_retry,

                }
                for name, spec in self._action_specs().items()
            },
        }
