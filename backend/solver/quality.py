"""Internal layout quality score. Not professional architectural approval."""

from __future__ import annotations

import os

from .architectural_validator import analyze_planning
from .cluster_metrics import analyze_clusters, mass_occupancy, occupancy_score
from .building_mass import BuildingMass
from .circulation import CirculationAnalysis, analyze_circulation
from .models import Envelope, Layout, RoomProgram
from .residual import ResidualReport, analyze_residual
from .room_rules import BEDROOM_TYPES, CIRCULATION_TYPES, CIRCULATION_RATIO_MAX, DAYLIGHT_TYPES, OUTDOOR_TYPES, WET_TYPES, aspect_limit, aspect_ratio
from .spatial_plan import SpatialPlan
from .topology import build_topology
from .usability import analyze_usability, empty_usability
from .validator import validate


def _aspect(w: int, d: int) -> float:
    return aspect_ratio(w, d)


def _clamp(n: int) -> int:
    return max(0, min(100, n))


# Organization before leftover packing. Residual must not dominate.
QUALITY_WEIGHTS: dict[str, int] = {
    "feasibility": 4,
    "vehicle_access": 3,
    "arrival": 3,
    "circulation": 3,
    "topology": 2,
    "adjacency": 3,
    "zoning": 2,
    "cluster": 2,
    "cluster_cohesion": 2,
    "public_private": 2,
    "room_usability": 2,
    "dead_ends": 2,
    "dead_space": 1,
    "mass_occupancy": 1,
    "narrow_residual": 1,
    "shape": 1,
    "room_proportion": 2,
    "daylight_potential": 2,
    "service_efficiency": 2,
    "furniture_clearance": 2,
    "site_utilization": 2,
}


def _weighted_overall(cats: dict[str, int]) -> int:
    num = 0
    den = 0
    for key, w in QUALITY_WEIGHTS.items():
        if key not in cats:
            continue
        num += w * cats[key]
        den += w
    if not den:
        return int(sum(cats.values()) / max(1, len(cats)))
    return int(num / den)


def _residual_scores(residual: ResidualReport, mass: BuildingMass | None = None) -> tuple[int, int]:
    """Hole-structure score. Total leftover area is occupancy, not dead_space."""
    if mass:
        base = max(1, mass.area)
        largest = residual.largest_residual_region
        narrow = residual.narrow_residual_area
        regions = residual.building_residual_region_count
        isolated = residual.isolated_residual_regions
    else:
        base = max(1, residual.envelope_area)
        largest = residual.largest_residual_region
        narrow = residual.narrow_residual_area
        regions = residual.residual_region_count
        isolated = residual.isolated_residual_regions
    largest_frac = largest / base
    dead_space = 100
    dead_space -= min(24, regions * 6)
    dead_space -= int(largest_frac * 100)
    if isolated:
        dead_space -= min(20, isolated * 8)
    narrow_frac = narrow / base
    narrow_q = 100 - int(narrow_frac * 280) - (12 if narrow else 0)
    return _clamp(dead_space), _clamp(narrow_q)


def _circulation_scores(circ: CirculationAnalysis, required_n: int) -> tuple[int, int]:
    if required_n:
        reach = int(100 * len(circ.reachable_required) / required_n)
    else:
        reach = 100
    # Target: circulation is present and not a huge leftover corridor.
    if circ.area <= 0:
        eff = 40
    else:
        # Higher served rooms per circulation sqft is better; clamp to a usable range.
        eff = _clamp(int(circ.efficiency * 800))
        if circ.area < 24:
            eff = min(eff, 70)
    frag_pen = min(30, circ.fragmentation * 10)
    ratio_pen = 0
    if circ.circulation_ratio > 0.12:
        ratio_pen = min(40, int((circ.circulation_ratio - 0.12) * 200))
    if circ.circulation_ratio > CIRCULATION_RATIO_MAX:
        ratio_pen = max(ratio_pen, 50)
    circulation_q = _clamp(int(0.45 * reach + 0.40 * eff + 0.15 * (100 - frag_pen)) - ratio_pen)
    dead_end_q = _clamp(100 - 18 * len(circ.dead_ends))
    return circulation_q, dead_end_q


