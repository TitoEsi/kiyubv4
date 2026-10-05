"""Human-readable change summary between two SceneDocuments (metric, v2 or legacy workflow shape)."""
from __future__ import annotations

import json
import math
from typing import Any

MAX_LINES = 12
MOVE_EPS_M = 0.01
AREA_EPS_M2 = 0.05
SIZE_EPS_M = 0.01


def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pt(p: Any) -> tuple[float, float] | None:
    if isinstance(p, dict):
        x, y = _num(p.get("x")), _num(p.get("y"))
        if x is not None and y is not None:
            return x, y
    return None


def _by_id(items: Any) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i, item in enumerate(items if isinstance(items, list) else []):
        if isinstance(item, dict):
            out[str(item.get("id") or f"#{i}")] = item
    return out


def _room_box(room: dict) -> tuple[float, float, float, float] | None:
    pos = _pt(room.get("position")) or _pt(room)
    dims = room.get("dimensions") if isinstance(room.get("dimensions"), dict) else room
    w = _num(dims.get("width"))
    h = _num(dims.get("height")) if dims.get("height") is not None else _num(dims.get("depth"))
    if pos is None or w is None or h is None:
        return None
    return pos[0], pos[1], w, h


def _room_area(room: dict) -> float | None:
    area = _num(room.get("area"))
    if area is not None:
        return area
    box = _room_box(room)
    return box[2] * box[3] if box else None


def _room_name(room: dict) -> str:
    return str(room.get("name") or room.get("type") or "Room").strip() or "Room"


def _room_at(rooms: dict[str, dict], p: tuple[float, float] | None) -> str | None:
    if p is None:
        return None
    best, best_d = None, math.inf
    for room in rooms.values():
        box = _room_box(room)
        if not box:
            continue
        x, y, w, h = box
        dx = max(x - p[0], 0.0, p[0] - (x + w))
        dy = max(y - p[1], 0.0, p[1] - (y + h))
        d = math.hypot(dx, dy)
        if d < best_d:
            best, best_d = room, d
    return _room_name(best) if best is not None and best_d <= 0.6 else None


def _wall_ends(w: dict) -> tuple[tuple[float, float], tuple[float, float]] | None:
    a, b = _pt(w.get("start")), _pt(w.get("end"))
    if a and b:
        return a, b
    x1, y1, x2, y2 = (_num(w.get(k)) for k in ("x1", "y1", "x2", "y2"))
    if None not in (x1, y1, x2, y2):
        return (x1, y1), (x2, y2)
    return None


def _moved(a: tuple[float, float] | None, b: tuple[float, float] | None) -> bool:
    return a is not None and b is not None and math.hypot(a[0] - b[0], a[1] - b[1]) > MOVE_EPS_M


def _openings(scene: dict) -> dict[str, dict]:
    raw = scene.get("openings")
    items: list[dict] = []
    if isinstance(raw, list):
        items = [o for o in raw if isinstance(o, dict)]
    elif isinstance(raw, dict):
        for key, kind in (("doors", "door"), ("windows", "window")):
            for o in raw.get(key) or []:
                if isinstance(o, dict):
                    items.append({"type": kind, **o})
    return _by_id(items)


def _opening_kind(o: dict) -> str:
    t = str(o.get("type") or "opening").lower()
    if "window" in t:
        return "window"
    if "door" in t:
        return "door"
    return t.replace("_", " ")


def _label(room: str | None, noun: str) -> str:
    return f"{room} {noun}" if room else noun[:1].upper() + noun[1:]


def _wall_mid(w: dict) -> tuple[float, float] | None:
    ends = _wall_ends(w)
    return ((ends[0][0] + ends[1][0]) / 2, (ends[0][1] + ends[1][1]) / 2) if ends else None


