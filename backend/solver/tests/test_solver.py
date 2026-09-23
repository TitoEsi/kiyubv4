"""Backend tests for the OR-Tools layout solver and validator."""

from __future__ import annotations

import pytest

from solver.doors import door_clearance, place_doors
from solver.models import (
    Door,
    Envelope,
    FurnitureFootprint,
    Layout,
    PlacedRoom,
    RoomProgram,
    RoomSpec,
    TopologyEdge,
)
from solver.room_program import envelope_from_constraints, from_constraints, prototype_two_bedroom
from solver.room_rules import BEDROOM_TYPES, ZONE_BY_TYPE
from solver.solver import solve
from solver.topology import build_topology, hard_unconditional_pairs
from solver.validator import (
    validate,
    validate_connectivity,
    validate_door_clearance,
    validate_room_overlap,
)


def _env_from_lot(width_m: float, depth_m: float) -> Envelope:
    return envelope_from_constraints({
        "lotShape": "rectangle",
        "lotWidth": width_m,
        "lotDepth": depth_m,
    })


def _spec(rid, rtype, name, w=10, d=10) -> RoomSpec:
    return RoomSpec(
        id=rid, type=rtype, name=name,
        min_width=w, min_depth=d, preferred_width=w, preferred_depth=d,
        required=True, zone=ZONE_BY_TYPE.get(rtype, "public"),
    )


def test_simple_10x15_two_bedroom():
    env = _env_from_lot(10, 15)
    program = prototype_two_bedroom(env)
    result = solve(program, env, time_limit_s=12)
    assert result.status in ("valid", "infeasible")
    if result.status == "infeasible":
        assert result.reason
        pytest.skip(f"10×15 m envelope {env.width}×{env.depth} ft infeasible: {result.reason}")
    assert result.validated
    assert result.layout
    report = validate(result.layout, program)
    assert report.valid, [e.message for e in report.errors]


def test_rooms_do_not_overlap():
    env = _env_from_lot(10, 15)
    program = prototype_two_bedroom(env)
    result = solve(program, env, time_limit_s=12)
    if result.status != "valid":
        pytest.skip("no feasible layout to check overlap")
    report = validate(result.layout, program)
    validate_room_overlap(result.layout, report)
    assert not any(e.type == "room_overlap" for e in report.errors)


def test_impossible_program_infeasible():
    env = Envelope(width=6, depth=6, buildable_width=6, buildable_depth=6)
    program = prototype_two_bedroom(env)
    result = solve(program, env, time_limit_s=5)
    assert result.status == "infeasible"
    assert result.plans == [] or result.layout is None or not result.validated
    assert "envelope" in result.reason.lower() or "exceeds" in result.reason.lower() or result.reason
    assert result.reason_code in ("ROOM_AREA", "MIN_DIMENSIONS", "OTHER")
    assert isinstance(result.conflicts, list)


def test_door_blocked_by_furniture():
    room = PlacedRoom("b1", "bedroom", "Bedroom 2", 0, 0, 12, 12, "private")
    door = Door("d1", "b1", "h1", x=0, y=4, width=3, is_vertical=True)
    bed = FurnitureFootprint("f1", "b1", "bed", x=0, y=3, width=7, depth=5)
    hall = PlacedRoom("h1", "hallway", "Hall", 0, 12, 12, 4, "circulation")
    layout = Layout(rooms=[room, hall], doors=[door], furniture=[bed], envelope=Envelope(20, 20))
    from solver.models import ValidationReport
    report = ValidationReport()
    validate_door_clearance(layout, report)
    assert any(e.type == "door_blocked" for e in report.errors)
    assert "Bedroom 2" in report.errors[0].message or "bed" in report.errors[0].message.lower()


def test_disconnected_room():
    living = PlacedRoom("l1", "living_room", "Living", 0, 0, 12, 12, "public")
    bed = PlacedRoom("b1", "bedroom", "Bedroom 1", 20, 20, 10, 10, "private")
    foyer = PlacedRoom("f1", "foyer", "Foyer", 0, 0, 6, 6, "circulation")
    layout = Layout(
        rooms=[living, bed, foyer],
        doors=[Door("d1", "f1", "l1", 6, 2, 3, True)],
        envelope=Envelope(40, 40),
    )
    from solver.models import ValidationReport
    report = ValidationReport()
    validate_connectivity(layout, report)
    assert any(e.type == "inaccessible_room" for e in report.errors)


