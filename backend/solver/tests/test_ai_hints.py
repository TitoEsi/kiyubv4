"""AI candidate → CP-SAT soft hint validation. Not professional architectural approval."""

from __future__ import annotations

from solver.ai_hints import hints_from_ai_candidate
from solver.building_mass import plan_building_mass
from solver.models import Layout, PlacedRoom, SolveResult
from solver.room_program import envelope_from_constraints, from_constraints
from solver.spatial_planner import COMPETITION_STRATEGIES, plan
from solver.strategy_competition import compete, evaluate_strategy


CONSTRAINTS = {
    "lotShape": "rectangle",
    "lotWidth": 20,
    "lotDepth": 30,
    "bedrooms": 2,
    "bathrooms": 1,
    "openPlan": False,
    "primarySuite": True,
    "homeOffice": True,
    "formalDining": False,
    "garage": "2car",
    "laundry": "room",
    "outdoor": "patio",
    "sqft": 1500,
    "stories": 1,
    "style": "modern",
    "ceilingHeight": "standard",
}


def _prog():
    env = envelope_from_constraints(CONSTRAINTS)
    program = from_constraints(CONSTRAINTS, env)
    return env, program


def _rooms_for(program, **overrides):
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
    for room, extra in zip(rooms, [{}] * len(rooms)):
        room.update(extra)
    for i, patch in overrides.get("patches", {}).items():
        rooms[i].update(patch)
    if "extra" in overrides:
        rooms.append(overrides["extra"])
    if "drop_type" in overrides:
        rooms = [r for r in rooms if r["type"] != overrides["drop_type"]]
    return rooms


def _housegan_plan(program, rooms, src_w=80.0, src_h=60.0):
    return {
        "generator": "moe+housegan",
        "totalWidth": src_w,
        "totalHeight": src_h,
        "rooms": rooms,
    }


def test_moe_zone_fallback_is_not_a_hint():
    env, program = _prog()
    plan = {
        "generator": "moe",
        "totalWidth": 40,
        "totalHeight": 40,
        "rooms": _rooms_for(program),
    }
    attempt = hints_from_ai_candidate({"plans": [plan]}, program, env)
    assert attempt.used is False
    assert attempt.hints is None
    assert attempt.reason == "not_housegan_candidate"


def test_empty_moe_is_not_a_hint():
    env, program = _prog()
    attempt = hints_from_ai_candidate({"plans": []}, program, env)
    assert attempt.used is False
    assert attempt.hints is None


def test_missing_office_rejected():
    env, program = _prog()
    rooms = _rooms_for(program, drop_type="home_office")
    attempt = hints_from_ai_candidate(
        {"plans": [_housegan_plan(program, rooms)]}, program, env,
    )
    assert attempt.hints is None
    assert attempt.reason == "type_multiset_mismatch"


def test_extra_pantry_rejected():
    env, program = _prog()
    rooms = _rooms_for(program, extra={"type": "pantry", "x": 0, "y": 0, "width": 5, "height": 5})
    attempt = hints_from_ai_candidate(
        {"plans": [_housegan_plan(program, rooms)]}, program, env,
    )
    assert attempt.hints is None
    assert attempt.reason == "type_multiset_mismatch"


def test_nan_and_zero_size_rejected():
    env, program = _prog()
    rooms = _rooms_for(program)
    rooms[0]["x"] = float("nan")
    attempt = hints_from_ai_candidate(
        {"plans": [_housegan_plan(program, rooms)]}, program, env,
    )
    assert attempt.hints is None
    assert attempt.reason == "non_finite_or_non_positive_box"

    rooms = _rooms_for(program)
    rooms[0]["width"] = 0
    attempt = hints_from_ai_candidate(
        {"plans": [_housegan_plan(program, rooms)]}, program, env,
    )
    assert attempt.hints is None
    assert attempt.reason == "non_finite_or_non_positive_box"


def test_valid_housegan_maps_one_to_one_and_scales():
    env, program = _prog()
    rooms = _rooms_for(program)
    src_w, src_h = 80.0, 40.0
    attempt = hints_from_ai_candidate(
        {"plans": [_housegan_plan(program, rooms, src_w, src_h)]}, program, env,
    )
    assert attempt.used is True
    assert attempt.hints is not None
    assert set(attempt.hints) == {spec.id for spec in program.rooms}
    assert attempt.conversion is not None
    assert attempt.conversion.scale_x == env.width / src_w
    assert attempt.conversion.scale_y == env.depth / src_h
    for spec in program.rooms:
        x, y, w, h = attempt.hints[spec.id]
        assert w >= 1 and h >= 1
        assert x >= 0 and y >= 0
        assert x + w <= env.width
        assert y + h <= env.depth


def test_compete_uses_spatial_candidates_and_one_hint_variant(monkeypatch):
    """HouseGAN/MOE boxes are one extra candidate, not applied to every strategy.

    Applying the same hint to all five strategies was a cartesian product that
    ignored fallback topology. Spatial strategies remain unevaluated against
    AI boxes; one hint pass is appended.
    """
    env, program = _prog()
    fake_hints = {spec.id: (1, 1, spec.min_width, spec.min_depth) for spec in program.rooms}
    seen: list = []

    def fake_eval(program, envelope, spatial, mass, use_clusters=True, time_limit_s=8.0, hints=None, **kwargs):
        from solver.strategy_competition import StrategyEvaluation
        seen.append((spatial.strategy.name, hints, kwargs.get("source")))
        return StrategyEvaluation(strategy=spatial.strategy.name, valid=False)

    monkeypatch.setattr("solver.strategy_competition.evaluate_strategy", fake_eval)
    winner, evals = compete(program, env, None, hints=fake_hints, time_limit_s=1)
    assert winner is None
    spatial_seen = [(n, h) for n, h, src in seen if src == "spatial" or (src is None and h is None)]
    # First N calls are spatial without hints; last is the hint variant.
    assert [n for n, h, _src in seen[:5]] == list(COMPETITION_STRATEGIES)
    assert all(h is None for _n, h, _src in seen[:5])
    assert seen[-1][1] is fake_hints
    assert seen[-1][2] == "housegan"
    assert len(evals) == 6


def test_infeasible_hints_retry_without_hints(monkeypatch):
    env, program = _prog()
    spatial = plan(program)
    fake_hints = {spec.id: (0, 0, spec.min_width, spec.min_depth) for spec in program.rooms}
    calls: list = []
    dummy_layout = Layout(
        rooms=[
            PlacedRoom(
                id=spec.id, type=spec.type, name=spec.name,
                x=0, y=0, width=spec.min_width, depth=spec.min_depth, zone=spec.zone,
            )
            for spec in program.rooms
        ],
        envelope=env,
    )

    def fake_solve(program, envelope, hints=None, time_limit_s=8.0, **kwargs):
        calls.append({"hints": hints, "clusters": kwargs.get("use_clusters")})
        if hints:
            return SolveResult(status="infeasible", validated=False, reason="hint conflict")
        return SolveResult(status="valid", validated=True, layout=dummy_layout)

    monkeypatch.setattr("solver.strategy_competition.solve", fake_solve)
    ev = evaluate_strategy(
        program, env, spatial, None,
        use_clusters=True, time_limit_s=1, hints=fake_hints,
    )
    assert ev.valid is True
    assert any(c["hints"] is fake_hints for c in calls)
    assert any(c["hints"] is None for c in calls)
