"""Phase 22 architectural engine tests. Not professional architectural approval."""

from __future__ import annotations

import asyncio

import torch

from moe.housegan.bubble_diagram import build_bubble_diagram
from moe.housegan.official_adapter import pack_official_inputs, unconstrained_masks
from solver.adapter import layout_to_floorplan
from solver.architectural_program import from_room_program, validate_program
from solver.building_mass import plan_building_mass
from solver.models import Layout, PlacedRoom
from solver.openings import place_windows
from solver.room_graph import build_room_graph
from solver.room_program import envelope_from_constraints, from_constraints
from solver.room_rules import HALL_MAX_AREA_FT2, HALL_MAX_SHORT_FT, size_caps
from solver.ruleset import default_ruleset
from solver.solver import solve
from solver.spatial_planner import (
    COMPETITION_STRATEGIES,
    EXTRA_STRATEGIES,
    cheap_filter_candidates,
    generate_strategy_candidates,
    plan,
)
from solver.topology import build_topology
from solver.walls import place_walls


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


def test_room_graph_kitchen_dining_and_bedroom_garage():
    env, program = _live()
    arch = from_room_program(program)
    assert validate_program(arch, env).ok
    graph = build_room_graph(arch)
    types = {s.id: s.room_type for s in arch.spaces}
    pairs = {(types[e.room_a], types[e.room_b], e.kind) for e in graph.edges}
    rev = {(types[e.room_b], types[e.room_a], e.kind) for e in graph.edges}
    assert ("kitchen", "dining_room", "required_adjacency") in pairs | rev
    assert ("bedroom", "garage", "forbidden_adjacency") in pairs | rev or (
        "master_bedroom", "garage", "forbidden_adjacency"
    ) in pairs | rev
    assert build_topology(program)
    assert build_room_graph(arch).topology_edges() == build_topology(program)


def test_cheap_filter_keeps_competition_order():
    _, program = _live()
    cands = generate_strategy_candidates(program)
    names = [c.strategy.name for c in cands]
    assert names[:5] == list(COMPETITION_STRATEGIES)
    assert set(EXTRA_STRATEGIES) <= set(names)
    filtered = cheap_filter_candidates(cands, program)
    assert [c.strategy.name for c in filtered][:5] == list(COMPETITION_STRATEGIES)


def test_hallway_size_caps_do_not_allow_square_40():
    env, program = _live()
    hall = next(r for r in program.rooms if r.type == "hallway")
    size_caps(hall, env.width, env.depth)
    assert HALL_MAX_SHORT_FT == 6
    assert HALL_MAX_AREA_FT2 == 240


def test_given_m_refine_changes_fixed_nodes():
    diagram = build_bubble_diagram({
        "bedrooms": 1,
        "bathrooms": 1,
        "garage": "none",
        "outdoor": "none",
        "primarySuite": False,
        "sqft": 800,
        "laundry": "none",
    })
    n = diagram.n
    z0, m0, _y0, _w0 = pack_official_inputs(diagram, device="cpu")
    unconstrained = unconstrained_masks(n, device="cpu")
    assert torch.equal(m0, unconstrained)
    prev = torch.ones(n, 64, 64)
    z1, m1, _y1, _w1 = pack_official_inputs(
        diagram, device="cpu", z=z0, prev_masks=prev, fixed_nodes=[0],
    )
    assert torch.equal(z0, z1)
    assert not torch.equal(m0, m1)
    assert torch.allclose(m1[0, 0], prev[0])
    assert (m1[0, 1] == 1).all()
    assert (m1[1, 1] == 0).all()


def test_missing_checkpoint_still_empty(monkeypatch, tmp_path):
    from moe.housegan.inference import generate_layouts, reset_housegan_runtime
    monkeypatch.setattr("moe.housegan.inference.WEIGHTS_DIR", tmp_path / "empty")
    reset_housegan_runtime()
    diagram = build_bubble_diagram({"bedrooms": 1, "bathrooms": 1, "sqft": 800, "garage": "none"})
    layouts = asyncio.run(generate_layouts(diagram, num_variants=1, mode="auto"))
    assert layouts == []


