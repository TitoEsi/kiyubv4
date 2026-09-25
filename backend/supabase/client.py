"""Anon + service-role Supabase clients. Service role stays backend-only."""
from __future__ import annotations

import importlib
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


def supabase_configured() -> bool:
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))


def supabase_url() -> str:
    return os.environ.get("SUPABASE_URL", "").rstrip("/")


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value


def _official_factory() -> Any:
    """Load site-packages `create_client` despite this local package name."""
    here = Path(__file__).resolve().parent
    backend_root = here.parent
    skip = {here.resolve(), backend_root.resolve()}
    saved_path = list(sys.path)
    saved_mods = {k: sys.modules.pop(k) for k in list(sys.modules) if k == "supabase" or k.startswith("supabase.")}
    sys.path = [p for p in saved_path if p and Path(p).resolve() not in skip]
    try:
        import httpx

        sdk = importlib.import_module("supabase")
        options_cls = sdk.ClientOptions
        create_client = sdk.create_client

        def make(url: str, key: str) -> Any:
            return create_client(
                url,
                key,
                options=options_cls(
                    auto_refresh_token=False,
                    persist_session=False,
                    httpx_client=httpx.Client(http2=False, timeout=60.0),
                ),
            )

        return make
    finally:
        sys.path = saved_path
        for key in list(sys.modules):
            if key == "supabase" or key.startswith("supabase."):
                sys.modules.pop(key, None)
        sys.modules.update(saved_mods)


@lru_cache(maxsize=1)
def get_service_client() -> Any:
    return _official_factory()(_require("SUPABASE_URL"), _require("SUPABASE_SERVICE_ROLE_KEY"))


@lru_cache(maxsize=1)
def get_anon_client() -> Any:
    return _official_factory()(_require("SUPABASE_URL"), _require("SUPABASE_ANON_KEY"))


def reset_clients() -> None:
    get_service_client.cache_clear()
    get_anon_client.cache_clear()
