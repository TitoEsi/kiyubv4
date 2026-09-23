"""Room usability scoring tests. Not professional architectural approval."""

from __future__ import annotations

from solver.building_mass import plan_building_mass
from solver.models import Door, Envelope, FurnitureFootprint, Layout, PlacedRoom
from solver.room_program import envelope_from_constraints, from_constraints
from solver.room_rules import BEDROOM_TYPES
from solver.solver import solve
from solver.spatial_planner import plan
from solver.usability import analyze_usability


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


def _door(room_id: str, x: float, y: float, vertical: bool = True, width: float = 3.0) -> Door:
    return Door(
        id="d0", room_a=room_id, room_b="hall",
        x=x, y=y, width=width, is_vertical=vertical, swing_direction="in",
    )


def _issue_types(report) -> set[str]:
    return {i.type for i in report.issues}


def test_bedroom_bed_blocking_door_fails():
    room = PlacedRoom("bed1", "bedroom", "Bedroom", 0, 0, 12, 12, "private")
    door = _door("bed1", 0, 4.5)
    bed = FurnitureFootprint("f0", "bed1", "bed", 0, 4, 7, 5)
    layout = Layout(rooms=[room], doors=[door], furniture=[bed], envelope=Envelope(12, 12))
    report = analyze_usability(layout)
    assert "bed_blocks_door" in _issue_types(report)
    assert report.door_clearance_score < 100


def test_bedroom_valid_bed_orientation_passes():
    room = PlacedRoom("bed1", "bedroom", "Bedroom", 0, 0, 12, 12, "private")
    door = _door("bed1", 0, 4.5)
    bed = FurnitureFootprint("f0", "bed1", "bed", 5, 0, 7, 5)
    layout = Layout(rooms=[room], doors=[door], furniture=[bed], envelope=Envelope(12, 12))
    report = analyze_usability(layout)
    assert "bed_blocks_door" not in _issue_types(report)
    assert report.door_clearance_score == 100


def test_door_swing_overlapping_bed_fails():
    room = PlacedRoom("bed1", "bedroom", "Bedroom", 0, 0, 12, 12, "private")
    door = _door("bed1", 0, 4.5)
    bed = FurnitureFootprint("f0", "bed1", "bed", 0, 4.5, 7, 5)
    layout = Layout(rooms=[room], doors=[door], furniture=[bed], envelope=Envelope(12, 12))
    report = analyze_usability(layout)
    assert {"bed_blocks_door", "swing_overlap"} & _issue_types(report)


def test_door_swing_clear_of_bed_passes():
    room = PlacedRoom("bed1", "bedroom", "Bedroom", 0, 0, 12, 12, "private")
    door = _door("bed1", 0, 4.5)
    bed = FurnitureFootprint("f0", "bed1", "bed", 5, 7, 7, 5)
    layout = Layout(rooms=[room], doors=[door], furniture=[bed], envelope=Envelope(12, 12))
    report = analyze_usability(layout)
    assert "bed_blocks_door" not in _issue_types(report)
    assert "swing_overlap" not in _issue_types(report)


def test_bathroom_door_colliding_with_toilet_fails():
    room = PlacedRoom("bath", "bathroom", "Bath", 0, 0, 6, 8, "private")
    door = _door("bath", 0, 3)
    toilet = FurnitureFootprint("f0", "bath", "toilet", 0, 2.5, 2, 2.5)
    layout = Layout(rooms=[room], doors=[door], furniture=[toilet], envelope=Envelope(6, 8))
    report = analyze_usability(layout)
    assert "door_fixture_collision" in _issue_types(report)
    assert report.fixture_clearance_score < 100


def test_bathroom_fixture_layout_with_clearance_passes():
    room = PlacedRoom("bath", "bathroom", "Bath", 0, 0, 8, 10, "private")
    door = _door("bath", 0, 3)
    toilet = FurnitureFootprint("f0", "bath", "toilet", 6, 0, 2, 2.5)
    lav = FurnitureFootprint("f1", "bath", "lavatory", 3, 0, 2.5, 2)
    layout = Layout(rooms=[room], doors=[door], furniture=[toilet, lav], envelope=Envelope(8, 10))
    report = analyze_usability(layout)
    assert "door_fixture_collision" not in _issue_types(report)
    assert "fixture_overlap" not in _issue_types(report)


def test_dining_table_insufficient_chair_clearance_fails():
    room = PlacedRoom("din", "dining_room", "Dining", 0, 0, 8, 8, "public")
    layout = Layout(rooms=[room], doors=[], furniture=[], envelope=Envelope(8, 8))
    report = analyze_usability(layout)
    assert "chair_clearance" in _issue_types(report)
    assert report.circulation_clearance_score < 100


