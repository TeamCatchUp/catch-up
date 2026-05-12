from catchup.workflows.nodes.base import BaseNode
from catchup.workflows.nodes.common.action import get_action_specs


class NodeRegistry:
    _nodes: dict[str, BaseNode] = {}

    @classmethod
    def register(cls, node: BaseNode) -> None:
        cls._nodes[node.name] = node

    @classmethod
    def get(cls, name: str) -> BaseNode:
        if name not in cls._nodes:
            raise KeyError(f"Node '{name}' is not registered.")
        return cls._nodes[name]

    @classmethod
    def all(cls) -> dict[str, BaseNode]:
        return cls._nodes

    @classmethod
    def schema(cls) -> dict[str, dict]:
        """
        등록된 모든 노드의 액션별 스키마를 반환한다.

        Workflow Builder Agent가 사용 가능한 노드 목록과
        각 액션의 입출력 스펙을 파악하기 위해 사용한다.
        """
        result = {}
        for name, node in cls._nodes.items():
            actions = {
                action_name: {
                    "description": spec.description,
                    "input_schema": spec.input_model.model_json_schema(),
                    "output_schema": spec.output_model.model_json_schema(),
                }
                for action_name, spec in get_action_specs(node).items()
            }
            result[name] = {
                "name": node.name,
                "display_name": node.display_name,
                "description": node.description,
                "actions": actions,
            }
        return result
