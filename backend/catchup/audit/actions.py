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


class IntegrationAction(BaseAuditAction):
    HANDLE_OAUTH_CALLBACK = "handle_oauth_callback"
    HANDLE_INSTALLATION = "handle_installation"
    PERSIST_OAUTH_TOKEN = "persist_oauth_token"
    REFRESH_OAUTH_TOKEN = "refresh_oauth_token"
    REGISTER_WEBHOOK = "register_webhook"


class SyncTriggerAction(BaseAuditAction):
    TRIGGER_FULL_SYNC = "trigger_full_sync"
    HANDLE_WEBHOOK_EVENT = "handle_webhook_event"
    START_CONFLUENCE_POLLING = "start_confluence_polling"


class SyncIngestionAction(BaseAuditAction):
    SUMMARIZE = "summarize"
    EMBED = "embed"
    PERSIST_DOCUMENT = "persist_document"


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