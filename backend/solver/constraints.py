"""CP-SAT hard constraints: envelope, sizes, no overlap, required adjacency."""

from __future__ import annotations

from ortools.sat.python import cp_model

from .models import Envelope, RoomSpec, TopologyEdge
from .room_rules import HALL_MAX_AREA_FT2, HALL_MAX_SHORT_FT, MIN_SHARED_WALL_FT, OUTDOOR_TYPES, size_caps


class PartVars:
    """One axis-aligned rectangle that may be optional (candidate not chosen)."""

    def __init__(self, x, y, w, h, presence, x2, y2):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.presence = presence
        self.x2 = x2
        self.y2 = y2


class RoomVars:
    def __init__(self, spec: RoomSpec, x, y, w, h, rotated):
        self.spec = spec
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.rotated = rotated
        self.parts: list[PartVars] = []
        self.choice_bools: list = []
        self.candidates: list = []
        self.rect_choice = None


def add_envelope_and_sizes(
    model: cp_model.CpModel,
    rooms: dict[str, RoomVars],
    envelope: Envelope,
) -> None:
    W, D = envelope.width, envelope.depth
    for rv in rooms.values():
        model.Add(rv.x >= 0)
        model.Add(rv.y >= 0)
        model.Add(rv.w > 0)
        model.Add(rv.h > 0)
        model.Add(rv.x + rv.w <= W)
        model.Add(rv.y + rv.h <= D)

        spec = rv.spec
        max_w, max_h = size_caps(spec, W, D)
        if spec.allow_rotate:
            # unrotated: w>=min_w, h>=min_d; rotated: w>=min_d, h>=min_w
            model.Add(rv.w >= spec.min_width).OnlyEnforceIf(rv.rotated.Not())
            model.Add(rv.h >= spec.min_depth).OnlyEnforceIf(rv.rotated.Not())
            model.Add(rv.w >= spec.min_depth).OnlyEnforceIf(rv.rotated)
            model.Add(rv.h >= spec.min_width).OnlyEnforceIf(rv.rotated)
            model.Add(rv.w <= max_w)
            model.Add(rv.h <= max_h)
        else:
            model.Add(rv.w >= spec.min_width)
            model.Add(rv.h >= spec.min_depth)
            model.Add(rv.w <= max_w)
            model.Add(rv.h <= max_h)


def add_hallway_geometry_caps(
    model: cp_model.CpModel,
    rooms: dict[str, RoomVars],
    envelope: Envelope,
) -> None:
    """Keep one hallway axis near corridor width; cap area. Length may grow."""
    W, D = envelope.width, envelope.depth
    max_area = min(HALL_MAX_AREA_FT2, max(1, W * D))
    for rid, rv in rooms.items():
        if rv.spec.type != "hallway":
            continue
        along_x = model.NewBoolVar(f"{rid}_hall_along_x")
        model.Add(rv.h <= HALL_MAX_SHORT_FT).OnlyEnforceIf(along_x)
        model.Add(rv.w <= HALL_MAX_SHORT_FT).OnlyEnforceIf(along_x.Not())
        area = model.NewIntVar(1, max(1, W * D), f"{rid}_hall_area")
        model.AddMultiplicationEquality(area, [rv.w, rv.h])
        model.Add(area <= max_area)


def add_no_overlap(
    model: cp_model.CpModel,
    rooms: dict[str, RoomVars],
    envelope: Envelope,
    include_outdoor: bool = True,
    flexible: bool = False,
) -> None:
    x_ints = []
    y_ints = []
    for rid, rv in rooms.items():
        if not include_outdoor and rv.spec.type in OUTDOOR_TYPES:
            continue
        if flexible and rv.parts:
            for i, p in enumerate(rv.parts):
                x_ints.append(model.NewOptionalIntervalVar(
                    p.x, p.w, p.x2, p.presence, f"{rid}_p{i}_xi",
                ))
                y_ints.append(model.NewOptionalIntervalVar(
                    p.y, p.h, p.y2, p.presence, f"{rid}_p{i}_yi",
                ))
            continue
        x_end = model.NewIntVar(0, envelope.width, f"{rid}_xend")
        y_end = model.NewIntVar(0, envelope.depth, f"{rid}_yend")
        model.Add(x_end == rv.x + rv.w)
        model.Add(y_end == rv.y + rv.h)
        x_ints.append(model.NewIntervalVar(rv.x, rv.w, x_end, f"{rid}_xi"))
        y_ints.append(model.NewIntervalVar(rv.y, rv.h, y_end, f"{rid}_yi"))
    if len(x_ints) >= 2:
        model.AddNoOverlap2D(x_ints, y_ints)


