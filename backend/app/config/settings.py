"""Application settings loaded from environment variables.

All configuration lives here. Never hardcode credentials or infrastructure
paths in application code — read them from `Settings`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings object.

    Values are loaded from environment variables (or an adjacent `.env` file).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Application ----
    app_name: str = Field(default="Predictive Insight Dashboard - Ingestion API")
    app_env: str = Field(default="development")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    app_log_level: str = Field(default="INFO")
    app_cors_origins: str = Field(default="http://localhost:3000")

    # ---- Supabase ----
    supabase_url: Optional[str] = Field(default=None)
    supabase_service_role_key: Optional[str] = Field(default=None)
    supabase_anon_key: Optional[str] = Field(default=None)
    supabase_storage_bucket: str = Field(default="datasets")

    # ---- Ingestion limits ----
    max_upload_size_mb: int = Field(default=200)
    max_zip_uncompressed_size_mb: int = Field(default=1024)
    max_zip_file_count: int = Field(default=200)

    # ---- Local storage fallback ----
    local_storage_dir: str = Field(default="./.local_storage")

    # ---- Derived helpers ----
    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def max_zip_uncompressed_size_bytes(self) -> int:
        return self.max_zip_uncompressed_size_mb * 1024 * 1024

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.app_cors_origins.split(",") if o.strip()]

    @property
    def supabase_configured(self) -> bool:
        """True only when both URL and service key look like real values.

        `.env.example` placeholders like 'your-service-role-key' are treated
        as unset so a fresh `copy .env.example .env` doesn't crash startup —
        the local fallback engages instead.
        """
        return _looks_real(self.supabase_url) and _looks_real(self.supabase_service_role_key)

    @property
    def local_storage_path(self) -> Path:
        return Path(self.local_storage_dir).resolve()

    @field_validator("app_log_level")
    @classmethod
    def _upper_log_level(cls, v: str) -> str:
        return v.upper()


_PLACEHOLDER_TOKENS = ("your-", "your_", "changeme", "xxxx", "todo")


def _looks_real(value: Optional[str]) -> bool:
    if not value:
        return False
    v = value.strip().lower()
    if not v:
        return False
    return not any(v.startswith(token) or token in v for token in _PLACEHOLDER_TOKENS)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor — one instance for the process lifetime."""
    return Settings()
