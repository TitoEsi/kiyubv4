"""Wall segments from realized room footprints. After valid layout, not HouseGAN masks.

Not professional architectural approval. Does not invent walls from empty geometry.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import Layout, WallSegment


SNAP = 0.25


def _q(v: float) -> float:
    return round(float(v) / SNAP) * SNAP


@dataclass
class _Edge:
    axis: str  # x | y  (x = vertical wall at x=pos, y = horizontal wall at y=pos)
    pos: float
    lo: float
    hi: float
    room_id: str


def _part_edges(room) -> list[_Edge]:
    edges: list[_Edge] = []
    for p in room.parts():
        x1, y1, x2, y2 = _q(p.x), _q(p.y), _q(p.x2), _q(p.y2)
        edges.append(_Edge("x", x1, min(y1, y2), max(y1, y2), room.id))
        edges.append(_Edge("x", x2, min(y1, y2), max(y1, y2), room.id))
        edges.append(_Edge("y", y1, min(x1, x2), max(x1, x2), room.id))
        edges.append(_Edge("y", y2, min(x1, x2), max(x1, x2), room.id))
    return edges


def _merge_intervals(items: list[tuple[float, float, str]]) -> list[tuple[float, float, list[str]]]:
    """Merge overlapping/touching intervals on one line. Shared span → both rooms."""
    if not items:
        return []
    points: list[float] = []
    for lo, hi, _rid in items:
        if hi - lo < SNAP:
            continue
        points.append(lo)
        points.append(hi)
    if not points:
        return []
    uniq = sorted(set(_q(p) for p in points))
    out: list[tuple[float, float, list[str]]] = []
    for a, b in zip(uniq, uniq[1:]):
        if b - a < SNAP:
            continue
        mid = (a + b) / 2.0
        rooms: list[str] = []
        for lo, hi, rid in items:
            if lo <= mid + 1e-9 and hi >= mid - 1e-9 and rid not in rooms:
                rooms.append(rid)
        if rooms:
            out.append((a, b, rooms))
    # Merge consecutive identical room sets
    merged: list[tuple[float, float, list[str]]] = []
    for lo, hi, rooms in out:
        if merged and merged[-1][2] == rooms and abs(merged[-1][1] - lo) < SNAP + 1e-9:
            merged[-1] = (merged[-1][0], hi, rooms)
        else:
            merged.append((lo, hi, rooms))
    return merged


def place_walls(layout: Layout) -> list[WallSegment]:
    """Unique snapped wall segments from room boundaries. No floating extras."""
    grouped: dict[tuple[str, float], list[tuple[float, float, str]]] = {}
    for room in layout.rooms:
        for e in _part_edges(room):
            grouped.setdefault((e.axis, e.pos), []).append((e.lo, e.hi, e.room_id))

    walls: list[WallSegment] = []
    n = 0
    for (axis, pos), items in sorted(grouped.items()):
        for lo, hi, rooms in _merge_intervals(items):
            if hi - lo < 1.0:
                continue
            kind = "interior" if len(rooms) >= 2 else "exterior"
            if axis == "x":
                x1, y1, x2, y2 = pos, lo, pos, hi
            else:
                x1, y1, x2, y2 = lo, pos, hi, pos
            walls.append(WallSegment(
                id=f"w{n}",
                x1=x1, y1=y1, x2=x2, y2=y2,
                kind=kind,
                room_ids=list(rooms),
            ))
            n += 1
    return walls


def wall_for_opening(
    walls: list[WallSegment],
    x: float,
    y: float,
    is_vertical: bool,
    width: float,
) -> WallSegment | None:
    """Nearest collinear wall that contains the opening center."""
    if is_vertical:
        cy = y + width / 2.0
        best = None
        best_d = 9e9
        for w in walls:
            if abs(w.x1 - w.x2) > SNAP:
                continue
            lo, hi = min(w.y1, w.y2), max(w.y1, w.y2)
            if cy < lo - 0.5 or cy > hi + 0.5:
                continue
            d = abs(w.x1 - x)
            if d < best_d:
                best_d = d
                best = w
        return best if best_d <= 1.5 else None
    cx = x + width / 2.0
    best = None
    best_d = 9e9
    for w in walls:
        if abs(w.y1 - w.y2) > SNAP:
            continue
        lo, hi = min(w.x1, w.x2), max(w.x1, w.x2)
        if cx < lo - 0.5 or cx > hi + 0.5:
            continue
        d = abs(w.y1 - y)
        if d < best_d:
            best_d = d
            best = w
    return best if best is not None and best_d <= 1.5 else None
