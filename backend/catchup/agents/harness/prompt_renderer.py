import json

from pydantic import BaseModel
from pydantic import Field

from catchup.agents.schemas import AgentSpec
from catchup.agents.schemas import ToolReferenceSpec
from catchup.agents.tools.registry import ToolRegistry
from catchup.agents.triggers.events import AgentWebhookEvent
from catchup.prompts.loader import prompt_loader


class _FieldInfo(BaseModel):
    type: str
    description: str
    reference_kind: str | None = None
    allowed_values: list[str] = Field(default_factory=list)


class _ToolContext(BaseModel):
    name: str
    type: str
    description: str
    input_fields: dict[str, _FieldInfo]
    output_fields: dict[str, _FieldInfo]

    model_config = {"arbitrary_types_allowed": True}


def _build_tool_context(
    qualified_name: str,
    references: list[ToolReferenceSpec],
) -> _ToolContext:
    """ToolRegistry에서 ActionSpec을 읽어 템플릿용 컨텍스트로 변환한다."""
    action_spec = ToolRegistry.get_action_spec(qualified_name)
    references_by_argument = {reference.argument: reference for reference in references}

    def extract_fields(model: type[BaseModel]) -> dict[str, _FieldInfo]:
        fields = {}
        for field_name, field_info in model.model_fields.items():
            annotation = field_info.annotation
            type_str = getattr(annotation, "__name__", str(annotation))
            description = field_info.description or ""
            reference = references_by_argument.get(field_name)
            fields[field_name] = _FieldInfo(
                type=type_str,
                description=description,
                reference_kind=reference.kind if reference else None,
                allowed_values=list(reference.values.keys()) if reference else [],
            )
        return fields

    return _ToolContext(
        name=qualified_name,
        type=action_spec.type.value,
        description=action_spec.description,
        input_fields=extract_fields(action_spec.input_model),
        output_fields=extract_fields(action_spec.output_model) if action_spec.output_model else {},
    )


def render_system_prompt(
    spec: AgentSpec,
    user_input_values: dict,
    trigger_event: AgentWebhookEvent,
) -> str:
    """AgentSpec과 런타임 컨텍스트로 Execution Agent 시스템 프롬프트를 렌더링한다.

    섹션별 출처:
      role, background, execution_guidelines — Builder Agent가 작성한 spec
      tools                                  — ToolRegistry 자동 렌더링
      user_inputs, trigger_event/payload     — 런타임 주입
      harness_rules                          — 고정 텍스트
    """
    tools = [
        _build_tool_context(
            tool_spec.name,
            spec.references.get(tool_spec.name, []),
        )
        for tool_spec in spec.tools
    ]
    event = trigger_event.model_dump(mode="json")

    return prompt_loader.get_prompt(
        "agents/execution_agent_system_prompt.j2",
        role=spec.system_prompt.role,
        background=spec.system_prompt.background,
        execution_guidelines=spec.system_prompt.execution_guidelines,
        tools=[t.model_dump() for t in tools],
        user_inputs=user_input_values,
        trigger_event={
            "event_id": event["event_id"],
            "external_event_id": event["external_event_id"],
            "source": event["source"],
            "event_type": event["event_type"],
            "occurred_at": event["occurred_at"],
            "received_at": event["received_at"],
        },
        trigger_payload_json=json.dumps(
            event["payload"],
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