def _fmt_area(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def _summarize_rooms(prev: dict[str, dict], nxt: dict[str, dict]) -> list[str]:
    lines: list[str] = []
    for rid, room in nxt.items():
        old = prev.get(rid)
        name = _room_name(room)
        if old is None:
            lines.append(f"{name} added")
            continue
        if _room_name(old) != name:
            lines.append(f"{_room_name(old)} renamed to {name}")
        a0, a1 = _room_area(old), _room_area(room)
        if a0 is not None and a1 is not None and abs(a1 - a0) >= AREA_EPS_M2:
            verb = "increased" if a1 > a0 else "decreased"
            lines.append(f"{name} area {verb} by {_fmt_area(abs(a1 - a0))} m²")
        else:
            b0, b1 = _room_box(old), _room_box(room)
            if b0 and b1 and _moved(b0[:2], b1[:2]):
                lines.append(f"{name} moved")
    for rid, room in prev.items():
        if rid not in nxt:
            lines.append(f"{_room_name(room)} removed")
    return lines


def _summarize_walls(prev: dict[str, dict], nxt: dict[str, dict], prev_rooms: dict, next_rooms: dict) -> list[str]:
    lines: list[str] = []
    for wid, wall in nxt.items():
        old = prev.get(wid)
        room = _room_at(next_rooms, _wall_mid(wall))
        if old is None:
            lines.append(f"{_label(room, 'wall')} added")
            continue
        e0, e1 = _wall_ends(old), _wall_ends(wall)
        if e0 and e1 and (_moved(e0[0], e1[0]) or _moved(e0[1], e1[1])):
            lines.append(f"{_label(room, 'wall')} moved")
        t0, t1 = _num(old.get("thickness")), _num(wall.get("thickness"))
        if t0 is not None and t1 is not None and abs(t1 - t0) > SIZE_EPS_M / 2:
            lines.append(f"{_label(room, 'wall')} thickness changed")
    for wid, wall in prev.items():
        if wid not in nxt:
            lines.append(f"{_label(_room_at(prev_rooms, _wall_mid(wall)), 'wall')} removed")
    return lines


def _opening_pos(o: dict) -> tuple[float, float] | None:
    return _pt(o.get("position")) or _pt(o)


def _summarize_openings(prev: dict[str, dict], nxt: dict[str, dict], prev_rooms: dict, next_rooms: dict) -> list[str]:
    lines: list[str] = []
    for oid, o in nxt.items():
        old = prev.get(oid)
        noun = _opening_kind(o)
        room = _room_at(next_rooms, _opening_pos(o))
        if old is None:
            lines.append(f"{_label(room, noun)} added")
            continue
        if _opening_kind(old) != noun:
            lines.append(f"{_label(room, _opening_kind(old))} changed to {noun}")
        if _moved(_opening_pos(old), _opening_pos(o)):
            lines.append(f"{_label(room, noun)} position changed")
        w0, w1 = _num(old.get("width")), _num(o.get("width"))
        h0, h1 = _num(old.get("height")), _num(o.get("height"))
        if (w0 is not None and w1 is not None and abs(w1 - w0) > SIZE_EPS_M) or (
            h0 is not None and h1 is not None and abs(h1 - h0) > SIZE_EPS_M
        ):
            lines.append(f"{_label(room, noun)} size changed")
        elif any(old.get(k) != o.get(k) for k in ("hinge", "swing", "rotation", "flipped", "swingDirection")):
            lines.append(f"{_label(room, noun)} swing changed")
    for oid, o in prev.items():
        if oid not in nxt:
            lines.append(f"{_label(_room_at(prev_rooms, _opening_pos(o)), _opening_kind(o))} removed")
    return lines


def _furniture_label(item: dict, rooms: dict[str, dict]) -> str:
    kind = str(item.get("kind") or "furniture").replace("_", " ").replace("-", " ")
    room = rooms.get(str(item.get("roomId"))) if item.get("roomId") else None
    room_name = _room_name(room) if room else _room_at(rooms, _pt(item.get("position")))
    return _label(room_name, kind)


def _summarize_furniture(prev: dict[str, dict], nxt: dict[str, dict], prev_rooms: dict, next_rooms: dict) -> list[str]:
    lines: list[str] = []
    for fid, item in nxt.items():
        old = prev.get(fid)
        if old is None:
            lines.append(f"{_furniture_label(item, next_rooms)} added")
        elif _moved(_pt(old.get("position")), _pt(item.get("position"))) or old.get("rotation") != item.get("rotation"):
            lines.append(f"{_furniture_label(item, next_rooms)} moved")
    for fid, item in prev.items():
        if fid not in nxt:
            lines.append(f"{_furniture_label(item, prev_rooms)} removed")
    return lines


def _same(a: Any, b: Any) -> bool:
    return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


_FLOOR_MEMBERSHIP = ("roomIds", "wallIds", "openingIds", "stairIds")


def _floor_settings(floors: Any) -> list:
    """Floor data without membership lists, which change whenever a room, wall or opening does."""
    if not isinstance(floors, list):
        return []
    return [{k: v for k, v in f.items() if k not in _FLOOR_MEMBERSHIP} if isinstance(f, dict) else f for f in floors]


def summarize_changes(prev: Any, nxt: Any) -> list[str]:
    """Readable lines describing how ``nxt`` differs from ``prev``; empty when nothing meaningful changed."""
    if not isinstance(nxt, dict):
        return []
    if not isinstance(prev, dict):
        return ["Initial version submitted"]
    prev_rooms, next_rooms = _by_id(prev.get("rooms")), _by_id(nxt.get("rooms"))
    lines = _summarize_rooms(prev_rooms, next_rooms)
    lines += _summarize_walls(_by_id(prev.get("walls")), _by_id(nxt.get("walls")), prev_rooms, next_rooms)
    lines += _summarize_openings(_openings(prev), _openings(nxt), prev_rooms, next_rooms)
    lines += _summarize_furniture(_by_id(prev.get("furniture")), _by_id(nxt.get("furniture")), prev_rooms, next_rooms)
    if not _same(prev.get("site"), nxt.get("site")):
        lines.append("Site details changed")
    if not _same(_floor_settings(prev.get("floorData")), _floor_settings(nxt.get("floorData"))) or prev.get("floors") != nxt.get("floors"):
        lines.append("Floor settings changed")
    if not lines:
        lines.append("Design details updated")
    deduped = list(dict.fromkeys(lines))
    if len(deduped) > MAX_LINES:
        extra = len(deduped) - (MAX_LINES - 1)
        deduped = deduped[: MAX_LINES - 1] + [f"and {extra} more changes"]
    return deduped
