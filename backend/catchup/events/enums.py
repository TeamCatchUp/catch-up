from enum import StrEnum


class EventTopic(StrEnum):
    AUDIT = "audit"


class EventType(StrEnum):
    AUTH = "AUTH"
    INTEGRATION = "INTEGRATION"
    SYNC = "SYNC"
    CHAT = "CHAT"
    AUDIT = "AUDIT"
    SYSTEM = "SYSTEM"


class AuthEventAction(StrEnum):
    # 로그인 시도
    LOGIN_ATTEMPT = "login_attempt"
    
    # 로그인 성공
    LOGIN_SUCCESS = "login_success"
    
    # 로그인 실패
    LOGIN_FAILURE = "login_failure"
    
    # 토큰 재발급
    TOKEN_REFRESH = "token_refresh"
    
    # 로그아웃
    LOGOUT = "logout"


class ChatEventAction(StrEnum):
    # 사용자 질문 생성
    MESSAGE_RECEIVED = "message_received"
    
    # 지식 베이스 검색 완료
    RETRIEVAL_COMPLETED = "retrieval_completed"
    
    # 답변 생성 완료
    RESPONSE_GENERATED = "response_generated"
    
    # 답변 생성 실패
    RESPONSE_FAILED = "response_failed"
    
    # 출처 목록 노출
    SOURCES_PROVIDED = "sources_provided"
    

class AwsS3EventAction(StrEnum):
    # s3 업로드 성공
    UPLOAD_SUCCESS = "upload_success"
    
    # s3 업로드 실패
    UPLOAD_FAILED = "upload_failed"
    


class SystemEventAction(StrEnum):
    STARTUP_DB_INIT = "startup_db_init"
    STARTUP_DB_SCHEMA_DRIFT = "startup_db_schema_drift"
    STARTUP_SCHEDULER_INIT = "startup_scheduler_init"
    STARTUP_CHECKPOINTER_INIT = "startup_checkpointer_init"
    STARTUP_REDIS_INIT = "startup_redis_init"
    SHUTDOWN_SCHEDULER = "shutdown_scheduler"
    SHUTDOWN_CHECKPOINTER = "shutdown_checkpointer"

# 1. Slack / Atalssian : 앱 설치 Callback (metadata에 성공 / 실패 / 실패 시 사유 기록)
# 2. Github : Installation Event를 Webhook으로 수신 (metadata에 성공 / 실패 / 실패 시 사유 기록)
# 3. DB 저장 시점에 저장 기록
class IntegrationEventAction(StrEnum):
    # Callback 수신
    OAUTH_CALLBACK = "oauth_callback"
    
    # Github Installation Event 수신
    INSTALLATION_EVENT_RECIEVED = "installation_event_recieved"
    
    # OAuth Token 저장 완료
    OAUTH_PERSISTED = "oauth_persisted"

    # Atlassian OAuth Token Refresh
    OAUTH_REFRESH_ATTEMPT = "oauth_refresh_attempt"
    OAUTH_REFRESH_SUCCESS = "oauth_refresh_success"
    OAUTH_REFRESH_FAILED = "oauth_refresh_failed"

    # Jira Dynamic Webhook Register
    WEBHOOK_REGISTER = "webhook_register_attempt"
    WEBHOOK_REGISTER_SUCCESS = "webhook_register_success"
    WEBHOOK_REGISTER_FAILED = "webhook_register_failed"




class SyncEventAction(StrEnum):
    FULL_SYNC_REQUESTED = "full_sync_reqeusted"
    WEBHOOK_EVENT_ACCEPTED = "webhook_event_accepted"
    CONFLUENCE_POLLING_STARTED = "confluence_polling_started"
    SYNC_SUCCESS = "sync_success"
    SYNC_FAILED = "sync_failed"