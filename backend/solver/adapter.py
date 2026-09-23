"""Convert between solver Layout and existing FloorPlan dicts."""

from __future__ import annotations

from .models import Layout, PlacedRoom, RoomProgram
from .footprint import boundary_segments, centroid_of


ROOM_COLORS = {
    "living_room": "#E8D5B7", "kitchen": "#B7D5E8", "dining_room": "#D5E8B7",
    "family_room": "#E8E0B7", "master_bedroom": "#D8B7E8", "bedroom": "#C8B7E8",
    "ensuite_bathroom": "#B7E8E0", "bathroom": "#B7E8D5", "half_bath": "#D0E8E8",
    "hallway": "#E0E0D3", "foyer": "#EEEAE0", "home_office": "#F5F0D3",
    "laundry_room": "#D3F5F5", "garage": "#D5D5CC", "walk_in_closet": "#E8D8E8",
    "closet": "#E0D8E0", "pantry": "#EDE8DC", "mudroom": "#E8E4D8",
    "utility_room": "#E8E8D3", "patio": "#E0EED8", "deck": "#E8E4D0",
}


def _footprint_payload(room: PlacedRoom) -> dict:
    parts = [
        {"x": p.x, "y": p.y, "width": p.width, "height": p.depth}
        for p in room.parts()
    ]
    cx, cy = centroid_of(room)
    return {
        "type": room.footprint.type if room.footprint else "rectangle",
        "parts": parts,
        "centroid": {"x": round(cx, 3), "y": round(cy, 3)},
        "boundary": [
            {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
            for x1, y1, x2, y2 in boundary_segments(room)
        ],
    }


def hints_from_moe_plan(plan: dict, program: RoomProgram) -> dict[str, tuple[int, int, int, int]]:
    """Map MOE rooms onto program ids by type order. Sizes become preferred hints."""
    unused: dict[str, list[dict]] = {}
    for r in plan.get("rooms") or []:
        unused.setdefault(r.get("type", ""), []).append(r)
    hints = {}
    for spec in program.rooms:
        bucket = unused.get(spec.type) or []
        if not bucket:
            continue
        src = bucket.pop(0)
        hints[spec.id] = (
            int(round(src.get("x", 0))),
            int(round(src.get("y", 0))),
            max(1, int(round(src.get("width", spec.min_width)))),
            max(1, int(round(src.get("height", spec.min_depth)))),
        )
    return hints


def layout_to_floorplan(layout: Layout, name: str = "KIYUB Plan", ceiling: int = 9) -> dict:
    rooms = []
    max_x = 0
    max_y = 0
    for r in layout.rooms:
        rooms.append({
            "id": r.id,
            "name": r.name,
            "type": r.type,
            "x": r.x,
            "y": r.y,
            "width": r.width,
            "height": r.depth,
            "color": ROOM_COLORS.get(r.type, "#E0E0E0"),
            "footprint": _footprint_payload(r),
        })
        max_x = max(max_x, r.x2)
        max_y = max(max_y, r.y2)
    doors = []
    for d in layout.doors:
        payload = {
            "id": d.id,
            "x": d.x,
            "y": d.y,
            "isVertical": d.is_vertical,
            "roomA": d.room_a,
            "roomB": d.room_b,
        }
        doors.append(payload)
    from .openings import door_openings
    walls = [w.as_dict() for w in (layout.walls or [])]
    openings = [o.as_dict() for o in (layout.openings or [])]
    openings.extend(o.as_dict() for o in door_openings(layout))
    furniture = [
        {
            "id": item.id,
            "roomId": item.room_id,
            "kind": item.kind,
            "x": item.x,
            "y": item.y,
            "width": item.width,
            "depth": item.depth,
            "rotation": 0,
        }
        for item in (layout.furniture or [])
    ]
    return {
        "id": f"ortools_{abs(hash(name)) % 10**8:08d}",
        "name": name,
        "totalWidth": max_x,
        "totalHeight": max_y,
        "ceilingHeight": ceiling,
        "rooms": rooms,
        "doors": doors,
        "walls": walls,
        "openings": openings,
        "furniture": furniture,
        "generator": "ortools",
        "validated": True,
    }
