from __future__ import annotations

SYNC_JOB_STATUS_CHANNEL_PREFIX = "sync:jobs"

def build_job_status_channel(job_id: str) -> str:
    normalized_job_id = job_id.strip()
    if not normalized_job_id:
        raise ValueError("job_id is required")
    return f"{SYNC_JOB_STATUS_CHANNEL_PREFIX}:{normalized_job_id}:status"
    