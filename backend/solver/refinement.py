"""Bounded post-solve refinement. Keep the best valid candidate.

Deterministic. No LLM. Not professional architectural approval.
"""

from __future__ import annotations

import os
from dataclasses import replace

from .building_mass import BuildingMass
from .models import Envelope, RoomProgram, RoomSpec
from .solver import solve
from .spatial_plan import SpatialPlan


def refinement_iters() -> int:
    try:
        return max(0, min(3, int(os.environ.get("KIYUB_REFINEMENT_ITERS", "2"))))
    except (TypeError, ValueError):
        return 2


def needs_refine(quality: dict | None) -> bool:
    if not quality:
        return False
    d = quality.get("diagnostics") or {}
    if d.get("cramped_rooms") or d.get("poor_aspect_ratios"):
        return True
    if (quality.get("furniture_clearance_score") or 100) < 55:
        return True
    cats = quality.get("categories") or {}
    if (cats.get("circulation") or 100) < 45:
        return True
    if (cats.get("room_proportion") or 100) < 55:
        return True
    return False


def _bump_spec(spec: RoomSpec) -> RoomSpec:
    mw = min(spec.preferred_width, spec.min_width + 1)
    md = min(spec.preferred_depth, spec.min_depth + 1)
    return replace(spec, min_width=max(spec.min_width, mw), min_depth=max(spec.min_depth, md))


def bump_program(program: RoomProgram, diagnostics: dict) -> RoomProgram:
    flagged = set(diagnostics.get("cramped_rooms") or [])
    flagged.update(diagnostics.get("poor_aspect_ratios") or [])
    rooms: list[RoomSpec] = []
    for spec in program.rooms:
        if spec.id in flagged or spec.name in flagged:
            rooms.append(_bump_spec(spec))
        else:
            rooms.append(spec)
    return replace(program, rooms=rooms)


def refine_result(
    result,
    program: RoomProgram,
    envelope: Envelope,
    spatial: SpatialPlan | None,
    mass: BuildingMass | None,
    use_clusters: bool,
    time_limit_s: float,
    hints: dict | None = None,
    max_iters: int | None = None,
) -> tuple:
    """Re-solve the same strategy with tighter mins. Returns (best_result, trace)."""
    iters = refinement_iters() if max_iters is None else max(0, max_iters)
    best = result
    best_score = (result.quality_score or {}).get("overall") or 0
    trace = []
    current_program = program
    for i in range(iters):
        q = best.quality_score or {}
        if not needs_refine(q):
            break
        bumped = bump_program(current_program, q.get("diagnostics") or {})
        if bumped.rooms == current_program.rooms:
            break
        nxt = solve(
            bumped, envelope, hints=hints, time_limit_s=time_limit_s,
            spatial_plan=spatial, building_mass=mass, use_clusters=use_clusters,
        )
        score = (nxt.quality_score or {}).get("overall") if nxt.status == "valid" else -1
        trace.append({
            "iteration": i + 1,
            "status": nxt.status,
            "score": score,
            "kept": bool(nxt.status == "valid" and nxt.validated and (score or 0) >= best_score),
        })
        if nxt.status == "valid" and nxt.validated and (score or 0) >= best_score:
            best = nxt
            best_score = score or 0
            current_program = bumped
        else:
            break
    return best, trace
