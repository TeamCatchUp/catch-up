from catchup.agents.triggers.base import EventSource
from catchup.agents.triggers.base import EventSpec


class TriggerRegistry:
    _sources: dict[str, EventSource] = {}

    @classmethod
    def register(cls, source: EventSource) -> None:
        """이벤트 소스를 레지스트리에 등록한다.

        서버 시작 시 각 EventSource 구현체가 스스로를 등록한다.
        """
        cls._sources[source.name] = source

    @classmethod
    def get_event_spec(cls, source: str, event_type: str) -> EventSpec:
        """trigger resolver에서 filter_condition 유효성 검증 시 사용된다.

        filter_condition의 키가 해당 소스/이벤트의 filterable_fields에
        정의된 필드인지 확인하는 진입점이다.
        """
        if source not in cls._sources:
            raise KeyError(f"Unknown source: {source}")
        return cls._sources[source].get_event_spec(event_type)

    @classmethod
    def schema(cls) -> dict:
        """Builder Agent가 사용 가능한 소스/이벤트/필터 전체 목록을 반환한다.

        Builder Agent는 이 스키마를 보고 trigger.config.source와
        filter를 안전하게 생성한다.
        """
        return {
            name: source.schema()
            for name, source in cls._sources.items()
        }
