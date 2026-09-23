"""Hybrid pipeline: MOE/HouseGAN proposes, OR-Tools constrains, validator verifies."""

from __future__ import annotations

import os
import time
import traceback

from .adapter import hints_from_moe_plan, layout_to_floorplan
from .ai_hints import hints_from_ai_candidate
from .architectural_program import from_room_program, validate_program
from .diagnostics import (
    classify_infeasibility,
    dump_live_constraints,
    log_constraints,
    log_envelope,
    log_room_program,
    log_topology,
)
from .building_mass import log_building_mass, plan_building_mass
from .models import SolveResult
from .refinement import refine_result
from .room_program import envelope_from_constraints, from_constraints
from .solver import solve
from .spatial_planner import log_spatial_plan, plan as build_spatial_plan
from .strategy_competition import compete


def _ceil_ft(constraints: dict) -> int:
    return {"standard": 9, "high": 10, "vaulted": 12}.get(
        constraints.get("ceilingHeight", "standard"), 9
    )


def _empty(
    status: str,
    reason: str,
    moe: dict,
    errors: list | None = None,
    reason_code: str = "",
    conflicts: list | None = None,
) -> dict:
    return {
        "plans": [],
        "status": status,
        "validated": False,
        "reason": reason,
        "reason_code": reason_code,
        "conflicts": conflicts or [],
        "validation_errors": errors or [],
        "expert_weights": moe.get("expert_weights") or {},
        "confidence": moe.get("confidence", 0),
        "irc_compliant": False,
        "quality_score": None,
        "selected_strategy": None,
        "strategy_evaluations": [],
        "ai_hints_used": False,
        "ai_hints_reason": "",
    }