def _exterior_sides(room, envelope: Envelope | None, mass: BuildingMass | None) -> int:
    n = 0
    if envelope:
        if room.x <= 0:
            n += 1
        if room.y <= 0:
            n += 1
        if room.x2 >= envelope.width:
            n += 1
        if room.y2 >= envelope.depth:
            n += 1
    if mass and n == 0:
        if room.x <= mass.x:
            n += 1
        if room.y <= mass.y:
            n += 1
        if room.x2 >= mass.x + mass.width:
            n += 1
        if room.y2 >= mass.y + mass.depth:
            n += 1
    return n


def _daylight_potential(layout: Layout, program: RoomProgram) -> tuple[int, list[str]]:
    """Exterior-edge heuristic. Not daylight simulation."""
    envelope = layout.envelope or program.envelope
    scores: list[int] = []
    problems: list[str] = []
    for r in layout.rooms:
        if r.type not in DAYLIGHT_TYPES:
            continue
        sides = _exterior_sides(r, envelope, None)
        if sides >= 2:
            scores.append(100)
        elif sides == 1:
            scores.append(80)
        else:
            scores.append(40)
            problems.append(r.id)
    if not scores:
        return 80, problems
    return _clamp(int(sum(scores) / len(scores))), problems


def _service_efficiency(layout: Layout, program: RoomProgram) -> tuple[int, list[str]]:
    wet = [r for r in layout.rooms if r.type in WET_TYPES]
    if len(wet) < 2:
        return 80, []
    env = layout.envelope or program.envelope
    diag = max(1.0, float((env.width ** 2 + env.depth ** 2) ** 0.5)) if env else 80.0
    dists: list[float] = []
    problems: list[str] = []
    for i, a in enumerate(wet):
        for b in wet[i + 1:]:
            ax, ay = a.x + a.width / 2.0, a.y + a.depth / 2.0
            bx, by = b.x + b.width / 2.0, b.y + b.depth / 2.0
            d = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
            dists.append(d)
            if d > 0.45 * diag:
                problems.append(f"{a.id}|{b.id}")
    if not dists:
        return 80, problems
    mean = sum(dists) / len(dists)
    # Closer wet rooms score higher; scattered wet rooms score lower.
    score = 100 - int(100 * min(1.0, mean / (0.55 * diag)))
    return _clamp(score), problems


def _site_utilization(
    layout: Layout,
    program: RoomProgram,
    occupancy_q: int,
    proportion_q: int,
) -> int:
    """Useful programmed space vs envelope. Penalize crush and unused fragments."""
    env = layout.envelope or program.envelope
    if not env or env.area <= 0:
        return occupancy_q
    from .footprint import union_area
    useful = 0
    preferred = 0
    for r in layout.rooms:
        if r.type in OUTDOOR_TYPES:
            continue
        useful += union_area(r)
    for spec in program.rooms:
        if spec.type in OUTDOOR_TYPES:
            continue
        preferred += spec.preferred_area or (spec.preferred_width * spec.preferred_depth)
    size_adeq = 100
    if preferred > 0:
        size_adeq = _clamp(int(100 * min(1.35, useful / preferred)))
        if useful > preferred * 1.35:
            size_adeq = _clamp(int(100 - 40 * ((useful / preferred) - 1.35)))
    # Envelope fill is informational: a good house may occupy ~40-70% of a large lot.
    fill = useful / max(1, env.area)
    fill_q = 100
    if fill < 0.28:
        fill_q = _clamp(int(100 * fill / 0.28))
    elif fill > 0.88:
        fill_q = _clamp(int(100 - 80 * (fill - 0.88) / 0.12))
    return _clamp(int(0.45 * size_adeq + 0.25 * fill_q + 0.20 * occupancy_q + 0.10 * proportion_q))


