from __future__ import annotations

from enum import StrEnum


class SyncDispatchStatus(StrEnum):
    ACCEPTED = "accepted"
    NO_EVENTS = "no_events"
    CONFLICT = "conflict"
    FAILED = "failed"


class SyncTrigger(StrEnum):
    API = "api"
    SCHEDULER = "scheduler"
    SYSTEM = "system"


class SyncTargetType(StrEnum):
    RESOURCE = "resource"
    CHANNEL = "channel"
    REPOSITORY = "repository"
    PROJECT = "project"
    SPACE = "space"


class SyncEventKind(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


class ClaimState(StrEnum):
    CLAIMED = "claimed"
    EVENT_NOT_FOUND = "event_not_found"
    EVENT_JOB_MISMATCH = "event_job_mismatch"
    EVENT_ALREADY_TERMINAL = "event_already_terminal"
    EVENT_CAS_CONFLICT = "event_cas_conflict"
    JOB_NOT_FOUND = "job_not_found"
    INVALID_INCREMENTAL_TASK = "invalid_incremental_task"
    RECORD_NOT_FOUND = "record_not_found"
    STALE_TASK = "stale_task"
    RECORD_CAS_CONFLICT = "record_cas_conflict"
