"""Window openings on exterior walls. Heuristic daylight, not code compliance.

Doors stay in doors.py. Windows are placed only on realized exterior walls.
"""
from __future__ import annotations

from .models import Layout, Opening
from .room_rules import DAYLIGHT_TYPES
from .walls import SNAP, wall_for_opening


WINDOW_WIDTH_FT = 4.0
WINDOW_HEIGHT_FT = 4.0
WINDOW_SILL_FT = 3.0
MIN_WALL_FOR_WINDOW_FT = 6.0


def _length(w) -> float:
    return abs(w.x2 - w.x1) + abs(w.y2 - w.y1)


def place_windows(layout: Layout) -> list[Opening]:
    """One window on the longest exterior wall of each daylight-required room."""
    walls = layout.walls or []
    if not walls:
        return []
    openings: list[Opening] = []
    n = 0
    used_walls: set[str] = set()
    for room in layout.rooms:
        if room.type not in DAYLIGHT_TYPES:
            continue
        candidates = [
            w for w in walls
            if w.kind == "exterior" and room.id in w.room_ids and _length(w) >= MIN_WALL_FOR_WINDOW_FT
        ]
        if not candidates:
            continue
        wall = max(candidates, key=_length)
        if wall.id in used_walls:
            remaining = [w for w in candidates if w.id not in used_walls]
            if not remaining:
                continue
            wall = max(remaining, key=_length)
        used_walls.add(wall.id)
        vertical = abs(wall.x1 - wall.x2) <= SNAP
        span = _length(wall)
        width = min(WINDOW_WIDTH_FT, max(2.0, span * 0.35))
        if vertical:
            y0 = min(wall.y1, wall.y2)
            y = y0 + (span - width) / 2.0
            x = wall.x1
        else:
            x0 = min(wall.x1, wall.x2)
            x = x0 + (span - width) / 2.0
            y = wall.y1
        openings.append(Opening(
            id=f"win{n}",
            wall_id=wall.id,
            kind="window",
            x=x,
            y=y,
            width=width,
            height=WINDOW_HEIGHT_FT,
            is_vertical=vertical,
            room_ids=[room.id],
            sill_height=WINDOW_SILL_FT,
        ))
        n += 1
    return openings


def door_openings(layout: Layout) -> list[Opening]:
    """Map placed doors onto wall members. Skip doors that do not sit on a wall."""
    walls = layout.walls or []
    if not walls:
        return []
    out: list[Opening] = []
    for i, d in enumerate(layout.doors):
        wall = wall_for_opening(walls, d.x, d.y, d.is_vertical, d.width)
        if wall is None:
            continue
        out.append(Opening(
            id=d.id or f"door{i}",
            wall_id=wall.id,
            kind="door",
            x=d.x,
            y=d.y,
            width=d.width,
            height=7.0,
            is_vertical=d.is_vertical,
            room_ids=[d.room_a, d.room_b],
            sill_height=0.0,
        ))
    return out
