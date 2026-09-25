"""Session-shaped store used by workflow services. Memory implementation for pytest."""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from typing import Any

from workflow.models import FieldRef, TABLES

JSONB_FIELDS: dict[type, set[str]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_cond(item: Any) -> tuple:
    if isinstance(item, tuple) and item and item[0] in ("eq", "ne", "in", "isnot"):
        return item
    raise TypeError(f"Unsupported filter: {item!r}")


def _attr(obj: Any, name: str) -> Any:
    return getattr(obj, name, None)


class Query:
    def __init__(self, store: "MemoryStore", target: type | FieldRef):
        self.store = store
        if isinstance(target, FieldRef):
            self.model = target.model
            self.column = target.name
        else:
            self.model = target
            self.column = None
        self._filters: list[tuple] = []
        self._joins: list[tuple[type, tuple]] = []
        self._order: list[tuple] = []
        self._limit: int | None = None

    def filter(self, *conds: Any) -> "Query":
        for c in conds:
            self._filters.append(_as_cond(c))
        return self

    def join(self, other: type, condition: Any) -> "Query":
        self._joins.append((other, _as_cond(condition)))
        return self

    def limit(self, n: int) -> "Query":
        self._limit = n
        return self

    def order_by(self, *specs: Any) -> "Query":
        for spec in specs:
            if isinstance(spec, tuple) and spec[0] in ("desc", "asc"):
                self._order.append(spec)
            elif isinstance(spec, FieldRef):
                self._order.append(("asc", spec.model, spec.name))
            else:
                raise TypeError(f"Unsupported order: {spec!r}")
        return self

    def _joined_row(self, row: Any) -> dict[type, Any] | None:
        joined: dict[type, Any] = {type(row): row}
        for other, cond in self._joins:
            op, model, name, value = cond
            if op != "eq" or not isinstance(value, FieldRef):
                return None
            if value.model is type(row) and model is other:
                row_val = _attr(row, value.name)
                if name == "id":
                    other_obj = self.store.get(other, row_val)
                else:
                    other_obj = next((c for c in self.store._rows(other) if _attr(c, name) == row_val), None)
            elif model is type(row) and value.model is other:
                row_val = _attr(row, name)
                if value.name == "id":
                    other_obj = self.store.get(other, row_val)
                else:
                    other_obj = next((c for c in self.store._rows(other) if _attr(c, value.name) == row_val), None)
            else:
                return None
            if other_obj is None:
                return None
            joined[other] = other_obj
        return joined

    def _match(self, row: Any) -> bool:
        joined = self._joined_row(row) if self._joins else {type(row): row}
        if joined is None:
            return False
        for cond in self._filters:
            op, model, name, value = cond
            target = joined.get(model)
            if target is None:
                if model is type(row):
                    target = row
                else:
                    return False
            actual = _attr(target, name)
            if isinstance(value, FieldRef):
                other = joined.get(value.model)
                if other is None:
                    return False
                value = _attr(other, value.name)
            if op == "eq" and actual != value:
                return False
            if op == "ne" and actual == value:
                return False
            if op == "in" and actual not in value:
                return False
            if op == "isnot":
                if value is None and actual is None:
                    return False
                if value is not None and actual == value:
                    return False
        return True

    def _sorted(self, rows: list[Any]) -> list[Any]:
        if not self._order:
            return rows
        out = list(rows)
        for spec in reversed(self._order):
            direction, _model, name = spec
            reverse = direction == "desc"

            def key(obj: Any, n: str = name):
                val = _attr(obj, n)
                if val is None:
                    return (1, datetime.min.replace(tzinfo=timezone.utc) if n.endswith("_at") else "")
                return (0, val)

            out.sort(key=key, reverse=reverse)
        return out

    def _execute(self) -> list[Any]:
        rows = [r for r in self.store._rows(self.model) if self._match(r)]
        rows = self._sorted(rows)
        if self._limit is not None:
            rows = rows[: self._limit]
        return rows

    def all(self) -> list[Any]:
        return self._execute()

    def first(self) -> Any | None:
        rows = self._execute()
        return rows[0] if rows else None

    def one_or_none(self) -> Any | None:
        rows = self._execute()
        if len(rows) > 1:
            raise ValueError(f"Multiple {self.model.__name__} rows")
        return rows[0] if rows else None

    def one(self) -> Any:
        row = self.one_or_none()
        if row is None:
            raise ValueError(f"No {self.model.__name__} row")
        return row

    def count(self) -> int:
        return len(self._execute())


class MemoryStore:
    """In-memory repository implementing the former SQLAlchemy Session surface."""

    def __init__(self) -> None:
        self._data: dict[type, dict[str, Any]] = {model: {} for model in TABLES}
        self._deleted: list[Any] = []

    def query(self, target: type | FieldRef) -> Query:
        return Query(self, target)

    def get(self, model: type, ident: str | None) -> Any | None:
        if ident is None:
            return None
        return self._data.get(model, {}).get(str(ident))

    def add(self, obj: Any) -> None:
        model = type(obj)
        if model not in self._data:
            self._data[model] = {}
        if not getattr(obj, "id", None):
            from workflow.models import _uuid
            obj.id = _uuid()
        self._data[model][str(obj.id)] = obj

    def delete(self, obj: Any) -> None:
        model = type(obj)
        self._data.get(model, {}).pop(str(obj.id), None)
        self._deleted.append(obj)

    def flush(self) -> None:
        for model, rows in self._data.items():
            for obj in rows.values():
                if not getattr(obj, "id", None):
                    from workflow.models import _uuid
                    obj.id = _uuid()

    def commit(self) -> None:
        self.flush()
        self._deleted.clear()

    def refresh(self, obj: Any) -> None:
        live = self.get(type(obj), getattr(obj, "id", None))
        if live is None or live is obj:
            return
        if is_dataclass(obj) and is_dataclass(live):
            for f in fields(obj):
                setattr(obj, f.name, getattr(live, f.name))

    def touch(self, obj: Any) -> None:
        return

    def close(self) -> None:
        return

    def _rows(self, model: type) -> list[Any]:
        return list(self._data.get(model, {}).values())

    def snapshot(self) -> dict[str, int]:
        return {model.__name__: len(rows) for model, rows in self._data.items()}


Store = MemoryStore
