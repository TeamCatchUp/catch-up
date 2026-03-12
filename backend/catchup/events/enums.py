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
    


# class SystemEventAction(StrEnum):
#     STARTUP_DB_INIT = "startup_db_init"
#     STARTUP_DB_SCHEMA_DRIFT = "startup_db_schema_drift"
#     STARTUP_SCHEDULER_INIT = "startup_scheduler_init"
#     STARTUP_CHECKPOINTER_INIT = "startup_checkpointer_init"
#     STARTUP_REDIS_INIT = "startup_redis_init"
#     SHUTDOWN_SCHEDULER = "shutdown_scheduler"
#     SHUTDOWN_CHECKPOINTER = "shutdown_checkpointer"


# class IntegrationEventAction(StrEnum):
#     OAUTH_CONNECT = "oauth_connect"
#     OAUTH_DISCONNECT = "oauth_disconnect"
#     OAUTH_REFRESH = "oauth_refresh"
#     WEBHOOK_REGISTER = "webhook_register"


# class SyncEventAction(StrEnum):
#     FULL_SYNC = "full_sync"
#     INCREMENTAL_SYNC = "incremental_sync"
#     SYNC_FAILURE = "sync_failure"
#     SCHEMA_DRIFT_DETECTED = "schema_drift_detected"
#     EMBEDDING_BATCH = "embedding_batch"