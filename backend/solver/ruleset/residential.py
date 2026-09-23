"""Residential planning heuristics. Not NBC or IRC."""
from __future__ import annotations

from ..models import Layout, RoomProgram
from ..room_rules import CIRCULATION_RATIO_MAX, HALL_MAX_AREA_FT2, OUTDOOR_TYPES
from .result import RuleResult


def evaluate(layout: Layout, program: RoomProgram) -> list[RuleResult]:
    from ..footprint import union_area
    results: list[RuleResult] = []
    indoor = [r for r in layout.rooms if r.type not in OUTDOOR_TYPES]
    enclosed = sum(union_area(r) for r in indoor)
    circ = sum(union_area(r) for r in indoor if r.type in ("hallway", "foyer"))
    ratio = circ / enclosed if enclosed else 0.0
    hall_area = sum(union_area(r) for r in layout.rooms if r.type == "hallway")
    if hall_area > HALL_MAX_AREA_FT2 or ratio > CIRCULATION_RATIO_MAX:
        results.append(RuleResult(
            "circulation_efficiency", "FAIL",
            f"Circulation area {circ} sf / enclosed {enclosed} sf (ratio {ratio:.2f}).",
            source="planning heuristic HALL_MAX_AREA_FT2 / CIRCULATION_RATIO_MAX",
            module="residential",
        ))
    elif ratio > 0.15:
        results.append(RuleResult(
            "circulation_efficiency", "WARNING",
            f"Circulation ratio {ratio:.2f} is high for this program.",
            source="planning heuristic",
            module="residential",
        ))
    else:
        results.append(RuleResult(
            "circulation_efficiency", "PASS",
            f"Circulation ratio {ratio:.2f} is within the planning heuristic.",
            source="planning heuristic",
            module="residential",
        ))
    beds = sum(1 for r in layout.rooms if r.type in ("bedroom", "master_bedroom"))
    if beds == program.bedrooms_requested:
        results.append(RuleResult(
            "bedroom_count", "PASS",
            f"{beds} bedrooms match the requested program.",
            source="RoomProgram",
            module="residential",
        ))
    else:
        results.append(RuleResult(
            "bedroom_count", "FAIL",
            f"Requested {program.bedrooms_requested} bedrooms, layout has {beds}.",
            source="RoomProgram",
            module="residential",
        ))
    results.append(RuleResult(
        "daylight_habitable", "UNKNOWN",
        "Habitable-room daylight is a geometric window heuristic, not a verified code check.",
        source="unverified",
        module="residential",
    ))
    return results
