"""Architectural planning engine tests. Not professional architectural approval."""

from __future__ import annotations

from solver.architectural_program import from_room_program
from solver.architectural_validator import analyze_planning
from solver.building_mass import plan_building_mass
from solver.doors import _shared_segment
from solver.models import Envelope, Layout, PlacedRoom
from solver.planning_profile import PHILIPPINE_RESIDENTIAL_DEFAULTS, RoomPlanningProfile
from solver.quality import QUALITY_WEIGHTS, _weighted_overall
from solver.room_program import envelope_from_constraints, from_constraints
from solver.room_rules import BATH_TYPES, BEDROOM_TYPES
from solver.site_plan import garage_touches_vehicle_frontage, plan_access
from solver.solver import solve
from solver.spatial_planner import COMPETITION_STRATEGIES, generate_strategy_candidates, plan
from solver.strategy_competition import StrategyEvaluation, select_evaluation
from solver.topology import build_topology, hard_unconditional_pairs


LIVE = {
    "lotShape": "rectangle",
    "lotWidth": 20,
    "lotDepth": 30,
    "bedrooms": 3,
    "bathrooms": 2,
    "openPlan": False,
    "primarySuite": True,
    "homeOffice": False,
    "formalDining": False,
    "garage": "2car",
    "laundry": "room",
    "outdoor": "patio",
    "sqft": 1800,
    "stories": 1,
    "style": "modern",
    "ceilingHeight": "standard",
}


def _live():
    env = envelope_from_constraints(LIVE)
    program = from_constraints(LIVE, env)
    return env, program


def test_garage_does_not_auto_create_mudroom():
    _, program = _live()
    types = [r.type for r in program.rooms]
    assert "garage" in types
    assert "mudroom" not in types
    assert not PHILIPPINE_RESIDENTIAL_DEFAULTS["auto_generate_mudroom"]


def test_laundry_remains_when_requested():
    _, program = _live()
    assert any(r.type == "laundry_room" for r in program.rooms)
    none = dict(LIVE, laundry="none", garage="none")
    env = envelope_from_constraints(none)
    program = from_constraints(none, env)
    assert not any(r.type == "laundry_room" for r in program.rooms)
    assert not any(r.type == "garage" for r in program.rooms)


def test_garage_requires_exterior_vehicle_access():
    env, program = _live()
    spatial = plan(program)
    mass = plan_building_mass(program, env, spatial)
    result = solve(
        program, env, time_limit_s=15,
        spatial_plan=spatial, building_mass=mass, use_clusters=True, flexible=False,
    )
    assert result.status == "valid", result.reason
    garage = next(r for r in result.layout.rooms if r.type == "garage")
    assert garage_touches_vehicle_frontage(garage, env)
    access = plan_access(program, env)
    report = analyze_planning(result.layout, program, spatial, access)
    assert report.vehicle_access_valid
    assert not any(i.code == "garage_without_vehicle_access" for i in report.errors)


def test_garage_is_not_an_isolated_central_room():
    env, program = _live()
    result = solve(program, env, time_limit_s=15, flexible=False)
    assert result.status == "valid", result.reason
    garage = next(r for r in result.layout.rooms if r.type == "garage")
    cx = garage.x + garage.width / 2
    cy = garage.y + garage.depth / 2
    interior = (
        0.3 * env.width < cx < 0.7 * env.width
        and 0.3 * env.depth < cy < 0.7 * env.depth
        and garage.y > 0 and garage.x > 0 and garage.x2 < env.width
    )
    assert not interior


def test_entry_has_arrival_relationship():
    env, program = _live()
    result = solve(program, env, time_limit_s=15, flexible=False)
    assert result.status == "valid", result.reason
    foyer = next(r for r in result.layout.rooms if r.type == "foyer")
    assert foyer.y == 0
    hall = next(r for r in result.layout.rooms if r.type == "hallway")
    assert _shared_segment(foyer, hall) is not None


def test_public_private_service_zones():
    _, program = _live()
    spatial = plan(program)
    types = {r.id: r.type for r in program.rooms}
    public = {types[i] for i in spatial.planning_zones.get("public", [])}
    private = {types[i] for i in spatial.planning_zones.get("private", [])}
    service = {types[i] for i in spatial.planning_zones.get("service", [])}
    arrival = {types[i] for i in spatial.planning_zones.get("arrival", [])}
    assert {"living_room", "kitchen"} <= public
    assert "bedroom" in private and "master_bedroom" in private
    assert "garage" in service or "garage" in arrival
    assert "foyer" in arrival
    assert "laundry_room" in service
    assert spatial.blocks
    assert {b.id for b in spatial.blocks} >= {"arrival", "public", "private", "service"}


