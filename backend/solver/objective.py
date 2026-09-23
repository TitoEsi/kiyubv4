"""Soft optimization: compactness, circulation, aspect, optional SpatialPlan bands."""

from __future__ import annotations

from ortools.sat.python import cp_model

from .building_mass import BuildingMass
from .constraints import RoomVars
from .models import Envelope
from .room_rules import BEDROOM_TYPES, CIRCULATION_TYPES, OUTDOOR_TYPES
from .spatial_plan import SpatialPlan


def _zone_band_bools(
    model: cp_model.CpModel,
    rooms: dict[str, RoomVars],
    envelope: Envelope,
    spatial: SpatialPlan | None,
) -> list:
    if not spatial:
        return []
    W, D = envelope.width, envelope.depth
    by_id_zone = {}
    for zone, ids in spatial.zones.items():
        for rid in ids:
            by_id_zone[rid] = zone
    bools = []
    for i, band in enumerate(spatial.strategy.bands):
        span = W if band.axis == "x" else D
        lo = int(band.lo_frac * span)
        hi = int(band.hi_frac * span)
        if hi <= lo:
            continue
        for rid, rv in rooms.items():
            if by_id_zone.get(rid) != band.zone:
                continue
            if rv.spec.type in OUTDOOR_TYPES and band.zone != "exterior":
                continue
            inside = model.NewBoolVar(f"band_{i}_{rid}")
            if band.axis == "y":
                c2 = model.NewIntVar(0, 2 * D, f"band_{i}_{rid}_c")
                model.Add(c2 == 2 * rv.y + rv.h)
                model.Add(c2 >= 2 * lo).OnlyEnforceIf(inside)
                model.Add(c2 <= 2 * hi).OnlyEnforceIf(inside)
            else:
                c2 = model.NewIntVar(0, 2 * W, f"band_{i}_{rid}_c")
                model.Add(c2 == 2 * rv.x + rv.w)
                model.Add(c2 >= 2 * lo).OnlyEnforceIf(inside)
                model.Add(c2 <= 2 * hi).OnlyEnforceIf(inside)
            bools.append(inside)
    return bools


def _inside_mass_bools(
    model: cp_model.CpModel,
    rooms: dict[str, RoomVars],
    envelope: Envelope,
    mass: BuildingMass | None,
) -> list:
    if not mass:
        return []
    mx2 = mass.x + mass.width
    my2 = mass.y + mass.depth
    bools = []
    for rid, rv in rooms.items():
        if rv.spec.type in OUTDOOR_TYPES:
            continue
        inside = model.NewBoolVar(f"mass_in_{rid}")
        model.Add(rv.x >= mass.x).OnlyEnforceIf(inside)
        model.Add(rv.y >= mass.y).OnlyEnforceIf(inside)
        model.Add(rv.x + rv.w <= mx2).OnlyEnforceIf(inside)
        model.Add(rv.y + rv.h <= my2).OnlyEnforceIf(inside)
        bools.append(inside)
    return bools


def _cluster_span_terms(
    model: cp_model.CpModel,
    rooms: dict[str, RoomVars],
    envelope: Envelope,
    spatial: SpatialPlan | None,
) -> list:
    if not spatial:
        return []
    W, D = envelope.width, envelope.depth
    terms = []
    for cl in spatial.clusters:
        if cl.id == "exterior" or cl.zone == "exterior":
            continue
        members = [
            rooms[rid] for rid in cl.room_ids
            if rid in rooms and rooms[rid].spec.type not in OUTDOOR_TYPES
        ]
        if len(members) < 2:
            continue
        xs = [rv.x for rv in members]
        ys = [rv.y for rv in members]
        xes = []
        yes = []
        for rv in members:
            xe = model.NewIntVar(0, W, f"cl_{cl.id}_{rv.spec.id}_xe")
            ye = model.NewIntVar(0, D, f"cl_{cl.id}_{rv.spec.id}_ye")
            model.Add(xe == rv.x + rv.w)
            model.Add(ye == rv.y + rv.h)
            xes.append(xe)
            yes.append(ye)
        xmin = model.NewIntVar(0, W, f"cl_{cl.id}_xmin")
        xmax = model.NewIntVar(0, W, f"cl_{cl.id}_xmax")
        ymin = model.NewIntVar(0, D, f"cl_{cl.id}_ymin")
        ymax = model.NewIntVar(0, D, f"cl_{cl.id}_ymax")
        model.AddMinEquality(xmin, xs)
        model.AddMaxEquality(xmax, xes)
        model.AddMinEquality(ymin, ys)
        model.AddMaxEquality(ymax, yes)
        span_x = model.NewIntVar(0, W, f"cl_{cl.id}_sx")
        span_y = model.NewIntVar(0, D, f"cl_{cl.id}_sy")
        model.Add(span_x == xmax - xmin)
        model.Add(span_y == ymax - ymin)
        wgt = max(1, cl.cohesion_weight)
        terms.append(wgt * span_x)
        terms.append(wgt * span_y)
    return terms