def add_flexible_geometry(
    model: cp_model.CpModel,
    rooms: dict[str, RoomVars],
    envelope: Envelope,
) -> None:
    """Exactly one shape candidate per room. Parts are relative to (x, y)."""
    from .footprint import generate_solver_candidates
    from .room_rules import size_caps

    W, D = envelope.width, envelope.depth
    for rid, rv in rooms.items():
        cands = generate_solver_candidates(rv.spec)
        max_w, max_h = size_caps(rv.spec, W, D)
        kept = []
        for cand in cands:
            if cand.variable_size:
                kept.append(cand)
                continue
            bw, bh = cand.bbox_size()
            if bw <= max_w and bh <= max_h and bw <= W and bh <= D:
                kept.append(cand)
        if not kept:
            kept = [cands[0]]
        bools = []
        for cand in kept:
            ch = model.NewBoolVar(f"{rid}_shape_{cand.key}")
            bools.append(ch)
            if cand.variable_size:
                rv.rect_choice = ch
                x2 = model.NewIntVar(0, W, f"{rid}_rect_x2")
                y2 = model.NewIntVar(0, D, f"{rid}_rect_y2")
                model.Add(x2 == rv.x + rv.w)
                model.Add(y2 == rv.y + rv.h)
                rv.parts.append(PartVars(rv.x, rv.y, rv.w, rv.h, ch, x2, y2))
                continue
            bw, bh = cand.bbox_size()
            model.Add(rv.w == bw).OnlyEnforceIf(ch)
            model.Add(rv.h == bh).OnlyEnforceIf(ch)
            model.Add(rv.rotated == 0).OnlyEnforceIf(ch)
            for pi, (px, py, pw, pd) in enumerate(cand.parts):
                xs = model.NewIntVar(-W, 2 * W, f"{rid}_{cand.key}_p{pi}_x")
                ys = model.NewIntVar(-D, 2 * D, f"{rid}_{cand.key}_p{pi}_y")
                xe = model.NewIntVar(-W, 2 * W, f"{rid}_{cand.key}_p{pi}_x2")
                ye = model.NewIntVar(-D, 2 * D, f"{rid}_{cand.key}_p{pi}_y2")
                model.Add(xs == rv.x + px)
                model.Add(ys == rv.y + py)
                model.Add(xe == xs + pw)
                model.Add(ye == ys + pd)
                model.Add(xs >= 0).OnlyEnforceIf(ch)
                model.Add(ys >= 0).OnlyEnforceIf(ch)
                model.Add(xe <= W).OnlyEnforceIf(ch)
                model.Add(ye <= D).OnlyEnforceIf(ch)
                rv.parts.append(PartVars(xs, ys, pw, pd, ch, xe, ye))
        model.Add(sum(bools) == 1)
        rv.choice_bools = bools
        rv.candidates = kept


def _nonneg_overlap(
    model: cp_model.CpModel,
    a1,
    a2,
    b1,
    b2,
    bound: int,
    name: str,
):
    """overlap = max(0, min(a2,b2) - max(a1,b1)). Raw gap may be negative."""
    max_lo = model.NewIntVar(0, bound, f"{name}_maxlo")
    min_hi = model.NewIntVar(0, bound, f"{name}_minhi")
    model.AddMaxEquality(max_lo, [a1, b1])
    model.AddMinEquality(min_hi, [a2, b2])
    raw = model.NewIntVar(-bound, bound, f"{name}_raw")
    model.Add(raw == min_hi - max_lo)
    overlap = model.NewIntVar(0, bound, f"{name}_ov")
    positive = model.NewBoolVar(f"{name}_pos")
    model.Add(raw >= 0).OnlyEnforceIf(positive)
    model.Add(raw < 0).OnlyEnforceIf(positive.Not())
    model.Add(overlap == raw).OnlyEnforceIf(positive)
    model.Add(overlap == 0).OnlyEnforceIf(positive.Not())
    return overlap


