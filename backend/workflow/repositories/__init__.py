"""Workflow repositories. Services keep the Session-shaped query API.

MemoryStore is the default pytest fake. SupabaseStore is used when
SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY are set. Multi-row writes
(generate: job + revisions + candidates) go through the service role so a
partial HTTP handler cannot leave orphans. RLS still protects direct
anon/authenticated access to Postgres.
"""
from .base import MemoryStore, Query, Store
from .supabase_store import SupabaseStore

__all__ = ["MemoryStore", "Query", "Store", "SupabaseStore"]
