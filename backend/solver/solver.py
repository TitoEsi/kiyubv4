"""OR-Tools CP-SAT layout solve. Deterministic, time-limited, fail-closed."""

from __future__ import annotations

import os

from .constraints import (
    RoomVars,
    add_envelope_and_sizes,
    add_entry_and_outdoor,
    add_flexible_geometry,
    add_hallway_geometry_caps,
    add_no_overlap,
    add_topology_adjacency,
    add_vehicle_access,
)
from .diagnostics import classify_infeasibility, early_reason_code, hard_edge_conflicts
from .doors import place_doors
from .furniture import place_furniture
from .models import Envelope, FootprintPart, Layout, PlacedRoom, RoomFootprint, RoomProgram, SolveResult, TopologyEdge
from .building_mass import BuildingMass
from .objective import add_objective
from .quality import score_layout
from .spatial_plan import SpatialPlan
from .spatial_planner import avoid_topology_edges, preferred_topology_edges
from .topology import build_topology
from .validator import validate


def flexible_geometry_enabled(override: bool | None = None) -> bool:
    if override is not None:
        return override
    return os.environ.get("KIYUB_FLEXIBLE_GEOMETRY", "0").strip() not in ("", "0", "false", "False")


def _early_infeasible(program: RoomProgram, envelope: Envelope) -> str | None:
    area = 0
    for spec in program.rooms:
        mw, md = spec.min_width, spec.min_depth
        if min(mw, md) > max(envelope.width, envelope.depth):
            return (
                f"Room {spec.name} minimum {mw}×{md} ft cannot fit in "
                f"{envelope.width}×{envelope.depth} ft envelope."
            )
        if max(mw, md) > envelope.width and max(mw, md) > envelope.depth:
            return (
                f"Room {spec.name} minimum {mw}×{md} ft cannot fit in "
                f"{envelope.width}×{envelope.depth} ft envelope."
            )
        area += mw * md
    if area > envelope.area:
        return (
            f"Requested program ({area} sqft of prototype minima) exceeds "
            f"available envelope {envelope.width}×{envelope.depth} ft "
            f"({envelope.area} sqft)."
        )
    return None


