from enum import StrEnum


class ActionType(StrEnum):
    READ = "read"
    WRITE = "write"


class FailurePolicy(StrEnum):
    RETRY_THEN_NOTIFY = "retry_then_notify"
    NOTIFY_AND_STOP = "notify_and_stop"
    SILENT_SKIP = "silent_skip"


class ConfirmationGate(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"