def refine_generation(constraints: dict, moe_result: dict | None = None) -> dict:
    moe = moe_result or {
        "plans": [],
        "expert_weights": {},
        "confidence": 0,
        "irc_compliant": False,
    }
    mode = os.environ.get("KIYUB_SOLVER_MODE", "hybrid").strip().lower()
    allow_fallback = os.environ.get("KIYUB_ORTOOLS_FALLBACK", "") == "1"
    ceiling = _ceil_ft(constraints)

    dump_live_constraints(constraints)
    log_constraints(constraints)

    if mode == "buildify":
        plans = list(moe.get("plans") or [])
        return {
            "plans": plans,
            "status": "fallback",
            "validated": False,
            "reason": "Buildify mode: OR-Tools refinement skipped (development).",
            "reason_code": "",
            "conflicts": [],
            "validation_errors": [],
            "expert_weights": moe.get("expert_weights") or {},
            "confidence": moe.get("confidence", 0),
            "irc_compliant": False,
        }

    try:
        envelope = envelope_from_constraints(constraints)
        program = from_constraints(constraints, envelope)
    except Exception as exc:
        print(f"[OR-TOOLS] generation_error: {exc}")
        return _empty(
            "generation_error",
            "Could not build a room program from the project requirements.",
            moe,
            reason_code="OTHER",
        )

    log_envelope(constraints, envelope)
    log_room_program(program, envelope)
    log_topology(program)
    arch = from_room_program(program)
    program_validation = validate_program(arch, envelope).as_dict()
    program_summary = arch.as_dict()

    spatial = None
    use_planner = os.environ.get("KIYUB_SPATIAL_PLANNER", "1").strip() != "0"
    if use_planner:
        spatial = build_spatial_plan(program)
        log_spatial_plan(spatial)

    mass = None
    use_mass = os.environ.get("KIYUB_BUILDING_MASS", "1").strip() != "0"
    if use_mass:
        mass = plan_building_mass(program, envelope, spatial)
        log_building_mass(mass)

    use_clusters = os.environ.get("KIYUB_CLUSTERS", "1").strip() != "0"
    use_multi = os.environ.get("KIYUB_MULTI_STRATEGY", "1").strip() != "0" and use_planner
    hint_attempt = hints_from_ai_candidate(moe, program, envelope)
    extra_hints = None
    extra_source = "moe_fallback"
    if not hint_attempt.used:
        moe_plans = list(moe.get("plans") or [])
        if moe_plans:
            extra_hints = hints_from_moe_plan(moe_plans[0], program) or None
            if extra_hints:
                extra_source = "moe_fallback"
    print(
        f"[KIYUB FLEX] KIYUB_FLEXIBLE_GEOMETRY="
        f"{os.environ.get('KIYUB_FLEXIBLE_GEOMETRY', '0')}"
    )
    print(f"[KIYUB AI HINTS] used={hint_attempt.used} reason={hint_attempt.reason}")

    timings: dict[str, float] = {}
    refinement_trace: list = []

    def _success(result: SolveResult, selected: str | None, evals: list, source: str = "spatial") -> dict:
        plans = [layout_to_floorplan(result.layout, name="KIYUB Plan", ceiling=ceiling)]
        access = None
        win_spatial = spatial
        for ev in evals:
            if getattr(ev, "strategy", None) == selected and getattr(ev, "spatial", None) is not None:
                win_spatial = ev.spatial
                break
        if win_spatial and getattr(win_spatial, "access", None) is not None:
            access = win_spatial.access.as_dict()
        planning = (result.quality_score or {}).get("planning")
        q = result.quality_score or {}
        ruleset_payload = None
        if result.layout:
            from .ruleset import default_ruleset
            rs = default_ruleset()
            ruleset_payload = rs.as_dict(rs.evaluate(result.layout, program))
        from .topology import build_topology
        return {
            "plans": plans,
            "status": "valid",
            "validated": True,
            "reason": "",
            "reason_code": "",
            "conflicts": [],
            "validation_errors": [],
            "expert_weights": moe.get("expert_weights") or {},
            "confidence": moe.get("confidence", 0),
            "irc_compliant": False,
            "quality_score": result.quality_score,
            "selected_strategy": selected,
            "selected_source": source,
            "strategy_evaluations": [e.as_dict() for e in evals],
            "planning": planning,
            "access": access,
            "ai_hints_used": hint_attempt.used,
            "ai_hints_reason": hint_attempt.reason,
            "refinement": refinement_trace,
            "timings": timings,
            "diagnostics": q.get("diagnostics"),
            "winner": selected,
            "program": program_summary,
            "program_validation": program_validation,
            "topology_count": len(build_topology(program)),
            "circulation_ratio": q.get("circulation_ratio"),
            "ruleset": ruleset_payload,
        }

    results: list[SolveResult] = []
    strategy_evals: list = []
    selected_strategy = spatial.strategy.name if spatial else None
    try:
        if use_multi:
            t0 = time.perf_counter()
            winner, strategy_evals = compete(
                program, envelope, mass,
                use_clusters=use_clusters, time_limit_s=8,
                hints=hint_attempt.hints if hint_attempt.used else None,
                extra_hints=extra_hints,
                extra_source=extra_source,
            )
            timings["ortools_compete_s"] = round(time.perf_counter() - t0, 3)
            if winner and winner.result and winner.result.layout:
                t1 = time.perf_counter()
                refined, refinement_trace = refine_result(
                    winner.result, program, envelope, winner.spatial, mass,
                    use_clusters=use_clusters, time_limit_s=8,
                    hints=winner.hints,
                )
                timings["refinement_s"] = round(time.perf_counter() - t1, 3)
                winner.result = refined
                return _success(
                    winner.result, winner.strategy, strategy_evals,
                    source=winner.source,
                )
            print("[KIYUB] All strategies infeasible; using existing mass/spatial fallback")
        elif mode == "hybrid":
            for moe_plan in moe.get("plans") or []:
                results.append(
                    solve(
                        program,
                        envelope,
                        hints=hints_from_moe_plan(moe_plan, program),
                        time_limit_s=8,
                        spatial_plan=spatial,
                        building_mass=mass,
                        use_clusters=use_clusters,
                    )
                )
                if results[-1].status == "valid":
                    break
        if not any(r.status == "valid" for r in results):
            results.append(
                solve(
                    program, envelope, hints=None, time_limit_s=10,
                    spatial_plan=spatial, building_mass=mass, use_clusters=use_clusters,
                )
            )
        if use_clusters and not any(r.status == "valid" for r in results):
            print("[KIYUB CLUSTER] infeasible with cluster guidance; retrying without cluster terms")
            results.append(
                solve(
                    program, envelope, hints=None, time_limit_s=10,
                    spatial_plan=spatial, building_mass=mass, use_clusters=False,
                )
            )
        if mass and not any(r.status == "valid" for r in results):
            print("[KIYUB MASS] infeasible with BuildingMass; retrying without mass")
            results.append(
                solve(
                    program, envelope, hints=None, time_limit_s=10,
                    spatial_plan=spatial, building_mass=None, use_clusters=False,
                )
            )
        if spatial and not any(r.status == "valid" for r in results):
            print("[KIYUB SPATIAL] infeasible with SpatialPlan; retrying without planner")
            results.append(
                solve(
                    program, envelope, hints=None, time_limit_s=10,
                    spatial_plan=None, use_clusters=False,
                )
            )
    except Exception as exc:
        traceback.print_exc()
        print(f"[OR-TOOLS] generation_error: {exc}")
        return _empty(
            "generation_error",
            "Layout solver failed unexpectedly. The generation engine did not produce a validated plan.",
            moe,
            reason_code="OTHER",
        )

    valid = [r for r in results if r.status == "valid" and r.layout]
    if valid:
        return _success(valid[0], selected_strategy, strategy_evals)

    last = results[-1] if results else None
    reason = (last.reason if last else "No feasible layout found.") or "No feasible layout found."
    reason_code = last.reason_code if last else "OTHER"
    conflicts = list(last.conflicts) if last else []
    errors = []
    if last and last.validation:
        errors = [e.as_dict() for e in last.validation.errors]

    if last and last.status == "infeasible" and reason_code in ("", "OTHER"):
        reason_code, conflicts, reason = classify_infeasibility(program, envelope)

    if allow_fallback and (moe.get("plans") or []):
        print("[OR-TOOLS] Using unvalidated MOE fallback (KIYUB_ORTOOLS_FALLBACK=1)")
        return {
            "plans": moe["plans"],
            "status": "fallback",
            "validated": False,
            "reason": reason,
            "reason_code": reason_code,
            "conflicts": conflicts,
            "validation_errors": errors,
            "expert_weights": moe.get("expert_weights") or {},
            "confidence": moe.get("confidence", 0),
            "irc_compliant": False,
            "selected_strategy": selected_strategy,
            "strategy_evaluations": [e.as_dict() for e in strategy_evals],
        }

    return _empty("infeasible", reason, moe, errors, reason_code, conflicts)
