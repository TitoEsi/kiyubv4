"""Phase 7 orthogonal footprint helpers and live flex checks.

Not professional architectural approval.
"""

from __future__ import annotations

from solver.building_mass import BuildingMass, plan_building_mass
from solver.cluster_metrics import mass_occupancy, occupied_room_area_sum
from solver.doors import place_doors
from solver.footprint import (
    bbox_of,
    boundary_segments,
    contains_rect,
    footprints_intersect,
    footprints_touch,
    generate_l_candidates,
    generate_shape_candidates,
    union_area,
    validate_footprint,
)
from solver.models import (
    Door,
    Envelope,
    FootprintPart,
    FurnitureFootprint,
    Layout,
    PlacedRoom,
    RoomFootprint,
    RoomSpec,
    TopologyEdge,
)
from solver.residual import analyze_residual
from solver.room_program import envelope_from_constraints, from_constraints
from solver.room_rules import BEDROOM_TYPES, ROOM_RULES, rule_for
from solver.solver import solve
from solver.spatial_planner import COMPETITION_STRATEGIES, plan
from solver.strategy_competition import compete
from solver.usability import analyze_usability
from solver.validator import validate_room_overlap, ValidationReport


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


def _l_living(x: int = 0, y: int = 0) -> PlacedRoom:
    fp = RoomFootprint(
        type="l_shape",
        parts=[
            FootprintPart(x, y, 12, 8),
            FootprintPart(x, y + 8, 6, 8),
        ],
    )
    return PlacedRoom("liv", "living_room", "Living", x, y, 12, 16, "public", footprint=fp)


def _rect(rid: str, rtype: str, name: str, x: int, y: int, w: int, d: int, zone: str = "public") -> PlacedRoom:
    return PlacedRoom(rid, rtype, name, x, y, w, d, zone)


def test_union_area_does_not_double_count():
    room = _l_living()
    assert union_area(room) == 12 * 8 + 6 * 8
    assert union_area(room) == 144
    bx, by, bw, bd = bbox_of(room)
    assert (bx, by, bw, bd) == (0, 0, 12, 16)
    assert union_area(room) < bw * bd


def test_bbox_is_not_occupied_area():
    room = _l_living()
    assert room.width * room.depth == 192
    assert union_area(room) == 144


def test_disconnected_parts_are_rejected():
    fp = RoomFootprint(
        type="composite",
        parts=[FootprintPart(0, 0, 8, 8), FootprintPart(20, 20, 8, 8)],
    )
    errs = validate_footprint(fp, min_clear=6, min_area=36)
    assert errs
    assert any("disconnect" in e for e in errs)


def test_connected_l_is_accepted():
    room = _l_living()
    assert validate_footprint(room, min_clear=6, min_area=80) == []


def test_min_clear_width_rejects_thin_arm():
    fp = RoomFootprint(
        type="l_shape",
        parts=[FootprintPart(0, 0, 12, 8), FootprintPart(0, 8, 2, 8)],
    )
    errs = validate_footprint(fp, min_clear=6, min_area=40)
    assert any("clear" in e for e in errs)


def test_true_intersection_not_bbox_collision():
    a = _l_living(0, 0)
    b = _rect("bed", "bedroom", "Bed", 6, 8, 6, 8, "private")
    assert a.x < b.x2 and a.x2 > b.x and a.y < b.y2 and a.y2 > b.y
    assert not footprints_intersect(a, b)
    report = ValidationReport()
    validate_room_overlap(Layout(rooms=[a, b], envelope=Envelope(20, 20)), report)
    assert not any(e.type == "room_overlap" for e in report.errors)


def test_real_part_intersection_is_collision():
    a = _l_living(0, 0)
    b = _rect("kit", "kitchen", "Kitchen", 2, 2, 8, 6)
    assert footprints_intersect(a, b)


def test_adjacency_on_real_part_edges():
    a = _l_living(0, 0)
    neighbor = _rect("kit", "kitchen", "Kitchen", 6, 8, 6, 8)
    assert footprints_touch(a, neighbor, min_share=3)
    far = _rect("bed", "bedroom", "Bed", 20, 0, 10, 10, "private")
    assert not footprints_touch(a, far, min_share=3)


