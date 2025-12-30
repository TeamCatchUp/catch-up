from enum import StrEnum

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Environment(StrEnum):
    development = "development"
    testing = "testing"
    production = "production"


env_file = ".env"


class Settings(BaseSettings):
    ENV: Environment = Environment.development

    MEILI_HTTP_ADDR: str = "http://localhost:7700"
    MEILI_KEY: str | None = None
    MEILI_INDEX: str

    OPENAI_API_KEY: str

    REDIS_URL: str

    model_config = SettingsConfigDict(
        env_prefix="", case_sensitive=False, env_file=".env", env_file_encoding="utf-8"
    )


settings = Settings()
