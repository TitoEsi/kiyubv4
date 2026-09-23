"""Multi-strategy competition tests. Not professional architectural approval."""

from __future__ import annotations

from solver.building_mass import plan_building_mass
from solver.room_program import envelope_from_constraints, from_constraints
from solver.room_rules import BEDROOM_TYPES
from solver.spatial_planner import (
    COMPETITION_STRATEGIES,
    generate_strategy_candidates,
    plan,
    strategy_fingerprint,
)
from solver.strategy_competition import (
    StrategyEvaluation,
    compete,
    select_evaluation,
)


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


def test_all_five_strategies_generated():
    _, program = _live()
    cands = generate_strategy_candidates(program)
    names = [c.strategy.name for c in cands]
    assert names[:len(COMPETITION_STRATEGIES)] == list(COMPETITION_STRATEGIES)
    assert names[:5] == [
        "patio_oriented", "central_spine", "linear", "service_side", "cluster",
    ]
    assert "rear_private" in names
    assert "living_core" in names


def test_strategies_have_distinct_preferences():
    _, program = _live()
    cands = generate_strategy_candidates(program)
    fps = [strategy_fingerprint(c) for c in cands]
    assert len(set(fps[:5])) == 5
    assert len(set(fps)) == len(fps)
    by_name = {c.strategy.name: c for c in cands}
    patio_pub = next(cl for cl in by_name["patio_oriented"].clusters if cl.id == "public")
    spine_pub = next(cl for cl in by_name["central_spine"].clusters if cl.id == "public")
    assert patio_pub.cy_frac != spine_pub.cy_frac
    cluster = by_name["cluster"]
    assert max(cl.cohesion_weight for cl in cluster.clusters) >= 4
    linear_service = next(cl for cl in by_name["linear"].clusters if cl.id == "service")
    side_service = next(cl for cl in by_name["service_side"].clusters if cl.id == "service")
    assert linear_service.band and linear_service.band.axis == "y"
    assert side_service.band and side_service.band.axis == "x"


def test_strategy_generation_is_deterministic():
    _, program = _live()
    a = generate_strategy_candidates(program)
    b = generate_strategy_candidates(program)
    assert [strategy_fingerprint(c) for c in a] == [strategy_fingerprint(c) for c in b]


def test_infeasible_candidate_is_not_selected():
    good = StrategyEvaluation(strategy="linear", valid=True, quality_score=70, residual_area=100, mass_occupancy=0.7, room_usability_score=90, circulation_clearance=80)
    bad = StrategyEvaluation(strategy="patio_oriented", valid=False, quality_score=99, residual_area=0, mass_occupancy=1.0)
    winner = select_evaluation([bad, good])
    assert winner is not None
    assert winner.strategy == "linear"


def test_selection_is_deterministic_and_uses_quality():
    a = StrategyEvaluation(strategy="patio_oriented", valid=True, quality_score=80, residual_area=200, mass_occupancy=0.7, room_usability_score=90, circulation_clearance=80)
    b = StrategyEvaluation(strategy="central_spine", valid=True, quality_score=85, residual_area=300, mass_occupancy=0.6, room_usability_score=70, circulation_clearance=70)
    c = StrategyEvaluation(strategy="linear", valid=True, quality_score=80, residual_area=150, mass_occupancy=0.7, room_usability_score=90, circulation_clearance=80)
    winner = select_evaluation([a, b, c])
    assert winner is not None
    assert winner.strategy == "central_spine"
    tied = select_evaluation([a, c])
    assert tied is not None
    assert tied.strategy == "linear"


def test_invalid_candidates_never_selected():
    evals = [
        StrategyEvaluation(strategy=n, valid=False, quality_score=100)
        for n in COMPETITION_STRATEGIES
    ]
    assert select_evaluation(evals) is None


def test_live_competition_preserves_program_and_metrics():
    env, program = _live()
    spatial = plan(program)
    mass = plan_building_mass(program, env, spatial)
    winner, evals = compete(program, env, mass, use_clusters=True, time_limit_s=8)
    assert len(evals) == 5
    assert any(e.valid for e in evals)
    assert winner is not None
    assert winner.valid
    assert winner.strategy in COMPETITION_STRATEGIES
    assert winner.result and winner.result.status == "valid"
    assert winner.result.validated is True
    q = winner.result.quality_score
    assert q
    assert q.get("mass_fill")
    fill = q["mass_fill"]
    mass_area = fill["mass_area"]
    if fill.get("exterior_cells_in_mass", 0) == 0 and mass_area:
        assert mass_area == (
            fill["room_cells_in_mass"]
            + fill["circulation_cells_in_mass"]
            + fill["building_residual_area"]
        )
    for ev in evals:
        if not ev.valid or not ev.result or not ev.result.layout:
            continue
        rooms = ev.result.layout.rooms
        beds = [r for r in rooms if r.type in BEDROOM_TYPES]
        assert len(beds) == program.bedrooms_requested
        assert any(r.type == "garage" for r in rooms)
        assert any(r.type == "patio" for r in rooms)
        assert ev.result.layout.envelope
        assert ev.result.layout.envelope.width == env.width
        assert ev.result.layout.envelope.depth == env.depth
    assert winner.residual_area is not None
    assert winner.mass_occupancy is not None
    assert "room_usability_score" in q
    assert q.get("categories", {}).get("mass_occupancy") is not None
    assert q.get("categories", {}).get("dead_space") is not None
    assert "not professional" in q["note"].lower()