def test_raster_does_not_fill_l_void():
    env = Envelope(width=20, depth=20)
    mass = BuildingMass(x=0, y=0, width=20, depth=20, preferred_area=400, min_area=200)
    room = _l_living()
    hall = _rect("h", "hallway", "Hall", 12, 0, 4, 8, "circulation")
    layout = Layout(rooms=[room, hall], envelope=env)
    report = analyze_residual(layout, mass)
    assert report.room_cells_in_mass == 144
    assert report.circulation_cells_in_mass == 32
    assert occupied_room_area_sum(layout) == 144 + 32
    assert mass.area == (
        report.room_cells_in_mass
        + report.circulation_cells_in_mass
        + report.exterior_cells_in_mass
        + report.building_residual_area
    )
    occ = mass_occupancy(layout, mass, report)
    assert occ == (144 + 32) / 400


def test_furniture_in_l_void_rejected():
    room = _l_living()
    assert contains_rect(room, 0, 0, 6, 6)
    assert not contains_rect(room, 8, 10, 3, 3)


def test_bed_blocking_door_still_fails_on_union():
    room = _rect("bed1", "bedroom", "Bedroom", 0, 0, 12, 12, "private")
    door = Door(id="d0", room_a="bed1", room_b="hall", x=0, y=4.5, width=3, is_vertical=True)
    bed = FurnitureFootprint("f0", "bed1", "bed", 0, 4, 7, 5)
    layout = Layout(rooms=[room], doors=[door], furniture=[bed], envelope=Envelope(12, 12))
    report = analyze_usability(layout)
    assert any(i.type == "bed_blocks_door" for i in report.issues)


def test_l_candidate_runs_through_paint_and_usability():
    spec = RoomSpec(
        id="liv", type="living_room", name="Living",
        min_width=10, min_depth=12, preferred_width=14, preferred_depth=16,
        required=True, zone="public",
    )
    cands = generate_l_candidates(spec)
    assert cands
    assert all(len(c.parts) == 2 for c in cands)
    assert all(c.complexity == 1 for c in cands)
    room = _l_living()
    hall = _rect("h", "hallway", "Hall", 12, 0, 4, 16, "circulation")
    door = Door(id="d0", room_a="liv", room_b="h", x=12, y=3, width=3, is_vertical=True)
    layout = Layout(
        rooms=[room, hall],
        doors=[door],
        furniture=[],
        envelope=Envelope(20, 20),
        topology=[TopologyEdge("liv", "h", "connected", hard=True)],
    )
    report = analyze_residual(layout)
    assert report.room_cells_in_mass == 144
    usability = analyze_usability(layout)
    assert usability.room_usability_score >= 0
    doors = place_doors(layout, layout.topology)
    assert doors
    assert doors[0].x == 12


def test_baths_and_closets_are_rectangle_only():
    for rtype in ("bathroom", "half_bath", "closet", "pantry", "garage", "patio"):
        rule = rule_for(rtype)
        assert rule["allowed_shapes"] == ["rectangle"]
        assert rule["max_components"] == 1
        spec = RoomSpec(
            id="r", type=rtype, name=rtype,
            min_width=rule["min_width"], min_depth=rule["min_depth"],
            preferred_width=rule["preferred_width"], preferred_depth=rule["preferred_depth"],
            required=True, zone="private",
        )
        assert generate_l_candidates(spec) == []


def test_living_and_bedrooms_allow_l():
    for rtype in ("living_room", "kitchen", "bedroom", "master_bedroom"):
        assert "l_shape" in ROOM_RULES[rtype]["allowed_shapes"]
        assert ROOM_RULES[rtype]["max_components"] == 2


def test_candidate_generator_is_small_and_deterministic():
    spec = RoomSpec(
        id="liv", type="living_room", name="Living",
        min_width=10, min_depth=12, preferred_width=14, preferred_depth=16,
        required=True, zone="public",
    )
    a = generate_shape_candidates(spec)
    b = generate_shape_candidates(spec)
    assert [c.key for c in a] == [c.key for c in b]
    rects = [c for c in a if c.type == "rectangle"]
    ells = [c for c in a if c.type == "l_shape"]
    assert 2 <= len(rects) <= 4
    assert 1 <= len(ells) <= 2
    assert all(len(c.parts) <= 2 for c in a)


