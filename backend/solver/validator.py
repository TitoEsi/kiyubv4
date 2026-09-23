"""Architectural validator. Geometry/relationships only — not building-code compliance."""

from __future__ import annotations

from collections import defaultdict, deque

from .doors import door_clearance
from .models import (
    FurnitureFootprint,
    Layout,
    PlacedRoom,
    Rect,
    RoomProgram,
    ValidationIssue,
    ValidationReport,
)
from .room_rules import (
    BATH_TYPES,
    BEDROOM_TYPES,
    CIRCULATION_TYPES,
    CIRCULATION_RATIO_MAX,
    HALL_MAX_AREA_FT2,
    HALL_MAX_SHORT_FT,
    OCCUPIED_TYPES,
    OUTDOOR_TYPES,
)
from .topology import required_access_pairs


def _overlap_area(a: PlacedRoom, b: PlacedRoom) -> float:
    from .footprint import intersection_area
    return float(intersection_area(a, b))


def validate_room_bounds(layout: Layout, report: ValidationReport) -> None:
    env = layout.envelope
    if not env:
        return
    for r in layout.rooms:
        if r.x < 0 or r.y < 0 or r.width <= 0 or r.depth <= 0:
            report.errors.append(ValidationIssue(
                "room_bounds", r.id, f"{r.name} has non-positive size or negative origin.",
            ))
        if r.x + r.width > env.width + 1e-6 or r.y + r.depth > env.depth + 1e-6:
            report.errors.append(ValidationIssue(
                "room_outside_envelope", r.id,
                f"{r.name} extends outside the buildable envelope "
                f"({env.width}×{env.depth} ft).",
            ))


def validate_room_overlap(layout: Layout, report: ValidationReport) -> None:
    rooms = layout.rooms
    for i, a in enumerate(rooms):
        for b in rooms[i + 1:]:
            if _overlap_area(a, b) > 0.05:
                report.errors.append(ValidationIssue(
                    "room_overlap", a.id,
                    f"{a.name} overlaps {b.name}.",
                ))


def validate_required_rooms(layout: Layout, program: RoomProgram, report: ValidationReport) -> None:
    beds = sum(1 for r in layout.rooms if r.type in BEDROOM_TYPES)
    baths = sum(1 for r in layout.rooms if r.type in BATH_TYPES)
    if beds != program.bedrooms_requested:
        report.errors.append(ValidationIssue(
            "bedroom_count", "",
            f"Requested {program.bedrooms_requested} bedrooms, layout has {beds}.",
        ))
    if baths != program.bathrooms_requested:
        report.errors.append(ValidationIssue(
            "bathroom_count", "",
            f"Requested {program.bathrooms_requested} bathrooms, layout has {baths}.",
        ))
    have = {r.id for r in layout.rooms}
    for spec in program.rooms:
        if spec.required and spec.id not in have:
            report.errors.append(ValidationIssue(
                "missing_room", spec.id, f"Required room {spec.name} is missing.",
            ))


def validate_connectivity(layout: Layout, report: ValidationReport) -> None:
    graph: dict[str, set[str]] = defaultdict(set)
    for d in layout.doors:
        graph[d.room_a].add(d.room_b)
        graph[d.room_b].add(d.room_a)

    foyer = next((r.id for r in layout.rooms if r.type == "foyer"), None)
    seeds = [foyer] if foyer else [r.id for r in layout.rooms if r.type in CIRCULATION_TYPES]
    if not seeds:
        seeds = [r.id for r in layout.rooms if r.type == "living_room"]
    seen: set[str] = set()
    q = deque([s for s in seeds if s])
    while q:
        cur = q.popleft()
        if cur in seen:
            continue
        seen.add(cur)
        for nxt in graph[cur]:
            if nxt not in seen:
                q.append(nxt)

    habitable = OCCUPIED_TYPES | BATH_TYPES | BEDROOM_TYPES
    for r in layout.rooms:
        if r.type in habitable and r.id not in seen:
            report.errors.append(ValidationIssue(
                "inaccessible_room", r.id,
                f"{r.name} is not connected to the foyer/circulation by a door.",
            ))


def validate_hallway_area(layout: Layout, report: ValidationReport) -> None:
    from .footprint import union_area
    for r in layout.rooms:
        if r.type != "hallway":
            continue
        area = union_area(r)
        short = min(r.width, r.depth)
        if area > HALL_MAX_AREA_FT2:
            report.errors.append(ValidationIssue(
                "hallway_area", r.id,
                f"{r.name} area {area} sf exceeds the {HALL_MAX_AREA_FT2} sf circulation cap.",
            ))
        if short > HALL_MAX_SHORT_FT:
            report.errors.append(ValidationIssue(
                "hallway_width", r.id,
                f"{r.name} short side {short} ft is too wide for a corridor.",
            ))


def validate_circulation_ratio(layout: Layout, report: ValidationReport) -> None:
    from .footprint import union_area
    indoor = [r for r in layout.rooms if r.type not in OUTDOOR_TYPES]
    enclosed = sum(union_area(r) for r in indoor)
    circ = sum(union_area(r) for r in indoor if r.type in CIRCULATION_TYPES)
    if enclosed <= 0:
        return
    ratio = circ / enclosed
    if ratio > CIRCULATION_RATIO_MAX:
        report.errors.append(ValidationIssue(
            "circulation_ratio", "",
            f"Circulation ratio {ratio:.2f} exceeds heuristic cap {CIRCULATION_RATIO_MAX:.2f}.",
        ))


