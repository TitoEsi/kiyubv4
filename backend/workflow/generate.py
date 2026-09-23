"""Call the existing MOE + refine pipeline. Do not replace /api/generate/moe."""
from __future__ import annotations

import os
import time
from typing import Any


def _stub_plan(idx: int) -> dict[str, Any]:
    return {
        "id": f"stub-{idx}",
        "name": f"Candidate {chr(65 + idx)}",
        "totalWidth": 40,
        "totalHeight": 30,
        "ceilingHeight": 9,
        "rooms": [
            {
                "id": f"living-{idx}",
                "name": "Living",
                "type": "living_room",
                "x": 0,
                "y": 0,
                "width": 18,
                "height": 14,
            },
            {
                "id": f"kitchen-{idx}",
                "name": "Kitchen",
                "type": "kitchen",
                "x": 18,
                "y": 0,
                "width": 12,
                "height": 12,
            },
        ],
        "walls": [],
        "doors": [],
        "windows": [],
        "stairs": [],
        "metadata": {"source": "workflow_stub", "generator": "stub"},
        "envelope": {"width": 40, "depth": 30},
    }


def brief_to_constraints(questionnaire: dict, specification: dict | None = None) -> dict:
    spec = specification or {}
    site = spec.get("site") or {}
    building = spec.get("building") or {}
    features = spec.get("features") or {}
    q = questionnaire or {}
    qsite = q.get("site") or {}
    house = q.get("house") or {}
    spaces = q.get("spaces") or {}
    prefs = q.get("preferences") or {}
    return {
        "lotShape": site.get("shape") or qsite.get("lotShape") or "rectangle",
        "lotWidth": float(site.get("width") or qsite.get("lotWidth") or 20),
        "lotDepth": float(site.get("depth") or qsite.get("lotDepth") or 30),
        "bedrooms": int(building.get("bedrooms") or house.get("bedrooms") or 3),
        "bathrooms": int(building.get("bathrooms") or house.get("bathrooms") or 2),
        "sqft": int(building.get("livingAreaSqft") or house.get("livingAreaSqft") or 1800),
        "stories": int(building.get("floors") or house.get("floors") or 1),
        "style": spec.get("style") or prefs.get("style") or "modern",
        "openPlan": bool(features.get("openPlan", prefs.get("openPlan", False))),
        "primarySuite": bool(features.get("primarySuite", prefs.get("primarySuite", True))),
        "homeOffice": bool(features.get("homeOffice", spaces.get("homeOffice", False))),
        "formalDining": bool(features.get("formalDining", prefs.get("formalDining", False))),
        "garage": features.get("garage") or spaces.get("garage") or "2car",
        "laundry": features.get("laundry") or spaces.get("laundry") or "room",
        "outdoor": features.get("outdoor") or spaces.get("outdoor") or "patio",
        "ceilingHeight": features.get("ceilingHeight") or prefs.get("ceilingHeight") or "standard",
    }


def run_generation(constraints: dict, num_variants: int = 3) -> dict:
    """Same internals as POST /api/generate/moe without replacing that route."""
    if os.environ.get("KIYUB_WORKFLOW_STUB_GENERATE") == "1":
        plans = [_stub_plan(i) for i in range(num_variants)]
        return {"status": "valid", "plans": plans, "validated": True}

    from moe.inference import LotConstraintError, predict_floor_plan
    from solver.pipeline import refine_generation
    from solver.room_program import envelope_from_constraints

    try:
        t_moe = time.perf_counter()
        moe = predict_floor_plan(constraints, num_variants=num_variants)
        moe_s = round(time.perf_counter() - t_moe, 3)
    except LotConstraintError:
        try:
            envelope_from_constraints(constraints)
        except LotConstraintError:
            raise
        moe = {"plans": [], "expert_weights": {}, "confidence": 0, "irc_compliant": False}
        moe_s = 0.0

    result = refine_generation(constraints, moe)
    result["applied_constraints"] = constraints
    result.setdefault("generation_debug", {})
    result["generation_debug"]["timings"] = {
        "buildify_moe_s": moe_s,
        "refine_generation_s": None,
    }
    return result
