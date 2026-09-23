"""Logging and infeasibility classification for the OR-Tools solver.

Diagnostic ablation flags must not be used to silently weaken production
constraints. The default generation path keeps adjacency, garage, patio,
and room counts as requested.
"""

from __future__ import annotations

import json
from pathlib import Path

from .envelope import (
    METERS_TO_FEET,
    SETBACK_FRONT_FT,
    SETBACK_REAR_FT,
    SETBACK_SIDE_FT,
)
from .models import Envelope, RoomProgram, TopologyEdge
from .topology import build_topology

LAST_CONSTRAINTS_PATH = Path(__file__).resolve().parent / "tests" / "_last_live_constraints.json"

REASON_CODES = (
    "ROOM_AREA",
    "MIN_DIMENSIONS",
    "ADJACENCY",
    "CIRCULATION",
    "EXTERIOR_ACCESS",
    "OTHER",
)


def dump_live_constraints(constraints: dict) -> None:
    LAST_CONSTRAINTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAST_CONSTRAINTS_PATH.write_text(
        json.dumps(constraints, indent=2, default=str),
        encoding="utf-8",
    )


def load_live_constraints() -> dict | None:
    if not LAST_CONSTRAINTS_PATH.exists():
        return None
    return json.loads(LAST_CONSTRAINTS_PATH.read_text(encoding="utf-8"))


def min_area_sum(program: RoomProgram) -> int:
    return sum(spec.min_width * spec.min_depth for spec in program.rooms)


def log_constraints(constraints: dict) -> None:
    print("[KIYUB POST] applied_constraints")
    print(json.dumps(constraints, indent=2, default=str))


def log_envelope(constraints: dict, envelope: Envelope) -> None:
    try:
        lot_w_m = float(constraints.get("lotWidth", 0) or 0)
        lot_d_m = float(constraints.get("lotDepth", 0) or 0)
    except (TypeError, ValueError):
        lot_w_m = lot_d_m = 0.0
    lot_w_ft = envelope.lot_width_ft or lot_w_m * METERS_TO_FEET
    lot_d_ft = envelope.lot_depth_ft or lot_d_m * METERS_TO_FEET
    build_w_ft = envelope.buildable_width or float(envelope.width)
    build_d_ft = envelope.buildable_depth or float(envelope.depth)
    build_w_m = build_w_ft / METERS_TO_FEET
    build_d_m = build_d_ft / METERS_TO_FEET
    print("[KIYUB ENVELOPE]")
    print(
        f"  lot: {lot_w_m:g} m × {lot_d_m:g} m "
        f"({lot_w_ft:.2f} ft × {lot_d_ft:.2f} ft)"
    )
    print(
        f"  placeholder setbacks: side={SETBACK_SIDE_FT:g} ft "
        f"front={SETBACK_FRONT_FT:g} ft rear={SETBACK_REAR_FT:g} ft "
        "(conceptual, not Philippine building-code values)"
    )
    print(
        f"  buildable: {build_w_ft:.2f} ft × {build_d_ft:.2f} ft "
        f"({build_w_m:.2f} m × {build_d_m:.2f} m)"
    )
    print(
        f"  integer envelope: {envelope.width} ft × {envelope.depth} ft "
        f"= {envelope.area} sqft"
    )


def log_room_program(program: RoomProgram, envelope: Envelope) -> None:
    area = min_area_sum(program)
    print("[KIYUB ROOM PROGRAM]")
    print(
        f"  bedrooms_requested={program.bedrooms_requested} "
        f"bathrooms_requested={program.bathrooms_requested} "
        f"outdoor_requested={program.outdoor_requested} "
        f"rooms={len(program.rooms)}"
    )
    for spec in program.rooms:
        print(
            f"  {spec.id} {spec.type} {spec.name} "
            f"min {spec.min_width}×{spec.min_depth} ft "
            f"pref {spec.preferred_width}×{spec.preferred_depth} ft "
            f"zone={spec.zone}"
        )
    print(
        f"  min-area sum {area} sqft vs envelope {envelope.area} sqft "
        f"({'EXCEEDS' if area > envelope.area else 'fits-by-area'})"
    )


