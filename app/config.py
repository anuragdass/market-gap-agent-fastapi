from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: Literal["anthropic", "openai", "google_genai"] = "anthropic"
    llm_model: str = "claude-sonnet-5"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None

    serper_api_key: str | None = None

    orchestration_mode: Literal["agent", "pipeline"] = "agent"

    # Postgres in docker compose (schema owned by Alembic, see migrations/);
    # sqlite+aiosqlite is the zero-setup fallback for bare `make run`/tests.
    database_url: str = "sqlite+aiosqlite:///./local.db"

    artifacts_dir: Path = Path("./artifacts")
    cache_dir: Path = Path("./.cache")
    max_concurrent_runs: int = 2
    run_timeout_seconds: int = 600
    max_documents_per_company: int = 8
    min_competitors: int = 4
    domain_wide_min_companies: int = 2
    min_quote_chars: int = 25
    max_quote_chars: int = 600

    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
