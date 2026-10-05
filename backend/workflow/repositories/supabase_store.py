"""Service-role Supabase store. RLS still applies to anon/authenticated clients."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, fields
from datetime import datetime
from typing import Any

from supabase.auth import parse_dt
from supabase.client import get_service_client
from workflow.models import (
    TABLES,
    AICandidate,
    Approval,
    ArchitectApplication,
    AuditEvent,
    ClientBrief,
    Comment,
    DesignDocument,
    GenerationJob,
    HistoricalActor,
    Inquiry,
    Invitation,
    Notification,
    Project,
    Revision,
    SiteConstraint,
    User,
)

from .base import MemoryStore, Query

JSON_COLS: dict[type, set[str]] = {
    ClientBrief: {"questionnaire", "specification"},
    DesignDocument: {"working_scene_document"},
    Revision: {"scene_document", "floor_plan"},
    GenerationJob: {"specification"},
    AuditEvent: {"metadata_json"},
}

DT_COLS = {
    "created_at",
    "updated_at",
    "completed_at",
    "working_updated_at",
    "expires_at",
    "accepted_at",
    "reviewed_at",
    "deleted_at",
    "terms_accepted_at",
    "privacy_accepted_at",
    "submitted_at",
    "resolved_at",
}

SKIP_ON_WRITE: dict[type, set[str]] = {
    User: {"password_hash"},
}

# Columns that must be cleared in Postgres when set back to None (e.g. reopening a comment).
WRITE_NULLS: dict[type, set[str]] = {
    Comment: {"resolved_at", "resolved_by", "resolution_note", "resolution_revision_id"},
}

# Parents before children. generation_jobs before ai_candidates (FK).
_WRITE_ORDER = (
    User,
    HistoricalActor,
    Project,
    ClientBrief,
    SiteConstraint,
    DesignDocument,
    Revision,
    GenerationJob,
    AICandidate,
    Comment,
    Approval,
    AuditEvent,
    Notification,
    Invitation,
    Inquiry,
    ArchitectApplication,
)
_WRITE_RANK = {model: i for i, model in enumerate(_WRITE_ORDER)}


def _json_load(value: Any, default: str = "{}") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _json_dump(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        if value == "":
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _iso(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def row_to_entity(model: type, row: dict[str, Any]) -> Any:
    kwargs: dict[str, Any] = {}
    names = {f.name for f in fields(model)}
    json_cols = JSON_COLS.get(model, set())
    for name in names:
        if name == "password_hash":
            kwargs[name] = ""
            continue
        if name not in row:
            continue
        value = row[name]
        if name in json_cols:
            default = "{}" if name != "working_scene_document" else None
            if value is None and default is None:
                kwargs[name] = None
            else:
                kwargs[name] = _json_load(value, default or "{}")
        elif name in DT_COLS:
            kwargs[name] = parse_dt(value)
        else:
            kwargs[name] = value
    return model(**kwargs)


def entity_to_row(obj: Any) -> dict[str, Any]:
    model = type(obj)
    payload = asdict(obj)
    for name in SKIP_ON_WRITE.get(model, set()):
        payload.pop(name, None)
    for name in JSON_COLS.get(model, set()):
        if name in payload:
            payload[name] = _json_dump(payload[name])
    nullable = WRITE_NULLS.get(model, set())
    for name, value in list(payload.items()):
        if value is None:
            if name not in nullable:
                payload.pop(name)
            continue
        if isinstance(value, datetime):
            payload[name] = value.isoformat()
    return payload


class SupabaseStore(MemoryStore):
    """Identity-map store backed by Supabase Postgres (service role)."""

    def __init__(self) -> None:
        super().__init__()
        self._client = get_service_client()
        self._loaded: set[type] = set()
        self._dirty: set[tuple[type, str]] = set()
        self._new: set[tuple[type, str]] = set()
        self._removed: list[tuple[type, str]] = []
        self._snapshots: dict[tuple[type, str], str] = {}

    def _table(self, model: type) -> str:
        return TABLES[model]

    def _exec(self, builder: Any) -> Any:
        last: Exception | None = None
        for attempt in range(3):
            try:
                return builder.execute()
            except Exception as exc:
                last = exc
                if "disconnected" not in str(exc).lower() and "RemoteProtocol" not in type(exc).__name__:
                    raise
                time.sleep(0.2 * (attempt + 1))
        assert last is not None
        raise last

    def _key(self, obj: Any) -> tuple[type, str]:
        return (type(obj), str(obj.id))

    def _snap(self, obj: Any) -> str:
        return json.dumps(entity_to_row(obj), sort_keys=True, default=str)

    def _remember(self, obj: Any) -> None:
        self._snapshots[self._key(obj)] = self._snap(obj)

    def _ensure(self, model: type) -> None:
        # Tech debt: first query of a model loads the full table so MemoryStore Query
        # filters can run in process. Do not replace with PostgREST filters without
        # preserving join/order/identity-map semantics.
        if model in self._loaded:
            return
        result = self._exec(self._client.table(self._table(model)).select("*"))
        for row in result.data or []:
            obj = row_to_entity(model, row)
            self._data.setdefault(model, {})[str(obj.id)] = obj
            self._remember(obj)
        self._loaded.add(model)

    def _rows(self, model: type) -> list[Any]:
        self._ensure(model)
        return super()._rows(model)

    def get(self, model: type, ident: str | None) -> Any | None:
        if ident is None:
            return None
        cached = self._data.get(model, {}).get(str(ident))
        if cached is not None:
            return cached
        if model in self._loaded:
            return None
        result = self._exec(self._client.table(self._table(model)).select("*").eq("id", ident).limit(1))
        rows = result.data or []
        if not rows:
            return None
        obj = row_to_entity(model, rows[0])
        self._data.setdefault(model, {})[str(obj.id)] = obj
        self._remember(obj)
        return obj

    def add(self, obj: Any) -> None:
        super().add(obj)
        key = (type(obj), str(obj.id))
        self._new.add(key)
        self._dirty.add(key)

    def delete(self, obj: Any) -> None:
        key = (type(obj), str(obj.id))
        super().delete(obj)
        self._removed.append(key)
        self._dirty.discard(key)
        self._new.discard(key)
        self._snapshots.pop(key, None)

    def query(self, target: Any) -> Query:
        model = target.model if hasattr(target, "model") else target
        self._ensure(model)
        return Query(self, target)

    def touch(self, obj: Any) -> None:
        ident = getattr(obj, "id", None)
        if ident is None:
            return
        self._dirty.add((type(obj), str(ident)))

    def commit(self) -> None:
        super().flush()
        for model, ident in self._removed:
            self._exec(self._client.table(self._table(model)).delete().eq("id", ident))
        self._removed.clear()
        pending = set(self._dirty | self._new)
        for model, rows in self._data.items():
            for ident, obj in rows.items():
                key = (model, ident)
                if key in pending:
                    continue
                if self._snapshots.get(key) != self._snap(obj):
                    pending.add(key)
        for model, ident in sorted(pending, key=lambda item: (_WRITE_RANK.get(item[0], 99), item[1])):
            obj = self._data.get(model, {}).get(ident)
            if obj is None:
                continue
            payload = entity_to_row(obj)
            self._exec(self._client.table(self._table(model)).upsert(payload))
            self._remember(obj)
        self._dirty.clear()
        self._new.clear()

    def refresh(self, obj: Any) -> None:
        model = type(obj)
        result = self._exec(self._client.table(self._table(model)).select("*").eq("id", obj.id).limit(1))
        rows = result.data or []
        if not rows:
            return
        live = row_to_entity(model, rows[0])
        self._data.setdefault(model, {})[str(live.id)] = live
        self._remember(live)
        for f in fields(model):
            if f.name == "password_hash":
                continue
            setattr(obj, f.name, getattr(live, f.name))
