from typing import Any

from pydantic import BaseModel
from pydantic import Field

from catchup.agents.enums import FailurePolicy


# === System Prompt ===
class SystemPromptSpec(BaseModel):
    role: str = Field(description="에이전트 역할과 목표")
    background: str = Field(description="조직/도메인 컨텍스트")
    execution_guidelines: str = Field(
        description="스텝별 워크플로우. 도구 호출과 LLM 추론 스텝을 혼합하여 기술"
    )


# === Tool ===
class ToolReferenceSpec(BaseModel):
    argument: str = Field(description="Tool input field name this reference constrains")
    kind: str = Field(description="Reference kind. Examples: slack_channel")
    values: dict[str, dict[str, Any]] = Field(
        description="Allowed human-readable input values mapped to non-secret resolved config"
    )


class ToolSpec(BaseModel):
    name: str = Field(description="'{tool}.{action}' 형식. ToolRegistry 참조")
    failure_policy: FailurePolicy = Field(description="실패 시 처리 정책")
    max_retry: int | None = Field(
        default=None,
        description="최대 재시도 횟수"
    )


# === Execution Agent 구동을 위해 필요한 최종 스펙 === 
class AgentSpec(BaseModel):
    agent_id: str = Field(description="논리적 에이전트 식별자. 버전 간 공유")
    name: str
    system_prompt: SystemPromptSpec
    tools: list[ToolSpec] = Field(description="사용 가능한 도구 목록")
    references: dict[str, list[ToolReferenceSpec]] = Field(
        default_factory=dict,
        description="Tool input argument별 허용 reference key와 resolved non-secret config"
    )
    execution_order: list[str] = Field(description="Harness 검증용 실행 순서")
