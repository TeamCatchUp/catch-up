from enum import StrEnum


class EventTopic(StrEnum):
    AUDIT = "audit"
    COST = "cost"


class EventType(StrEnum):
    AUTH = "AUTH"
    ONBOARDING = "ONBOARDING"
    INTEGRATION = "INTEGRATION"
    SYNC = "SYNC"
    CHAT = "CHAT"
    SYSTEM = "SYSTEM"
    USER = "USER"
    OAUTH = "OAUTH"
    USER_SETTINGS = "USER_SETTINGS"


# Event Actions
class BaseEventAction(StrEnum):
    pass


class AdminOAuthAction(BaseEventAction):
    SYNC_USERS = "sync_users"


class AuthEventAction(BaseEventAction):
    # 로그인
    LOGIN = "login"

    # 토큰 재발급
    TOKEN_REFRESH = "token_refresh"

    # 로그아웃
    LOGOUT = "logout"


class ChatEventAction(BaseEventAction):
    # 사용자 질문 생성
    USER_QUERY_SENT = "user_query_sent"

    # 답변 생성
    ASSISTANT_RESPONSE_GENERATED = "assistant_response_generated"

    # 출처 목록 노출
    SOURCES_PROVIDED = "sources_provided"


class AwsS3EventAction(BaseEventAction):
    AUDIT_FILE_UPLOADED = "audit_file_uploaded"


class SystemEventAction(BaseEventAction):
    STARTUP_SCHEDULER_INIT = "startup_scheduler_init"
    STARTUP_CHECKPOINTER_INIT = "startup_checkpointer_init"
    STARTUP_REDIS_INIT = "startup_redis_init"
    SHUTDOWN_SCHEDULER = "shutdown_scheduler"
    SHUTDOWN_CHECKPOINTER = "shutdown_checkpointer"


# 1. Slack / Atalssian : 앱 설치 Callback (metadata에 성공 / 실패 / 실패 시 사유 기록)
# 2. Github : Installation Event를 Webhook으로 수신 (metadata에 성공 / 실패 / 실패 시 사유 기록)
# 3. OAUTH_TOKEN_PERSISTED : DB 저장 시점에 저장 기록
class IntegrationEventAction(BaseEventAction):
    # Callback 수신
    OAUTH_CALLBACK = "oauth_callback"

    # Github Installation Event 수신
    INSTALLATION_EVENT_RECEIVED = "installation_event_received"

    # OAuth Token 저장 완료
    OAUTH_TOKEN_PERSISTED = "oauth_persisted"

    # Atlassian OAuth Token Refresh
    OAUTH_REFRESH = "oauth_refresh"

    # Jira Dynamic Webhook Register
    WEBHOOK_REGISTER = "webhook_register"


# DB 저장 성공 여부와 실행 Queue인 Redis Stream 발행 성공 여부로 로그에 기록
class SyncTriggerEventAction(BaseEventAction):
    # Full Sync Trigger
    FULL_SYNC_REQUESTED = "full_sync_requested"
    # Incremental Sync Trigger
    WEBHOOK_EVENT_RECEIVED = "webhook_event_received"
    CONFLUENCE_POLLING_STARTED = "confluence_polling_started"


class SyncIngestionEventAction(BaseEventAction):
    SUMMARIZE = "summarize"
    EMBED = "embed"
    DOCUMENT_PERSISTED = "document_persisted"


class UserEventAction(BaseEventAction):
    USER_PROMOTED = "user_promoted"
    ADMIN_REVOKED = "admin_revoked"


class UserCustomPromptEventAction(BaseEventAction):
    CREATED = "custom_prompt_created"
    EDITED = "custom_prompt_edited"
    DELETED = "custom_prompt_deleted"


class UserOnboardingEventAction(BaseEventAction):
    COMPLETED = "user_onboarding_completed"