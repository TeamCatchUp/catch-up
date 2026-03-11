from enum import StrEnum

from dotenv import load_dotenv
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

load_dotenv()


# 서버 구동 환경
class Environment(StrEnum):
    development = "development"
    testing = "testing"
    production = "production"


class Settings(BaseSettings):
    #=============================#
    #     System Base Settings    #
    #=============================#
    # Server Environment
    ENV: Environment = Environment.development
    
    # Logging
    SERVICE_NAME: str = "catchup"
    APP_VERSIONS: str = "0.1.0"  #TODO: app version 갱신 방법
    LOG_LEVEL: str
    
    # logging - console
    LOG_CONSOLE_ENABLED: bool = True
    
    # logging - file (dev)
    LOG_JSON_FILE_ENABLED: bool = False
    LOG_JSON_FILE_PATH: str = "/var/log/catchup/app.jsonl"
    LOG_JSON_MAX_BYTES: int = 50 * 1024 * 1024
    LOG_JSON_BACKUP_COUNT: int = 5

    # Logging - audit (prod)
    LOG_AUDIT_FILE_ENABLED: bool = True
    LOG_AUDIT_FILE_PATH: str = "/var/log/catchup/audit/audit.jsonl"
    LOG_AUDIT_ROTATION_WHEN: str = "H"
    LOG_AUDIT_ROTATION_INTERVAL: int = 1
    LOG_AUDIT_BACKUP_COUNT: int = 168 # 24 * 7
    
    
    #========================#
    #     InfraStructures    #
    #========================#
    # Redis
    REDIS_URL: str
    REDIS_CLUSTER_MODE: bool

    # PostgreSQL
    DB_DIALECT: str = "postgresql"
    DB_DRIVER: str = "psycopg"  # psycopg3 (langchain-postgres 호환)
    DB_USERNAME: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int
    DB_DATABASE: str
    
    # AWS S3
    AWS_S3_AUDIT_ENABLED: bool = False
    AWS_S3_AUDIT_BUCKET_NAME: str | None = None
    AWS_S3_AUDIT_PREFIX: str | None = None
    AWS_S3_AUDIT_UPLOAD_INTERVAL_SECONDS: int | None = None
    
    # Neo4j (Deprecated)
    NEO4J_USER: str | None = None
    NEO4J_PASSWORD: str | None = None
    NEO4J_URI: str | None = None
    ENABLE_NEO4J: bool = False

    # Langfuse
    ENABLE_LANGFUSE: bool
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_BASE_URL: str | None = None
        
    # AWS Bedrock
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_CREDENTIALS_PROFILE_NAME: str | None = None
    AWS_BEARER_TOKEN_BEDROCK: str | None = None
    AWS_REGION: str
    AWS_BEDROCK_EMBEDDING_MODEL: str
    AWS_BEDROCK_SMALL_MODEL: str
    AWS_BEDROCK_LARGE_MODEL: str
    AWS_RERANK_MODEL_ARN: str
    AWS_RERANK_MODEL_REGION: str
    AWS_EMBEDDING_MODEL_REGION: str

    # Cohere (native)
    COHERE_API_KEY: str
    COHERE_EMBEDDING_MODEL: str = "embed-v4.0"
    
    # OpenAI (native)
    OPENAI_API_KEY: str
    OPENAI_EMBEDDING_MODEL: str
    OPENAI_SMALL_MODEL: str
    OPENAI_LARGE_MODEL: str
    
    #=======================#
    #     RAG Parameters    #
    #=======================#
    # Custom Rerank Parameters
    RERANK_TOP_N: int
    RERANK_TOTAL_K: int

    #=======================================#
    #     Knowledge Source Integrations     #
    #=======================================#
    # Github
    GITHUB_BASE_URL: str
    GITHUB_APP_ID: int
    GITHUB_APP_PRIVATE_KEY: str
    GITHUB_APP_WEBHOOK_SECRET: str
    GITHUB_APP_CLIENT_ID: str
    GITHUB_APP_CLIENT_SECRET: str
    
    # Atlassian
    ATLASSIAN_CLIENT_ID: str
    ATLASSIAN_CLIENT_SECRET: str
    ATLASSIAN_REDIRECT_URI: str
    ATLASSIAN_WEBHOOK_CALLBACK_BASE_URL: str
    JIRA_WEBHOOK_REFRESH_INTERVAL_HOURS: int = 6
    JIRA_WEBHOOK_REFRESH_THRESHOLD_HOURS: int = 24
    JIRA_WEBHOOK_JWT_LEEWAY_SECONDS: int = 30
    ATLASSIAN_SCOPES: str = (
        "read:me read:jira-work read:jira-user read:email-address:jira "
        "manage:jira-webhook read:account read:email-address:confluence "
        "read:confluence-content.all read:confluence-space.summary "
        "read:confluence-user search:confluence readonly:content.attachment:confluence "
        "offline_access read:space:confluence read:space-details:confluence read:space.permission:confluence "
        "read:content-details:confluence "
        "read:page:confluence read:blogpost:confluence read:comment:confluence "
        "read:attachment:confluence read:label:confluence"
    )

    ATLASSIAN_AUTH_URL: str = "https://auth.atlassian.com/authorize"
    ATLASSIAN_TOKEN_URL: str = "https://auth.atlassian.com/oauth/token"
    ATLASSIAN_API_URL: str = "https://api.atlassian.com"
    ATLASSIAN_TOKEN_REFRESH_INTERVAL_MINUTES: int = 30

    # Slack OAuth
    SLACK_CLIENT_ID: str
    SLACK_CLIENT_SECRET: str
    SLACK_REDIRECT_URI: str
    SLACK_BOT_SCOPES: str = "channels:read channels:history groups:read groups:history mpim:history mpim:read users:read users:read.email users.profile:read usergroups:read team:read app_mentions:read assistant:write chat:write chat:write.customize commands reactions:read reactions:write emoji:read files:read links:read im:read im:history"
    SLACK_SIGNING_SECRET: str

    # Slack API URLs
    SLACK_AUTH_URL: str = "https://slack.com/oauth/v2/authorize"
    SLACK_TOKEN_URL: str = "https://slack.com/api/oauth.v2.access"
    SLACK_API_URL: str = "https://slack.com/api"

    # PGVector Settings
    PGVECTOR_COLLECTION_NAME: str = "vectorstore"  # 통합 Collection (Jira, Slack, GitHub 등)
    PGVECTOR_EMBEDDING_DIMENSIONS: int = 1536  # Cohere embed-v4.0

    # Embedding Settings
    EMBEDDING_MAX_CONCURRENCY: int = 5  # 동시 Embedding API 호출 수
    EMBEDDING_BATCH_SIZE: int = 96  # Cohere embed-v4 max texts per request

    # Jira Sync Settings
    JIRA_SYNC_BATCH_SIZE: int = 100  # Jira API max per request
    JIRA_SYNC_MAX_CONCURRENT_REQUESTS: int = 5  # Rate limit safe
    JIRA_SYNC_COMMENTS_LIMIT: int = 5  # Recent comments to include
    JIRA_API_RATE_LIMIT_DELAY: float = 0.1  # Seconds between requests

    # Confluence Sync Settings
    CONFLUENCE_SYNC_MAX_CONCURRENT_REQUEST: int = 5
    CONFLUENCE_SYNC_RATE_LIMIT_DELAY: float = 0.1

    # Common Sync Settings
    DEFAULT_SYNC_DAYS: int = 1095

    # Slack Sync Settings
    SLACK_SYNC_MAX_CONCURRENT_REQUESTS: int = 10  # 동시 요청 수
    SLACK_CHANNEL_SYNC_CONCURRENCY: int = 5  # 채널 병렬 동기화 최대 동시 실행 수
    SLACK_API_RATE_LIMIT_DELAY: float = 0.1  # 요청 간 딜레이 (초)
    SLACK_MIN_TEXT_LENGTH: int = 5  # 이 길이 이하의 텍스트는 제외 (Reply 등)
    SLACK_MESSAGE_BATCH_SIZE: int = 500  # 한 번에 가져올 메시지 수

    # GitHub Sync Settings
    GITHUB_SYNC_MAX_CONCURRENT_REQUESTS: int = 10  # 동시 요청 수 (5,000 req/hour 제한)
    GITHUB_SYNC_BATCH_SIZE: int = 100  # 한 번에 가져올 엔티티 수 (per_page)
    GITHUB_API_RATE_LIMIT_DELAY: float = 0.1  # 요청 간 딜레이 (초)
    GITHUB_SYNC_COMMENTS_LIMIT: int = 10  # Issue/PR에 포함할 최근 코멘트 수
    # Wehbhook Event Buffering & Scheduler Settings
    WEBHOOK_BUFFER_TTL: int = 3900 # 65분 : Buffer 60분
    WEBHOOK_FLUSH_INTERVAL_HOURS: int = 1  
    WEBHOOK_ENABLE_AUTO_SYNC: bool = True

    # api_server 시작 시 Sync Worker 자동 기동 여부
    SYNC_WORKER_AUTOSTART: bool = True
    # 큐가 비었을 때 worker 루프 대기 시간(초)
    SYNC_WORKER_IDLE_SLEEP_SECONDS: float = 0.5
    # Redis blocking pop timeout(초)
    SYNC_QUEUE_BLOCK_TIMEOUT_SECONDS: int = 3

    # 동일 Job 내 채널 병렬 처리 수
    SYNC_WORKER_CHANNEL_CONCURRENCY: int = 5

    # 재시도 정책
    SYNC_JOB_MAX_ATTEMPTS: int = 3
    SYNC_JOB_RETRY_BASE_DELAY_SECONDS: float = 2.0
    SYNC_JOB_RETRY_MAX_DELAY_SECONDS: float = 30.0

    # Lock TTL
    SYNC_LOCK_TEAM_TTL_SECONDS: int = 21600      # 6h
    SYNC_LOCK_CHANNEL_TTL_SECONDS: int = 600     # 10m
    SYNC_LOCK_REFRESH_INTERVAL_SECONDS: float = 60.0

    # Job 상태/이벤트 보관 TTL
    SYNC_JOB_META_TTL_SECONDS: int = 86400       # 24h
    SYNC_JOB_EVENT_TTL_SECONDS: int = 86400      # 24h

    # SSE heartbeat 주기
    SYNC_SSE_HEARTBEAT_SECONDS: int = 15
    # Incremental sync_from fallback (team/channel cursor 없을 때)
    SYNC_INCREMENTAL_FALLBACK_HOURS: int = 2

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlalchemy_database_url(self) -> str:
        
        return URL.create(
            drivername=f"{self.DB_DIALECT}+{self.DB_DRIVER}",
            username=self.DB_USERNAME,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_DATABASE
        ).render_as_string(hide_password=False)
    
    @model_validator(mode="after")
    def validate_langfuse_config(self) -> "Settings":
        if self.ENABLE_LANGFUSE:
            if not all([self.LANGFUSE_SECRET_KEY, self.LANGFUSE_PUBLIC_KEY, self.LANGFUSE_BASE_URL]):
                raise ValueError(
                    "ENABLE_LANGFUSE is set to be True: all keys related to Langfuse must be set."
                )
        return self


class AuthSettings(BaseSettings):
    JWT_ACCESS_TOKEN_SECRET_KEY: str
    JWT_REFRESH_TOKEN_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Keycloak
    KC_PUBLIC_URL: str
    KC_INTERNAL_URL: str
    KC_REALM: str
    KC_CLIENT_ID: str
    KC_CLIENT_SECRET: str
    KC_REDIRECT_URI: str

    FRONTEND_REDIRECT_URI: str

    HTTP_ONLY: bool
    SECURE: bool
    SAMESITE: str
    
    # Google (Deprecated)
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URI: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
auth_settings = AuthSettings()
