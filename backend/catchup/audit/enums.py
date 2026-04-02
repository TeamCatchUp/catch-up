"""
[DEPRECATED WARNING] BaseAuditAction 기반 감사로그 작성 방식 개편
"""
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
