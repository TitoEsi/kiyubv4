"""Architectural program, zoning, and relationship-graph tests."""

from __future__ import annotations

from solver.architectural_program import from_room_program, validate_program
from solver.planning_graph import build_planning_graph
from solver.room_graph import build_room_graph
from solver.room_program import envelope_from_constraints, from_constraints
from solver.room_rules import aspect_limit, rule_for
from solver.spatial_planner import plan
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


def test_room_requirements_include_aspect_and_area_bands():
    env = envelope_from_constraints(LIVE)
    program = from_constraints(LIVE, env)
    bed = next(r for r in program.rooms if r.type == "bedroom")
    assert bed.max_aspect_ratio <= 2.2
    assert bed.preferred_area >= bed.min_width * bed.min_depth
    assert bed.max_area >= bed.preferred_area
    rule = rule_for("bedroom")
    assert rule["max_aspect_ratio"] == aspect_limit("bedroom")
    living = next(r for r in program.rooms if r.type == "living_room")
    assert living.preferred_width >= living.min_width


def test_public_private_service_zones_on_program():
    env = envelope_from_constraints(LIVE)
    program = from_constraints(LIVE, env)
    arch = from_room_program(program)
    assert arch.first("living_room").zone == "public"
    assert arch.first("bedroom").zone == "private"
    assert arch.first("laundry_room").zone == "service"
    kitchen = arch.first("kitchen")
    assert kitchen is not None
    assert "public" in kitchen.planning_zones
    assert "service" in kitchen.planning_zones


def test_kitchen_dining_strong_and_bedroom_entry_discouraged():
    env = envelope_from_constraints(LIVE)
    program = from_constraints(LIVE, env)
    arch = from_room_program(program)
    rels = build_planning_graph(arch)
    types = {s.id: s.room_type for s in arch.spaces}
    pairs = {(types[r.room_a], types[r.room_b], r.kind, r.strength) for r in rels}
    rev = {(types[r.room_b], types[r.room_a], r.kind, r.strength) for r in rels}
    assert ("kitchen", "dining_room", "connected", "required") in pairs | rev
    assert ("living_room", "dining_room", "near", "preferred") in pairs | rev
    assert ("bedroom", "foyer", "avoid", "avoid") in pairs | rev or (
        "master_bedroom", "foyer", "avoid", "avoid"
    ) in pairs | rev
    hard = hard_unconditional_pairs(build_topology(program))
    typed = {tuple(sorted((types[a], types[b]))) for a, b in hard}
    assert ("bedroom", "foyer") not in typed
    assert ("foyer", "master_bedroom") not in typed
    spatial = plan(program)
    assert any(r.kind == "avoid" for r in spatial.relations)


def test_kitchen_dining_required_and_bedroom_garage_forbidden():
    env = envelope_from_constraints(LIVE)
    program = from_constraints(LIVE, env)
    arch = from_room_program(program)
    graph = build_room_graph(arch)
    types = {s.id: s.room_type for s in arch.spaces}
    kinds = {
        (types[e.room_a], types[e.room_b], e.kind, e.hard)
        for e in graph.edges
    }
    rev = {
        (types[e.room_b], types[e.room_a], e.kind, e.hard)
        for e in graph.edges
    }
    assert ("kitchen", "dining_room", "required_adjacency", True) in kinds | rev
    assert ("bedroom", "garage", "forbidden_adjacency", True) in kinds | rev or (
        "master_bedroom", "garage", "forbidden_adjacency", True
    ) in kinds | rev
    topo = build_topology(program)
    topo_kinds = {(e.room_a, e.room_b, e.relation, e.hard) for e in topo}
    topo_rev = {(e.room_b, e.room_a, e.relation, e.hard) for e in topo}
    k = arch.first("kitchen").id
    d = arch.first("dining_room").id
    assert (k, d, "connected", True) in topo_kinds | topo_rev
    g = arch.first("garage").id
    bed = arch.first("bedroom").id or arch.first("master_bedroom").id
    assert (bed, g, "separated", True) in topo_kinds | topo_rev
    rels = build_planning_graph(arch)
    assert rels == build_planning_graph(arch)


def test_validate_program_live_request():
    env = envelope_from_constraints(LIVE)
    program = from_constraints(LIVE, env)
    arch = from_room_program(program)
    report = validate_program(arch, env)
    assert report.ok
    assert not report.errors
    assert arch.as_dict()["bedrooms_requested"] == 3
    assert "kitchen" in arch.as_dict()["types"]
