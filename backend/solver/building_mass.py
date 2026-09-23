"""Building mass / footprint planning target.

Preferred area comes from ROOM_RULES via ArchitecturalProgram.
Not a second size table. Not a hard CP-SAT rectangle. Not Philippine code.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .architectural_program import from_room_program
from .models import Envelope, RoomProgram
from .room_rules import CIRCULATION_TYPES, OUTDOOR_TYPES
from .spatial_plan import SpatialPlan

# Slack beyond room rectangles already in the program (foyer/hall counted in required).
CIRCULATION_EXTRA_FACTOR = 0.05
# Approximate wall thickness / structure between rooms.
WALL_STRUCTURE_FACTOR = 0.08
# Construction slack; garage/mud preferred area is already in required_program_area.
SERVICE_EXTRA_FACTOR = 0.02
# Preferred depth/width. Compact residential footprint, not a 10x100 bar.
TARGET_ASPECT = 1.25
ASPECT_MAX = 2.2
# Use more of a large lot without filling it. Evaluator still distinguishes packing.
UTILIZATION_TARGET = 0.58
UTILIZATION_HI = 0.72


@dataclass
class BuildingMass:
    """Architectural planning target. Integer feet. Not a forced fill rectangle."""

    x: int
    y: int
    width: int
    depth: int
    shape: str = "rectangle"
    patio_reserve_depth: int = 0
    preferred_area: int = 0
    min_area: int = 0
    aspect: float = 1.0
    allowances: dict = field(default_factory=dict)

    @property
    def area(self) -> int:
        return self.width * self.depth

    @property
    def frontage(self) -> tuple[int, int]:
        return self.x, self.width

    @property
    def rear_y(self) -> int:
        return self.y + self.depth

    def contains_cell(self, x: int, y: int) -> bool:
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.depth

    def contains_rect(self, x: int, y: int, w: int, d: int) -> bool:
        return (
            x >= self.x
            and y >= self.y
            and x + w <= self.x + self.width
            and y + d <= self.y + self.depth
        )

    def as_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "depth": self.depth,
            "area": self.area,
            "shape": self.shape,
            "frontage": {"x": self.x, "width": self.width},
            "rear_y": self.rear_y,
            "patio_reserve_depth": self.patio_reserve_depth,
            "preferred_area": self.preferred_area,
            "min_area": self.min_area,
            "aspect": round(self.aspect, 3),
            "allowances": dict(self.allowances),
        }


def preferred_building_area(program: RoomProgram) -> tuple[int, int, dict]:
    """Return (preferred_area, min_area, allowances) from existing ROOM_RULES sizes."""
    arch = from_room_program(program)
    required = 0
    occupied_pref = 0
    min_area = 0
    for space in arch.spaces:
        if space.room_type in OUTDOOR_TYPES:
            continue
        required += space.preferred_area
        min_area += space.min_area
        if space.room_type not in CIRCULATION_TYPES:
            occupied_pref += space.preferred_area
    circ_extra = int(round(CIRCULATION_EXTRA_FACTOR * occupied_pref))
    wall = int(round(WALL_STRUCTURE_FACTOR * required))
    service = int(round(SERVICE_EXTRA_FACTOR * required))
    preferred = required + circ_extra + wall + service
    allowances = {
        "required_program_area": required,
        "occupied_preferred": occupied_pref,
        "circulation_extra": circ_extra,
        "circulation_extra_factor": CIRCULATION_EXTRA_FACTOR,
        "wall_structure": wall,
        "wall_structure_factor": WALL_STRUCTURE_FACTOR,
        "service_extra": service,
        "service_extra_factor": SERVICE_EXTRA_FACTOR,
        "min_building_area": min_area,
    }
    return preferred, min_area, allowances


def _patio_reserve(program: RoomProgram) -> int:
    if not program.outdoor_requested:
        return 0
    outdoor = [r for r in program.rooms if r.type in OUTDOOR_TYPES]
    if not outdoor:
        return 0
    spec = outdoor[0]
    return max(spec.min_depth, spec.preferred_depth)


def _clamp_aspect(width: int, depth: int) -> tuple[int, int]:
    lo, hi = min(width, depth), max(width, depth)
    if lo <= 0:
        return max(1, width), max(1, depth)
    if hi / lo <= ASPECT_MAX:
        return width, depth
    area = width * depth
    if width >= depth:
        width = int(round(math.sqrt(area * ASPECT_MAX)))
        depth = max(1, int(round(area / max(width, 1))))
    else:
        depth = int(round(math.sqrt(area * ASPECT_MAX)))
        width = max(1, int(round(area / max(depth, 1))))
    return max(1, width), max(1, depth)


def plan_building_mass(
    program: RoomProgram,
    envelope: Envelope | None = None,
    spatial: SpatialPlan | None = None,
) -> BuildingMass:
    env = envelope or program.envelope
    preferred, min_area, allowances = preferred_building_area(program)
    patio_reserve = _patio_reserve(program)
    max_w = max(1, env.width)
    max_d = max(1, env.depth - patio_reserve)
    if max_d < 1:
        patio_reserve = max(0, env.depth - 1)
        max_d = max(1, env.depth - patio_reserve)

    envelope_usable = max_w * max_d
    target = int(envelope_usable * UTILIZATION_TARGET)
    hi = int(envelope_usable * UTILIZATION_HI)
    if envelope_usable > preferred:
        grown = min(target, hi, int(preferred * 1.30))
        preferred = max(preferred, grown)
    allowances = dict(allowances)
    allowances["utilization_target"] = UTILIZATION_TARGET
    allowances["utilization_hi"] = UTILIZATION_HI
    allowances["envelope_usable"] = envelope_usable

    width = max(1, int(round(math.sqrt(preferred / TARGET_ASPECT))))
    depth = max(1, int(round(preferred / width)))
    width, depth = _clamp_aspect(width, depth)
    width = min(width, max_w)
    depth = min(depth, max_d)

    def grow(w: int, d: int) -> tuple[int, int]:
        while w * d < min_area and (w < max_w or d < max_d):
            if w <= d and w < max_w:
                w += 1
            elif d < max_d:
                d += 1
            elif w < max_w:
                w += 1
            else:
                break
        return w, d

    width, depth = grow(width, depth)
    width, depth = _clamp_aspect(width, depth)
    width = min(width, max_w)
    depth = min(depth, max_d)
    if width * depth < min_area:
        width, depth = grow(width, depth)
        width = min(width, max_w)
        depth = min(depth, max_d)

    aspect = depth / width if width else 1.0
    if aspect > ASPECT_MAX or (width / depth if depth else 1.0) > ASPECT_MAX:
        width, depth = _clamp_aspect(min(width, max_w), min(depth, max_d))
        width = min(width, max_w)
        depth = min(depth, max_d)

    x = max(0, (env.width - width) // 2)
    y = 0
    if y + depth + patio_reserve > env.depth:
        depth = max(1, env.depth - patio_reserve - y)
    mass = BuildingMass(
        x=x,
        y=y,
        width=width,
        depth=depth,
        patio_reserve_depth=patio_reserve,
        preferred_area=preferred,
        min_area=min_area,
        aspect=depth / width if width else 1.0,
        allowances=allowances,
    )
    _ = spatial  # strategy bands already locate garage at front/side; mass stays y=0
    if spatial and any(r.type == "garage" for r in program.rooms):
        allowances = dict(mass.allowances)
        allowances["garage_arrival"] = "front_or_side"
        mass.allowances = allowances
    return mass


def log_building_mass(mass: BuildingMass) -> None:
    print(
        f"[KIYUB MASS] {mass.width}x{mass.depth} ft at ({mass.x},{mass.y}) "
        f"area={mass.area} preferred={mass.preferred_area} min={mass.min_area} "
        f"aspect={mass.aspect:.2f} patio_reserve={mass.patio_reserve_depth}"
    )
    a = mass.allowances
    print(
        f"[KIYUB MASS] allowances required={a.get('required_program_area')} "
        f"circ_extra={a.get('circulation_extra')} wall={a.get('wall_structure')} "
        f"service={a.get('service_extra')}"
    )
    print("[KIYUB MASS] Planning target, not a hard fill constraint or professional approval.")