def solve(
    program: RoomProgram,
    envelope: Envelope | None = None,
    hints: dict[str, tuple[int, int, int, int]] | None = None,
    time_limit_s: float = 10.0,
    require_adjacency: bool = True,
    use_objective: bool = True,
    pin_entry_outdoor: bool = True,
    outdoor_in_overlap: bool = True,
    topology_edges: list[TopologyEdge] | None = None,
    classify: bool = False,
    spatial_plan: SpatialPlan | None = None,
    building_mass: BuildingMass | None = None,
    use_clusters: bool = True,
    flexible: bool | None = None,
    _flex_fallback: bool = False,
) -> SolveResult:
    from ortools.sat.python import cp_model

    use_flex = flexible_geometry_enabled(flexible) and not _flex_fallback
    env = envelope or program.envelope
    print("[OR-TOOLS] Building room program")
    print(f"[OR-TOOLS] Rooms: {len(program.rooms)}")
    print(f"[OR-TOOLS] Buildable envelope: {env.width}ft x {env.depth}ft")
    print(
        f"[OR-TOOLS] Flags: require_adjacency={require_adjacency} "
        f"use_objective={use_objective} pin_entry_outdoor={pin_entry_outdoor} "
        f"outdoor_in_overlap={outdoor_in_overlap} "
        f"building_mass={'yes' if building_mass else 'no'} "
        f"use_clusters={use_clusters} "
        f"flexible_geometry={use_flex}"
    )
    if building_mass:
        print(
            f"[KIYUB MASS] target {building_mass.width}x{building_mass.depth} "
            f"at ({building_mass.x},{building_mass.y})"
        )

    reason = _early_infeasible(program, env)
    if reason:
        code = early_reason_code(reason)
        print(f"[OR-TOOLS] No feasible layout found")
        print(f"[OR-TOOLS] Reason: {reason}")
        print(f"[OR-TOOLS] reason_code: {code}")
        return SolveResult(
            status="infeasible",
            reason=reason,
            reason_code=code,
            conflicts=[{"type": code.lower(), "message": reason}],
            validated=False,
        )

    topology = topology_edges if topology_edges is not None else build_topology(program)
    if spatial_plan:
        seen = {(e.room_a, e.room_b, e.relation) for e in topology}
        for e in preferred_topology_edges(spatial_plan) + avoid_topology_edges(spatial_plan):
            key = (e.room_a, e.room_b, e.relation)
            rev = (e.room_b, e.room_a, e.relation)
            if key not in seen and rev not in seen:
                topology.append(e)
                seen.add(key)
    model = cp_model.CpModel()
    rooms: dict[str, RoomVars] = {}
    for spec in program.rooms:
        x = model.NewIntVar(0, env.width, f"{spec.id}_x")
        y = model.NewIntVar(0, env.depth, f"{spec.id}_y")
        w = model.NewIntVar(1, env.width, f"{spec.id}_w")
        h = model.NewIntVar(1, env.depth, f"{spec.id}_h")
        rot = model.NewBoolVar(f"{spec.id}_rot")
        rooms[spec.id] = RoomVars(spec, x, y, w, h, rot)

    add_envelope_and_sizes(model, rooms, env)
    add_hallway_geometry_caps(model, rooms, env)
    if use_flex:
        add_flexible_geometry(model, rooms, env)
    add_no_overlap(model, rooms, env, include_outdoor=outdoor_in_overlap, flexible=use_flex)
    if pin_entry_outdoor:
        add_entry_and_outdoor(model, rooms, env)
        add_vehicle_access(model, rooms, env)
    if require_adjacency or use_objective:
        soft = add_topology_adjacency(
            model, rooms, topology, env, require_adjacency=require_adjacency
        )
    else:
        soft = []
    if use_objective:
        add_objective(
            model, rooms, env, soft,
            spatial=spatial_plan, building_mass=building_mass, use_clusters=use_clusters,
        )

    if hints:
        for rid, (hx, hy, hw, hh) in hints.items():
            if rid in rooms:
                model.AddHint(rooms[rid].x, int(hx))
                model.AddHint(rooms[rid].y, int(hy))
                model.AddHint(rooms[rid].w, int(hw))
                model.AddHint(rooms[rid].h, int(hh))

    solver = cp_model.CpSolver()
    solver.parameters.random_seed = 1
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = float(time_limit_s)

    print("[OR-TOOLS] Solving layout")
    status = solver.Solve(model)
    ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    if not ok and use_flex:
        print("[KIYUB] Flexible geometry fallback=rectangle")
        return solve(
            program,
            envelope=env,
            hints=hints,
            time_limit_s=time_limit_s,
            require_adjacency=require_adjacency,
            use_objective=use_objective,
            pin_entry_outdoor=pin_entry_outdoor,
            outdoor_in_overlap=outdoor_in_overlap,
            topology_edges=topology,
            classify=classify,
            spatial_plan=spatial_plan,
            building_mass=building_mass,
            use_clusters=use_clusters,
            flexible=False,
            _flex_fallback=True,
        )
    if not ok:
        if status == cp_model.INFEASIBLE:
            msg = "requested program exceeds available envelope or adjacency constraints"
            code = "OTHER"
        elif status == cp_model.MODEL_INVALID:
            msg = "layout model is invalid"
            code = "OTHER"
        else:
            msg = "solver reached the time limit without a feasible layout"
            code = "OTHER"
        conflicts: list[dict] = []
        if classify:
            code, conflicts, msg = classify_infeasibility(program, env)
        elif require_adjacency:
            conflicts = hard_edge_conflicts(program, topology)
        print("[OR-TOOLS] No feasible layout found")
        print(f"[OR-TOOLS] Reason: {msg}")
        print(f"[OR-TOOLS] reason_code: {code}")
        return SolveResult(
            status="infeasible",
            reason=msg,
            reason_code=code,
            conflicts=conflicts,
            validated=False,
        )

    placed = []
    n_l = 0
    for spec in program.rooms:
        rv = rooms[spec.id]
        ox = solver.Value(rv.x)
        oy = solver.Value(rv.y)
        ww = solver.Value(rv.w)
        hh = solver.Value(rv.h)
        fp = None
        if use_flex and rv.candidates and rv.choice_bools:
            chosen = None
            for ch, cand in zip(rv.choice_bools, rv.candidates):
                if solver.Value(ch):
                    chosen = cand
                    break
            if chosen is not None and not chosen.variable_size:
                parts = [
                    FootprintPart(ox + px, oy + py, pw, pd)
                    for px, py, pw, pd in chosen.parts
                ]
                fp = RoomFootprint(type=chosen.type, parts=parts)
                if chosen.type == "l_shape":
                    n_l += 1
        placed.append(PlacedRoom(
            id=spec.id,
            type=spec.type,
            name=spec.name,
            x=ox,
            y=oy,
            width=ww,
            depth=hh,
            zone=spec.zone,
            footprint=fp,
        ))
    if use_flex:
        print(f"[KIYUB FLEX] l_shape_rooms={n_l} rectangle_fallback_parts={len(placed) - n_l}")

    layout = Layout(rooms=placed, envelope=env, topology=topology)
    layout.doors = place_doors(layout, topology)
    from .walls import place_walls
    from .openings import place_windows
    layout.walls = place_walls(layout)
    layout.openings = place_windows(layout)
    layout.furniture = place_furniture(layout)

    report = validate(layout, program)
    if not report.valid and use_flex:
        print("[OR-TOOLS] Validation: FAIL")
        for err in report.errors:
            print(f"[OR-TOOLS]   {err.type}: {err.message}")
        print("[KIYUB] Flexible geometry fallback=rectangle")
        return solve(
            program,
            envelope=env,
            hints=hints,
            time_limit_s=time_limit_s,
            require_adjacency=require_adjacency,
            use_objective=use_objective,
            pin_entry_outdoor=pin_entry_outdoor,
            outdoor_in_overlap=outdoor_in_overlap,
            topology_edges=topology,
            classify=classify,
            spatial_plan=spatial_plan,
            building_mass=building_mass,
            use_clusters=use_clusters,
            flexible=False,
            _flex_fallback=True,
        )
    if not report.valid:
        print("[OR-TOOLS] Validation: FAIL")
        for err in report.errors:
            print(f"[OR-TOOLS]   {err.type}: {err.message}")
        return SolveResult(
            status="infeasible",
            layout=layout,
            reason="; ".join(e.message for e in report.errors) or "validator rejected layout",
            reason_code="OTHER",
            conflicts=[e.as_dict() for e in report.errors],
            validation=report,
            validated=False,
        )

    print("[OR-TOOLS] Feasible solution found")
    print("[OR-TOOLS] Validation: PASS")
    quality = score_layout(layout, program, spatial_plan, building_mass)
    print(f"[KIYUB SPATIAL] quality_score {quality['overall']} {quality['note']}")
    res = quality.get("residual") or {}
    circ = quality.get("circulation") or {}
    print(
        f"[KIYUB RESIDUAL] area={res.get('residual_area')} regions={res.get('residual_region_count')} "
        f"largest={res.get('largest_residual_region')} narrow={res.get('narrow_residual_area')} "
        f"isolated={res.get('isolated_residual_regions')} "
        f"building={res.get('building_residual_area')} site={res.get('site_open_space_area')}"
    )
    print("[KIYUB RESIDUAL] Geometric leftover detection, not professional architectural approval.")
    print(
        f"[KIYUB CIRCULATION] area={circ.get('circulation_area')} length={circ.get('circulation_length')} "
        f"width={circ.get('circulation_width')} efficiency={circ.get('circulation_efficiency')} "
        f"reachable={circ.get('reachable_count')} unreachable={circ.get('unreachable_count')} "
        f"dead_ends={circ.get('dead_end_count')}"
    )
    print("[KIYUB CIRCULATION] Heuristic circulation graph, not professional architectural approval.")
    cl = quality.get("clusters") or {}
    print(
        f"[KIYUB CLUSTER] occupancy={quality.get('mass_occupancy_ratio')} "
        f"mean_cohesion={cl.get('mean_cohesion')} "
        f"clusters={len(cl.get('clusters') or [])}"
    )
    print("[KIYUB CLUSTER] Soft organization inside BuildingMass, not hard cluster rectangles.")
    fill = quality.get("mass_fill") or {}
    print(
        f"[KIYUB METRICS] mass={fill.get('mass_area')} "
        f"room_cells={fill.get('room_cells_in_mass')} "
        f"circ_cells={fill.get('circulation_cells_in_mass')} "
        f"residual={fill.get('building_residual_area')} "
        f"occupancy={fill.get('mass_occupancy')} "
        f"room_sum={fill.get('occupied_room_area_sum')}"
    )
    print("[KIYUB METRICS] Raster occupancy inside BuildingMass, not professional architectural approval.")
    print(
        f"[KIYUB USABILITY] score={quality.get('room_usability_score')} "
        f"door={quality.get('door_clearance_score')} "
        f"furniture={quality.get('furniture_clearance_score')} "
        f"fixture={quality.get('fixture_clearance_score')} "
        f"issues={len(quality.get('usability_issues') or [])}"
    )
    print("[KIYUB USABILITY] Internal clearance heuristics, not professional architectural approval.")
    return SolveResult(
        status="valid",
        layout=layout,
        reason="",
        reason_code="",
        conflicts=[],
        validation=report,
        validated=True,
        quality_score=quality,
    )
