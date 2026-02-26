from __future__ import annotations

from enum import StrEnum

class EventType(StrEnum):
    AUTH = "AUTH"
    INTEGRATION = "INTEGRATION"
    SYNC = "SYNC"
    CHAT = "CHAT"
    SYSTEM = "SYSTEM"

class AuthEventAction(StrEnum):
    LOGIN_ATTEMPT = "login_attempt"
    TOKEN_REFRESH = "token_refresh"
    LOGOUT = "logout"

class IntegrationEventAction(StrEnum):
    OAUTH_CONNECT = "oauth_connect"
    OAUTH_DISCONNECT = "oauth_disconnect"
    OAUTH_REFRESH = "oauth_refresh"
    WEBHOOK_REGISTER = "webhook_register"
    CONNECTOR_HEALTH_CHECK = "connector_health_check"

class SyncEventAction(StrEnum):
    FULL_SYNC = "full_sync"
    INCREMENTAL_SYNC = "incremental_sync"
    SYNC_FAILURE = "sync_failure"
    SCHEMA_DRIFT_DETECTED = "schema_drift_detected"
    EMBEDDING_BATCH = "embedding_batch"


class ChatEventAction(StrEnum):
    MESSAGE_SENT = "message_sent"
    MESSAGE_FAILED = "message_failed"