def test_bedroom_does_not_require_garage_traversal():
    env, program = _live()
    result = solve(program, env, time_limit_s=15, flexible=False)
    assert result.status == "valid", result.reason
    report = analyze_planning(result.layout, program)
    garage_bed = [
        i for i in report.issues
        if i.code == "bedroom_access_through_private_room" and "garage" in i.message.lower()
    ]
    assert not garage_bed


def test_patio_and_public_adjacencies():
    env, program = _live()
    result = solve(program, env, time_limit_s=15, flexible=False)
    assert result.status == "valid", result.reason
    rooms = {r.type: r for r in result.layout.rooms if r.type in (
        "living_room", "dining_room", "kitchen", "patio",
        "master_bedroom", "ensuite_bathroom", "walk_in_closet",
    )}
    assert _shared_segment(rooms["kitchen"], rooms["dining_room"]) is not None
    patio = rooms["patio"]
    public = [rooms["living_room"], rooms["dining_room"], rooms["kitchen"]]
    assert any(_shared_segment(patio, r) is not None for r in public)
    assert _shared_segment(rooms["master_bedroom"], rooms["ensuite_bathroom"]) is not None
    assert _shared_segment(rooms["master_bedroom"], rooms["walk_in_closet"]) is not None


def test_room_counts_and_lot_preserved():
    env, program = _live()
    result = solve(program, env, time_limit_s=15, flexible=False)
    assert result.status == "valid", result.reason
    rooms = result.layout.rooms
    assert len([r for r in rooms if r.type in BEDROOM_TYPES]) == 3
    assert len([r for r in rooms if r.type in BATH_TYPES]) == 2
    assert any(r.type == "garage" for r in rooms)
    assert any(r.type == "patio" for r in rooms)
    assert any(r.type == "laundry_room" for r in rooms)
    assert not any(r.type == "mudroom" for r in rooms)
    assert result.layout.envelope.width == env.width
    assert result.layout.envelope.depth == env.depth
    assert len(rooms) == len(program.rooms)


def test_strategies_still_compete_with_blocks():
    env, program = _live()
    cands = generate_strategy_candidates(program)
    assert [c.strategy.name for c in cands][:len(COMPETITION_STRATEGIES)] == list(COMPETITION_STRATEGIES)
    for spatial in cands:
        assert spatial.blocks
        assert spatial.access is not None
        assert {b.id for b in spatial.blocks} >= {"arrival", "public", "private", "service"}
    spatial = plan(program)
    mass = plan_building_mass(program, env, spatial)
    result = solve(
        program, env, time_limit_s=15,
        spatial_plan=spatial, building_mass=mass, use_clusters=True, flexible=False,
    )
    assert result.status == "valid", result.reason
    q = result.quality_score
    assert q and q.get("planning")
    assert "vehicle_access" in q["categories"]
    assert "arrival" in q["categories"]
    assert q.get("zoning_score") is not None
    assert not PHILIPPINE_RESIDENTIAL_DEFAULTS["irc_compliant"]


def test_rectangular_fallback_still_works():
    env, program = _live()
    result = solve(program, env, time_limit_s=15, flexible=False)
    assert result.status == "valid", result.reason
    assert all(len(r.parts()) >= 1 for r in result.layout.rooms)


def test_planning_profile_garage_semantics():
    profile = RoomPlanningProfile.for_type("garage")
    assert profile.requires_vehicle_access
    assert "front" in profile.allowed_frontage
    assert "side" in profile.allowed_frontage
    assert "arrival" in profile.planning_zones
    foyer = RoomPlanningProfile.for_type("foyer")
    assert foyer.preferred_frontage == "front"


def test_avoid_relations_exist_without_hard_garage_bedroom():
    _, program = _live()
    spatial = plan(program)
    kinds = {r.kind for r in spatial.relations}
    assert "avoid" in kinds
    types = {r.id: r.type for r in program.rooms}
    hard = hard_unconditional_pairs(build_topology(program))
    typed = {tuple(sorted((types[a], types[b]))) for a, b in hard}
    assert ("bedroom", "garage") not in typed
    assert ("garage", "master_bedroom") not in typed


def test_central_garage_synthetic_is_flagged():
    env = Envelope(width=40, depth=40)
    garage = PlacedRoom("g", "garage", "Garage", 14, 14, 12, 12, "service")
    foyer = PlacedRoom("f", "foyer", "Foyer", 0, 0, 8, 8, "circulation")
    hall = PlacedRoom("h", "hallway", "Hall", 8, 0, 4, 20, "circulation")
    living = PlacedRoom("l", "living_room", "Living", 12, 0, 14, 12, "public")
    layout = Layout(rooms=[garage, foyer, hall, living], envelope=env)
    _, program = _live()
    report = analyze_planning(layout, program)
    assert any(i.code == "garage_inside_central_zone" for i in report.issues)
    assert any(i.code == "garage_without_vehicle_access" for i in report.issues)
    assert any(i.severity == "error" for i in report.issues)
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert warnings
    # Warnings do not, by themselves, define validity; missing vehicle access is the error.
    assert report.errors
    assert not report.valid