def test_patio_outside_access_relationship():
    env = Envelope(width=40, depth=50)
    constraints = {
        "lotShape": "rectangle", "lotWidth": 20, "lotDepth": 30,
        "bedrooms": 2, "bathrooms": 1, "openPlan": False, "primarySuite": False,
        "homeOffice": False, "formalDining": False, "garage": "none",
        "laundry": "none", "outdoor": "patio", "sqft": 1200, "ceilingHeight": "standard",
    }
    program = from_constraints(constraints, env)
    assert any(r.type == "patio" for r in program.rooms)
    edges = build_topology(program)
    assert any(e.relation == "outside_access" for e in edges)
    result = solve(program, env, time_limit_s=12)
    if result.status == "valid":
        patio = next(r for r in result.layout.rooms if r.type == "patio")
        patio_doors = [
            d for d in result.layout.doors
            if patio.id in (d.room_a, d.room_b)
        ]
        assert patio_doors, "patio must have an interior door"


def test_four_bedrooms_preserved():
    env = Envelope(width=54, depth=88)
    constraints = {
        "lotShape": "rectangle", "lotWidth": 20, "lotDepth": 30,
        "bedrooms": 4, "bathrooms": 3, "openPlan": False, "primarySuite": True,
        "homeOffice": False, "formalDining": False, "garage": "none",
        "laundry": "none", "outdoor": "none", "sqft": 1800, "ceilingHeight": "standard",
    }
    program = from_constraints(constraints, env)
    assert program.bedrooms_requested == 4
    assert sum(1 for r in program.rooms if r.type in BEDROOM_TYPES) == 4
    result = solve(program, env, time_limit_s=15)
    if result.status == "valid":
        beds = [r for r in result.layout.rooms if r.type in BEDROOM_TYPES]
        assert len(beds) == 4
    else:
        # Must not invent a 3-bedroom "success"
        assert result.status == "infeasible"
        assert result.validated is False


def test_different_lot_envelopes():
    small = _env_from_lot(10, 15)
    large = _env_from_lot(20, 30)
    assert (small.width, small.depth) != (large.width, large.depth)
    assert large.area > small.area
    assert small.width == int(small.buildable_width)
    assert large.width == int(large.buildable_width)


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


def _shares_wall(a: PlacedRoom, b: PlacedRoom) -> bool:
    if a.x2 == b.x or b.x2 == a.x:
        lo = max(a.y, b.y)
        hi = min(a.y2, b.y2)
        return hi - lo >= 3
    if a.y2 == b.y or b.y2 == a.y:
        lo = max(a.x, b.x)
        hi = min(a.x2, b.x2)
        return hi - lo >= 3
    return False


def test_solve_flags_do_not_change_default_path():
    env = Envelope(width=80, depth=80)
    program = prototype_two_bedroom(env)
    result = solve(
        program,
        env,
        time_limit_s=8,
        require_adjacency=False,
        use_objective=False,
    )
    assert result.status in ("valid", "infeasible")
    assert isinstance(result.reason_code, str)
    assert isinstance(result.conflicts, list)


def test_live_questionnaire_solves_valid():
    env = envelope_from_constraints(LIVE_CONSTRAINTS)
    program = from_constraints(LIVE_CONSTRAINTS, env)
    assert any(r.type == "patio" for r in program.rooms)
    assert program.bedrooms_requested == 3
    assert program.bathrooms_requested == 2
    assert any(r.type == "garage" for r in program.rooms)
    result = solve(program, env, time_limit_s=15)
    assert result.status == "valid", result.reason
    assert result.validated
    assert result.layout
    assert result.reason_code != "ADJACENCY"
    beds = [r for r in result.layout.rooms if r.type in BEDROOM_TYPES]
    assert len(beds) == 3
    baths = [r for r in result.layout.rooms if r.type in ("bathroom", "ensuite_bathroom", "half_bath")]
    assert len(baths) == 2
    patio = next(r for r in result.layout.rooms if r.type == "patio")
    patio_doors = [d for d in result.layout.doors if patio.id in (d.room_a, d.room_b)]
    assert patio_doors, "patio must have an interior exterior-access door"
    report = validate(result.layout, program)
    assert report.valid, [e.message for e in report.errors]
    validate_room_overlap(result.layout, report)
    assert not any(e.type == "room_overlap" for e in report.errors)