def _share_wall_geom(
    model: cp_model.CpModel,
    ax, ay, aw, ah, ax2, ay2,
    bx, by, bw, bh, bx2, by2,
    envelope: Envelope,
    name: str,
    min_share: int = MIN_SHARED_WALL_FT,
):
    """Boolean: two rectangles share a wall of at least min_share feet."""
    left = model.NewBoolVar(f"{name}_L")
    right = model.NewBoolVar(f"{name}_R")
    below = model.NewBoolVar(f"{name}_B")
    above = model.NewBoolVar(f"{name}_A")
    touch = model.NewBoolVar(name)
    y_ov = _nonneg_overlap(model, ay, ay2, by, by2, envelope.depth, f"{name}_y")
    x_ov = _nonneg_overlap(model, ax, ax2, bx, bx2, envelope.width, f"{name}_x")

    model.Add(ax + aw == bx).OnlyEnforceIf(left)
    model.Add(y_ov >= min_share).OnlyEnforceIf(left)

    model.Add(bx + bw == ax).OnlyEnforceIf(right)
    model.Add(y_ov >= min_share).OnlyEnforceIf(right)

    model.Add(ay + ah == by).OnlyEnforceIf(below)
    model.Add(x_ov >= min_share).OnlyEnforceIf(below)

    model.Add(by + bh == ay).OnlyEnforceIf(above)
    model.Add(x_ov >= min_share).OnlyEnforceIf(above)

    model.AddBoolOr([left, right, below, above]).OnlyEnforceIf(touch)
    model.Add(sum([left, right, below, above]) == 0).OnlyEnforceIf(touch.Not())
    return touch


def _forbid_wall_share(
    model: cp_model.CpModel,
    a: RoomVars,
    b: RoomVars,
    envelope: Envelope,
    name: str,
    min_share: int = MIN_SHARED_WALL_FT,
) -> None:
    """Hard: a and b must not share a wall of min_share feet."""
    a_y2 = model.NewIntVar(0, envelope.depth, f"{name}_ay2")
    b_y2 = model.NewIntVar(0, envelope.depth, f"{name}_by2")
    model.Add(a_y2 == a.y + a.h)
    model.Add(b_y2 == b.y + b.h)
    a_x2 = model.NewIntVar(0, envelope.width, f"{name}_ax2")
    b_x2 = model.NewIntVar(0, envelope.width, f"{name}_bx2")
    model.Add(a_x2 == a.x + a.w)
    model.Add(b_x2 == b.x + b.w)
    y_ov = _nonneg_overlap(model, a.y, a_y2, b.y, b_y2, envelope.depth, f"{name}_fy")
    x_ov = _nonneg_overlap(model, a.x, a_x2, b.x, b_x2, envelope.width, f"{name}_fx")
    left = model.NewBoolVar(f"{name}_L")
    right = model.NewBoolVar(f"{name}_R")
    below = model.NewBoolVar(f"{name}_B")
    above = model.NewBoolVar(f"{name}_A")
    model.Add(a.x + a.w == b.x).OnlyEnforceIf(left)
    model.Add(a.x + a.w != b.x).OnlyEnforceIf(left.Not())
    model.Add(b.x + b.w == a.x).OnlyEnforceIf(right)
    model.Add(b.x + b.w != a.x).OnlyEnforceIf(right.Not())
    model.Add(a.y + a.h == b.y).OnlyEnforceIf(below)
    model.Add(a.y + a.h != b.y).OnlyEnforceIf(below.Not())
    model.Add(b.y + b.h == a.y).OnlyEnforceIf(above)
    model.Add(b.y + b.h != a.y).OnlyEnforceIf(above.Not())
    model.Add(y_ov < min_share).OnlyEnforceIf(left)
    model.Add(y_ov < min_share).OnlyEnforceIf(right)
    model.Add(x_ov < min_share).OnlyEnforceIf(below)
    model.Add(x_ov < min_share).OnlyEnforceIf(above)


def _share_wall(
    model: cp_model.CpModel,
    a: RoomVars,
    b: RoomVars,
    envelope: Envelope,
    name: str,
    min_share: int = MIN_SHARED_WALL_FT,
) -> cp_model.IntVar:
    """Boolean: a and b share a wall of at least min_share feet.

    With flexible parts: any part of A may share a wall with any part of B.
    """
    if a.parts and b.parts:
        pair_touches = []
        for i, pa in enumerate(a.parts):
            for j, pb in enumerate(b.parts):
                t = _share_wall_geom(
                    model,
                    pa.x, pa.y, pa.w, pa.h, pa.x2, pa.y2,
                    pb.x, pb.y, pb.w, pb.h, pb.x2, pb.y2,
                    envelope, f"{name}_{i}_{j}", min_share,
                )
                model.Add(t == 0).OnlyEnforceIf(pa.presence.Not())
                model.Add(t == 0).OnlyEnforceIf(pb.presence.Not())
                pair_touches.append(t)
        touch = model.NewBoolVar(name)
        model.AddBoolOr(pair_touches).OnlyEnforceIf(touch)
        model.Add(sum(pair_touches) == 0).OnlyEnforceIf(touch.Not())
        return touch

    a_y2 = model.NewIntVar(0, envelope.depth, f"{name}_ay2")
    b_y2 = model.NewIntVar(0, envelope.depth, f"{name}_by2")
    model.Add(a_y2 == a.y + a.h)
    model.Add(b_y2 == b.y + b.h)
    a_x2 = model.NewIntVar(0, envelope.width, f"{name}_ax2")
    b_x2 = model.NewIntVar(0, envelope.width, f"{name}_bx2")
    model.Add(a_x2 == a.x + a.w)
    model.Add(b_x2 == b.x + b.w)
    return _share_wall_geom(
        model, a.x, a.y, a.w, a.h, a_x2, a_y2,
        b.x, b.y, b.w, b.h, b_x2, b_y2,
        envelope, name, min_share,
    )


