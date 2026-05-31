"""Builder/관리 도구에 Trigger 이벤트 스펙 목록을 제공하는 registry.

리뷰 흐름에서는 base.py의 EventSource 구현들이 모인 조회 표면으로 보면 된다.
현재 webhook ingress 런타임은 registry를 거치지 않고 DB condition을 직접
검증하므로, 이 파일의 책임은 실행 판정이 아니라 condition 작성 가능 범위를
외부 도구에 노출하는 데 있다.
"""

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
        """Builder/관리 도구가 source별 event 스펙을 조회할 때 사용된다.

        런타임 resolver는 현재 registry를 통하지 않고 DB policy와 where
        evaluator만으로 match를 결정한다.
        """
        if source not in cls._sources:
            raise KeyError(f"Unknown source: {source}")
        return cls._sources[source].get_event_spec(event_type)

    @classmethod
    def schema(cls) -> dict:
        """Builder Agent가 사용 가능한 소스/이벤트/필터 전체 목록을 반환한다.

        Builder Agent는 이 스키마를 보고 trigger.config.source와
        filter 후보를 생성한다.
        """
        return {
            name: source.schema()
            for name, source in cls._sources.items()
        }
