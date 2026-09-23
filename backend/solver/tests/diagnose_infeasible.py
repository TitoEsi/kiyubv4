"""
Ablation matrix for the current questionnaire OR-Tools infeasibility.

Does not permanently drop garage/patio/office/adjacency/zoning.
Does not silently reduce bedrooms in the production path.

Usage (from backend/):
    .venv\\Scripts\\python.exe -m solver.tests.diagnose_infeasible
"""

from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

# Allow `python solver/tests/diagnose_infeasible.py` from backend/
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from solver.diagnostics import (  # noqa: E402
    dump_live_constraints,
    load_live_constraints,
    log_envelope,
    log_room_program,
    log_topology,
    min_area_sum,
)
from solver.room_program import envelope_from_constraints, from_constraints  # noqa: E402
from solver.solver import solve  # noqa: E402
from solver.topology import build_topology  # noqa: E402

# Questionnaire initial defaults (live form POST if the user did not change fields).
LIVE_QUESTIONNAIRE_DEFAULTS = {
    "lotShape": "rectangle",
    "lotWidth": 20,
    "lotDepth": 30,
    "bedrooms": 3,
    "bathrooms": 2,
    "sqft": 1800,
    "stories": 1,
    "style": "modern",
    "openPlan": False,
    "primarySuite": True,
    "homeOffice": False,
    "formalDining": False,
    "garage": "2car",
    "laundry": "room",
    "outdoor": "patio",
    "ceilingHeight": "standard",
}

TIME_LIMIT = 8.0


def _load_payload() -> tuple[dict, str]:
    captured = load_live_constraints()
    if captured:
        return captured, str(
            Path(__file__).resolve().parent / "_last_live_constraints.json"
        )
    dump_live_constraints(LIVE_QUESTIONNAIRE_DEFAULTS)
    return LIVE_QUESTIONNAIRE_DEFAULTS, "questionnaire defaults (no prior live POST dump)"


def _status(result) -> str:
    extra = f" code={result.reason_code}" if result.reason_code else ""
    if result.status == "valid":
        return f"FEASIBLE{extra}"
    if result.layout is not None:
        return f"CP-SAT_OK validator-fail{extra} - {result.reason}"
    return f"INFEASIBLE{extra} - {result.reason}"


def _run(label: str, constraints: dict, **solve_kw) -> dict:
    env = envelope_from_constraints(constraints)
    program = from_constraints(constraints, env)
    topology = solve_kw.pop("topology_edges", None)
    t0 = time.perf_counter()
    result = solve(
        program,
        env,
        hints=None,
        time_limit_s=solve_kw.pop("time_limit_s", TIME_LIMIT),
        topology_edges=topology,
        classify=False,
        **solve_kw,
    )
    elapsed = time.perf_counter() - t0
    line = f"{label}: {_status(result)} ({elapsed:.2f}s) rooms={len(program.rooms)}"
    print(line)
    return {
        "label": label,
        "status": result.status,
        "reason": result.reason,
        "reason_code": result.reason_code,
        "elapsed": round(elapsed, 2),
        "rooms": len(program.rooms),
        "feasible": result.status == "valid",
        "cp_sat": result.status == "valid" or result.layout is not None,
    }


