"""Circulation vs residual-space tests. Not professional architectural approval."""

from __future__ import annotations

from solver.circulation import analyze_circulation
from solver.models import Door, Envelope, Layout, PlacedRoom, RoomProgram, RoomSpec
from solver.quality import score_layout
from solver.residual import analyze_residual
from solver.room_program import envelope_from_constraints, from_constraints
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


def _spec(rid: str, rtype: str, name: str, w: int, d: int, zone: str) -> RoomSpec:
    return RoomSpec(
        id=rid, type=rtype, name=name,
        min_width=1, min_depth=1, preferred_width=w, preferred_depth=d,
        required=True, zone=zone,
    )


def _room(rid: str, rtype: str, name: str, x: int, y: int, w: int, d: int, zone: str) -> PlacedRoom:
    return PlacedRoom(id=rid, type=rtype, name=name, x=x, y=y, width=w, depth=d, zone=zone)


def _program(rooms: list[PlacedRoom], env: Envelope, beds: int = 0, baths: int = 0) -> RoomProgram:
    specs = [
        _spec(r.id, r.type, r.name, r.width, r.depth, r.zone)
        for r in rooms
    ]
    return RoomProgram(
        rooms=specs,
        envelope=env,
        bedrooms_requested=beds,
        bathrooms_requested=baths,
        outdoor_requested=any(r.type == "patio" for r in rooms),
    )


def test_intentional_hallway_is_not_residual():
    env = Envelope(width=10, depth=20)
    hall = _room("h", "hallway", "Hall", 0, 0, 4, 20, "circulation")
    living = _room("l", "living_room", "Living", 4, 0, 6, 20, "public")
    layout = Layout(rooms=[hall, living], envelope=env)
    report = analyze_residual(layout)
    assert report.residual_area == 0
    assert report.residual_region_count == 0
    assert report.narrow_residual_area == 0


def test_isolated_empty_pocket_is_residual():
    env = Envelope(width=12, depth=12)
    rooms = [
        _room("top", "living_room", "Top", 0, 0, 12, 3, "public"),
        _room("bot", "kitchen", "Bottom", 0, 9, 12, 3, "public"),
        _room("left", "bedroom", "Left", 0, 3, 3, 6, "private"),
        _room("right", "bathroom", "Right", 9, 3, 3, 6, "private"),
    ]
    layout = Layout(rooms=rooms, envelope=env)
    report = analyze_residual(layout)
    assert report.residual_region_count >= 1
    assert report.residual_area == 36
    assert report.largest_residual_region == 36
    assert report.isolated_residual_regions >= 1


def test_narrow_leftover_strip_is_penalized():
    env = Envelope(width=13, depth=20)
    living = _room("l", "living_room", "Living", 3, 0, 10, 20, "public")
    layout = Layout(rooms=[living], envelope=env)
    residual = analyze_residual(layout)
    assert residual.residual_area == 60
    assert residual.regions
    assert residual.regions[0].min_width <= 3
    assert residual.narrow_residual_area > 0
    program = _program(layout.rooms, env)
    q = score_layout(layout, program)
    assert q["categories"]["narrow_residual"] < 100
    assert q["residual"]["narrow_residual_area"] > 0


def test_valid_hallway_is_not_narrow_residual_penalized():
    env = Envelope(width=14, depth=20)
    hall = _room("h", "hallway", "Hall", 0, 0, 4, 20, "circulation")
    living = _room("l", "living_room", "Living", 4, 0, 10, 20, "public")
    layout = Layout(rooms=[hall, living], envelope=env)
    residual = analyze_residual(layout)
    assert residual.residual_area == 0
    assert residual.narrow_residual_area == 0
    program = _program(layout.rooms, env)
    q = score_layout(layout, program)
    assert q["categories"]["narrow_residual"] == 100
    strip_env = Envelope(width=13, depth=20)
    strip = Layout(rooms=[_room("l", "living_room", "Living", 3, 0, 10, 20, "public")], envelope=strip_env)
    strip_q = score_layout(strip, _program(strip.rooms, strip_env))
    assert strip_q["categories"]["narrow_residual"] < q["categories"]["narrow_residual"]


def test_required_rooms_reachable_through_circulation():
    env = Envelope(width=24, depth=16)
    foyer = _room("f", "foyer", "Foyer", 0, 0, 6, 6, "circulation")
    hall = _room("h", "hallway", "Hall", 6, 0, 4, 12, "circulation")
    living = _room("l", "living_room", "Living", 10, 0, 10, 10, "public")
    bed = _room("b", "bedroom", "Bedroom", 0, 8, 6, 8, "private")
    doors = [
        Door("d0", "f", "h", 6, 3, 3, True),
        Door("d1", "h", "l", 10, 5, 3, True),
    ]
    layout = Layout(rooms=[foyer, hall, living, bed], doors=doors, envelope=env)
    program = _program(layout.rooms, env, beds=1)
    analysis = analyze_circulation(layout, program)
    assert "l" in analysis.reachable_required
    assert "b" in analysis.unreachable_required
    q = score_layout(layout, program)
    assert q["circulation"]["unreachable_count"] >= 1
    assert "not professional" in q["note"].lower()


def test_live_20x30_remains_valid_with_residual_metrics():
    env = envelope_from_constraints(LIVE_CONSTRAINTS)
    program = from_constraints(LIVE_CONSTRAINTS, env)
    spatial = plan(program)
    result = solve(program, env, time_limit_s=15, spatial_plan=spatial)
    assert result.status == "valid", result.reason
    assert result.validated is True
    q = result.quality_score
    assert q
    assert "residual" in q
    assert "circulation" in q
    assert q["residual"]["residual_area"] >= 0
    assert q["circulation"]["circulation_area"] > 0
    residual = analyze_residual(result.layout)
    circ = analyze_circulation(result.layout, program, spatial)
    assert residual.residual_area == q["residual"]["residual_area"]
    used = sum(r.width * r.depth for r in result.layout.rooms)
    assert residual.residual_area == env.area - used
    assert any(r.type == "hallway" for r in result.layout.rooms)
    required = circ.reachable_required + circ.unreachable_required
    assert required
    assert len(circ.reachable_required) >= 1
    report_valid = result.validated
    assert report_valid is True
    assert q["overall"] != report_valid