def add_topology_adjacency(
    model: cp_model.CpModel,
    rooms: dict[str, RoomVars],
    edges: list[TopologyEdge],
    envelope: Envelope,
    require_adjacency: bool = True,
) -> list:
    """
    Relation encoding:
    - connected (hard, no group): must share a wall
    - accessed_by / outside_access with choice_group: at least one pair shares a wall
    - accessed_by / outside_access hard, no group: must share a wall with that target
    - adjacent / near: soft objective bonus
    - separated / avoid: soft wall-share penalty
    """
    from collections import defaultdict

    soft_bools = []
    grouped: dict[str, list] = defaultdict(list)
    hard_pairs: list[tuple[str, str, str]] = []
    or_groups: dict[str, list[tuple[str, str, str]]] = defaultdict(list)

    names = {rid: rv.spec.name for rid, rv in rooms.items()}

    for i, e in enumerate(edges):
        if e.room_a not in rooms or e.room_b not in rooms:
            continue

        if e.relation in ("separated", "avoid"):
            if e.hard and require_adjacency:
                _forbid_wall_share(
                    model, rooms[e.room_a], rooms[e.room_b], envelope,
                    f"forbid_{i}_{e.relation}",
                )
            else:
                touch = _share_wall(
                    model, rooms[e.room_a], rooms[e.room_b], envelope, f"adj_{i}_{e.relation}"
                )
                soft_bools.append(("avoid", touch))
            continue

        touch = _share_wall(
            model, rooms[e.room_a], rooms[e.room_b], envelope, f"adj_{i}_{e.relation}"
        )
        a_name = names.get(e.room_a, e.room_a)
        b_name = names.get(e.room_b, e.room_b)

        if e.relation in ("adjacent", "near") and not e.hard:
            soft_bools.append(("prefer", touch))
            continue

        if e.choice_group and e.hard and e.relation in ("accessed_by", "outside_access", "connected"):
            grouped[e.choice_group].append(touch)
            or_groups[e.choice_group].append((a_name, e.relation, b_name))
            soft_bools.append(("prefer", touch))
            continue

        enforce_hard = (
            require_adjacency
            and e.hard
            and e.relation in ("connected", "accessed_by")
            and not e.choice_group
        )
        if enforce_hard:
            model.Add(touch == 1)
            hard_pairs.append((a_name, e.relation, b_name))
        else:
            soft_bools.append(("prefer", touch))

    if require_adjacency:
        for gid, touches in grouped.items():
            if touches:
                model.AddBoolOr(touches)
        print("[KIYUB CP-SAT] hard wall-share pairs")
        for a, rel, b in hard_pairs:
            print(f"  {a} --{rel}-- {b}")
        print("[KIYUB CP-SAT] OR groups")
        for gid, pairs in or_groups.items():
            desc = " OR ".join(f"{a}--{rel}--{b}" for a, rel, b in pairs)
            print(f"  {gid}: {desc}")

    return soft_bools


def add_entry_and_outdoor(
    model: cp_model.CpModel,
    rooms: dict[str, RoomVars],
    envelope: Envelope,
) -> None:
    """Foyer on the front edge (outside → entry). Outdoor rooms on the rear edge."""
    for rv in rooms.values():
        if rv.spec.type == "foyer":
            model.Add(rv.y == 0)
        if rv.spec.type in OUTDOOR_TYPES:
            model.Add(rv.y + rv.h == envelope.depth)


def add_vehicle_access(
    model: cp_model.CpModel,
    rooms: dict[str, RoomVars],
    envelope: Envelope,
) -> None:
    """Garage must touch street frontage or a side edge. Not an interior-only room."""
    W = envelope.width
    for rid, rv in rooms.items():
        if rv.spec.type != "garage":
            continue
        front = model.NewBoolVar(f"{rid}_veh_front")
        left = model.NewBoolVar(f"{rid}_veh_left")
        right = model.NewBoolVar(f"{rid}_veh_right")
        model.Add(rv.y == 0).OnlyEnforceIf(front)
        model.Add(rv.x == 0).OnlyEnforceIf(left)
        model.Add(rv.x + rv.w == W).OnlyEnforceIf(right)
        model.AddBoolOr([front, left, right])