def _cluster_band_bools(
    model: cp_model.CpModel,
    rooms: dict[str, RoomVars],
    envelope: Envelope,
    spatial: SpatialPlan | None,
    mass: BuildingMass | None,
) -> list:
    if not spatial:
        return []
    ox = mass.x if mass else 0
    oy = mass.y if mass else 0
    span_x = mass.width if mass else envelope.width
    span_y = mass.depth if mass else envelope.depth
    bools = []
    for cl in spatial.clusters:
        band = cl.band
        if not band or cl.id == "exterior":
            continue
        span = span_x if band.axis == "x" else span_y
        origin = ox if band.axis == "x" else oy
        lo = origin + int(band.lo_frac * span)
        hi = origin + int(band.hi_frac * span)
        if hi <= lo:
            continue
        bound = max(envelope.width, envelope.depth)
        for rid in cl.room_ids:
            rv = rooms.get(rid)
            if not rv or rv.spec.type in OUTDOOR_TYPES:
                continue
            inside = model.NewBoolVar(f"clband_{cl.id}_{rid}")
            if band.axis == "y":
                c2 = model.NewIntVar(0, 2 * bound, f"clband_{cl.id}_{rid}_c")
                model.Add(c2 == 2 * rv.y + rv.h)
                model.Add(c2 >= 2 * lo).OnlyEnforceIf(inside)
                model.Add(c2 <= 2 * hi).OnlyEnforceIf(inside)
            else:
                c2 = model.NewIntVar(0, 2 * bound, f"clband_{cl.id}_{rid}_c")
                model.Add(c2 == 2 * rv.x + rv.w)
                model.Add(c2 >= 2 * lo).OnlyEnforceIf(inside)
                model.Add(c2 <= 2 * hi).OnlyEnforceIf(inside)
            bools.append(inside)
    return bools