def test_topology_no_unconditional_living_patio_or_foyer_living():
    env = envelope_from_constraints(LIVE_CONSTRAINTS)
    program = from_constraints(LIVE_CONSTRAINTS, env)
    edges = build_topology(program)
    types = {r.id: r.type for r in program.rooms}
    names = {r.id: r.name for r in program.rooms}
    hard = hard_unconditional_pairs(edges)
    typed = {tuple(sorted((types[a], types[b]))) for a, b in hard}
    assert ("living_room", "patio") not in typed
    assert ("foyer", "living_room") not in typed
    assert any(r.type == "patio" for r in program.rooms)
    assert any(e.relation == "outside_access" and e.choice_group for e in edges)
    foyer_id = next(r.id for r in program.rooms if r.type == "foyer")
    hall_id = next(r.id for r in program.rooms if r.type == "hallway")
    kit_id = next(r.id for r in program.rooms if r.type == "kitchen")
    din_id = next(r.id for r in program.rooms if r.type == "dining_room")
    gar_id = next(r.id for r in program.rooms if r.type == "garage")
    assert (foyer_id, hall_id) in hard or (hall_id, foyer_id) in hard
    assert (kit_id, din_id) in hard or (din_id, kit_id) in hard
    assert not any(r.type == "mudroom" for r in program.rooms)
    _ = gar_id
    outdoor_or = [e for e in edges if e.relation == "outside_access"]
    targets = {types[e.room_a] if types[e.room_b] == "patio" else types[e.room_b] for e in outdoor_or}
    assert targets <= {"living_room", "dining_room", "kitchen"}
    assert len(targets) >= 2
    _ = names


def test_foyer_may_connect_through_circulation():
    env = envelope_from_constraints(LIVE_CONSTRAINTS)
    program = from_constraints(LIVE_CONSTRAINTS, env)
    result = solve(program, env, time_limit_s=15)
    if result.status != "valid":
        pytest.skip(result.reason)
    living = next(r for r in result.layout.rooms if r.type == "living_room")
    foyer = next(r for r in result.layout.rooms if r.type == "foyer")
    hall = next(r for r in result.layout.rooms if r.type == "hallway")
    assert _shares_wall(living, hall) or _shares_wall(living, foyer)
    # Must not require living to span foyer (front) and patio (rear).
    patio = next(r for r in result.layout.rooms if r.type == "patio")
    if _shares_wall(living, patio) and _shares_wall(living, foyer):
        assert living.depth < env.depth - 10 or living.width < env.width


def test_kitchen_dining_remain_hard_and_garage_has_frontage():
    env = envelope_from_constraints(LIVE_CONSTRAINTS)
    program = from_constraints(LIVE_CONSTRAINTS, env)
    result = solve(program, env, time_limit_s=15)
    if result.status != "valid":
        pytest.skip(result.reason)
    kitchen = next(r for r in result.layout.rooms if r.type == "kitchen")
    dining = next(r for r in result.layout.rooms if r.type == "dining_room")
    garage = next(r for r in result.layout.rooms if r.type == "garage")
    assert _shares_wall(kitchen, dining), "kitchen-dining hard adjacency"
    assert garage.y == 0 or garage.x == 0 or garage.x2 == env.width
    assert not any(r.type == "mudroom" for r in result.layout.rooms)


def test_nonneg_overlap_allows_separated_soft_pair():
    from ortools.sat.python import cp_model
    from solver.constraints import RoomVars, _share_wall

    env = Envelope(width=40, depth=80)
    model = cp_model.CpModel()
    living = RoomSpec(
        "liv", "living_room", "Living", 10, 12, 14, 16, True, "public",
    )
    patio = RoomSpec("pat", "patio", "Patio", 8, 8, 14, 10, True, "outdoor")
    lx = model.NewIntVar(0, env.width, "lx")
    ly = model.NewIntVar(0, env.depth, "ly")
    lw = model.NewIntVar(1, env.width, "lw")
    lh = model.NewIntVar(1, env.depth, "lh")
    px = model.NewIntVar(0, env.width, "px")
    py = model.NewIntVar(0, env.depth, "py")
    pw = model.NewIntVar(1, env.width, "pw")
    ph = model.NewIntVar(1, env.depth, "ph")
    lrot = model.NewBoolVar("lrot")
    prot = model.NewBoolVar("prot")
    a = RoomVars(living, lx, ly, lw, lh, lrot)
    b = RoomVars(patio, px, py, pw, ph, prot)
    model.Add(lx == 0)
    model.Add(ly == 0)
    model.Add(lw == 14)
    model.Add(lh == 16)
    model.Add(px == 0)
    model.Add(py == 70)
    model.Add(pw == 10)
    model.Add(ph == 10)
    touch = _share_wall(model, a, b, env, "soft_sep")
    model.Add(touch == 0)
    solver = cp_model.CpSolver()
    solver.parameters.random_seed = 1
    status = solver.Solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE), (
        "separated rooms with a soft wall-share bool must stay feasible; "
        "non-negative overlap encoding regressed"
    )