def validate_forbidden_pairs(layout: Layout, report: ValidationReport) -> None:
    from .doors import _shared_segment
    rooms = {r.id: r for r in layout.rooms}
    for e in layout.topology or []:
        if e.relation not in ("separated", "avoid") or not e.hard:
            continue
        a, b = rooms.get(e.room_a), rooms.get(e.room_b)
        if not a or not b:
            continue
        if _shared_segment(a, b) is not None:
            report.errors.append(ValidationIssue(
                "forbidden_adjacency", a.id,
                f"{a.name} shares a wall with forbidden neighbor {b.name}.",
            ))


def validate_doors(layout: Layout, report: ValidationReport) -> None:
    ids = {r.id for r in layout.rooms}
    for d in layout.doors:
        if d.room_a not in ids or d.room_b not in ids:
            report.errors.append(ValidationIssue(
                "door_invalid", d.room_a,
                f"Door {d.id} does not join two rooms in the layout.",
            ))


def validate_door_clearance(layout: Layout, report: ValidationReport) -> None:
    furn_by_room: dict[str, list[FurnitureFootprint]] = defaultdict(list)
    for f in layout.furniture:
        furn_by_room[f.room_id].append(f)

    for d in layout.doors:
        for rid in (d.room_a, d.room_b):
            room = layout.room_by_id(rid)
            if not room or room.type not in ("bedroom", "master_bedroom"):
                continue
            clr = door_clearance(d, room)
            for f in furn_by_room[rid]:
                fr = Rect(x=f.x, y=f.y, width=f.width, depth=f.depth)
                if clr.intersects(fr):
                    report.errors.append(ValidationIssue(
                        "door_blocked", rid,
                        f"{room.name} door clearance intersects {f.kind} footprint.",
                    ))


def validate_circulation(layout: Layout, report: ValidationReport) -> None:
    if not any(r.type in CIRCULATION_TYPES for r in layout.rooms):
        report.errors.append(ValidationIssue(
            "missing_circulation", "",
            "Layout has no foyer or hallway for circulation.",
        ))


def validate_outdoor_access(layout: Layout, program: RoomProgram, report: ValidationReport) -> None:
    if not program.outdoor_requested:
        return
    outdoor = [r for r in layout.rooms if r.type in OUTDOOR_TYPES]
    if not outdoor:
        report.errors.append(ValidationIssue(
            "missing_outdoor", "",
            "Outdoor space was requested but is not in the layout.",
        ))
        return
    outdoor_ids = {r.id for r in outdoor}
    linked = any(
        (d.room_a in outdoor_ids) or (d.room_b in outdoor_ids)
        for d in layout.doors
    )
    if not linked:
        report.errors.append(ValidationIssue(
            "outdoor_no_access", outdoor[0].id,
            f"{outdoor[0].name} has no door from an interior room.",
        ))


def validate_furniture_clearance(layout: Layout, report: ValidationReport) -> None:
    by_room: dict[str, list[FurnitureFootprint]] = defaultdict(list)
    for f in layout.furniture:
        by_room[f.room_id].append(f)
    for rid, items in by_room.items():
        room = layout.room_by_id(rid)
        if not room:
            continue
        for f in items:
            from .footprint import contains_rect
            if not contains_rect(room, f.x, f.y, f.width, f.depth):
                report.errors.append(ValidationIssue(
                    "furniture_outside_room", rid,
                    f"{f.kind} in {room.name} extends outside the room.",
                ))
        for i, a in enumerate(items):
            ra = Rect(x=a.x, y=a.y, width=a.width, depth=a.depth)
            for b in items[i + 1:]:
                rb = Rect(x=b.x, y=b.y, width=b.width, depth=b.depth)
                if ra.intersects(rb):
                    report.warnings.append(ValidationIssue(
                        "furniture_overlap", rid,
                        f"{a.kind} overlaps {b.kind} in {room.name}.",
                        severity="warning",
                    ))


def validate_dead_space(layout: Layout, report: ValidationReport) -> None:
    env = layout.envelope
    if not env or env.area <= 0:
        return
    from .footprint import union_area
    used = sum(union_area(r) for r in layout.rooms)
    unused = env.area - used
    if unused / env.area > 0.45:
        report.warnings.append(ValidationIssue(
            "dead_space", "",
            f"Unused envelope area is {unused} sqft "
            f"({unused / env.area:.0%} of {env.area} sqft). Prototype efficiency check.",
            severity="warning",
        ))


def validate(layout: Layout, program: RoomProgram) -> ValidationReport:
    report = ValidationReport()
    validate_room_bounds(layout, report)
    validate_room_overlap(layout, report)
    validate_required_rooms(layout, program, report)
    validate_doors(layout, report)
    validate_circulation(layout, report)
    validate_hallway_area(layout, report)
    validate_circulation_ratio(layout, report)
    validate_connectivity(layout, report)
    validate_forbidden_pairs(layout, report)
    validate_door_clearance(layout, report)
    validate_furniture_clearance(layout, report)
    validate_outdoor_access(layout, program, report)
    validate_dead_space(layout, report)
    return report