def add_objective(
    model: cp_model.CpModel,
    rooms: dict[str, RoomVars],
    envelope: Envelope,
    adjacency_bools: list,
    spatial: SpatialPlan | None = None,
    building_mass: BuildingMass | None = None,
    use_clusters: bool = True,
) -> None:
    W, D = envelope.width, envelope.depth
    ox = building_mass.x if building_mass else 0
    oy = building_mass.y if building_mass else 0

    xmax = model.NewIntVar(0, W, "xmax")
    ymax = model.NewIntVar(0, D, "ymax")
    xmin = model.NewIntVar(0, W, "xmin")
    ymin = model.NewIntVar(0, D, "ymin")
    ends = []
    origins = []
    for rid, rv in rooms.items():
        if rv.spec.type in OUTDOOR_TYPES:
            continue
        xe = model.NewIntVar(0, W, f"{rid}_xe")
        ye = model.NewIntVar(0, D, f"{rid}_ye")
        model.Add(xe == rv.x + rv.w)
        model.Add(ye == rv.y + rv.h)
        ends.append((xe, ye))
        origins.append((rv.x, rv.y))
    if ends:
        model.AddMaxEquality(xmax, [xe for xe, _ in ends])
        model.AddMaxEquality(ymax, [ye for _, ye in ends])
        model.AddMinEquality(xmin, [x for x, _ in origins])
        model.AddMinEquality(ymin, [y for _, y in origins])
    else:
        model.Add(xmax == 0)
        model.Add(ymax == 0)
        model.Add(xmin == 0)
        model.Add(ymin == 0)

    xmax_rel = model.NewIntVar(-W, W, "xmax_rel")
    ymax_rel = model.NewIntVar(-D, D, "ymax_rel")
    model.Add(xmax_rel == xmax - ox)
    model.Add(ymax_rel == ymax - oy)
    overshoot_x = model.NewIntVar(0, W, "mass_overshoot_x")
    overshoot_y = model.NewIntVar(0, D, "mass_overshoot_y")
    zero = model.NewIntVar(0, 0, "mass_zero")
    if building_mass:
        dx = model.NewIntVar(-W, W, "mass_dx")
        dy = model.NewIntVar(-D, D, "mass_dy")
        model.Add(dx == ox - xmin)
        model.Add(dy == oy - ymin)
        model.AddMaxEquality(overshoot_x, [dx, zero])
        model.AddMaxEquality(overshoot_y, [dy, zero])
    else:
        model.Add(overshoot_x == 0)
        model.Add(overshoot_y == 0)

    hall_width_excess = []
    hall_area_excess = []
    for rid, rv in rooms.items():
        if rv.spec.type not in CIRCULATION_TYPES:
            continue
        # Do not minimize hallway length. Penalize a fat short-side and area above cap.
        pref_w = max(1, int(rv.spec.preferred_width))
        short = model.NewIntVar(0, max(W, D), f"{rid}_hall_short")
        model.AddMinEquality(short, [rv.w, rv.h])
        excess = model.NewIntVar(0, max(W, D), f"{rid}_hall_ex")
        slack = model.NewIntVar(-max(W, D), max(W, D), f"{rid}_hall_raw")
        model.Add(slack == short - (pref_w + 1))
        model.AddMaxEquality(excess, [slack, zero])
        hall_width_excess.append(excess)
        if rv.spec.type == "hallway":
            area = model.NewIntVar(1, max(1, W * D), f"{rid}_hall_obj_area")
            model.AddMultiplicationEquality(area, [rv.w, rv.h])
            area_slack = model.NewIntVar(-W * D, W * D, f"{rid}_hall_area_raw")
            area_ex = model.NewIntVar(0, W * D, f"{rid}_hall_area_ex")
            pref_area = max(1, int(rv.spec.preferred_width) * int(rv.spec.preferred_depth))
            model.Add(area_slack == area - pref_area)
            model.AddMaxEquality(area_ex, [area_slack, zero])
            hall_area_excess.append(area_ex)

    size_dev = []
    aspect = []
    bound = max(W, D)
    for rid, rv in rooms.items():
        if rv.spec.type in OUTDOOR_TYPES:
            continue
        pw, pd = int(rv.spec.preferred_width), int(rv.spec.preferred_depth)
        dw0 = model.NewIntVar(-bound, bound, f"{rid}_dw0")
        dh0 = model.NewIntVar(-bound, bound, f"{rid}_dh0")
        dw1 = model.NewIntVar(-bound, bound, f"{rid}_dw1")
        dh1 = model.NewIntVar(-bound, bound, f"{rid}_dh1")
        model.Add(dw0 == rv.w - pw)
        model.Add(dh0 == rv.h - pd)
        model.Add(dw1 == rv.w - pd)
        model.Add(dh1 == rv.h - pw)
        adw0 = model.NewIntVar(0, bound, f"{rid}_adw0")
        adh0 = model.NewIntVar(0, bound, f"{rid}_adh0")
        adw1 = model.NewIntVar(0, bound, f"{rid}_adw1")
        adh1 = model.NewIntVar(0, bound, f"{rid}_adh1")
        model.AddAbsEquality(adw0, dw0)
        model.AddAbsEquality(adh0, dh0)
        model.AddAbsEquality(adw1, dw1)
        model.AddAbsEquality(adh1, dh1)
        unrot = model.NewIntVar(0, 2 * bound, f"{rid}_sz0")
        rot = model.NewIntVar(0, 2 * bound, f"{rid}_sz1")
        chosen = model.NewIntVar(0, 2 * bound, f"{rid}_sz")
        model.Add(unrot == adw0 + adh0)
        model.Add(rot == adw1 + adh1)
        if rv.spec.allow_rotate:
            model.Add(chosen == unrot).OnlyEnforceIf(rv.rotated.Not())
            model.Add(chosen == rot).OnlyEnforceIf(rv.rotated)
        else:
            model.Add(chosen == unrot)
        weight = 2 if rv.spec.type in BEDROOM_TYPES else 1
        if rv.spec.type in CIRCULATION_TYPES:
            weight = 1
        size_dev.append(weight * chosen)
        if rv.spec.type in CIRCULATION_TYPES or rv.spec.type == "garage":
            continue
        delta = model.NewIntVar(-bound, bound, f"{rid}_asp_d")
        model.Add(delta == rv.w - rv.h)
        adiff = model.NewIntVar(0, bound, f"{rid}_asp")
        model.AddAbsEquality(adiff, delta)
        aspect.append((2 if rv.spec.type in BEDROOM_TYPES else 1) * adiff)

    # Do not minimize occupied area or crush the bounding box.
    # Light overshoot penalty keeps indoor rooms near the planned mass.
    terms = [overshoot_x, overshoot_y]
    if use_clusters and building_mass:
        under_x = model.NewIntVar(0, W, "mass_under_x")
        under_y = model.NewIntVar(0, D, "mass_under_y")
        gx = model.NewIntVar(-W, W, "mass_gx")
        gy = model.NewIntVar(-D, D, "mass_gy")
        model.Add(gx == (building_mass.x + building_mass.width) - xmax)
        model.Add(gy == (building_mass.y + building_mass.depth) - ymax)
        model.AddMaxEquality(under_x, [gx, zero])
        model.AddMaxEquality(under_y, [gy, zero])
        terms.extend([under_x, under_y])
    terms.extend(hall_width_excess)
    terms.extend(hall_area_excess)
    terms.extend(size_dev)
    terms.extend(aspect)
    if adjacency_bools:
        for item in adjacency_bools:
            if isinstance(item, tuple) and len(item) == 2:
                kind, b = item
                if kind == "avoid":
                    terms.append(5 * b)
                else:
                    terms.append(-5 * b)
            else:
                terms.append(-4 * item)
    for b in _zone_band_bools(model, rooms, envelope, spatial):
        terms.append(-3 * b)
    for b in _inside_mass_bools(model, rooms, envelope, building_mass):
        terms.append(-6 * b)
    if use_clusters:
        terms.extend(_cluster_span_terms(model, rooms, envelope, spatial))
        for b in _cluster_band_bools(model, rooms, envelope, spatial, building_mass):
            terms.append(-5 * b)
    for rv in rooms.values():
        if rv.rect_choice is not None:
            terms.append(-2 * rv.rect_choice)
    model.Minimize(sum(terms) if terms else 0)
