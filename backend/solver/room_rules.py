"""
Prototype room minimums for the OR-Tools layout solver.

These are engineering placeholders for packing feasibility.
They are NOT Philippine National Building Code values and are NOT
verified IRC legal minimums. Replace this table with a verified
ruleset in a later phase.
"""

from __future__ import annotations

import math

_RECT = {"allowed_shapes": ["rectangle"], "preferred_shapes": ["rectangle"], "max_components": 1}
_RECT_L = {"allowed_shapes": ["rectangle", "l_shape"], "preferred_shapes": ["rectangle"], "max_components": 2}

# Aspect heuristics (not code). Halls are allowed to be long.
DEFAULT_MAX_ASPECT = 2.8
BEDROOM_MAX_ASPECT = 2.2
CIRCULATION_MAX_ASPECT = 8.0
GARAGE_MAX_ASPECT = 3.5

# Soft growth beyond preferred. Rooms may use the site; they may not fill the lot.
PREFERRED_GROWTH = 1.6
PREFERRED_GROWTH_FT = 12
HALL_LENGTH_GROWTH_FT = 24
HALL_MAX_SHORT_FT = 6
HALL_MAX_AREA_FT2 = 240
# Heuristic, not code. Pathological corridors (~800 sf) fail validity.
CIRCULATION_RATIO_MAX = 0.22

# min_w, min_d, preferred_w, preferred_d (feet). Shape fields are packing hints, not a second size table.
ROOM_RULES: dict[str, dict] = {
    "living_room": {"min_width": 10, "min_depth": 12, "preferred_width": 14, "preferred_depth": 16, "max_aspect_ratio": 2.6, **_RECT_L},
    "kitchen": {"min_width": 8, "min_depth": 10, "preferred_width": 12, "preferred_depth": 12, "max_aspect_ratio": 2.4, **_RECT_L},
    "dining_room": {"min_width": 8, "min_depth": 10, "preferred_width": 12, "preferred_depth": 12, "max_aspect_ratio": 2.4, **_RECT_L},
    "family_room": {"min_width": 10, "min_depth": 12, "preferred_width": 14, "preferred_depth": 14, "max_aspect_ratio": 2.6, **_RECT_L},
    "master_bedroom": {"min_width": 10, "min_depth": 12, "preferred_width": 14, "preferred_depth": 14, "max_aspect_ratio": BEDROOM_MAX_ASPECT, **_RECT_L},
    "bedroom": {"min_width": 9, "min_depth": 10, "preferred_width": 11, "preferred_depth": 12, "max_aspect_ratio": BEDROOM_MAX_ASPECT, **_RECT_L},
    "ensuite_bathroom": {"min_width": 6, "min_depth": 8, "preferred_width": 8, "preferred_depth": 10, "max_aspect_ratio": 2.4, **_RECT},
    "bathroom": {"min_width": 5, "min_depth": 7, "preferred_width": 6, "preferred_depth": 8, "max_aspect_ratio": 2.6, **_RECT},
    "half_bath": {"min_width": 3, "min_depth": 6, "preferred_width": 4, "preferred_depth": 6, "max_aspect_ratio": 2.5, **_RECT},
    "hallway": {"min_width": 4, "min_depth": 8, "preferred_width": 4, "preferred_depth": 16, "max_aspect_ratio": CIRCULATION_MAX_ASPECT, **_RECT},
    "foyer": {"min_width": 6, "min_depth": 6, "preferred_width": 8, "preferred_depth": 8, "max_aspect_ratio": 2.5, **_RECT},
    "home_office": {"min_width": 8, "min_depth": 9, "preferred_width": 10, "preferred_depth": 12, "max_aspect_ratio": 2.4, **_RECT_L},
    "laundry_room": {"min_width": 5, "min_depth": 6, "preferred_width": 7, "preferred_depth": 8, "max_aspect_ratio": 2.6, **_RECT},
    "garage": {"min_width": 12, "min_depth": 18, "preferred_width": 20, "preferred_depth": 20, "max_aspect_ratio": GARAGE_MAX_ASPECT, **_RECT},
    "walk_in_closet": {"min_width": 5, "min_depth": 5, "preferred_width": 6, "preferred_depth": 7, "max_aspect_ratio": 2.4, **_RECT},
    "closet": {"min_width": 3, "min_depth": 3, "preferred_width": 4, "preferred_depth": 5, "max_aspect_ratio": 2.5, **_RECT},
    "pantry": {"min_width": 4, "min_depth": 4, "preferred_width": 5, "preferred_depth": 6, "max_aspect_ratio": 2.5, **_RECT},
    "mudroom": {"min_width": 5, "min_depth": 6, "preferred_width": 6, "preferred_depth": 8, "max_aspect_ratio": 2.6, **_RECT},
    "utility_room": {"min_width": 5, "min_depth": 6, "preferred_width": 6, "preferred_depth": 8, "max_aspect_ratio": 2.6, **_RECT},
    "patio": {"min_width": 8, "min_depth": 8, "preferred_width": 14, "preferred_depth": 10, "max_aspect_ratio": 3.0, **_RECT},
    "deck": {"min_width": 8, "min_depth": 8, "preferred_width": 12, "preferred_depth": 10, "max_aspect_ratio": 3.0, **_RECT},
}

