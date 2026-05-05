from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from catchup.db.models import SourceType

CREATED_AT_TOOLS = [
    SourceType.GITHUB,
    SourceType.SLACK,
    SourceType.CHANNEL_TALK,
]

UPDATED_AT_TOOLS = [
    SourceType.CONFLUENCE,
    SourceType.JIRA,
]


class TemporalFilter(BaseModel):
    """
    시간 필터링 명세.
    Retrieval 시점에 시간 필터링이 필요한 경우,
    SQL과 Python Dict 기반 필터링을 모두 지원하기 위한 공통 스키마이다.
    """

    time_field: str = Field(
        ..., description="created_at 또는 updated_at (협업 툴 종류마다 다름.)"
    )
    start_date: datetime
    end_date: datetime
    tools: list[SourceType]


def build_temporal_filters(
    tool_filters: list[SourceType] | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[TemporalFilter]:
    if not (start_date and end_date):
        return []

    target_tools = tool_filters or [e for e in SourceType]
    filters = []

    created_at_tools = [t for t in target_tools if t in CREATED_AT_TOOLS]

    if created_at_tools:
        filters.append(
            TemporalFilter(
                time_field="created_at",
                start_date=start_date,
                end_date=end_date,
                tools=created_at_tools,
            )
        )

    updated_at_tools = [t for t in target_tools if t in UPDATED_AT_TOOLS]

    if updated_at_tools:
        filters.append(
            TemporalFilter(
                time_field="updated_at",
                start_date=start_date,
                end_date=end_date,
                tools=updated_at_tools,
            )
        )

    return filters
