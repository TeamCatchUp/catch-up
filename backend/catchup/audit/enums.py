### TODO: events/enums로 이관
from __future__ import annotations

from enum import StrEnum

class EventType(StrEnum):
    AUTH = "AUTH"
    INTEGRATION = "INTEGRATION"
    SYNC = "SYNC"
    CHAT = "CHAT"
    SYSTEM = "SYSTEM"

class SystemEventAction(StrEnum):
    STARTUP_DB_INIT = "startup_db_init"
    STARTUP_DB_SCHEMA_DRIFT = "startup_db_schema_drift"
    STARTUP_SCHEDULER_INIT = "startup_scheduler_init"
    STARTUP_CHECKPOINTER_INIT = "startup_checkpointer_init"
    STARTUP_REDIS_INIT = "startup_redis_init"
    SHUTDOWN_SCHEDULER = "shutdown_scheduler"
    SHUTDOWN_CHECKPOINTER = "shutdown_checkpointer"

class AuthEventAction(StrEnum):
    LOGIN_ATTEMPT = "login_attempt"
    TOKEN_REFRESH = "token_refresh"
    LOGOUT = "logout"

class IntegrationEventAction(StrEnum):
    OAUTH_CONNECT = "oauth_connect"
    OAUTH_DISCONNECT = "oauth_disconnect"
    OAUTH_REFRESH = "oauth_refresh"
    WEBHOOK_REGISTER = "webhook_register"

class SyncEventAction(StrEnum):
    FULL_SYNC = "full_sync"
    INCREMENTAL_SYNC = "incremental_sync"
    SYNC_FAILURE = "sync_failure"
    SCHEMA_DRIFT_DETECTED = "schema_drift_detected"
    EMBEDDING_BATCH = "embedding_batch"


class ChatEventAction(StrEnum):
    MESSAGE_SENT = "message_sent"
    MESSAGE_FAILED = "message_failed"

### =================
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
