from enum import StrEnum

class AuditLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEventStatus(StrEnum):
    ATTEMPT = "ATTEMPT"
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"


class AuditResult(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
