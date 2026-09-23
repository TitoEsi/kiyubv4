"""Orthogonal multi-rectangle room footprints. Integer feet, same origin as PlacedRoom.

Authoritative occupied geometry is the union of axis-aligned parts.
Bounding box remains compatibility. Invalid geometry is rejected, not repaired.
Not professional architectural approval.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from typing import Iterable, Sequence

from .models import Envelope, FootprintPart, PlacedRoom, RoomFootprint, RoomSpec
from .room_rules import MIN_SHARED_WALL_FT, rule_for

MAX_COMPONENTS = 2


@dataclass(frozen=True)
class ShapeCandidate:
    """Relative parts from origin (0, 0). variable_size uses live CP-SAT w,h."""

    key: str
    type: str  # rectangle | l_shape
    parts: tuple[tuple[int, int, int, int], ...]
    complexity: int = 0
    variable_size: bool = False

    def bbox_size(self) -> tuple[int, int]:
        if not self.parts:
            return (0, 0)
        max_x = max(x + w for x, _y, w, _d in self.parts)
        max_y = max(y + d for _x, y, _w, d in self.parts)
        return (max_x, max_y)


def _parts_of(obj) -> list[FootprintPart]:
    if isinstance(obj, PlacedRoom):
        return obj.parts()
    if isinstance(obj, RoomFootprint):
        return list(obj.parts)
    if isinstance(obj, FootprintPart):
        return [obj]
    if isinstance(obj, (list, tuple)):
        out: list[FootprintPart] = []
        for item in obj:
            if isinstance(item, FootprintPart):
                out.append(item)
            elif isinstance(item, (tuple, list)) and len(item) >= 4:
                out.append(FootprintPart(int(item[0]), int(item[1]), int(item[2]), int(item[3])))
        return out
    return []


def rectangle_footprint(x: int, y: int, width: int, depth: int) -> RoomFootprint:
    return RoomFootprint(
        type="rectangle",
        parts=[FootprintPart(x, y, width, depth)],
    )


def footprint_from_parts(
    parts: Sequence[FootprintPart] | Sequence[tuple[int, int, int, int]],
    type_name: str | None = None,
) -> RoomFootprint:
    parsed = _parts_of(parts)
    if type_name is None:
        type_name = "rectangle" if len(parsed) <= 1 else "l_shape"
    return RoomFootprint(type=type_name, parts=parsed)


def bbox_of(obj) -> tuple[int, int, int, int]:
    parts = _parts_of(obj)
    if not parts:
        if isinstance(obj, PlacedRoom):
            return (obj.x, obj.y, obj.width, obj.depth)
        return (0, 0, 0, 0)
    min_x = min(p.x for p in parts)
    min_y = min(p.y for p in parts)
    max_x = max(p.x2 for p in parts)
    max_y = max(p.y2 for p in parts)
    return (min_x, min_y, max_x - min_x, max_y - min_y)


def centroid_of(obj) -> tuple[float, float]:
    parts = _parts_of(obj)
    area = 0
    cx = 0.0
    cy = 0.0
    for p in parts:
        a = p.width * p.depth
        if a <= 0:
            continue
        area += a
        cx += (p.x + p.width / 2.0) * a
        cy += (p.y + p.depth / 2.0) * a
    if area <= 0:
        x, y, w, d = bbox_of(obj)
        return (x + w / 2.0, y + d / 2.0)
    return (cx / area, cy / area)


def cells_of(obj) -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    for p in _parts_of(obj):
        if p.width <= 0 or p.depth <= 0:
            continue
        for y in range(p.y, p.y2):
            for x in range(p.x, p.x2):
                cells.add((x, y))
    return cells


def union_area(obj) -> int:
    return len(cells_of(obj))


def contains_cell(obj, x: int, y: int) -> bool:
    for p in _parts_of(obj):
        if p.x <= x < p.x2 and p.y <= y < p.y2:
            return True
    return False


def contains_rect(obj, x: float, y: float, width: float, depth: float) -> bool:
    """True iff the furniture rectangle lies inside the union (not the bbox void)."""
    if width <= 0 or depth <= 0:
        return False
    x0 = int(round(x))
    y0 = int(round(y))
    x1 = int(round(x + width))
    y1 = int(round(y + depth))
    if x1 <= x0:
        x1 = x0 + 1
    if y1 <= y0:
        y1 = y0 + 1
    # Tight float bounds: every covered cell of the closed-open rect must be inside.
    lo_x = int(x) if x >= 0 or x == int(x) else int(x) - 1
    lo_y = int(y) if y >= 0 or y == int(y) else int(y) - 1
    hi_x = int(x + width - 1e-9) + 1
    hi_y = int(y + depth - 1e-9) + 1
    if abs(x - round(x)) < 1e-6 and abs(y - round(y)) < 1e-6:
        lo_x, lo_y, hi_x, hi_y = x0, y0, x1, y1
    if hi_x <= lo_x or hi_y <= lo_y:
        return False
    for cy in range(lo_y, hi_y):
        for cx in range(lo_x, hi_x):
            if not contains_cell(obj, cx, cy):
                return False
    return True


def parts_intersect(a: FootprintPart, b: FootprintPart) -> bool:
    return a.x < b.x2 and a.x2 > b.x and a.y < b.y2 and a.y2 > b.y


def footprints_intersect(a, b) -> bool:
    pa = _parts_of(a)
    pb = _parts_of(b)
    if not pa or not pb:
        return False
    ax, ay, aw, ad = bbox_of(a)
    bx, by, bw, bd = bbox_of(b)
    if ax + aw <= bx or bx + bw <= ax or ay + ad <= by or by + bd <= ay:
        return False
    for ra in pa:
        for rb in pb:
            if parts_intersect(ra, rb):
                return True
    return False


def intersection_area(a, b) -> int:
    return len(cells_of(a) & cells_of(b))


def parts_touch(a: FootprintPart, b: FootprintPart, min_share: int = MIN_SHARED_WALL_FT) -> bool:
    if a.x2 == b.x or b.x2 == a.x:
        return min(a.y2, b.y2) - max(a.y, b.y) >= min_share
    if a.y2 == b.y or b.y2 == a.y:
        return min(a.x2, b.x2) - max(a.x, b.x) >= min_share
    return False


def footprints_touch(a, b, min_share: int = MIN_SHARED_WALL_FT) -> bool:
    for ra in _parts_of(a):
        for rb in _parts_of(b):
            if parts_touch(ra, rb, min_share):
                return True
    return False


def _connected(parts: list[FootprintPart]) -> bool:
    if not parts:
        return False
    cells = cells_of(parts)
    if not cells:
        return False
    start = next(iter(cells))
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (x + dx, y + dy)
            if nxt in cells and nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return len(seen) == len(cells)


def boundary_segments(obj) -> list[tuple[int, int, int, int]]:
    """Outer wall segments. Internal shared edges are not walls."""
    unit: Counter[tuple[str, int, int]] = Counter()
    for p in _parts_of(obj):
        for x in range(p.x, p.x2):
            unit[("h", x, p.y)] += 1
            unit[("h", x, p.y2)] += 1
        for y in range(p.y, p.y2):
            unit[("v", p.x, y)] += 1
            unit[("v", p.x2, y)] += 1
    outer_h = sorted((x, y) for (axis, x, y), n in unit.items() if axis == "h" and n == 1)
    outer_v = sorted((x, y) for (axis, x, y), n in unit.items() if axis == "v" and n == 1)
    segs: list[tuple[int, int, int, int]] = []

    def merge(points: list[tuple[int, int]], vertical: bool) -> None:
        if not points:
            return
        if vertical:
            points = sorted(points, key=lambda t: (t[0], t[1]))
            i = 0
            while i < len(points):
                x, y0 = points[i]
                y1 = y0 + 1
                j = i + 1
                while j < len(points) and points[j][0] == x and points[j][1] == y1:
                    y1 += 1
                    j += 1
                segs.append((x, y0, x, y1))
                i = j
        else:
            points = sorted(points, key=lambda t: (t[1], t[0]))
            i = 0
            while i < len(points):
                x0, y = points[i]
                x1 = x0 + 1
                j = i + 1
                while j < len(points) and points[j][1] == y and points[j][0] == x1:
                    x1 += 1
                    j += 1
                segs.append((x0, y, x1, y))
                i = j

    merge(outer_h, vertical=False)
    merge(outer_v, vertical=True)
    return segs


def min_clear_width(obj) -> int:
    parts = [p for p in _parts_of(obj) if p.width > 0 and p.depth > 0]
    if not parts:
        return 0
    return min(min(p.width, p.depth) for p in parts)


def shape_complexity(obj) -> int:
    parts = _parts_of(obj)
    n = len(parts)
    if n <= 1:
        return 0
    if n == 2:
        return 1
    return 2


def validate_footprint(
    obj,
    min_clear: int | None = None,
    min_area: int | None = None,
    envelope: Envelope | None = None,
    max_components: int = MAX_COMPONENTS,
) -> list[str]:
    """Return rejection reasons. Empty list means valid. Does not repair."""
    errors: list[str] = []
    parts = _parts_of(obj)
    if not parts:
        return ["empty footprint"]
    if len(parts) > max_components:
        errors.append(f"more than {max_components} parts")
    for i, p in enumerate(parts):
        if p.width <= 0 or p.depth <= 0:
            errors.append(f"part {i} non-positive size")
    if any("non-positive" in e for e in errors):
        return errors
    if not _connected(parts):
        errors.append("disconnected parts")
    if len(parts) == 2 and not parts_touch(parts[0], parts[1], min_share=1):
        errors.append("parts do not share a positive-length edge")
    if min_clear is not None and min_clear_width(obj) < min_clear:
        errors.append("arm below minimum clear width")
    area = union_area(obj)
    if min_area is not None and area < min_area:
        errors.append("union area below minimum")
    if envelope is not None:
        for p in parts:
            if p.x < 0 or p.y < 0 or p.x2 > envelope.width or p.y2 > envelope.depth:
                errors.append("part outside envelope")
                break
    return errors


def paint_cells(grid: list[list[int]], obj, label: int, width: int, depth: int) -> None:
    for p in _parts_of(obj):
        x0 = max(0, p.x)
        y0 = max(0, p.y)
        x1 = min(width, p.x2)
        y1 = min(depth, p.y2)
        for y in range(y0, y1):
            row = grid[y]
            for x in range(x0, x1):
                row[x] = label


def _normalize(parts: Iterable[tuple[int, int, int, int]]) -> tuple[tuple[int, int, int, int], ...]:
    items = [(int(x), int(y), int(w), int(d)) for x, y, w, d in parts]
    min_x = min(p[0] for p in items)
    min_y = min(p[1] for p in items)
    return tuple((x - min_x, y - min_y, w, d) for x, y, w, d in items)


def generate_rect_candidates(spec: RoomSpec) -> list[ShapeCandidate]:
    seen: set[tuple[int, int]] = set()
    out: list[ShapeCandidate] = []

    def add(w: int, d: int) -> None:
        if w <= 0 or d <= 0 or (w, d) in seen:
            return
        seen.add((w, d))
        key = f"rect_{w}x{d}"
        out.append(ShapeCandidate(
            key=key, type="rectangle", parts=((0, 0, w, d),), complexity=0,
        ))

    add(spec.min_width, spec.min_depth)
    add(spec.preferred_width, spec.preferred_depth)
    if spec.allow_rotate:
        add(spec.min_depth, spec.min_width)
        add(spec.preferred_depth, spec.preferred_width)
    return out[:4]


def generate_l_candidates(spec: RoomSpec) -> list[ShapeCandidate]:
    rule = rule_for(spec.type)
    allowed = rule.get("allowed_shapes") or ["rectangle"]
    if "l_shape" not in allowed:
        return []
    min_w = max(1, spec.min_width)
    min_d = max(1, spec.min_depth)
    pref_w = max(min_w, spec.preferred_width)
    pref_d = max(min_d, spec.preferred_depth)
    arm_w = min_w
    stem_w = max(pref_w, arm_w + 2)
    stem_d = max(min_d, (pref_d * 2) // 3)
    extra_d = max(min_d, pref_d - stem_d if pref_d > stem_d else min_d)
    if stem_w <= arm_w:
        return []
    W, D1, A, D2 = stem_w, stem_d, arm_w, extra_d
    raw = [
        ((0, 0, W, D1), (0, D1, A, D2)),
        ((0, 0, W, D1), (W - A, D1, A, D2)),
        ((0, D2, W, D1), (0, 0, A, D2)),
        ((0, D2, W, D1), (W - A, 0, A, D2)),
    ]
    out: list[ShapeCandidate] = []
    seen: set[tuple[tuple[int, int, int, int], ...]] = set()
    min_clear = min(min_w, min_d)
    min_area = min_w * min_d
    for i, parts in enumerate(raw):
        norm = _normalize(parts)
        if norm in seen:
            continue
        fp = footprint_from_parts(norm, "l_shape")
        errs = validate_footprint(fp, min_clear=min_clear, min_area=min_area, max_components=2)
        if errs:
            continue
        if union_area(fp) >= bbox_of(fp)[2] * bbox_of(fp)[3]:
            continue
        seen.add(norm)
        out.append(ShapeCandidate(
            key=f"l_{i}_{norm[0][2]}x{norm[0][3]}",
            type="l_shape",
            parts=norm,
            complexity=1,
        ))
        if len(out) >= 2:
            break
    return out


def generate_shape_candidates(spec: RoomSpec) -> list[ShapeCandidate]:
    """Deterministic ~2-4 rectangles plus 1-2 L templates. Invalid filtered out."""
    return generate_rect_candidates(spec) + generate_l_candidates(spec)


def generate_solver_candidates(spec: RoomSpec) -> list[ShapeCandidate]:
    """CP-SAT set: one variable-size rectangle plus up to two validated L templates."""
    free = ShapeCandidate(
        key="rect_free",
        type="rectangle",
        parts=((0, 0, spec.preferred_width, spec.preferred_depth),),
        complexity=0,
        variable_size=True,
    )
    return [free, *generate_l_candidates(spec)]


def placed_from_candidate(
    spec: RoomSpec,
    origin_x: int,
    origin_y: int,
    candidate: ShapeCandidate,
    width: int | None = None,
    depth: int | None = None,
) -> PlacedRoom:
    if candidate.variable_size:
        w = int(width if width is not None else spec.preferred_width)
        d = int(depth if depth is not None else spec.preferred_depth)
        return PlacedRoom(
            id=spec.id, type=spec.type, name=spec.name,
            x=origin_x, y=origin_y, width=w, depth=d, zone=spec.zone,
        )
    parts = [
        FootprintPart(origin_x + x, origin_y + y, w, d)
        for x, y, w, d in candidate.parts
    ]
    bx, by, bw, bd = bbox_of(parts)
    return PlacedRoom(
        id=spec.id, type=spec.type, name=spec.name,
        x=bx, y=by, width=bw, depth=bd, zone=spec.zone,
        footprint=RoomFootprint(type=candidate.type, parts=parts),
    )
