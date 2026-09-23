"""Simplified furniture footprints for usability checks, not rendering."""

from __future__ import annotations

from .doors import door_clearance
from .models import Door, FurnitureFootprint, Layout, PlacedRoom, Rect
from .room_rules import OUTDOOR_TYPES


def _rect_for(f: FurnitureFootprint) -> Rect:
    return Rect(x=f.x, y=f.y, width=f.width, depth=f.depth)


def _fits(room: PlacedRoom, x: float, y: float, w: float, d: float) -> bool:
    from .footprint import contains_rect
    return contains_rect(room, x, y, w, d)


def _candidates(room: PlacedRoom, w: float, d: float) -> list[tuple[float, float, float, float]]:
    """Place along each wall of each footprint part."""
    opts: list[tuple[float, float, float, float]] = []
    for p in room.parts():
        opts.extend([
            (p.x, p.y, w, d),
            (p.x2 - w, p.y, w, d),
            (p.x, p.y2 - d, w, d),
            (p.x2 - w, p.y2 - d, w, d),
            (p.x, p.y, d, w),
            (p.x2 - d, p.y, d, w),
            (p.x, p.y2 - w, d, w),
            (p.x2 - d, p.y2 - w, d, w),
        ])
    return [o for o in opts if _fits(room, *o)]


def place_furniture(layout: Layout) -> list[FurnitureFootprint]:
    items: list[FurnitureFootprint] = []
    n = 0
    doors_by_room: dict[str, list[Door]] = {}
    for d in layout.doors:
        doors_by_room.setdefault(d.room_a, []).append(d)
        doors_by_room.setdefault(d.room_b, []).append(d)

    def add(room_id: str, kind: str, x: float, y: float, w: float, d: float) -> None:
        nonlocal n
        items.append(FurnitureFootprint(
            id=f"f{n}", room_id=room_id, kind=kind, x=x, y=y, width=w, depth=d,
        ))
        n += 1

    for room in layout.rooms:
        if room.type in OUTDOOR_TYPES or room.type in ("hallway", "foyer", "garage", "closet", "walk_in_closet", "pantry"):
            continue
        room_doors = doors_by_room.get(room.id, [])
        clearances = [door_clearance(d, room) for d in room_doors]

        def ok(x, y, w, d) -> bool:
            r = Rect(x=x, y=y, width=w, depth=d)
            return not any(r.intersects(c) for c in clearances)

        if room.type in ("bedroom", "master_bedroom"):
            placed = False
            sizes = [(7, 5), (5, 7)]
            if room.type == "master_bedroom":
                sizes = [(7, 6), (6, 7), (7, 5), (5, 7)]
            for bw, bd in sizes:
                for x, y, w, d in _candidates(room, bw, bd):
                    if ok(x, y, w, d):
                        add(room.id, "bed", x, y, w, d)
                        placed = True
                        break
                if placed:
                    break
            # Do not plant a blocking bed. Missing furniture is a usability penalty, not infeasibility.

        elif room.type == "living_room":
            for x, y, w, d in _candidates(room, 7, 3):
                if ok(x, y, w, d):
                    add(room.id, "sofa", x, y, w, d)
                    break

        elif room.type == "dining_room":
            cx = room.x + max(0.5, (room.width - 5) / 2)
            cy = room.y + max(0.5, (room.depth - 3) / 2)
            if _fits(room, cx, cy, 5, 3) and ok(cx, cy, 5, 3):
                add(room.id, "dining_table", cx, cy, 5, 3)

        elif room.type in ("bathroom", "ensuite_bathroom"):
            for kind, fw, fd in (("toilet", 2, 3), ("lavatory", 2, 2), ("shower", 3, 3)):
                if room.type == "bathroom" and kind == "shower":
                    continue
                for x, y, w, d in _candidates(room, fw, fd):
                    used = [_rect_for(i) for i in items if i.room_id == room.id]
                    r = Rect(x=x, y=y, width=w, depth=d)
                    if ok(x, y, w, d) and not any(r.intersects(u) for u in used):
                        add(room.id, kind, x, y, w, d)
                        break

    return items
