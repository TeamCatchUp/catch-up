"""Builder가 안전한 trigger condition을 만들 수 있도록 이벤트 스펙을 정의한다.

리뷰 흐름에서는 런타임 match보다 앞선 설계 입력으로 읽는다. 이 파일은
resolver.py가 직접 호출하는 실행 경로가 아니라, Builder/관리 도구가 어떤
source/event/filter 조합을 저장해도 되는지 알려 주는 계약이다.

핵심 개념 구분:
  filterable_fields (EventSpec) — Builder Agent가 policies.py의 where clause를
                                  만들 수 있도록 path/op/value 계약을 선언한다.
  condition (AgentTrigger)      — Builder Agent가 실제로 저장하는 실행 정책 JSON.
                                  policies.py가 이 JSON의 policy shape를 검증한다.

예시:
  EventSpec(
      type="user_chat.new_message",
      description="유저 채팅방에 새 메시지가 생성됨",
      filterable_fields={
          "channel_id": FilterFieldSpec(
              path="$.payload.entity.channelId",
              type="string",
              description="메시지가 발생한 채널 ID",
              operators=["eq", "in"],
              examples=["ch-001"],
          ),
      },
  )

  Builder Agent는 위 스펙을 보고 다음 condition clause를 만들 수 있다.
  {
      "path": "$.payload.entity.channelId",
      "op": "eq",
      "value": "ch-001",
  }
"""
from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import Field

FieldType = Literal["string", "integer", "boolean"]
FilterOperator = Literal["eq", "neq", "in", "exists"]


class FilterFieldSpec(BaseModel):
    """Builder가 policies.py의 where clause를 만들 때 참조하는 필드 명세."""

    path: str = Field(
        description="condition.where.all[]에 들어갈 JSONPath 표현식",
    )
    type: FieldType = Field(
        description="value 타입 힌트. Builder가 적절한 값을 요청/생성할 때 사용한다.",
    )
    description: str = Field(description="Builder에게 노출할 필드 설명")
    operators: list[FilterOperator] = Field(
        default_factory=lambda: ["eq"],
        min_length=1,
        description="이 필드에서 사용할 수 있는 where operator 목록",
    )
    examples: list[Any] = Field(
        default_factory=list,
        description="Builder가 condition 예시를 만들 때 참고할 값",
    )

    def condition_clause(
        self,
        value: Any,
        *,
        op: FilterOperator | None = None,
    ) -> dict[str, Any]:
        """policies.py의 where.all[]에 들어갈 clause를 만든다."""
        selected_op = op or self.operators[0]
        if selected_op not in self.operators:
            raise ValueError(f"Unsupported operator for field: {selected_op}")
        return {
            "path": self.path,
            "op": selected_op,
            "value": value,
        }


class EventSpec(BaseModel):
    type: str
    description: str
    filterable_fields: dict[str, FilterFieldSpec] = Field(
        description=(
            "이 이벤트에서 어떤 필드를 condition.where clause로 쓸 수 있는지를 "
            "나타낸다. Builder Agent가 trigger.condition을 작성할 때 참조한다."
        )
    )


class EventSource:
    name: str
    display_name: str
    supported_events: list[EventSpec]

    def schema(self) -> dict:
        """이 소스가 지원하는 이벤트 목록을 반환한다.

        TriggerRegistry.schema()에서 호출되며, Builder Agent가
        trigger.condition을 안전하게 생성하는 데 사용된다.
        """
        return {
            "display_name": self.display_name,
            "events": {
                event.type: {
                    "description": event.description,
                    "filterable_fields": {
                        name: field.model_dump(mode="json")
                        for name, field in event.filterable_fields.items()
                    },
                }
                for event in self.supported_events
            },
        }

    def get_event_spec(self, event_type: str) -> EventSpec:
        """event_type에 해당하는 EventSpec을 반환한다.

        현재 런타임 resolver는 저장된 policy JSON과 where clause를 직접
        평가한다. 이 스펙은 Builder가 안전한 condition 후보를 만들 때 쓰는
        설계 입력이다.
        """
        for event in self.supported_events:
            if event.type == event_type:
                return event
        raise KeyError(f"Unknown event type: {event_type}")
