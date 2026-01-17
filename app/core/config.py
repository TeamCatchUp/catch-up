from enum import StrEnum

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


# 서버 구동 환경
class Environment(StrEnum):
    development = "development"
    testing = "testing"
    production = "production"


# Meilisearch 구동 환경
class MeiliEnvironment(StrEnum):
    development = "development"
    production = "production"


# env 파일명
env_file = ".env"


# 환경변수 주입
class Settings(BaseSettings):
    ENV: Environment = Environment.development

    MEILI_ENVIRONMENT: MeiliEnvironment = "development"
    MEILI_HTTP_ADDR: str = "http://localhost:7700"
    MEILI_KEY: str | None = None
    MEILI_DEFAULT_INDEX: str | None
    MEILI_GITHUB_CODEBASE_INDEX: str | None
    MEILI_GITHUB_ISSUES_INDEX: str | None
    MEILI_GITHUB_PRS_INDEX: str | None

    OPENAI_API_KEY: str

    REDIS_URL: str

    LANGFUSE_SECRET_KEY: str
    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_BASE_URL: str

    COHERE_API_KEY: str
    RERANK_THRESHOLD: float

    # Performance variables
    COHERE_RERANK_TOP_N: int
    MEILISEARCH_SEMANTIC_RATIO: float
    MEILISEARCH_MIN_K_PER_INDEX: int
    MEILISEARCH_GLOBAL_RETRIEVAL_BUDGET: int
    CUSTOM_RERANK_TOTAL_K: int
    OPENAI_EMBEDDING_MODEL: str
    OPENAI_CHAT_MODEL: str

    GITHUB_TOKEN: str
    GITHUB_BASE_URL: str

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# settings 변수로 환경변수 접근 가능
settings = Settings()
