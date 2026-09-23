"""The only module that reads the environment. Bible §8, §16."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ENGINE_VERSION = "0.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: Literal["gemini", "anthropic", "none"] = "none"
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    anthropic_model: str = "claude-sonnet-5"
    demo_only: bool = False
    max_upload_mb: int = 15
    cors_origins: str = ""
    geosearch_url: str = "https://geosearch.planninglabs.nyc/v2/search"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
