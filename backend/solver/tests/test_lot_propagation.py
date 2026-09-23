"""Lot dimension propagation. No silent 10x10 / 36ft defaults that ignore the lot."""

from __future__ import annotations

from moe.housegan.bubble_diagram import build_bubble_diagram
from solver.building_mass import plan_building_mass
from solver.envelope import compute_buildable_envelope
from solver.room_program import envelope_from_constraints, from_constraints
from solver.room_rules import size_caps
from solver.spatial_planner import plan


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


def test_envelope_matches_20x30_meters():
    raw = compute_buildable_envelope(LIVE)
    env = envelope_from_constraints(LIVE)
    assert abs(raw["lot_width_ft"] - 20 * 3.28084) < 0.01
    assert abs(raw["lot_depth_ft"] - 30 * 3.28084) < 0.01
    assert env.lot_width_ft == raw["lot_width_ft"]
    assert env.lot_depth_ft == raw["lot_depth_ft"]
    assert env.width == int(raw["buildable_width"])
    assert env.depth == int(raw["buildable_depth"])
    assert env.width not in (10, 20, 50) or raw["lot_width_ft"] > 50
    assert env.width > 40
    assert env.depth > 70


def test_bubble_diagram_capped_to_buildable_envelope():
    env = compute_buildable_envelope(LIVE)
    diagram = build_bubble_diagram(LIVE)
    assert diagram.house_w <= env["buildable_width"] + 1e-6
    assert diagram.house_h <= env["buildable_depth"] + 1e-6
    tiny = dict(LIVE, lotWidth=8, lotDepth=10, garage="none", outdoor="none", sqft=800)
    tiny_env = compute_buildable_envelope(tiny)
    tiny_d = build_bubble_diagram(tiny)
    assert tiny_d.house_w <= tiny_env["buildable_width"] + 1e-6
    assert tiny_d.house_h <= tiny_env["buildable_depth"] + 1e-6
    assert tiny_d.house_w < 36.0


def test_building_mass_inside_envelope():
    env = envelope_from_constraints(LIVE)
    program = from_constraints(LIVE, env)
    spatial = plan(program)
    mass = plan_building_mass(program, env, spatial)
    assert mass.width <= env.width
    assert mass.depth <= env.depth
    assert mass.x + mass.width <= env.width
    assert mass.y + mass.depth <= env.depth


def test_size_caps_are_site_aware_not_preferred_plus_six():
    env = envelope_from_constraints(LIVE)
    program = from_constraints(LIVE, env)
    living = next(r for r in program.rooms if r.type == "living_room")
    max_w, max_h = size_caps(living, env.width, env.depth)
    assert max_w > living.preferred_width + 6 or max_h > living.preferred_depth + 6
    assert max_w <= env.width
    assert max_h <= env.depth
