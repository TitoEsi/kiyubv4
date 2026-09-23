"""20x30 m generation upgrade regression. Not professional architectural approval."""

from __future__ import annotations

from solver.pipeline import refine_generation
from solver.quality import score_layout
from solver.room_program import envelope_from_constraints, from_constraints
from solver.room_rules import BEDROOM_TYPES, aspect_ratio
from solver.solver import solve
from solver.spatial_planner import plan
from solver.validator import validate


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


def test_live_20x30_generates_valid_plan_with_diagnostics():
    env = envelope_from_constraints(LIVE)
    program = from_constraints(LIVE, env)
    spatial = plan(program)
    result = solve(
        program, env, time_limit_s=15,
        spatial_plan=spatial, flexible=False,
    )
    assert result.status == "valid", result.reason
    assert result.validated
    assert result.layout
    assert result.layout.envelope.lot_width_ft == env.lot_width_ft
    assert result.layout.envelope.lot_depth_ft == env.lot_depth_ft
    report = validate(result.layout, program)
    assert report.valid, [e.message for e in report.errors]
    q = result.quality_score or score_layout(result.layout, program, spatial)
    assert q.get("diagnostics")
    cats = q["categories"]
    assert "room_proportion" in cats
    assert "daylight_potential" in cats
    assert "service_efficiency" in cats
    assert "site_utilization" in cats
    beds = [r for r in result.layout.rooms if r.type in BEDROOM_TYPES]
    assert len(beds) == 3
    for bed in beds:
        assert aspect_ratio(bed.width, bed.depth) <= 2.8
        assert bed.width >= 9 and bed.depth >= 9 or min(bed.width, bed.depth) >= 9
    for r in result.layout.rooms:
        assert r.x >= 0 and r.y >= 0
        assert r.x2 <= env.width
        assert r.y2 <= env.depth


def test_refine_generation_exposes_candidates_and_debug_fields():
    moe = {"plans": [], "expert_weights": {}, "confidence": 0, "irc_compliant": False}
    result = refine_generation(LIVE, moe)
    assert result["status"] in ("valid", "infeasible", "generation_error")
    if result["status"] != "valid":
        return
    assert result["plans"]
    plan0 = result["plans"][0]
    assert plan0["rooms"]
    assert result.get("strategy_evaluations")
    assert result.get("quality_score")
    q = result["quality_score"]
    assert q.get("diagnostics")
    assert "not professional" in (q.get("note") or "").lower()
    env = envelope_from_constraints(LIVE)
    assert abs(plan0["totalWidth"] - env.width) < env.width  # footprint inside envelope
    xs = [r["x"] + r["width"] for r in plan0["rooms"]]
    ys = [r["y"] + r["height"] for r in plan0["rooms"]]
    assert max(xs) <= env.width + 1
    assert max(ys) <= env.depth + 1