ZONE_BY_TYPE: dict[str, str] = {
    "living_room": "public",
    "dining_room": "public",
    "kitchen": "public",
    "family_room": "public",
    "home_office": "public",
    "master_bedroom": "private",
    "bedroom": "private",
    "ensuite_bathroom": "private",
    "bathroom": "private",
    "half_bath": "private",
    "walk_in_closet": "private",
    "closet": "private",
    "garage": "service",
    "laundry_room": "service",
    "mudroom": "service",
    "pantry": "service",
    "utility_room": "service",
    "hallway": "circulation",
    "foyer": "circulation",
    "patio": "outdoor",
    "deck": "outdoor",
}

BEDROOM_TYPES = frozenset({"bedroom", "master_bedroom"})
BATH_TYPES = frozenset({"bathroom", "ensuite_bathroom", "half_bath"})
OCCUPIED_TYPES = frozenset({
    "living_room", "dining_room", "kitchen", "family_room", "home_office",
    "master_bedroom", "bedroom", "ensuite_bathroom", "bathroom", "half_bath",
    "laundry_room", "mudroom",
})
CIRCULATION_TYPES = frozenset({"hallway", "foyer"})
OUTDOOR_TYPES = frozenset({"patio", "deck"})
WET_TYPES = frozenset({
    "kitchen", "bathroom", "ensuite_bathroom", "half_bath", "laundry_room",
})
DAYLIGHT_TYPES = frozenset({
    "living_room", "dining_room", "family_room", "kitchen",
    "master_bedroom", "bedroom", "home_office",
})

DOOR_CLEARANCE_FT = 3
DOOR_WIDTH_FT = 3
MIN_SHARED_WALL_FT = 3


def rule_for(room_type: str) -> dict:
    base = {
        "min_width": 6, "min_depth": 6, "preferred_width": 8, "preferred_depth": 8,
        "allowed_shapes": ["rectangle"], "preferred_shapes": ["rectangle"], "max_components": 1,
        "max_aspect_ratio": DEFAULT_MAX_ASPECT,
    }
    found = ROOM_RULES.get(room_type)
    if not found:
        return dict(base)
    merged = dict(base)
    merged.update(found)
    pw = int(merged["preferred_width"])
    pd = int(merged["preferred_depth"])
    merged.setdefault("preferred_area", pw * pd)
    merged.setdefault("max_area", int(merged["preferred_area"] * 1.8))
    merged.setdefault("max_aspect_ratio", aspect_limit(room_type, merged))
    return merged


def aspect_limit(room_type: str, rule: dict | None = None) -> float:
    if rule and rule.get("max_aspect_ratio"):
        return float(rule["max_aspect_ratio"])
    if room_type in CIRCULATION_TYPES:
        return CIRCULATION_MAX_ASPECT
    if room_type in BEDROOM_TYPES:
        return BEDROOM_MAX_ASPECT
    if room_type == "garage" or room_type in OUTDOOR_TYPES:
        return GARAGE_MAX_ASPECT
    return DEFAULT_MAX_ASPECT


def aspect_ratio(width: float, depth: float) -> float:
    lo, hi = min(width, depth), max(width, depth)
    return hi / lo if lo > 0 else 9.0


def size_caps(spec, envelope_width: int, envelope_depth: int) -> tuple[int, int]:
    """Hard CP-SAT upper bounds. Site-aware and still bounded. Does not fill the lot."""
    pw = max(int(spec.preferred_width), int(spec.min_width), 1)
    pd = max(int(spec.preferred_depth), int(spec.min_depth), 1)
    rtype = getattr(spec, "type", "")
    if rtype in CIRCULATION_TYPES:
        if rtype == "hallway":
            # Length may grow; short-side/area caps are CP-SAT constraints, not both-axes growth.
            max_long = max(pw, pd) + HALL_LENGTH_GROWTH_FT
            max_w = min(envelope_width, max_long)
            max_h = min(envelope_depth, max_long)
            return max(1, max_w), max(1, max_h)
        max_w = min(envelope_width, pw + PREFERRED_GROWTH_FT)
        max_h = min(envelope_depth, pd + PREFERRED_GROWTH_FT)
        return max(1, max_w), max(1, max_h)
    grow = max(PREFERRED_GROWTH_FT, int(max(pw, pd) * (PREFERRED_GROWTH - 1.0)))
    max_w = min(envelope_width, pw + grow)
    max_h = min(envelope_depth, pd + grow)
    max_area = int(getattr(spec, "max_area", 0) or 0)
    if max_area > 0:
        side = max(pw, pd, int(math.sqrt(max_area) * 1.35) + 1)
        max_w = min(max_w, side)
        max_h = min(max_h, side)
    return max(1, max_w), max(1, max_h)