def test_boundary_omits_internal_shared_edge():
    room = _l_living()
    segs = boundary_segments(room)
    internal = [s for s in segs if s == (0, 8, 6, 8) or s == (6, 8, 0, 8)]
    assert not internal
    assert segs
    lengths = [abs(x2 - x1) + abs(y2 - y1) for x1, y1, x2, y2 in segs]
    assert sum(lengths) == 2 * (12 + 8) + 2 * (6 + 8) - 2 * 6


def test_flexible_geometry_off_live_20x30_valid():
    env = envelope_from_constraints(LIVE_CONSTRAINTS)
    program = from_constraints(LIVE_CONSTRAINTS, env)
    spatial = plan(program)
    mass = plan_building_mass(program, env, spatial)
    result = solve(
        program, env, time_limit_s=15,
        spatial_plan=spatial, building_mass=mass, use_clusters=True,
        flexible=False,
    )
    assert result.status == "valid", result.reason
    assert result.validated is True
    rooms = result.layout.rooms
    assert len([r for r in rooms if r.type in BEDROOM_TYPES]) == 3
    assert any(r.type == "garage" for r in rooms)
    assert any(r.type == "patio" for r in rooms)
    assert all(
        r.footprint is None or r.footprint.type == "rectangle" or len(r.parts()) == 1
        for r in rooms
    )


def test_flexible_geometry_on_live_20x30_valid():
    env = envelope_from_constraints(LIVE_CONSTRAINTS)
    program = from_constraints(LIVE_CONSTRAINTS, env)
    spatial = plan(program)
    mass = plan_building_mass(program, env, spatial)
    result = solve(
        program, env, time_limit_s=18,
        spatial_plan=spatial, building_mass=mass, use_clusters=True,
        flexible=True,
    )
    assert result.status == "valid", result.reason
    assert result.validated is True
    rooms = result.layout.rooms
    assert len(rooms) == len(program.rooms)
    assert len([r for r in rooms if r.type in BEDROOM_TYPES]) == 3
    assert any(r.type == "garage" for r in rooms)
    assert any(r.type == "patio" for r in rooms)
    fill = (result.quality_score or {}).get("mass_fill") or {}
    if fill.get("mass_area") and not fill.get("exterior_cells_in_mass"):
        assert fill["mass_area"] == (
            fill["room_cells_in_mass"]
            + fill["circulation_cells_in_mass"]
            + fill["building_residual_area"]
        )
    shapes = {r.footprint.type if r.footprint else "rectangle" for r in rooms}
    assert "rectangle" in shapes
    for r in rooms:
        payload_parts = r.parts()
        assert payload_parts
        if r.type in ("bathroom", "half_bath", "closet", "pantry", "garage", "patio"):
            assert len(payload_parts) == 1


def test_flex_strategies_still_compete(monkeypatch):
    monkeypatch.setenv("KIYUB_FLEXIBLE_GEOMETRY", "1")
    env = envelope_from_constraints(LIVE_CONSTRAINTS)
    program = from_constraints(LIVE_CONSTRAINTS, env)
    spatial = plan(program)
    mass = plan_building_mass(program, env, spatial)
    winner, evals = compete(program, env, mass, use_clusters=True, time_limit_s=8)
    assert len(evals) == 5
    assert {e.strategy for e in evals} == set(COMPETITION_STRATEGIES)
    assert winner is not None and winner.valid
    assert winner.result and winner.result.validated
    for ev in evals:
        if not ev.valid or not ev.result or not ev.result.layout:
            continue
        rooms = ev.result.layout.rooms
        assert len([r for r in rooms if r.type in BEDROOM_TYPES]) == program.bedrooms_requested
        assert any(r.type == "garage" for r in rooms)
        assert any(r.type == "patio" for r in rooms)
        assert ev.result.layout.envelope.width == env.width
        assert ev.result.layout.envelope.depth == env.depth
