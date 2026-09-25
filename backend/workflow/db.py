"""Workflow session factory. MemoryStore in tests; Supabase when configured."""
from __future__ import annotations

import os

from .repositories.base import MemoryStore

SessionLocal = None
_memory: MemoryStore | None = None
_force_memory = False


def supabase_enabled() -> bool:
    if os.environ.get("KIYUB_WORKFLOW_MEMORY") == "1":
        return False
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))


def require_supabase_runtime() -> None:
    """Refuse API startup on MemoryStore. Tests use KIYUB_WORKFLOW_MEMORY or reset_store()."""
    if os.environ.get("KIYUB_WORKFLOW_MEMORY") == "1":
        raise RuntimeError(
            "KIYUB_WORKFLOW_MEMORY=1 is test-only. Unset it to run the API against Supabase."
        )
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required. "
            "The API will not start with in-memory persistence."
        )


def configure(url: str | None = None) -> None:
    """Reset the in-memory store. Pass a url (e.g. 'memory') to force MemoryStore."""
    global SessionLocal, _memory, _force_memory
    _force_memory = url is not None
    _memory = MemoryStore()

    def _session() -> MemoryStore:
        if not _force_memory and supabase_enabled():
            from .repositories.supabase_store import SupabaseStore

            return SupabaseStore()
        assert _memory is not None
        return _memory

    SessionLocal = _session


configure()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Schema lives in supabase/migrations/. Memory store is already empty."""
    if _memory is None:
        configure()


def reset_store() -> None:
    configure("memory")