def test_three_car_garage_does_not_add_mudroom():
    c = dict(LIVE, garage="3car", sqft=2200)
    env = envelope_from_constraints(c)
    program = from_constraints(c, env)
    types = [r.type for r in program.rooms]
    assert types.count("garage") == 1
    assert "mudroom" not in types


def test_living_dining_preferred_and_kitchen_dining_required():
    _, program = _live()
    spatial = plan(program)
    types = {r.id: r.type for r in program.rooms}
    living = next(r.id for r in program.rooms if r.type == "living_room")
    dining = next(r.id for r in program.rooms if r.type == "dining_room")
    kitchen = next(r.id for r in program.rooms if r.type == "kitchen")
    pairs = {(types[r.room_a], types[r.room_b], r.kind, r.strength) for r in spatial.relations}
    rev = {(types[r.room_b], types[r.room_a], r.kind, r.strength) for r in spatial.relations}
    assert ("kitchen", "dining_room", "connected", "required") in pairs | rev
    assert ("living_room", "dining_room", "near", "preferred") in pairs | rev
    hard = hard_unconditional_pairs(build_topology(program))
    typed = {tuple(sorted((types[a], types[b]))) for a, b in hard}
    assert ("dining_room", "living_room") not in typed
    assert ("dining_room", "kitchen") in typed


def test_access_beats_residual_in_selection_and_weights():
    organized = StrategyEvaluation(
        strategy="patio_oriented", valid=True, quality_score=70,
        residual_area=220, access_score=100, circulation_score=80,
        adjacency_score=80, zoning_score=80, room_usability_score=70,
    )
    packed = StrategyEvaluation(
        strategy="cluster", valid=True, quality_score=70,
        residual_area=20, access_score=20, circulation_score=80,
        adjacency_score=80, zoning_score=80, room_usability_score=70,
    )
    winner = select_evaluation([packed, organized])
    assert winner is not None
    assert winner.strategy == "patio_oriented"
    assert QUALITY_WEIGHTS["vehicle_access"] > QUALITY_WEIGHTS["dead_space"]
    assert QUALITY_WEIGHTS["arrival"] > QUALITY_WEIGHTS["mass_occupancy"]
    organized_cats = {
        "feasibility": 100, "vehicle_access": 100, "arrival": 100,
        "circulation": 80, "adjacency": 80, "zoning": 80,
        "public_private": 80, "room_usability": 70,
        "dead_space": 50, "mass_occupancy": 60, "shape": 70,
    }
    packed_cats = dict(organized_cats)
    packed_cats["vehicle_access"] = 20
    packed_cats["arrival"] = 40
    packed_cats["dead_space"] = 100
    packed_cats["mass_occupancy"] = 100
    assert _weighted_overall(organized_cats) > _weighted_overall(packed_cats)


def test_planning_program_spaces_and_access_zones():
    env, program = _live()
    arch = from_room_program(program)
    garage = arch.first("garage")
    assert garage is not None
    assert garage.requires_vehicle_access
    assert "arrival" in garage.planning_zones
    living = arch.first("living_room")
    assert living is not None
    assert living.planning_zones == ["public"]
    access = plan_access(program, env)
    assert access.site.street_edge == "y0"
    assert access.driveway.kind == "driveway"
    assert access.front_walk.kind == "front_walk"
    assert set(access.garage_allowed_edges) >= {"front", "left", "right"}
    a = generate_strategy_candidates(program)
    b = generate_strategy_candidates(program)
    assert [s.strategy.name for s in a] == [s.strategy.name for s in b]
    assert [tuple((bl.id, bl.cx_frac, bl.cy_frac) for bl in s.blocks) for s in a] == [
        tuple((bl.id, bl.cx_frac, bl.cy_frac) for bl in s.blocks) for s in b
    ]


def test_circulation_reaches_required_rooms_without_garage_only():
    env, program = _live()
    result = solve(program, env, time_limit_s=15, flexible=False)
    assert result.status == "valid", result.reason
    report = analyze_planning(result.layout, program)
    assert not any(i.code == "isolated_required_room" for i in report.errors)
    env2 = envelope_from_constraints(LIVE)
    assert env.width == env2.width and env.depth == env2.depth
    assert result.layout.envelope.lot_width_ft == env.lot_width_ft
    assert result.layout.envelope.lot_depth_ft == env.lot_depth_ft