def main() -> int:
    constraints, source = _load_payload()
    print("=" * 72)
    print("KIYUB OR-Tools infeasibility matrix")
    print(f"Payload source: {source}")
    print(json.dumps(constraints, indent=2, default=str))
    print("=" * 72)

    env = envelope_from_constraints(constraints)
    program = from_constraints(constraints, env)
    log_envelope(constraints, env)
    log_room_program(program, env)
    log_topology(program)
    print(
        f"min-area {min_area_sum(program)} sqft vs envelope {env.area} sqft "
        f"lot {constraints.get('lotWidth')}m x {constraints.get('lotDepth')}m"
    )
    print()

    rows: list[dict] = []

    print("--- A full current request (adjacency ON, objective ON) ---")
    rows.append(_run("A full", constraints, require_adjacency=True, use_objective=True))

    print("--- B no home office ---")
    if not constraints.get("homeOffice"):
        print("B skipped: home office already off in payload")
        rows.append({
            "label": "B no office",
            "status": "skipped",
            "reason": "homeOffice already false",
            "reason_code": "",
            "elapsed": 0,
            "rooms": len(program.rooms),
            "feasible": None,
            "cp_sat": None,
        })
    else:
        c = copy.deepcopy(constraints)
        c["homeOffice"] = False
        rows.append(_run("B no office", c))

    print("--- C garage none (keep other rooms) ---")
    c = copy.deepcopy(constraints)
    c["garage"] = "none"
    rows.append(_run("C garage none", c))

    print("--- D outdoor none ---")
    c = copy.deepcopy(constraints)
    c["outdoor"] = "none"
    rows.append(_run("D outdoor none", c))

    print("--- E primarySuite false ---")
    c = copy.deepcopy(constraints)
    c["primarySuite"] = False
    rows.append(_run("E no suite", c))

    print("--- F bedrooms - 1 (diagnostic only; production must not drop beds) ---")
    c = copy.deepcopy(constraints)
    c["bedrooms"] = max(1, int(c.get("bedrooms", 3)) - 1)
    rows.append(_run("F bedrooms-1", c))

    print("--- G same program, require_adjacency=False ---")
    rows.append(_run(
        "G no adjacency",
        constraints,
        require_adjacency=False,
        use_objective=True,
    ))

    print("--- H hard constraints only, no Minimize ---")
    rows.append(_run(
        "H no objective",
        constraints,
        require_adjacency=True,
        use_objective=False,
    ))

    print("--- Extra: drop only garage-mudroom edge ---")
    types = {r.id: r.type for r in program.rooms}

    def _pair_types(edge):
        return {types.get(edge.room_a), types.get(edge.room_b)}

    extra_topo = [
        e for e in build_topology(program)
        if not (e.relation == "connected" and _pair_types(e) == {"garage", "mudroom"})
    ]
    rows.append(_run(
        "X drop garage-mud edge",
        constraints,
        topology_edges=extra_topo,
    ))

    print("--- Extra: drop only living-patio outside_access edge ---")
    no_patio_edge = [
        e for e in build_topology(program)
        if e.relation != "outside_access"
    ]
    rows.append(_run(
        "X drop patio access edge",
        constraints,
        topology_edges=no_patio_edge,
    ))

    print("--- Extra: patio excluded from AddNoOverlap / rear pin (diagnostic) ---")
    rows.append(_run(
        "X patio outside overlap",
        constraints,
        pin_entry_outdoor=False,
        outdoor_in_overlap=False,
    ))

    print("--- Extra: packing only (no adj, no objective) ---")
    rows.append(_run(
        "X packing only",
        constraints,
        require_adjacency=False,
        use_objective=False,
    ))

    print()
    print("=" * 72)
    print("WITH vs WITHOUT adjacency")
    a = next(r for r in rows if r["label"] == "A full")
    g = next(r for r in rows if r["label"] == "G no adjacency")
    h = next(r for r in rows if r["label"] == "H no objective")
    print(f"  WITH adjacency (A):    {a['status']} {a['reason']}")
    print(f"  WITHOUT adjacency (G): {g['status']} {g['reason']}")
    print("WITH vs WITHOUT objective")
    print(f"  WITH objective (A):    {a['status']} {a['reason']}")
    print(f"  WITHOUT objective (H): {h['status']} {h['reason']}")
    print()
    print("Matrix")
    for r in rows:
        mark = "FEASIBLE" if r["feasible"] else ("SKIP" if r["feasible"] is None else "INFEASIBLE")
        print(f"  {r['label']:<28} {mark:<12} {r['elapsed']:>6}s  {r['reason']}")

    print()
    d = next(r for r in rows if r["label"] == "D outdoor none")
    c_row = next(r for r in rows if r["label"] == "C garage none")
    packing = next(r for r in rows if r["label"] == "X packing only")
    patio_edge = next((r for r in rows if r["label"] == "X drop patio access edge"), None)

    if a["feasible"]:
        bottleneck = "NONE - full request is feasible"
    elif (g["feasible"] or g.get("cp_sat")) and not a["feasible"] and not a.get("cp_sat"):
        bottleneck = (
            "ADJACENCY - packing works without hard wall-share; "
            "recommended production fix is access to hallway OR foyer, "
            "not every private room wall-sharing the hallway."
        )
    elif (d["feasible"] or d.get("cp_sat")) and not a.get("cp_sat"):
        bottleneck = (
            "EXTERIOR_ACCESS - patio-off is the flip; outdoor modeling, not lot area. "
            "Living cannot wall-share both front foyer and rear patio under the room max-size cap."
        )
    elif patio_edge and (patio_edge["feasible"] or patio_edge.get("cp_sat")) and not a.get("cp_sat"):
        bottleneck = (
            "EXTERIOR_ACCESS/ADJACENCY - dropping living-patio wall-share is the flip. "
            "Keep patio; do not require living to share a wall with both foyer and rear patio."
        )
    elif (c_row["feasible"] or c_row.get("cp_sat")) and not a.get("cp_sat"):
        bottleneck = "GARAGE - garage size/edge is the flip."
    elif packing["feasible"] is False and not packing.get("cp_sat"):
        area = min_area_sum(program)
        if area > env.area:
            bottleneck = "ROOM_AREA - min-area already exceeds envelope (genuine envelope)."
        else:
            bottleneck = (
                "OTHER packing - even packing without adjacency is infeasible. "
                "Not a silent 2-bed success case."
            )
    else:
        bottleneck = "OTHER - see matrix rows; do not drop bedrooms in production."

    print(f"BOTTLENECK: {bottleneck}")
    print("Production constraints were not permanently dropped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
