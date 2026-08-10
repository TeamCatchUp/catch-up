"""기존 APScheduler 작업의 다음 실행 시각만 교체한다."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Protocol

from apscheduler.job import Job


class DynamicRescheduler(Protocol):
    def reschedule_job(self, job_id: str, **kwargs: Any) -> Job: ...


def reschedule_one_shot_job(
    scheduler: DynamicRescheduler,
    *,
    job_id: str,
    next_run_at: datetime,
) -> Job:

    normalized_job_id = job_id.strip()
    if not normalized_job_id:
        raise ValueError("job_id must not be blank")
    if next_run_at.tzinfo is None or next_run_at.utcoffset() is None:
        raise ValueError("next_run_at must include timezone information")

    # TODO(llm-wiki-settings-db): 호출 전 별도 LLM Wiki 설정 DB에서 최신
    # next_run_at을 읽고 실행권 lock을 획득한다.
    # TODO(llm-wiki-settings-api): 설정 API가 DB 갱신을 확정한 뒤 이 함수를
    # 호출하도록 연결한다. 
    return scheduler.reschedule_job(
        normalized_job_id,
        trigger="date",
        run_date=next_run_at,
    )
