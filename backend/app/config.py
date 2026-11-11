"""The only module that reads the environment. Bible §8, §16."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ENGINE_VERSION = "0.2.0"
"""0.2.0 (v1.1): the time-uncertainty rule, bible §11.1.7. No v1.0 input changes its verdict."""

APP_VERSION = "1.1.0"
"""Bible §19. Semver for the product as a whole, shown in the footer, `/api/health` and
every generated PDF. The engine and its parameters keep their own stamps, because a
change to the wizard is not a change to any verdict."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: Literal["gemini", "anthropic", "none"] = "none"
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    anthropic_model: str = "claude-sonnet-5"
    demo_only: bool = False
    max_upload_mb: int = 15
    max_fixes: int = 5_000
    """Bible §16: location points accepted in one analyse request."""
    max_advocate_rows: int = 50_000
    max_advocate_lookups: int = 1_000
    """New addresses one batch upload may look up. A 50,000-row file naming 50,000 unknown
    addresses would otherwise point 50,000 requests at a free city service. Rows over the
    budget are reported as fixable — a lat/lng column needs no lookups at all."""
    max_advocate_map_records: int = 10_000
    """Filings returned to the browser so the map can draw a server's week.

    Whole servers at a time, highest-ranked first. The cap exists because a 50,000-row
    file would otherwise answer with ten megabytes of JSON for a map that only ever shows
    one server at a time."""
    max_household: int = 25
    cors_origins: str = ""
    rate_limit_per_minute: int = 30
    """Sustained requests per minute per client on the routes that cost money. 0 disables."""
    rate_limit_burst: int = 10
    """How many of that minute's budget may be spent at once."""
    rate_limit_trusted_hops: int = 0
    """Proxies in front of this app whose `X-Forwarded-For` entries can be believed."""
    geosearch_url: str = "https://geosearch.planninglabs.nyc/v2/search"

    # --- v1.1 -------------------------------------------------------------------------
    llm_real_data_allowed: bool = False
    """Whether this deployment may be sent real court papers. False shows a blocking
    notice on every upload. Setting it true is a statement that the configured provider's
    plan excludes training on inputs - a statement Rahul verifies, never the code."""
    extract_rate_limit_per_minute: int = 60
    """Sustained `/api/extract` calls a minute per client. A batch upload is the browser
    calling this route once per file, so it gets its own, larger budget. 0 disables."""
    extract_rate_limit_burst: int = 6
    max_extract_pages: int = 25
    """Pages accepted in one uploaded file. A whole NYC consumer court file is ~6-10."""
    max_batch_affidavits: int = 200
    """Confirmed affidavits accepted in one `/api/advocate/batch` request."""
    supabase_url: str = ""
    supabase_service_key: str = ""
    metrics_enabled: bool = False
    """Day-level usage counters and the attorneys' contact form. Off locally."""
    leads_per_hour: int = 5
    """Contact-form submissions a client may make in an hour. Counted in memory only."""

    @property
    def store_configured(self) -> bool:
        return self.metrics_enabled and bool(self.supabase_url and self.supabase_service_key)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