def test_lot_scaling_20x20_and_20x30_not_crushed():
    from solver.ai_hints import hints_from_ai_candidate

    for w_m, d_m in ((20, 20), (20, 30)):
        constraints = dict(LIVE, lotWidth=w_m, lotDepth=d_m)
        env = envelope_from_constraints(constraints)
        program = from_constraints(constraints, env)
        diagram = build_bubble_diagram(constraints)
        assert diagram.house_w >= min(36.0, env.width * 0.6)
        assert diagram.house_h >= min(36.0, env.depth * 0.5)
        rooms = []
        x = 0.0
        for spec in program.rooms:
            rooms.append({
                "type": spec.type,
                "x": x,
                "y": 0.0,
                "width": float(spec.min_width),
                "height": float(spec.min_depth),
            })
            x += float(spec.min_width)
        plan_payload = {
            "generator": "moe+housegan",
            "totalWidth": float(env.width),
            "totalHeight": float(env.depth),
            "rooms": rooms,
        }
        attempt = hints_from_ai_candidate({"plans": [plan_payload]}, program, env)
        assert attempt.used, attempt.reason
        assert attempt.conversion is not None
        assert 0.5 <= attempt.conversion.scale_x <= 2.0
        assert 0.5 <= attempt.conversion.scale_y <= 2.0
        for spec in program.rooms:
            hx, hy, hw, hh = attempt.hints[spec.id]
            assert hw >= 1 and hh >= 1
            assert hx + hw <= env.width
            assert hy + hh <= env.depth


def test_live_20x30_3br_hallway_not_enormous():
    env, program = _live()
    spatial = plan(program)
    mass = plan_building_mass(program, env, spatial)
    result = solve(
        program, env, time_limit_s=20,
        spatial_plan=spatial, building_mass=mass, use_clusters=True, flexible=False,
    )
    assert result.status == "valid", result.reason
    assert result.validated
    rooms = result.layout.rooms
    types = {r.type for r in rooms}
    assert {
        "bedroom", "master_bedroom", "living_room", "dining_room", "kitchen",
        "laundry_room", "garage", "hallway",
    } <= types
    baths = sum(1 for r in rooms if r.type in ("bathroom", "ensuite_bathroom", "half_bath"))
    beds = sum(1 for r in rooms if r.type in ("bedroom", "master_bedroom"))
    assert beds == 3
    assert baths == 2
    hall = next(r for r in rooms if r.type == "hallway")
    hall_area = hall.width * hall.depth
    assert hall_area <= HALL_MAX_AREA_FT2
    assert min(hall.width, hall.depth) <= HALL_MAX_SHORT_FT
    q = result.quality_score or {}
    assert q.get("circulation_ratio", 1) <= 0.22
    assert q.get("objective_breakdown")
    assert q.get("hard_valid") is True
    assert result.layout.walls
    payload = layout_to_floorplan(result.layout)
    assert payload["walls"]
    assert payload["openings"] or payload["doors"]


def test_walls_from_layout_no_duplicates():
    living = PlacedRoom("liv", "living_room", "Living", 0, 0, 12, 12, "public")
    kit = PlacedRoom("kit", "kitchen", "Kitchen", 12, 0, 10, 12, "public")
    layout = Layout(rooms=[living, kit])
    walls = place_walls(layout)
    layout.walls = walls
    assert walls
    ids = [w.id for w in walls]
    assert len(ids) == len(set(ids))
    shared = [w for w in walls if w.kind == "interior" and set(w.room_ids) == {"liv", "kit"}]
    assert shared
    layout.openings = place_windows(layout)
    assert any(o.kind == "window" for o in layout.openings)


def test_ruleset_unknown_for_unverified_ph_and_never_irc():
    env, program = _live()
    spatial = plan(program)
    result = solve(program, env, time_limit_s=20, spatial_plan=spatial, flexible=False)
    assert result.status == "valid", result.reason
    rs = default_ruleset()
    findings = rs.evaluate(result.layout, program)
    payload = rs.as_dict(findings)
    assert payload["irc_compliant"] is False
    statuses = {r.code: r.status for r in findings}
    assert statuses["nbc_setbacks"] == "UNKNOWN"
    assert statuses["nbc_room_minima"] == "UNKNOWN"
    assert statuses["irc_compliant"] == "UNKNOWN"
    assert "PASS" in {r.status for r in findings}
