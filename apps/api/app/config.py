"""Application configuration.

All settings come from environment variables (see ``.env.example``). Secrets
are read here server-side only and are never serialised back to clients.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = .../Takshashila-Archive-Intelligence (when running from the repo).
REPO_ROOT = Path(__file__).resolve().parents[3]


def config_dir() -> Path:
    """Locate the config/ directory across layouts (repo checkout vs Docker).

    Checks, in order: $CONFIG_DIR, <repo>/config, /config, and apps/api-relative
    fallbacks. Returns the first that exists, else the repo-root default.
    """
    import os

    candidates = []
    env = os.environ.get("CONFIG_DIR")
    if env:
        candidates.append(Path(env))
    candidates += [
        REPO_ROOT / "config",
        Path("/config"),
        Path(__file__).resolve().parents[2] / "config",  # apps/api/config (unlikely)
        Path.cwd() / "config",
    ]
    for c in candidates:
        if c.exists():
            return c
    return REPO_ROOT / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Database
    database_url: str = Field(
        default="sqlite+pysqlite:///./data/dev.db",
        alias="DATABASE_URL",
    )

    # Jobs
    redis_url: str = Field(default="", alias="REDIS_URL")
    jobs_inline: bool = Field(default=True, alias="JOBS_INLINE")

    # Storage
    data_dir: str = Field(default="./data", alias="DATA_DIR")

    # API
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")
    max_download_mb: int = Field(default=200, alias="MAX_DOWNLOAD_MB")
    app_secret_key: str = Field(default="dev-insecure-secret-change-me", alias="APP_SECRET_KEY")

    # AI providers (server-side only)
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    openai_compatible_api_key: str = Field(default="", alias="OPENAI_COMPATIBLE_API_KEY")
    openai_compatible_base_url: str = Field(default="", alias="OPENAI_COMPATIBLE_BASE_URL")

    # Embeddings
    embedding_provider: str = Field(default="none", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="", alias="EMBEDDING_MODEL")
    embedding_api_key: str = Field(default="", alias="EMBEDDING_API_KEY")
    embedding_base_url: str = Field(default="", alias="EMBEDDING_BASE_URL")
    embedding_dimensions: int = Field(default=1024, alias="EMBEDDING_DIMENSIONS")
    embedding_batch_size: int = Field(default=32, alias="EMBEDDING_BATCH_SIZE")

    # ── Derived helpers ────────────────────────────────────
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        if not p.is_absolute():
            p = REPO_ROOT / p
        return p

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def use_celery(self) -> bool:
        return bool(self.redis_url) and not self.jobs_inline

    def env_api_key_for(self, provider_id: str) -> str:
        """Return the environment-configured API key for a provider id (may be '')."""
        return {
            "groq": self.groq_api_key,
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "openai_compatible": self.openai_compatible_api_key,
        }.get(provider_id, "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
