"""수동 검색용 시간 필터 빌더."""

from datetime import datetime
from datetime import timezone

from catchup.db.models import SourceType
from catchup.schemas.filters import TemporalFilter

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def build_manual_search_temporal_filters(
    tool_filters: list[SourceType] | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[TemporalFilter]:
    """수동 검색용 시간 필터를 생성한다.

    모든 툴에 created_at을 적용한다.
    start_date나 end_date 중 하나라도 지정되면 필터를 생성한다.
    - start_date 미지정: EPOCH (1970-01-01)으로 resolve한다.
    - end_date 미지정: 현재 시각(UTC)으로 resolve한다.
    """
    if not (start_date or end_date):
        return []

    resolved_start = start_date or EPOCH
    resolved_end = end_date or datetime.now(timezone.utc)
    target_tools = tool_filters or list(SourceType)

    return [
        TemporalFilter(
            time_field="created_at",
            start_date=resolved_start,
            end_date=resolved_end,
            tools=target_tools,
        )
    ]
