from enum import StrEnum

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
    DB_DRIVER: str = "psycopg2"
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

    COHERE_API_KEY: str
    RERANK_THRESHOLD: float

    COHERE_RERANK_TOP_N: int
    MEILISEARCH_SEMANTIC_RATIO: float
    MEILISEARCH_MIN_K_PER_INDEX: int
    MEILISEARCH_GLOBAL_RETRIEVAL_BUDGET: int
    CUSTOM_RERANK_TOTAL_K: int
    OPENAI_EMBEDDING_MODEL: str
    OPENAI_CHAT_MODEL: str
    FINAL_SOURCES_SANITY_THRESHOLD: float

    GITHUB_TOKEN: str
    GITHUB_BASE_URL: str

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
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str

    FRONTEND_REDIRECT_URI: str

    HTTP_ONLY: bool
    SECURE: bool
    SAMESITE: str

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
auth_settings = AuthSettings()
