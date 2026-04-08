from catchup.audit.base import BaseAuditAction


class UnknownTaskAction(BaseAuditAction):
    """
    audit_event_handler()의 action 필드 누락 시 Fallback
    """
    UNKNOWN = "unknown"


class AdminOAuthAction(BaseAuditAction):
    SYNC_USERS = "sync_users"


class AuthAction(BaseAuditAction):
    LOGIN_ATTEMPT = "login_attempt"
    LOGIN = "login"
    REFRESH_TOKEN = "refresh_token"
    LOGOUT = "logout"


class ChatAction(BaseAuditAction):
    SEND_QUERY = "send_query"
    GENERATE_RESPONSE = "generate_response"
    PROVIDE_SOURCES = "provide_sources"


class AwsS3Action(BaseAuditAction):
    UPLOAD_AUDIT_FILE = "upload_audit_file"


class SystemAction(BaseAuditAction):
    INIT_SCHEDULER = "init_scheduler"
    INIT_CHECKPOINTER = "init_checkpointer"
    INIT_REDIS = "init_redis"
    SHUTDOWN_SCHEDULER = "shutdown_scheduler"
    SHUTDOWN_CHECKPOINTER = "shutdown_checkpointer"

# ======================= SYNC FLOW AUDIT =======================

class SyncTriggerAction(BaseAuditAction):

    # "sync_trigger.full_sync_request"
    FULL_SYNC_REQUEST = "full_sync_request"

    # "sync_trigger.incremental"
    INCREMENTAL = "incremental"

class FullSyncAction(BaseAuditAction):
    """
    dispatch() 이후 full sync 처리 단위와 주요 전이를 기록
    """
    # "full_sync.job"
    # ATTEMPT : JOB_STARTED | SUCCESS : JOB_SUCCESS | FAIL : JOB_FAILED
    JOB = "job"

    # "full_sync.event"
    # ATTEMPT : EVENT_STARTED | SUCCESS : EVENT_SUCCESS | FAIL : EVENT_FAILED
    # 재시도 이벤트는 metadata.is_retry로, requeue는 metadata.phase="requeue"로 구분
    EVENT = "event"

class IncrementalSyncAction(BaseAuditAction):
    """
    incremental dispatch 이후 record / outbox / worker 처리 단위를 기록
    """
    # "incremental_sync.record"
    # ATTEMPT : RECORD_PROCESSING | SUCCESS : RECORD_SYNCED | FAIL : RECORD_DEAD
    # 재시도 레코드는 metadata.is_retry로, requeue는 metadata.phase="requeue"로 구분
    RECORD = "record"

# class SyncIngestionAction(BaseAuditAction):
#     # "sync_ingestion.fetch"
#     FETCH = "fetch"
#     # "sync_ingestion.transform"
#     TRANSFORM = "transform"
#     # "sync_ingestion.summarize"
#     SUMMARIZE = "summarize"
#     # "sync_ingestion.embed"
#     EMBED = "embed"
#     # "sync_ingestion.persist"
#     PERSIST = "persist"


# ======================= CONNECTOR AUDIT =======================
class IntegrationAction(BaseAuditAction):
    HANDLE_OAUTH_CALLBACK = "handle_oauth_callback"
    HANDLE_INSTALLATION = "handle_installation"
    REGISTER_WEBHOOK = "register_webhook"

# ======================= USER AUDIT =======================
class UserRoleAction(BaseAuditAction):
    PROMOTE = "promote"
    REVOKE_ADMIN = "revoke_admin"


class UserCustomPromptAction(BaseAuditAction):
    CREATE = "create"
    EDIT = "edit"
    DELETE = "delete"


class UserOnboardingAction(BaseAuditAction):
    SUBMIT = "submit"


class UserMappingAction(BaseAuditAction):
    UPLOAD_FILE = "upload_file"