def log_topology(program: RoomProgram, edges: list[TopologyEdge] | None = None) -> None:
    topology = edges if edges is not None else build_topology(program)
    names = {r.id: r.name for r in program.rooms}
    hard = [e for e in topology if e.hard]
    soft = [e for e in topology if not e.hard]
    print("[KIYUB TOPOLOGY] hard")
    for e in hard:
        a = names.get(e.room_a, e.room_a)
        b = names.get(e.room_b, e.room_b)
        print(f"  {a} --{e.relation}-- {b}")
    print("[KIYUB TOPOLOGY] soft")
    for e in soft:
        a = names.get(e.room_a, e.room_a)
        b = names.get(e.room_b, e.room_b)
        print(f"  {a} --{e.relation}-- {b}")


def early_reason_code(reason: str) -> str:
    lower = reason.lower()
    if "cannot fit" in lower:
        return "MIN_DIMENSIONS"
    if "exceeds" in lower and "sqft" in lower:
        return "ROOM_AREA"
    return "OTHER"


def hard_edge_conflicts(program: RoomProgram, edges: list[TopologyEdge] | None = None) -> list[dict]:
    topology = edges if edges is not None else build_topology(program)
    names = {r.id: r.name for r in program.rooms}
    kinds = {"connected", "accessed_by", "outside_access", "adjacent"}
    return [
        {
            "type": "hard_adjacency",
            "room_a": names.get(e.room_a, e.room_a),
            "room_b": names.get(e.room_b, e.room_b),
            "relation": e.relation,
        }
        for e in topology
        if e.hard and e.relation in kinds
    ]


def _cpsat_found_layout(result) -> bool:
    return result.status == "valid" or result.layout is not None


def classify_infeasibility(
    program: RoomProgram,
    envelope: Envelope,
    time_limit_s: float = 5.0,
) -> tuple[str, list[dict], str]:
    """Ablate adjacency / outdoor pin / packing to name the bottleneck."""
    from .solver import _early_infeasible, solve

    early = _early_infeasible(program, envelope)
    if early:
        code = early_reason_code(early)
        return code, [{"type": code.lower(), "message": early}], early

    packing = solve(
        program,
        envelope,
        hints=None,
        time_limit_s=time_limit_s,
        require_adjacency=False,
        use_objective=False,
        classify=False,
    )
    if _cpsat_found_layout(packing):
        conflicts = hard_edge_conflicts(program)
        msg = (
            "Hard wall-share adjacency makes the program infeasible; "
            "packing without adjacency is feasible."
        )
        from .topology import hard_unconditional_pairs
        topology = build_topology(program)
        types = {r.id: r.type for r in program.rooms}
        hard_pairs = {
            tuple(sorted((types.get(a, a), types.get(b, b))))
            for a, b in hard_unconditional_pairs(topology)
        }
        if ("living_room", "patio") in hard_pairs or ("patio", "living_room") in hard_pairs:
            msg += (
                " A rear-pinned patio cannot share a wall with the living room "
                "while the foyer is pinned to the front edge — the living room "
                "max size is much smaller than the lot depth."
            )
        return "ADJACENCY", conflicts, msg

    circulation = solve(
        program,
        envelope,
        hints=None,
        time_limit_s=time_limit_s,
        require_adjacency=False,
        use_objective=False,
        pin_entry_outdoor=False,
        outdoor_in_overlap=True,
        classify=False,
    )
    if _cpsat_found_layout(circulation):
        return (
            "CIRCULATION",
            [{"type": "entry_or_outdoor_pin", "message": "foyer y==0 or patio rear pin"}],
            "Foyer front-edge and/or outdoor rear-edge pins make packing infeasible.",
        )

    exterior = solve(
        program,
        envelope,
        hints=None,
        time_limit_s=time_limit_s,
        require_adjacency=False,
        use_objective=False,
        pin_entry_outdoor=False,
        outdoor_in_overlap=False,
        classify=False,
    )
    if _cpsat_found_layout(exterior):
        return (
            "EXTERIOR_ACCESS",
            [{"type": "patio_in_envelope", "message": "patio packed inside envelope with rear pin"}],
            "Patio/deck occupancy inside the interior envelope makes packing infeasible.",
        )

    return (
        "OTHER",
        [{"type": "packing", "message": packing.reason or "no-overlap packing infeasible"}],
        packing.reason
        or "requested program exceeds available envelope or adjacency constraints",
    )
