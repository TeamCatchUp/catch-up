from __future__ import annotations

from enum import StrEnum
from typing import Final

SYNC_EVENTS_STREAM_KEY: Final[str] = "sync:events"
SYNC_EVENTS_CONSUMER_GROUP: Final[str] = "sync:workers"
SYNC_EVENTS_DEADLETTER_STREAM_KEY: Final[str] = "sync:events:dlq"

STREAM_READ_NEW_MESSAGE_ID: Final[str] = ">"
STREAM_CLAIM_START_ID: Final[str] = "0-0"


class SyncStreamFailureReason(StrEnum):
    INVALID_STREAM_PAYLOAD = "invalid_stream_payload"
    EVENT_NOT_FOUND = "event_not_found"
    EVENT_ALREADY_TERMINAL = "event_already_terminal"
    EVENT_CAS_CONFLICT = "event_cas_conflict"
    RECORD_STATE_CONFLICT = "record_state_conflict"
    PROCESSING_EXCEPTION = "processing_exception"
    UNSUPPORTED_HANDLER = "unsupported_handler"
