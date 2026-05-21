"""search.filters 단위 테스트."""

from datetime import datetime
from datetime import timezone

from catchup.db.models import SourceType
from catchup.search.filters import EPOCH
from catchup.search.filters import build_manual_search_temporal_filters


def test_both_absent_returns_empty():
    """start_date, end_date 둘 다 없으면 빈 리스트를 반환한다."""
    result = build_manual_search_temporal_filters()
    assert result == []


def test_start_date_only():
    """start_date만 있으면 end_date를 now(UTC)로 resolve한다."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = build_manual_search_temporal_filters(start_date=start)
    assert len(result) == 1
    tf = result[0]
    assert tf.time_field == "created_at"
    assert tf.start_date == start
    assert tf.end_date > start


def test_end_date_only():
    """end_date만 있으면 start_date를 EPOCH으로 resolve한다."""
    end = datetime(2026, 4, 1, tzinfo=timezone.utc)
    result = build_manual_search_temporal_filters(end_date=end)
    assert len(result) == 1
    tf = result[0]
    assert tf.time_field == "created_at"
    assert tf.start_date == EPOCH
    assert tf.end_date == end


def test_both_present():
    """start_date, end_date 둘 다 있으면 그대로 반환한다."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 4, 1, tzinfo=timezone.utc)
    result = build_manual_search_temporal_filters(start_date=start, end_date=end)
    assert len(result) == 1
    tf = result[0]
    assert tf.start_date == start
    assert tf.end_date == end


def test_all_source_types_included_when_no_tool_filters():
    """tool_filters 없으면 모든 SourceType이 포함된다."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = build_manual_search_temporal_filters(start_date=start)
    tf = result[0]
    assert set(tf.tools) == set(SourceType)


def test_tool_filters_respected():
    """tool_filters가 있으면 해당 툴만 포함된다."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = build_manual_search_temporal_filters(
        tool_filters=[SourceType.SLACK, SourceType.GITHUB],
        start_date=start,
    )
    tf = result[0]
    assert set(tf.tools) == {SourceType.SLACK, SourceType.GITHUB}


def test_always_uses_created_at():
    """tool_filters에 Confluence/Jira가 포함돼도 time_field는 created_at이다."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = build_manual_search_temporal_filters(
        tool_filters=[SourceType.CONFLUENCE, SourceType.JIRA],
        start_date=start,
    )
    assert result[0].time_field == "created_at"
