"""F-12: local fallback must be opt-in in production."""

from __future__ import annotations

import pytest


def _fresh_service(monkeypatch, **env_overrides):
    """Rebuild SupabaseService with a fresh Settings, bypassing lru_cache."""
    from app.config import settings as settings_module
    from app.database import supabase as supabase_module

    # Keep Supabase env vars empty (shadowing the real .env, per conftest).
    # Reset the two knobs this suite exercises so per-test overrides win.
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("LOCAL_FALLBACK_ENABLED", raising=False)
    for k, v in env_overrides.items():
        monkeypatch.setenv(k, v)

    settings_module.get_settings.cache_clear()
    return supabase_module.SupabaseService(settings=settings_module.get_settings())


def test_production_without_supabase_refuses_to_boot(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path))
    from app.ingestion.exceptions import DatabaseConnectionError

    with pytest.raises(DatabaseConnectionError):
        _fresh_service(monkeypatch, APP_ENV="production")


def test_production_with_explicit_opt_in_allows_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path))
    service = _fresh_service(
        monkeypatch, APP_ENV="production", LOCAL_FALLBACK_ENABLED="true"
    )
    # Backend is the local one \u2014 storage_dir exists.
    assert service.settings.allow_local_fallback is True


def test_dev_default_still_falls_back(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path))
    service = _fresh_service(monkeypatch, APP_ENV="development")
    assert service.settings.allow_local_fallback is True
