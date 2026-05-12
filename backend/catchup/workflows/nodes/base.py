from enum import StrEnum

from catchup.workflows.nodes.common.action import ActionSpec
from catchup.workflows.nodes.common.action import get_action_specs


class NodeTypes(StrEnum):
    CONNECTOR = "connector"
    TOOL = "tool"
    LLM = "llm"


class BaseNode:
    """
    모든 워크플로우 노드의 최상위 Base 클래스.

    액션 메서드에 @action 데코레이터로 입출력 스키마를 선언한다.
    execute() 호출 시 선언된 input_model로 Pydantic 검증이 수행된다.
    ValidationError는 그대로 전파되어 Builder Agent 피드백 루프에 활용된다.
    """

    def __init__(
        self,
        name: str,
        display_name: str,
        description: str,
    ):
        self.name = name
        self.display_name = display_name
        self.description = description

    def get_action_spec(self, action: str) -> ActionSpec | None:
        method = getattr(self, action, None)
        if method is None:
            return None
        return getattr(getattr(method, "__func__", None), "__action_spec__", None)

    async def execute(
        self,
        action: str,
        inputs: dict,
        node_results: dict,
    ) -> dict:
        method = getattr(self, action, None)
        if method is None:
            raise NotImplementedError(f"{self.name}.{action} is not implemented.")

        spec = self.get_action_spec(action)
        # 스펙이 있으면 Pydantic 검증 수행, 없으면 raw dict 전달
        validated = spec.input_model(**inputs) if spec else inputs

        result = await method(validated, node_results)

        if spec:
            # OutputModel로 반환값 검증 후 직렬화된 dict로 반환
            # ValidationError는 그대로 전파 → Builder Agent 피드백 루프에 활용
            return spec.output_model(**result).model_dump()

        return result


class BaseConnector(BaseNode):
    pass


class BaseTool(BaseNode):
    pass


class BaseLlm(BaseNode):
    pass