def test_dining_table_valid_circulation_passes():
    room = PlacedRoom("din", "dining_room", "Dining", 0, 0, 16, 14, "public")
    layout = Layout(rooms=[room], doors=[], furniture=[], envelope=Envelope(16, 14))
    report = analyze_usability(layout)
    assert "chair_clearance" not in _issue_types(report)


def test_living_room_blocked_entry_fails():
    room = PlacedRoom("liv", "living_room", "Living", 0, 0, 14, 14, "public")
    door = _door("liv", 0, 5)
    sofa = FurnitureFootprint("f0", "liv", "sofa", 0, 4, 7, 3)
    layout = Layout(rooms=[room], doors=[door], furniture=[sofa], envelope=Envelope(14, 14))
    report = analyze_usability(layout)
    assert {"blocked_entry", "swing_overlap"} & _issue_types(report)
    assert report.circulation_clearance_score < 100 or report.door_clearance_score < 100


def test_living_room_valid_circulation_passes():
    room = PlacedRoom("liv", "living_room", "Living", 0, 0, 16, 16, "public")
    door = _door("liv", 0, 6)
    layout = Layout(rooms=[room], doors=[door], furniture=[], envelope=Envelope(16, 16))
    report = analyze_usability(layout)
    assert "blocked_entry" not in _issue_types(report)


def test_kitchen_aisle_below_minimum_fails():
    room = PlacedRoom("kit", "kitchen", "Kitchen", 0, 0, 5, 10, "public")
    layout = Layout(rooms=[room], doors=[], furniture=[], envelope=Envelope(5, 10))
    report = analyze_usability(layout)
    assert "aisle_narrow" in _issue_types(report)
    assert report.circulation_clearance_score < 100


def test_kitchen_valid_aisle_passes():
    room = PlacedRoom("kit", "kitchen", "Kitchen", 0, 0, 12, 12, "public")
    layout = Layout(rooms=[room], doors=[], furniture=[], envelope=Envelope(12, 12))
    report = analyze_usability(layout)
    assert "aisle_narrow" not in _issue_types(report)


def test_primary_suite_valid_arrangement_passes():
    master = PlacedRoom("m", "master_bedroom", "Master", 0, 0, 14, 14, "private")
    bath = PlacedRoom("e", "ensuite_bathroom", "Ensuite", 14, 0, 8, 10, "private")
    closet = PlacedRoom("c", "walk_in_closet", "Closet", 14, 10, 6, 7, "private")
    doors = [
        _door("m", 0, 5),
        Door(id="d1", room_a="m", room_b="e", x=14, y=3, width=3, is_vertical=True),
        Door(id="d2", room_a="m", room_b="c", x=14, y=11, width=3, is_vertical=True),
    ]
    layout = Layout(rooms=[master, bath, closet], doors=doors, furniture=[], envelope=Envelope(22, 17))
    report = analyze_usability(layout)
    hard = [i for i in report.issues if i.severity == "hard"]
    assert not hard, [i.as_dict() for i in hard]
    assert report.room_usability_score == 100


def test_original_bed_blocking_door_regression():
    """Original KIYUB defect: bed physically blocks the only bedroom entry."""
    room = PlacedRoom("bed1", "bedroom", "Bedroom 1", 0, 0, 11, 12, "private")
    door = _door("bed1", 0, 4)
    bed = FurnitureFootprint("f0", "bed1", "bed", 0, 3, 7, 5)
    layout = Layout(rooms=[room], doors=[door], furniture=[bed], envelope=Envelope(11, 12))
    report = analyze_usability(layout)
    assert "bed_blocks_door" in _issue_types(report)


def test_live_20x30_remains_valid_with_usability_scores():
    env = envelope_from_constraints(LIVE_CONSTRAINTS)
    program = from_constraints(LIVE_CONSTRAINTS, env)
    spatial = plan(program)
    mass = plan_building_mass(program, env, spatial)
    result = solve(
        program, env, time_limit_s=15,
        spatial_plan=spatial, building_mass=mass, use_clusters=True,
    )
    assert result.status == "valid", result.reason
    assert result.validated is True
    q = result.quality_score
    assert q
    assert "room_usability" in q["categories"]
    assert q["room_usability_score"] >= 0
    assert isinstance(q["usability_issues"], list)
    beds = [r for r in result.layout.rooms if r.type in BEDROOM_TYPES]
    assert len(beds) == 3
    assert any(r.type == "garage" for r in result.layout.rooms)
    assert any(r.type == "patio" for r in result.layout.rooms)
    assert q.get("mass_fill")
    assert "not professional" in q["note"].lower()
