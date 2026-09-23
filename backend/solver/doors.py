"""Doors on shared walls implied by topology. Prototype usability, not code compliance."""

from __future__ import annotations

from .models import Door, Layout, PlacedRoom, Rect, TopologyEdge
from .room_rules import DOOR_CLEARANCE_FT, DOOR_WIDTH_FT, MIN_SHARED_WALL_FT, OUTDOOR_TYPES


def _shared_segment(a: PlacedRoom, b: PlacedRoom) -> tuple[str, float, float, float] | None:
    """Return (axis, pos, start, end) if rooms share a wall on actual part edges."""
    best = None
    best_len = 0.0
    for pa in a.parts():
        for pb in b.parts():
            if pa.x2 == pb.x or pb.x2 == pa.x:
                pos = pa.x2 if pa.x2 == pb.x else pb.x2
                lo = max(pa.y, pb.y)
                hi = min(pa.y2, pb.y2)
                span = hi - lo
                if span >= MIN_SHARED_WALL_FT and span > best_len:
                    best = ("vertical", float(pos), float(lo), float(hi))
                    best_len = span
            if pa.y2 == pb.y or pb.y2 == pa.y:
                pos = pa.y2 if pa.y2 == pb.y else pb.y2
                lo = max(pa.x, pb.x)
                hi = min(pa.x2, pb.x2)
                span = hi - lo
                if span >= MIN_SHARED_WALL_FT and span > best_len:
                    best = ("horizontal", float(pos), float(lo), float(hi))
                    best_len = span
    return best


def place_doors(layout: Layout, edges: list[TopologyEdge]) -> list[Door]:
    doors: list[Door] = []
    seen: set[tuple[str, str]] = set()
    n = 0
    access = {"connected", "accessed_by", "outside_access", "adjacent"}
    for e in edges:
        if e.relation not in access:
            continue
        key = tuple(sorted((e.room_a, e.room_b)))
        if key in seen:
            continue
        a = layout.room_by_id(e.room_a)
        b = layout.room_by_id(e.room_b)
        if not a or not b:
            continue
        seg = _shared_segment(a, b)
        if not seg:
            continue
        axis, pos, lo, hi = seg
        mid = (lo + hi) / 2.0
        width = min(DOOR_WIDTH_FT, hi - lo)
        is_vertical = axis == "vertical"
        door_type = "exterior" if e.relation == "outside_access" else "interior"
        if is_vertical:
            x, y = pos, mid - width / 2.0
        else:
            x, y = mid - width / 2.0, pos
        doors.append(Door(
            id=f"d{n}",
            room_a=e.room_a,
            room_b=e.room_b,
            x=x,
            y=y,
            width=width,
            is_vertical=is_vertical,
            door_type=door_type,
        ))
        seen.add(key)
        n += 1
    return doors


def door_clearance(door: Door, room: PlacedRoom) -> Rect:
    """Clearance rectangle inside `room` in front of the door. Prototype 3 ft."""
    from .footprint import contains_cell

    c = float(DOOR_CLEARANCE_FT)
    w = float(door.width)
    if door.is_vertical:
        mid_y = int(door.y + w / 2.0)
        right_inside = contains_cell(room, int(door.x), mid_y) or contains_cell(room, int(door.x + 0.5), mid_y)
        left_inside = contains_cell(room, int(door.x - 1), mid_y) or contains_cell(room, int(door.x - 0.5), mid_y)
        if right_inside and not left_inside:
            return Rect(x=door.x, y=door.y, width=c, depth=w)
        if left_inside and not right_inside:
            return Rect(x=door.x - c, y=door.y, width=c, depth=w)
        inside_right = abs(door.x - room.x) < abs(door.x - room.x2)
        x = door.x if inside_right else door.x - c
        return Rect(x=x, y=door.y, width=c, depth=w)
    mid_x = int(door.x + w / 2.0)
    down_inside = contains_cell(room, mid_x, int(door.y)) or contains_cell(room, mid_x, int(door.y + 0.5))
    up_inside = contains_cell(room, mid_x, int(door.y - 1)) or contains_cell(room, mid_x, int(door.y - 0.5))
    if down_inside and not up_inside:
        return Rect(x=door.x, y=door.y, width=w, depth=c)
    if up_inside and not down_inside:
        return Rect(x=door.x, y=door.y - c, width=w, depth=c)
    inside_down = abs(door.y - room.y) < abs(door.y - room.y2)
    y = door.y if inside_down else door.y - c
    return Rect(x=door.x, y=y, width=w, depth=c)


def door_swing_rect(door: Door, room: PlacedRoom) -> Rect:
    """Opening envelope inside `room`. Same prototype as door_clearance.

    Hinge is inferred from the shared wall; swing_direction 'in' opens into
    the destination room. Not a licensed door schedule.
    """
    return door_clearance(door, room)

