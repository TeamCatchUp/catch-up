"""server/initialization.py의 orphan 인덱스 빌드 종료 로직을 검증한다.

배경: 서버 시작 시 ensure_vector_index()와 ensure_ks_all_indices()가
asyncio.create_task()로 동시 실행되면, 후자가 호출하는
_terminate_orphaned_index_builds()가 전자가 방금 시작한 정상 CREATE INDEX
CONCURRENTLY 커넥션을 이전 컨테이너의 고아 빌드로 오판해 종료시키는 레이스
컨디션이 있었다. backend_start가 서버 프로세스 시작 시각보다 이전인
커넥션만 orphan으로 판정하도록 고쳐 이를 방지한다.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from catchup.server.initialization import _terminate_orphaned_index_builds

CUTOFF = datetime.datetime(2026, 7, 1, tzinfo=datetime.timezone.utc)


class TestTerminateOrphanedIndexBuilds:
    @pytest.mark.asyncio
    async def test_select_query_filters_by_backend_start_cutoff(self):
        """orphan 판정 쿼리는 backend_start cutoff 조건과 파라미터를 포함해야 한다."""
        conn = MagicMock()
        empty_cursor = AsyncMock()
        empty_cursor.fetchall = AsyncMock(return_value=[])
        conn.execute = AsyncMock(return_value=empty_cursor)

        await _terminate_orphaned_index_builds(conn, CUTOFF)

        select_calls = [
            c for c in conn.execute.call_args_list if "pg_stat_activity" in c.args[0]
        ]
        assert select_calls, "pg_stat_activity 조회가 최소 1회 실행되어야 한다."
        for c in select_calls:
            sql, params = c.args[0], c.args[1]
            assert "backend_start" in sql
            assert params["cutoff"] == CUTOFF

    @pytest.mark.asyncio
    async def test_does_not_terminate_when_query_returns_no_rows(self):
        """cutoff 필터를 통과하지 못해 DB가 빈 결과를 반환하면 아무것도 종료하지 않는다."""
        conn = MagicMock()
        empty_cursor = AsyncMock()
        empty_cursor.fetchall = AsyncMock(return_value=[])
        conn.execute = AsyncMock(return_value=empty_cursor)

        await _terminate_orphaned_index_builds(conn, CUTOFF)

        terminate_calls = [
            c for c in conn.execute.call_args_list if "pg_terminate_backend" in c.args[0]
        ]
        assert terminate_calls == []

    @pytest.mark.asyncio
    async def test_terminates_pid_returned_by_query(self):
        """cutoff 조건을 통과해 반환된 pid는 여전히 종료 대상이 된다."""
        conn = MagicMock()
        call_count = {"n": 0}

        async def execute_side_effect(sql, params=None):
            cursor = AsyncMock()
            if "pg_stat_activity" in sql:
                call_count["n"] += 1
                rows = [(4321,)] if call_count["n"] == 1 else []
                cursor.fetchall = AsyncMock(return_value=rows)
            else:
                cursor.fetchall = AsyncMock(return_value=[])
            return cursor

        conn.execute = AsyncMock(side_effect=execute_side_effect)

        await _terminate_orphaned_index_builds(conn, CUTOFF)

        terminate_calls = [
            c for c in conn.execute.call_args_list if "pg_terminate_backend" in c.args[0]
        ]
        assert len(terminate_calls) == 1
        assert terminate_calls[0].args[1] == {"pid": 4321}
