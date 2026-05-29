from typing import Literal

from pydantic import BaseModel
from pydantic import Field

from catchup.agents.enums import ConfirmationGate
from catchup.agents.enums import FailurePolicy


# === Trigger ===
class WebhookConfig(BaseModel):
    source: str = Field(description="이벤트 소스. jira, channeltalk, slack 등")
    filter: dict[str, str] = Field(
        default=dict,
        description="KV 매칭 필터. 런타임에서 all(payload[k]==v) 평가"
    )


class TriggerSpec(BaseModel):
    type: Literal["webhook"] = Field(description="트리거 유형")
    config: WebhookConfig


# === System Prompt ===
class SystemPromptSpec(BaseModel):
    role: str = Field(description="에이전트 역할과 목표")
    background: str = Field(description="조직/도메인 컨텍스트")
    execution_guidelines: str = Field(
        description="스텝별 워크플로우. 도구 호출과 LLM 추론 스텝을 혼합하여 기술"
    )


# === Tool ===
class ToolSpec(BaseModel):
    name: str = Field(description="'{tool}.{action}' 형식. ToolRegistry 참조")
    confirmation_gate: ConfirmationGate = Field(description="도구 실행 승인 방식")
    failure_policy: FailurePolicy = Field(description="실패 시 처리 정책")
    max_retry: int | None = Field(
        default=None,
        description="최대 재시도 횟수"
    )


# === User Input ===
class RequiredUserInput(BaseModel):
    key: str = Field(description="user_input_values 컬럼(JSONB)에 저장되는 키")
    label: str = Field(description="사용자에게 보여주는 레이블")
    type: Literal["string", "integer", "boolean"]


# === Execution Agent 구동을 위해 필요한 최종 스펙 === 
class AgentSpec(BaseModel):
    agent_id: str = Field(description="논리적 에이전트 식별자. 버전 간 공유")
    name: str
    trigger: TriggerSpec
    system_prompt: SystemPromptSpec
    tools: list[ToolSpec] = Field(description="사용 가능한 도구 목록")
    execution_order: list[str] = Field(description="Harness 검증용 실행 순서")
    required_user_inputs: list[RequiredUserInput]  # TODO: tool binding 메커니즘 도입