def score_layout(
    layout: Layout,
    program: RoomProgram,
    spatial: SpatialPlan | None = None,
    building_mass: BuildingMass | None = None,
) -> dict:
    report = validate(layout, program)
    rooms = {r.id: r for r in layout.rooms}

    residual = analyze_residual(layout, building_mass)
    circulation = analyze_circulation(layout, program, spatial)

    feasibility = 100 if report.valid else max(0, 60 - 15 * len(report.errors))

    topology = layout.topology or build_topology(program)
    hard = [e for e in topology if e.hard]
    adj_hits = 0
    adj_need = 0
    from .doors import _shared_segment

    def placed_share(a, b) -> bool:
        ra, rb = rooms.get(a), rooms.get(b)
        if not ra or not rb:
            return False
        return _shared_segment(ra, rb) is not None

    for e in hard:
        if e.choice_group:
            continue
        adj_need += 1
        if placed_share(e.room_a, e.room_b):
            adj_hits += 1
    topology_q = int(100 * adj_hits / adj_need) if adj_need else 80

    dead_space_q, narrow_q = _residual_scores(residual, building_mass)
    required_n = len(circulation.reachable_required) + len(circulation.unreachable_required)
    circulation_q, dead_end_q = _circulation_scores(circulation, required_n)

    shape_pen = 0
    shape_n = 0
    poor_aspect: list[str] = []
    cramped: list[str] = []
    from .footprint import shape_complexity, union_area
    by_spec = {s.id: s for s in program.rooms}
    for r in layout.rooms:
        if r.type in CIRCULATION_TYPES or r.type in OUTDOOR_TYPES or r.type == "garage":
            continue
        shape_n += 1
        ar = _aspect(r.width, r.depth)
        limit = aspect_limit(r.type)
        spec = by_spec.get(r.id)
        if spec and spec.max_aspect_ratio:
            limit = float(spec.max_aspect_ratio)
        if ar > limit:
            shape_pen += min(40, int((ar - limit) * 25))
            poor_aspect.append(r.id)
        pref_area = (spec.preferred_area if spec and spec.preferred_area else 0)
        if spec and not pref_area:
            pref_area = spec.preferred_width * spec.preferred_depth
        area = union_area(r)
        if spec and area < spec.min_width * spec.min_depth * 1.05:
            cramped.append(r.id)
        elif pref_area and area < pref_area * 0.72:
            cramped.append(r.id)
        shape_pen += shape_complexity(r) * 8
    shape_q = max(0, 100 - (shape_pen // max(1, shape_n)))
    proportion_q = shape_q
    if cramped:
        proportion_q = _clamp(proportion_q - 8 * min(4, len(cramped)))

    cluster_q = 70
    cluster_info = analyze_clusters(layout, spatial)
    cohesion_q = _clamp(int(100 * cluster_info["mean_cohesion"])) if spatial else 70
    if spatial:
        hits = 0
        need = 0
        for cl in spatial.clusters:
            ids = [i for i in cl.room_ids if i in rooms]
            if len(ids) < 2:
                continue
            need += 1
            ok = False
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    if placed_share(a, b):
                        ok = True
            if ok:
                hits += 1
        if need:
            cluster_q = int(100 * hits / need)

    occupancy = mass_occupancy(layout, building_mass, residual)
    occupancy_q = occupancy_score(occupancy) if building_mass else 70

    if os.environ.get("KIYUB_USABILITY", "1").strip() != "0":
        usability = analyze_usability(layout)
    else:
        usability = empty_usability()

    adjacency_q = topology_q
    poor_adj: list[str] = []
    if spatial:
        pref_hits = 0
        for a, b, _rel in spatial.preferred_edges:
            if placed_share(a, b):
                pref_hits += 1
            else:
                ra, rb = rooms.get(a), rooms.get(b)
                if ra and rb:
                    poor_adj.append(f"{ra.name}|{rb.name}")
        if spatial.preferred_edges:
            adjacency_q = int(100 * pref_hits / len(spatial.preferred_edges))

    access = spatial.access if spatial else None
    planning = analyze_planning(layout, program, spatial, access)
    vehicle_q = 100 if planning.vehicle_access_valid else 20
    arrival_q = 100 if planning.arrival_valid else 40
    zoning_q = _clamp(int(100 * (
        0.4 * planning.public_cohesion
        + 0.4 * planning.private_cohesion
        + 0.2 * planning.service_cohesion
    )))
    sep_q = _clamp(int(100 * planning.public_private_separation))
    if not planning.outdoor_relationship and program.outdoor_requested:
        adjacency_q = max(0, adjacency_q - 12)
    for iss in planning.issues:
        if iss.code == "garage_separates_public_spaces":
            vehicle_q = min(vehicle_q, 55)
            zoning_q = min(zoning_q, 60)
        if iss.code == "garage_inside_central_zone":
            vehicle_q = min(vehicle_q, 40)

    daylight_q, daylight_problems = _daylight_potential(layout, program)
    service_q, service_problems = _service_efficiency(layout, program)
    site_q = _site_utilization(layout, program, occupancy_q, proportion_q)
    furniture_q = usability.furniture_clearance_score
    privacy_conflicts = [
        i.room for i in planning.issues
        if i.code in ("bedroom_access_through_private_room",) or "privacy" in i.code
    ]

    cats = {
        "feasibility": feasibility,
        "vehicle_access": vehicle_q,
        "arrival": arrival_q,
        "topology": topology_q,
        "circulation": circulation_q,
        "dead_space": dead_space_q,
        "shape": shape_q,
        "room_proportion": proportion_q,
        "cluster": cluster_q,
        "cluster_cohesion": cohesion_q,
        "mass_occupancy": occupancy_q,
        "adjacency": adjacency_q,
        "narrow_residual": narrow_q,
        "dead_ends": dead_end_q,
        "room_usability": usability.room_usability_score,
        "public_private": sep_q,
        "zoning": zoning_q,
        "daylight_potential": daylight_q,
        "service_efficiency": service_q,
        "furniture_clearance": furniture_q,
        "site_utilization": site_q,
    }
    diagnostics = {
        "cramped_rooms": cramped,
        "poor_aspect_ratios": poor_aspect,
        "excessive_corridor_area": max(0, circulation.area - 80) if circulation.area else 0,
        "excessive_corridor_length": max(0, circulation.length - 40) if circulation.length else 0,
        "dead_space_area": residual.building_residual_area,
        "poor_adjacencies": poor_adj[:12],
        "privacy_conflicts": privacy_conflicts,
        "daylight_problems": daylight_problems,
        "furniture_conflicts": [
            i.room for i in usability.issues if i.severity == "hard" and i.category in ("furniture", "door")
        ],
        "service_problems": service_problems,
        "note": "Internal layout diagnostics. Not professional architectural approval.",
    }
    overall = _weighted_overall(cats)
    return {
        "overall": overall,
        "categories": cats,
        "note": "Internal optimization score. Not professional architectural approval or code compliance.",
        "residual": residual.as_dict(),
        "circulation": circulation.as_dict(),
        "building_mass": building_mass.as_dict() if building_mass else None,
        "site_open_space_area": residual.site_open_space_area,
        "building_residual_area": residual.building_residual_area,
        "clusters": cluster_info,
        "mass_occupancy_ratio": round(occupancy, 4),
        "mass_fill": {
            "mass_area": building_mass.area if building_mass else 0,
            "room_cells_in_mass": residual.room_cells_in_mass,
            "circulation_cells_in_mass": residual.circulation_cells_in_mass,
            "exterior_cells_in_mass": residual.exterior_cells_in_mass,
            "building_residual_area": residual.building_residual_area,
            "occupied_room_area_sum": residual.occupied_room_area_sum,
            "mass_occupancy": round(occupancy, 4),
            "note": (
                "1-ft raster inside BuildingMass. Occupancy is ROOM+CIRCULATION "
                "cells / mass.area. occupied_room_area_sum is the global union "
                "diagnostic, not occupancy. Walls are not modeled. Not professional "
                "architectural approval."
            ),
        },
        "furniture_clearance_score": usability.furniture_clearance_score,
        "door_clearance_score": usability.door_clearance_score,
        "circulation_clearance_score": usability.circulation_clearance_score,
        "fixture_clearance_score": usability.fixture_clearance_score,
        "room_usability_score": usability.room_usability_score,
        "usability_issues": [i.as_dict() for i in usability.issues],
        "planning": planning.as_dict(),
        "zoning_score": zoning_q,
        "diagnostics": diagnostics,
        "daylight_potential_score": daylight_q,
        "service_efficiency_score": service_q,
        "site_utilization_score": site_q,
        "room_proportion_score": proportion_q,
        "circulation_area": circulation.area,
        "enclosed_floor_area": circulation.enclosed_floor_area,
        "circulation_ratio": round(circulation.circulation_ratio, 4),
        "objective_breakdown": {
            "circulation_area": circulation.area,
            "enclosed_floor_area": circulation.enclosed_floor_area,
            "circulation_ratio": round(circulation.circulation_ratio, 4),
            "categories": cats,
        },
        "hard_valid": report.valid,
        "hard_failures": [e.as_dict() for e in report.errors],
    }
