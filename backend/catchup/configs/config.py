from enum import StrEnum
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


# 서버 구동 환경
class Environment(StrEnum):
    development = "development"
    testing = "testing"
    production = "production"


class MeiliEnvironment(StrEnum):
    development = "development"
    production = "production"


class Settings(BaseSettings):
    ENV: Environment = Environment.development

    DB_DIALECT: str = "postgresql"
    DB_DRIVER: str = "psycopg"  # psycopg3 (langchain-postgres 호환)
    DB_USERNAME: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int
    DB_DATABASE: str

    MEILI_ENVIRONMENT: MeiliEnvironment = "development"
    MEILI_HTTP_ADDR: str = "http://localhost:7700"
    MEILI_KEY: str | None = None
    MEILI_DEFAULT_INDEX: str | None = None
    MEILI_GITHUB_CODEBASE_INDEX: str | None = None
    MEILI_GITHUB_ISSUES_INDEX: str | None = None
    MEILI_GITHUB_PRS_INDEX: str | None = None

    OPENAI_API_KEY: str
    REDIS_URL: str

    LANGFUSE_SECRET_KEY: str
    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_BASE_URL: str
    ENABLE_LANGFUSE: bool

    COHERE_API_KEY: str
    RERANK_THRESHOLD: float

    COHERE_RERANK_TOP_N: int
    MEILISEARCH_SEMANTIC_RATIO: float
    MEILISEARCH_MIN_K_PER_INDEX: int
    MEILISEARCH_GLOBAL_RETRIEVAL_BUDGET: int
    OPENAI_EMBEDDING_MODEL: str
    COHERE_EMBEDDING_MODEL: str = "embed-v4.0"
    OPENAI_SMALL_MODEL: str
    OPENAI_LARGE_MODEL: str
    FINAL_SOURCES_SANITY_THRESHOLD: float
    RERANK_TOP_N: int
    RERANK_TOTAL_K: int

    GITHUB_TOKEN: str
    GITHUB_BASE_URL: str

    GITHUB_APP_ID: int
    GITHUB_APP_PRIVATE_KEY_PATH: str
    GITHUB_APP_WEBHOOK_SECRET: str
    GITHUB_APP_CLIENT_ID: str
    GITHUB_APP_CLIENT_SECRET: str

    JIRA_CLIENT_ID: str
    JIRA_CLIENT_SECRET: str
    JIRA_REDIRECT_URI: str
    JIRA_WEBHOOK_CALLBACK_BASE_URL: str
    JIRA_WEBHOOK_REFRESH_INTERVAL_HOURS: int = 6
    JIRA_WEBHOOK_REFRESH_THRESHOLD_HOURS: int = 24
    JIRA_WEBHOOK_JWT_LEEWAY_SECONDS: int = 30
    JIRA_SCOPES: str = "read:me read:jira-work read:jira-user manage:jira-webhook read:account offline_access"

    ATLASSIAN_AUTH_URL: str = "https://auth.atlassian.com/authorize"
    ATLASSIAN_TOKEN_URL: str = "https://auth.atlassian.com/oauth/token"
    ATLASSIAN_API_URL: str = "https://api.atlassian.com"

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

    # Jira Sync Settings
    JIRA_SYNC_BATCH_SIZE: int = 100  # Jira API max per request
    JIRA_SYNC_MAX_CONCURRENT_REQUESTS: int = 5  # Rate limit safe
    JIRA_SYNC_COMMENTS_LIMIT: int = 5  # Recent comments to include
    JIRA_API_RATE_LIMIT_DELAY: float = 0.1  # Seconds between requests
    
    # Neo4j
    NEO4J_USER:Optional[str] 
    NEO4J_PASSWORD: Optional[str]
    NEO4J_URI: Optional[str]
    ENABLE_NEO4J: bool = False

    # Slack Sync Settings
    SLACK_SYNC_MAX_CONCURRENT_REQUESTS: int = 10  # 동시 요청 수
    SLACK_API_RATE_LIMIT_DELAY: float = 0.1  # 요청 간 딜레이 (초)
    SLACK_MIN_TEXT_LENGTH: int = 5  # 이 길이 이하의 텍스트는 제외 (Reply 등)
    SLACK_MESSAGE_BATCH_SIZE: int = 200  # 한 번에 가져올 메시지 수
    SLACK_DEFAULT_SYNC_DAYS: int = 1095  # 기본 동기화 기간 (3년 = 1095일)

    # GitHub Sync Settings
    GITHUB_SYNC_MAX_CONCURRENT_REQUESTS: int = 10  # 동시 요청 수 (5,000 req/hour 제한)
    GITHUB_SYNC_BATCH_SIZE: int = 100  # 한 번에 가져올 엔티티 수 (per_page)
    GITHUB_API_RATE_LIMIT_DELAY: float = 0.1  # 요청 간 딜레이 (초)
    GITHUB_SYNC_COMMENTS_LIMIT: int = 10  # Issue/PR에 포함할 최근 코멘트 수
    GITHUB_SYNC_DEFAULT_DAYS: int = 90  # 기본 동기화 기간 (일)

    # Wehbhook Event Buffering & Scheduler Settings
    WEBHOOK_BUFFER_TTL: int = 3900 # 65분 : Buffer 60분
    WEBHOOK_FLUSH_INTERVAL_HOURS: int = 1  
    WEBHOOK_ENABLE_AUTO_SYNC: bool = True
    
    # AWS
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str

    # AWS Bedrock
    # Bedrock API Key
    AWS_BEARER_TOKEN_BEDROCK: str
    AWS_REGION: str
    AWS_BEDROCK_EMBEDDING_MODEL: str
    AWS_BEDROCK_SMALL_MODEL: str
    AWS_BEDROCK_LARGE_MODEL: str
    AWS_RERANK_MODEL_ARN: str
    AWS_RERANK_MODEL_REGION: str


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlalchemy_database_url(self) -> str:
        return (
            f"{self.DB_DIALECT}+{self.DB_DRIVER}://"
            f"{self.DB_USERNAME}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/"
            f"{self.DB_DATABASE}"
        )


class AuthSettings(BaseSettings):
    JWT_ACCESS_TOKEN_SECRET_KEY: str
    JWT_REFRESH_TOKEN_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Google
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str
    
    # Okta
    OKTA_DOMAIN: str
    OKTA_CLIENT_ID: str
    OKTA_CLIENT_SECRET: str
    OKTA_REDIRECT_URI: str

    FRONTEND_REDIRECT_URI: str

    HTTP_ONLY: bool
    SECURE: bool
    SAMESITE: str

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
auth_settings = AuthSettings()
