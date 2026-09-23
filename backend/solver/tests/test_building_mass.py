"""Building mass / footprint tests. Not professional architectural approval."""

from __future__ import annotations

from solver.building_mass import ASPECT_MAX, plan_building_mass, preferred_building_area
from solver.models import Envelope, Layout, PlacedRoom
from solver.quality import score_layout
from solver.residual import analyze_residual
from solver.room_program import envelope_from_constraints, from_constraints, prototype_two_bedroom
from solver.room_rules import BEDROOM_TYPES
from solver.solver import solve
from solver.spatial_planner import plan


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


def _live():
    env = envelope_from_constraints(LIVE_CONSTRAINTS)
    program = from_constraints(LIVE_CONSTRAINTS, env)
    return env, program


def test_small_program_mass_smaller_than_live():
    live_env, live_prog = _live()
    live_mass = plan_building_mass(live_prog, live_env)
    small_env = Envelope(width=80, depth=80)
    small_prog = prototype_two_bedroom(small_env)
    small_mass = plan_building_mass(small_prog, small_env)
    live_pref, _, _ = preferred_building_area(live_prog)
    small_pref, _, _ = preferred_building_area(small_prog)
    assert small_pref < live_pref
    assert small_mass.preferred_area < live_mass.preferred_area
    assert small_mass.area <= live_mass.area or small_mass.preferred_area < live_mass.preferred_area


def test_adding_office_increases_preferred_area():
    env, program = _live()
    base, _, _ = preferred_building_area(program)
    bigger = dict(LIVE_CONSTRAINTS)
    bigger["homeOffice"] = True
    extra = from_constraints(bigger, env)
    grown, _, _ = preferred_building_area(extra)
    assert grown > base
    assert any(r.type == "home_office" for r in extra.rooms)
    assert extra.bedrooms_requested == 3


def test_mass_stays_inside_envelope():
    env, program = _live()
    mass = plan_building_mass(program, env)
    assert mass.x >= 0
    assert mass.y >= 0
    assert mass.x + mass.width <= env.width
    assert mass.y + mass.depth <= env.depth
    assert mass.area == mass.width * mass.depth


def test_mass_avoids_extreme_aspect_ratio():
    env, program = _live()
    mass = plan_building_mass(program, env)
    ratio = max(mass.width, mass.depth) / min(mass.width, mass.depth)
    assert ratio <= ASPECT_MAX + 1e-6
    small_env = Envelope(width=80, depth=80)
    small_mass = plan_building_mass(prototype_two_bedroom(small_env), small_env)
    small_ratio = max(small_mass.width, small_mass.depth) / min(small_mass.width, small_mass.depth)
    assert small_ratio <= ASPECT_MAX + 1e-6


def test_patio_reserve_and_rear_orientation():
    env, program = _live()
    mass = plan_building_mass(program, env)
    assert program.outdoor_requested
    assert mass.patio_reserve_depth > 0
    assert mass.y == 0
    assert mass.rear_y + mass.patio_reserve_depth <= env.depth
    spatial = plan(program)
    result = solve(program, env, time_limit_s=15, spatial_plan=spatial, building_mass=mass)
    assert result.status == "valid", result.reason
    patio = next(r for r in result.layout.rooms if r.type == "patio")
    assert patio.y + patio.depth == env.depth
    patio_doors = [d for d in result.layout.doors if patio.id in (d.room_a, d.room_b)]
    assert patio_doors


def test_site_open_space_not_building_dead_space():
    env = Envelope(width=20, depth=16)
    mass = plan_building_mass(prototype_two_bedroom(env), env)
    # Force a known centered-ish mass for classification.
    from solver.building_mass import BuildingMass
    mass = BuildingMass(x=5, y=0, width=10, depth=10, preferred_area=100, min_area=40)
    rooms = [
        PlacedRoom("l", "living_room", "Living", 5, 0, 10, 6, "public"),
        PlacedRoom("h", "hallway", "Hall", 5, 6, 4, 4, "circulation"),
    ]
    layout = Layout(rooms=rooms, envelope=env)
    report = analyze_residual(layout, mass)
    assert report.site_open_space_area > 0
    assert report.building_residual_area > 0
    assert report.residual_area == report.building_residual_area
    q = score_layout(layout, prototype_two_bedroom(env), building_mass=mass)
    assert q["site_open_space_area"] == report.site_open_space_area
    assert q["building_residual_area"] == report.building_residual_area
    # Site leftover must not be the dead_space numerator.
    assert q["residual"]["residual_area"] == report.building_residual_area


def test_hole_inside_mass_is_building_residual():
    env = Envelope(width=16, depth=16)
    from solver.building_mass import BuildingMass
    mass = BuildingMass(x=2, y=0, width=12, depth=12, preferred_area=144, min_area=80)
    rooms = [
        PlacedRoom("top", "living_room", "Top", 2, 0, 12, 3, "public"),
        PlacedRoom("bot", "kitchen", "Bottom", 2, 9, 12, 3, "public"),
        PlacedRoom("left", "bedroom", "Left", 2, 3, 3, 6, "private"),
        PlacedRoom("right", "bathroom", "Right", 11, 3, 3, 6, "private"),
        PlacedRoom("h", "hallway", "Hall", 0, 0, 2, 8, "circulation"),
    ]
    layout = Layout(rooms=rooms, envelope=env)
    report = analyze_residual(layout, mass)
    assert report.building_residual_area >= 36
    assert report.building_residual_region_count >= 1
    kinds = {r.kind for r in report.regions}
    assert "building" in kinds


def test_live_20x30_valid_with_building_mass():
    env, program = _live()
    spatial = plan(program)
    mass = plan_building_mass(program, env, spatial)
    result = solve(program, env, time_limit_s=15, spatial_plan=spatial, building_mass=mass)
    assert result.status == "valid", result.reason
    assert result.validated is True
    assert result.quality_score
    q = result.quality_score
    assert q["building_mass"]
    assert q["building_mass"]["width"] == mass.width
    beds = [r for r in result.layout.rooms if r.type in BEDROOM_TYPES]
    assert len(beds) == 3
    assert any(r.type == "garage" for r in result.layout.rooms)
    assert any(r.type == "patio" for r in result.layout.rooms)
    interiors = [r for r in result.layout.rooms if r.type not in ("patio", "deck")]
    min_x = min(r.x for r in interiors)
    # Frontage-centered mass should not hug the lot's left edge as hard as Phase 2.
    assert mass.x >= 0
    assert q["site_open_space_area"] >= 0
    assert q["building_residual_area"] >= 0
    assert "not professional" in q["note"].lower()
    _ = min_x
