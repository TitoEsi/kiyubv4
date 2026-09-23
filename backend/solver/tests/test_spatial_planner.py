"""Architectural spatial planning layer tests. Does not claim code compliance."""

from __future__ import annotations

from solver.architectural_program import from_constraints as program_from_constraints
from solver.architectural_program import from_room_program, semantic_zone
from solver.furniture_templates import FURNITURE_TEMPLATES, templates_for
from solver.quality import score_layout
from solver.room_program import envelope_from_constraints, from_constraints
from solver.room_rules import BEDROOM_TYPES
from solver.solver import solve
from solver.spatial_planner import STRATEGIES, default_strategy_name, plan
from solver.topology import build_topology, hard_unconditional_pairs


LIVE_CONSTRAINTS = {
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


def _live_program():
    env = envelope_from_constraints(LIVE_CONSTRAINTS)
    program = from_constraints(LIVE_CONSTRAINTS, env)
    return env, program


def test_program_spaces_from_questionnaire():
    env, program = _live_program()
    arch = from_room_program(program)
    via_constraints = program_from_constraints(LIVE_CONSTRAINTS, env)
    assert arch.bedrooms_requested == 3
    assert via_constraints.bedrooms_requested == 3
    assert arch.bathrooms_requested == 2
    assert arch.outdoor_requested
    types = {s.room_type for s in arch.spaces}
    assert "garage" in types
    assert "patio" in types
    assert "laundry_room" in types
    assert "mudroom" not in types
    assert "home_office" not in types
    living = arch.first("living_room")
    assert living is not None
    assert living.min_area == living.min_width * living.min_depth
    assert living.zone == "public"
    patio = arch.first("patio")
    assert patio is not None
    assert patio.zone == "exterior"
    assert semantic_zone("patio") == "exterior"


def test_zoning_classification():
    _, program = _live_program()
    spatial = plan(program)
    assert spatial.zones["public"]
    assert spatial.zones["private"]
    assert spatial.zones["service"]
    assert spatial.zones["circulation"]
    assert spatial.zones["exterior"]
    types = {r.id: r.type for r in program.rooms}
    assert all(types[i] != "garage" for i in spatial.zones["public"])
    assert any(types[i] == "patio" for i in spatial.zones["exterior"])


def test_semantic_relationships_not_all_wall_share():
    _, program = _live_program()
    spatial = plan(program)
    kinds = {r.kind for r in spatial.relations}
    assert "outside_access" in kinds
    assert "accessed_by" in kinds
    assert "connected" in kinds
    patio_rels = [r for r in spatial.relations if r.kind == "outside_access"]
    assert patio_rels
    assert all(r.strength == "preferred" for r in patio_rels)
    types = {r.id: r.type for r in program.rooms}
    hard = hard_unconditional_pairs(build_topology(program))
    typed = {tuple(sorted((types[a], types[b]))) for a, b in hard}
    assert ("living_room", "patio") not in typed
    assert ("foyer", "living_room") not in typed


def test_circulation_graph_connects_required_rooms():
    _, program = _live_program()
    spatial = plan(program)
    foyer = next(r.id for r in program.rooms if r.type == "foyer")
    hall = next(r.id for r in program.rooms if r.type == "hallway")
    nodes = {n.room_id for n in spatial.circulation.nodes}
    assert foyer in nodes
    assert hall in nodes
    linked = set()
    for e in spatial.circulation.edges:
        linked.add(e.room_a)
        linked.add(e.room_b)
    for r in program.rooms:
        if r.type in ("bedroom", "master_bedroom", "bathroom", "laundry_room"):
            assert r.id in linked or r.id in nodes


def test_clusters_created_from_requested_program():
    _, program = _live_program()
    spatial = plan(program)
    names = {c.name for c in spatial.clusters}
    assert "primary_suite" in names
    assert "public" in names
    assert "service" in names
    assert "private" in names
    assert "circulation" in names
    assert "exterior" in names
    suite = next(c for c in spatial.clusters if c.name == "primary_suite")
    types = {r.id: r.type for r in program.rooms}
    assert "master_bedroom" in {types[i] for i in suite.room_ids}


def test_strategies_defined_and_default_patio_oriented():
    assert set(STRATEGIES) >= {
        "public_private_split", "central_spine", "linear", "service_side", "patio_oriented",
        "rear_private", "living_core",
    }
    _, program = _live_program()
    assert default_strategy_name(program) == "patio_oriented"
    spatial = plan(program)
    assert spatial.strategy.name == "patio_oriented"
    program.outdoor_requested = False
    assert default_strategy_name(program) == "central_spine"


def test_spatial_plan_passed_to_solver_live_request():
    env, program = _live_program()
    spatial = plan(program)
    result = solve(program, env, time_limit_s=15, spatial_plan=spatial)
    assert result.status == "valid", result.reason
    assert result.validated
    assert result.quality_score
    assert result.quality_score["overall"] >= 0
    assert "not professional" in result.quality_score["note"].lower()
    patio = next(r for r in result.layout.rooms if r.type == "patio")
    patio_doors = [d for d in result.layout.doors if patio.id in (d.room_a, d.room_b)]
    assert patio_doors
    beds = [r for r in result.layout.rooms if r.type in BEDROOM_TYPES]
    assert len(beds) == 3
    assert any(r.type == "garage" for r in result.layout.rooms)


def test_furniture_templates_exist_without_changing_placement():
    assert templates_for("bedroom")
    assert templates_for("kitchen")
    kinds = {t.kind for t in FURNITURE_TEMPLATES}
    assert {"bed", "sofa", "dining_table", "toilet", "lavatory", "shower", "counter"} <= kinds


def test_quality_score_does_not_replace_validated():
    env, program = _live_program()
    spatial = plan(program)
    result = solve(program, env, time_limit_s=15, spatial_plan=spatial)
    assert result.status == "valid", result.reason
    q = score_layout(result.layout, program, spatial)
    assert result.validated is True
    assert q["overall"] != result.validated
    assert "code compliance" in q["note"].lower()
