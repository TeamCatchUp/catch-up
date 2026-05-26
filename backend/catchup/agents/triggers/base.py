"""
Trigger Registry: 트리거로 등록 가능한 이벤트 소스와 그 명세를 관리한다.

핵심 개념 구분:
  filterable_fields (EventSpec)   — "이 이벤트에서 어떤 필드를 조건으로 쓸 수 있는가"의 스키마 선언.
                                    Builder Agent가 filter를 작성할 때 참조한다.
  filter_condition (AgentTrigger) — Builder Agent가 실제로 건 조건값 {"channel_id": "C123ABC"}.
                                    trigger resolver가 웹훅 payload와 대조해 발동 여부를 결정한다.
"""
from typing import Literal

from pydantic import BaseModel
from pydantic import Field


class EventSpec(BaseModel):
    type: str
    description: str
    filterable_fields: dict[
        str, Literal["string", "integer", "boolean"]
    ] = Field(
        description=(
            "이 이벤트에서 어떤 필드를 조건으로 쓸 수 있는지를 나타낸다. "
            "Builder Agent가 filter를 작성할 때 참조한다."
        )
    )

    def schema_dict(self) -> dict:
        """Builder Agent에게 노출할 이벤트 스펙을 직렬화한다.

        TriggerRegistry.schema()가 이 메서드를 호출해 소스별 스키마를 조립한다.
        """
        return {
            "description": self.description,
            "filterable_fields": self.filterable_fields,
        }


class EventSource:
    name: str
    display_name: str
    supported_events: list[EventSpec]

    def schema(self) -> dict:
        """이 소스가 지원하는 이벤트 목록을 반환한다.

        TriggerRegistry.schema()에서 호출되며, Builder Agent가
        trigger.config.filter를 안전하게 생성하는 데 사용된다.
        """
        return {
            "display_name": self.display_name,
            "events": {
                event.type: event.schema_dict()
                for event in self.supported_events
            },
        }

    def get_event_spec(self, event_type: str) -> EventSpec:
        """event_type에 해당하는 EventSpec을 반환한다.

        trigger resolver가 filter_condition의 키가 filterable_fields에
        정의된 필드인지 검증하는 데 사용된다.
        """
        for event in self.supported_events:
            if event.type == event_type:
                return event
        raise KeyError(f"Unknown event type: {event_type}")
