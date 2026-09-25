"""Session factory must follow live env; MemoryStore is explicit/test-only."""
from __future__ import annotations

import os

import pytest

from workflow.db import configure, require_supabase_runtime, reset_store, supabase_enabled
from workflow.repositories.base import MemoryStore


def _keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role")
    monkeypatch.delenv("KIYUB_WORKFLOW_MEMORY", raising=False)


def _patch_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("supabase.client.get_service_client", lambda: object())
    monkeypatch.setattr(
        "workflow.repositories.supabase_store.get_service_client",
        lambda: object(),
        raising=False,
    )


def test_require_runtime_rejects_memory_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    _keys(monkeypatch)
    monkeypatch.setenv("KIYUB_WORKFLOW_MEMORY", "1")
    with pytest.raises(RuntimeError, match="test-only"):
        require_supabase_runtime()


def test_require_runtime_rejects_missing_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KIYUB_WORKFLOW_MEMORY", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    with pytest.raises(RuntimeError, match="required"):
        require_supabase_runtime()


def test_normal_config_uses_supabase_store(monkeypatch: pytest.MonkeyPatch) -> None:
    _keys(monkeypatch)
    _patch_client(monkeypatch)
    configure()
    from workflow.db import SessionLocal
    from workflow.repositories.supabase_store import SupabaseStore

    db = SessionLocal()
    assert isinstance(db, SupabaseStore)
    assert supabase_enabled() is True


def test_reset_store_uses_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    _keys(monkeypatch)
    reset_store()
    from workflow.db import SessionLocal

    assert isinstance(SessionLocal(), MemoryStore)


def test_memory_env_uses_memory_store(monkeypatch: pytest.MonkeyPatch) -> None:
    _keys(monkeypatch)
    monkeypatch.setenv("KIYUB_WORKFLOW_MEMORY", "1")
    configure()
    from workflow.db import SessionLocal

    assert supabase_enabled() is False
    assert isinstance(SessionLocal(), MemoryStore)


def test_env_flip_does_not_pin_store(monkeypatch: pytest.MonkeyPatch) -> None:
    _keys(monkeypatch)
    _patch_client(monkeypatch)
    configure()
    from workflow.db import SessionLocal
    from workflow.repositories.supabase_store import SupabaseStore

    monkeypatch.setenv("KIYUB_WORKFLOW_MEMORY", "1")
    assert isinstance(SessionLocal(), MemoryStore)
    monkeypatch.delenv("KIYUB_WORKFLOW_MEMORY")
    os.environ.pop("KIYUB_WORKFLOW_MEMORY", None)
    assert supabase_enabled() is True
    assert isinstance(SessionLocal(), SupabaseStore)
