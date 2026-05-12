import hashlib
import json
import re
from functools import lru_cache
from typing import Any

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from catchup.workflows.graph.state import WorkflowState
from catchup.workflows.nodes.base import BaseNode
from catchup.workflows.nodes.common.registry import NodeRegistry


# {{ trigger.message }} 또는 {{ node_results.search.results }} 형태
_EXPR_RE = re.compile(r"^\{\{\s*([\w.]+)\s*\}\}$")


def _resolve_expr(expr: str, state: WorkflowState) -> Any:
    match = _EXPR_RE.match(expr)
    if not match:
        return expr  # 표현식이 아니면 리터럴 값으로 반환

    value: Any = state
    for key in match.group(1).split("."):
        try:
            value = value[key]
        except (KeyError, TypeError) as e:
            raise KeyError(f"Failed to resolve expression '{expr}': {e}") from e
    return value


def resolve_inputs(inputs_spec: dict, state: WorkflowState) -> dict:
    """노드 스펙의 inputs 딕셔너리에서 모든 표현식을 해석한다."""
    return {
        key: _resolve_expr(value, state) if isinstance(value, str) else value
        for key, value in inputs_spec.items()
    }


class WorkflowCompileError(Exception):
    pass


def _field_annotation(model, field: str) -> Any | None:
    f = model.model_fields.get(field)
    return f.annotation if f else None


def _validate_spec(spec: dict) -> None:
    """JSON 스펙의 구조적 유효성과 노드 간 타입 호환성을 검증한다.

    검증 단계:
    1. 노드 등록 여부
    2. 액션 존재 여부
    3. input 필드 존재 여부 (InputModel.model_fields 기준)
    4. 노드 간 타입 호환성 ({{ node_results.NODE.FIELD }} 표현식 추적)
    """
    node_specs: dict[str, dict] = {n["id"]: n for n in spec.get("nodes", [])}

    for node_id, node_spec in node_specs.items():
        try:
            node = NodeRegistry.get(node_spec["node"])
        except KeyError:
            raise WorkflowCompileError(f"Node '{node_spec['node']}' is not registered.")

        action_spec = node.get_action_spec(node_spec["action"])
        if action_spec is None:
            raise WorkflowCompileError(
                f"Action '{node_spec['action']}' not found on node '{node_spec['node']}'."
            )

        for field in node_spec.get("inputs", {}):
            if _field_annotation(action_spec.input_model, field) is None:
                raise WorkflowCompileError(
                    f"Input field '{field}' not found on "
                    f"{node_spec['node']}.{node_spec['action']}."
                )

    # {{ node_results.FROM_NODE_ID.FROM_FIELD }} 표현식으로 노드 간 타입 호환성 검증
    for node_id, node_spec in node_specs.items():
        to_node = NodeRegistry.get(node_spec["node"])
        to_action_spec = to_node.get_action_spec(node_spec["action"])

        for to_field, value in node_spec.get("inputs", {}).items():
            if not isinstance(value, str):
                continue

            match = _EXPR_RE.match(value)
            if not match:
                continue

            path = match.group(1).split(".")
            if path[0] != "node_results" or len(path) < 3:
                continue

            from_node_id, from_field = path[1], path[2]

            if from_node_id not in node_specs:
                raise WorkflowCompileError(
                    f"Expression '{value}' references unknown node '{from_node_id}'."
                )

            from_node = NodeRegistry.get(node_specs[from_node_id]["node"])
            from_action_spec = from_node.get_action_spec(
                node_specs[from_node_id]["action"]
            )
            if from_action_spec is None:
                continue

            from_type = _field_annotation(from_action_spec.output_model, from_field)
            to_type = _field_annotation(to_action_spec.input_model, to_field)

            if from_type is None:
                raise WorkflowCompileError(
                    f"Output field '{from_field}' not found on "
                    f"{node_specs[from_node_id]['node']}.{node_specs[from_node_id]['action']}."
                )

            if from_type != to_type:
                raise WorkflowCompileError(
                    f"Type mismatch: {from_node_id}.{from_field} ({from_type}) → "
                    f"{node_id}.{to_field} ({to_type})."
                )


def _build_node_fn(node: BaseNode, node_spec: dict):
    """노드 스펙을 WorkflowState를 받는 LangGraph 비동기 함수로 변환한다."""
    node_id = node_spec["id"]
    action = node_spec["action"]
    inputs_spec = node_spec.get("inputs", {})

    async def node_fn(state: WorkflowState) -> dict:
        inputs = resolve_inputs(inputs_spec, state)
        result = await node.execute(action, inputs, state["node_results"])
        # 자기 결과만 반환. _merge_node_results reducer가 기존 node_results에 머지한다.
        return {"node_results": {node_id: result}}

    node_fn.__name__ = f"{node_spec['node']}__{action}"
    return node_fn


@lru_cache(maxsize=128)
def _compile_cached(spec_hash: str, spec_json: str):
    spec = json.loads(spec_json)
    graph: StateGraph = StateGraph(WorkflowState)

    for node_spec in spec["nodes"]:
        node = NodeRegistry.get(node_spec["node"])
        graph.add_node(node_spec["id"], _build_node_fn(node, node_spec))

    graph.add_edge(START, spec["nodes"][0]["id"])

    for edge in spec["edges"]:
        graph.add_edge(edge["from"], edge["to"])

    graph.add_edge(spec["nodes"][-1]["id"], END)

    return graph.compile()


def compile_workflow(spec: dict):
    """JSON 스펙을 검증하고 LangGraph CompiledGraph로 변환한다.

    동일한 스펙은 해시 기반으로 캐싱되어 재컴파일 비용이 없다.

    Raises:
        WorkflowCompileError: node not registered, action not found, type mismatch, etc.
    """
    _validate_spec(spec)

    spec_json = json.dumps(spec, sort_keys=True, ensure_ascii=False)
    spec_hash = hashlib.md5(spec_json.encode()).hexdigest()

    return _compile_cached(spec_hash, spec_json)
