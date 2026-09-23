"""Room furniture/fixture usability. Scoring layer, not FloorPlan rendering.

Hard: door swing vs major items, entry path, fixture overlap, min clearance.
Soft: extra clearance, centering, preferred orientation.
Does not change validated. Does not drop rooms.
Not professional architectural approval or code compliance.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .doors import door_swing_rect
from .furniture_templates import FurnitureTemplate, templates_for
from .models import Door, FurnitureFootprint, Layout, PlacedRoom, Rect
from .room_rules import CIRCULATION_TYPES, DOOR_CLEARANCE_FT, OUTDOOR_TYPES

PATH_MIN = float(DOOR_CLEARANCE_FT)
KITCHEN_AISLE_MIN = 4.0
CHAIR_CLEARANCE = 3.0
MAJOR_KINDS = frozenset({
    "bed", "wardrobe", "sofa", "dining_table", "toilet", "shower",
    "stove", "refrigerator", "vehicle", "counter", "media_wall",
})
FIXTURE_KINDS = frozenset({
    "toilet", "lavatory", "shower", "stove", "refrigerator", "counter",
})
SKIP_TYPES = CIRCULATION_TYPES | OUTDOOR_TYPES | frozenset({"hallway", "foyer"})


@dataclass
class UsabilityIssue:
    category: str
    room: str
    type: str
    severity: str
    geometry: dict | None = None
    message: str = ""

    def as_dict(self) -> dict:
        return {
            "category": self.category,
            "room": self.room,
            "type": self.type,
            "severity": self.severity,
            "geometry": self.geometry,
            "message": self.message,
        }


@dataclass
class UsabilityReport:
    furniture_clearance_score: int = 100
    door_clearance_score: int = 100
    circulation_clearance_score: int = 100
    fixture_clearance_score: int = 100
    room_usability_score: int = 100
    issues: list[UsabilityIssue] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "furniture_clearance_score": self.furniture_clearance_score,
            "door_clearance_score": self.door_clearance_score,
            "circulation_clearance_score": self.circulation_clearance_score,
            "fixture_clearance_score": self.fixture_clearance_score,
            "room_usability_score": self.room_usability_score,
            "issues": [i.as_dict() for i in self.issues],
            "note": "Internal usability heuristics. Not professional architectural approval.",
        }


def empty_usability() -> UsabilityReport:
    return UsabilityReport()


def _rect(item: FurnitureFootprint) -> Rect:
    return Rect(x=item.x, y=item.y, width=item.width, depth=item.depth)


def _fits(room: PlacedRoom, x: float, y: float, w: float, d: float) -> bool:
    from .footprint import contains_rect
    return contains_rect(room, x, y, w, d)


def _wall_candidates(room: PlacedRoom, w: float, d: float) -> list[tuple[float, float, float, float]]:
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
    seen: set[tuple[float, float, float, float]] = set()
    out = []
    for o in opts:
        if _fits(room, *o) and o not in seen:
            seen.add(o)
            out.append(o)
    return out


def _center(room: PlacedRoom, w: float, d: float) -> tuple[float, float, float, float] | None:
    from .footprint import centroid_of
    cx, cy = centroid_of(room)
    x = cx - w / 2.0
    y = cy - d / 2.0
    if _fits(room, x, y, w, d):
        return (x, y, w, d)
    x = room.x + max(0.0, (room.width - w) / 2.0)
    y = room.y + max(0.0, (room.depth - d) / 2.0)
    if _fits(room, x, y, w, d):
        return (x, y, w, d)
    return None


def _issue(
    category: str,
    room: PlacedRoom,
    typ: str,
    severity: str,
    message: str,
    geom: Rect | None = None,
) -> UsabilityIssue:
    geometry = None
    if geom:
        geometry = {"x": geom.x, "y": geom.y, "width": geom.width, "depth": geom.depth}
    return UsabilityIssue(category, room.id, typ, severity, geometry, message)


def _check_hard(
    room: PlacedRoom,
    doors: list[Door],
    items: list[FurnitureFootprint],
) -> list[UsabilityIssue]:
    issues: list[UsabilityIssue] = []
    rects = [(i, _rect(i)) for i in items]
    for i, (a, ra) in enumerate(rects):
        for b, rb in rects[i + 1:]:
            if ra.intersects(rb) and (a.kind in FIXTURE_KINDS and b.kind in FIXTURE_KINDS):
                issues.append(_issue(
                    "fixture", room, "fixture_overlap", "hard",
                    f"{a.kind} overlaps {b.kind} in {room.name}.", ra,
                ))
            elif ra.intersects(rb) and a.kind in MAJOR_KINDS and b.kind in MAJOR_KINDS:
                issues.append(_issue(
                    "furniture", room, "furniture_overlap", "hard",
                    f"{a.kind} overlaps {b.kind} in {room.name}.", ra,
                ))

    for door in doors:
        swing = door_swing_rect(door, room)
        for item, r in rects:
            if not r.intersects(swing):
                continue
            if item.kind == "bed":
                issues.append(_issue(
                    "door", room, "bed_blocks_door", "hard",
                    f"Bed blocks door entry in {room.name}.", r,
                ))
            elif item.kind == "toilet":
                issues.append(_issue(
                    "fixture", room, "door_fixture_collision", "hard",
                    f"Door swing collides with toilet in {room.name}.", r,
                ))
            elif item.kind in MAJOR_KINDS:
                issues.append(_issue(
                    "door", room, "swing_overlap", "hard",
                    f"Door swing overlaps {item.kind} in {room.name}.", r,
                ))

    for item in items:
        if item.kind != "dining_table":
            continue
        if room.width < item.width + 2 * CHAIR_CLEARANCE or room.depth < item.depth + 2 * CHAIR_CLEARANCE:
            issues.append(_issue(
                "circulation", room, "chair_clearance", "hard",
                f"Dining table lacks chair clearance in {room.name}.",
                _rect(item),
            ))

    if room.type == "kitchen":
        depths = [i.depth if i.width >= i.depth else i.width for i in items if i.kind in ("counter", "stove", "refrigerator")]
        used = max(depths, default=0.0)
        if used:
            aisle = min(room.width, room.depth) - used
            if aisle < KITCHEN_AISLE_MIN:
                issues.append(_issue(
                    "circulation", room, "aisle_narrow", "hard",
                    f"Kitchen aisle {aisle:.1f} ft is below {KITCHEN_AISLE_MIN} ft in {room.name}.",
                ))

    if room.type == "living_room":
        for door in doors:
            swing = door_swing_rect(door, room)
            for item, r in rects:
                if item.kind in ("sofa", "media_wall") and r.intersects(swing):
                    issues.append(_issue(
                        "circulation", room, "blocked_entry", "hard",
                        f"Living furniture blocks entry in {room.name}.", r,
                    ))

    return issues


def _orientations(tmpl: FurnitureTemplate) -> list[tuple[float, float]]:
    out = [(tmpl.width, tmpl.depth)]
    if "hw" in tmpl.orientation_options and tmpl.width != tmpl.depth:
        out.append((tmpl.depth, tmpl.width))
    return out


def _make(room_id: str, kind: str, x: float, y: float, w: float, d: float, n: int) -> FurnitureFootprint:
    return FurnitureFootprint(id=f"u{n}", room_id=room_id, kind=kind, x=x, y=y, width=w, depth=d)


def _place_candidates(
    room: PlacedRoom,
    doors: list[Door],
) -> tuple[list[FurnitureFootprint], list[UsabilityIssue]]:
    tmpls = templates_for(room.type)
    if not tmpls:
        return [], []
    n = 0
    items: list[FurnitureFootprint] = []

    def try_kind(kind: str, placement: str) -> FurnitureFootprint | None:
        nonlocal n
        matches = [t for t in tmpls if t.kind == kind]
        if not matches:
            return None
        tmpl = matches[0]
        for w, d in _orientations(tmpl):
            spots = [_center(room, w, d)] if placement == "center" else _wall_candidates(room, w, d)
            for spot in spots:
                if not spot:
                    continue
                x, y, ww, dd = spot
                cand = _make(room.id, kind, x, y, ww, dd, n)
                if not _check_hard(room, doors, items + [cand]):
                    n += 1
                    return cand
        return None

    if room.type in ("bedroom", "master_bedroom"):
        bed = try_kind("bed", "wall")
        if not bed:
            return [], [_issue(
                "furniture", room, "bed_blocks_door", "hard",
                f"No bed orientation keeps the entry clear in {room.name}.",
            )]
        items.append(bed)
        ward = try_kind("wardrobe", "wall")
        if ward:
            items.append(ward)
        return items, []

    if room.type == "living_room":
        sofa = try_kind("sofa", "wall")
        if not sofa:
            return [], [_issue(
                "circulation", room, "blocked_entry", "hard",
                f"No sofa placement keeps the entry clear in {room.name}.",
            )]
        items.append(sofa)
        table = try_kind("coffee_table", "center")
        if table:
            items.append(table)
        return items, []

    if room.type == "dining_room":
        table = try_kind("dining_table", "center")
        if not table:
            return [], [_issue(
                "circulation", room, "chair_clearance", "hard",
                f"Dining table cannot fit with chair clearance in {room.name}.",
            )]
        items.append(table)
        return items, []

    if room.type == "kitchen":
        counter = try_kind("counter", "wall")
        if not counter:
            return [], [_issue(
                "circulation", room, "aisle_narrow", "hard",
                f"Kitchen cannot keep a {KITCHEN_AISLE_MIN} ft aisle in {room.name}.",
            )]
        items.append(counter)
        fridge = try_kind("refrigerator", "wall")
        if fridge:
            items.append(fridge)
        stove = try_kind("stove", "wall")
        if stove:
            items.append(stove)
        return items, []

    if room.type in ("bathroom", "ensuite_bathroom", "half_bath"):
        toilet = try_kind("toilet", "wall")
        if not toilet:
            return [], [_issue(
                "fixture", room, "door_fixture_collision", "hard",
                f"Toilet cannot clear the door swing in {room.name}.",
            )]
        items.append(toilet)
        lav = try_kind("lavatory", "wall")
        if lav:
            items.append(lav)
        if room.type != "half_bath":
            shower = try_kind("shower", "wall")
            if shower:
                items.append(shower)
        return items, []

    if room.type in ("walk_in_closet", "closet", "mudroom"):
        storage = try_kind("storage", "wall")
        if storage:
            items.append(storage)
        return items, []

    if room.type == "garage":
        vehicle = try_kind("vehicle", "center")
        if not vehicle:
            return [], [_issue(
                "circulation", room, "blocked_entry", "hard",
                f"Garage cannot fit a vehicle footprint plus pedestrian path in {room.name}.",
            )]
        items.append(vehicle)
        return items, []

    return items, []


def _score(issues: list[UsabilityIssue]) -> UsabilityReport:
    scores = {
        "furniture": 100,
        "door": 100,
        "circulation": 100,
        "fixture": 100,
    }
    for iss in issues:
        if iss.category not in scores:
            continue
        pen = 35 if iss.severity == "hard" else 10
        scores[iss.category] = max(0, scores[iss.category] - pen)
    overall = int(sum(scores.values()) / 4)
    return UsabilityReport(
        furniture_clearance_score=scores["furniture"],
        door_clearance_score=scores["door"],
        circulation_clearance_score=scores["circulation"],
        fixture_clearance_score=scores["fixture"],
        room_usability_score=overall,
        issues=issues,
    )


def analyze_usability(layout: Layout) -> UsabilityReport:
    furn: dict[str, list[FurnitureFootprint]] = {}
    for f in layout.furniture:
        furn.setdefault(f.room_id, []).append(f)
    doors_of: dict[str, list[Door]] = {}
    for d in layout.doors:
        doors_of.setdefault(d.room_a, []).append(d)
        doors_of.setdefault(d.room_b, []).append(d)

    issues: list[UsabilityIssue] = []
    for room in layout.rooms:
        if room.type in SKIP_TYPES:
            continue
        doors = doors_of.get(room.id, [])
        existing = furn.get(room.id, [])
        if existing:
            issues.extend(_check_hard(room, doors, existing))
        else:
            _items, cand_issues = _place_candidates(room, doors)
            issues.extend(cand_issues)
    return _score(issues)
