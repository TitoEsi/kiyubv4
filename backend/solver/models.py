from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

SolveStatus = Literal["valid", "infeasible", "generation_error", "fallback"]


@dataclass
class Envelope:
    """Buildable rectangle in integer feet. Setbacks are placeholders, not Philippine code."""

    width: int
    depth: int
    lot_width_ft: float = 0.0
    lot_depth_ft: float = 0.0
    buildable_width: float = 0.0
    buildable_depth: float = 0.0

    @property
    def area(self) -> int:
        return self.width * self.depth


@dataclass
class RoomSpec:
    id: str
    type: str
    name: str
    min_width: int
    min_depth: int
    preferred_width: int
    preferred_depth: int
    required: bool
    zone: str
    floor: int = 1
    allow_rotate: bool = True
    max_aspect_ratio: float = 2.8
    max_area: int = 0
    preferred_area: int = 0


@dataclass
class FootprintPart:
    x: int
    y: int
    width: int
    depth: int

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.depth

    def as_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "width": self.width, "depth": self.depth}


@dataclass
class RoomFootprint:
    """Union of axis-aligned integer-foot rectangles. Authoritative occupied geometry."""

    type: str = "rectangle"  # rectangle | l_shape | composite
    parts: list[FootprintPart] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "type": self.type,
            "parts": [p.as_dict() for p in self.parts],
        }


@dataclass
class PlacedRoom:
    id: str
    type: str
    name: str
    x: int
    y: int
    width: int
    depth: int
    zone: str
    footprint: RoomFootprint | None = None

    def __post_init__(self) -> None:
        if self.footprint is None or not self.footprint.parts:
            self.footprint = RoomFootprint(
                type="rectangle",
                parts=[FootprintPart(self.x, self.y, self.width, self.depth)],
            )

    def parts(self) -> list[FootprintPart]:
        if self.footprint and self.footprint.parts:
            return self.footprint.parts
        return [FootprintPart(self.x, self.y, self.width, self.depth)]

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.depth

    def intersects(self, other: "PlacedRoom") -> bool:
        from .footprint import footprints_intersect
        return footprints_intersect(self, other)


@dataclass
class WallSegment:
    id: str
    x1: float
    y1: float
    x2: float
    y2: float
    kind: str = "interior"  # interior | exterior
    room_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "kind": self.kind,
            "roomIds": list(self.room_ids),
        }


@dataclass
class Opening:
    id: str
    wall_id: str
    kind: str  # door | window
    x: float
    y: float
    width: float
    height: float = 4.0
    is_vertical: bool = False
    room_ids: list[str] = field(default_factory=list)
    sill_height: float = 0.0

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "wallId": self.wall_id,
            "kind": self.kind,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "isVertical": self.is_vertical,
            "roomIds": list(self.room_ids),
            "sillHeight": self.sill_height,
        }


@dataclass
class Door:
    id: str
    room_a: str
    room_b: str
    x: float
    y: float
    width: float
    is_vertical: bool
    door_type: str = "interior"
    swing_direction: str = "in"


@dataclass
class FurnitureFootprint:
    id: str
    room_id: str
    kind: str
    x: float
    y: float
    width: float
    depth: float


@dataclass
class Rect:
    x: float
    y: float
    width: float
    depth: float

    @property
    def x2(self) -> float:
        return self.x + self.width

    @property
    def y2(self) -> float:
        return self.y + self.depth

    def intersects(self, other: "Rect") -> bool:
        return self.x < other.x2 and self.x2 > other.x and self.y < other.y2 and self.y2 > other.y


@dataclass
class TopologyEdge:
    room_a: str
    room_b: str
    relation: str  # adjacent | connected | near | accessed_by | outside_access | separated
    hard: bool = True
    choice_group: str | None = None


@dataclass
class RoomProgram:
    rooms: list[RoomSpec]
    envelope: Envelope
    outdoor_requested: bool = False
    bedrooms_requested: int = 0
    bathrooms_requested: int = 0


@dataclass
class Layout:
    rooms: list[PlacedRoom]
    doors: list[Door] = field(default_factory=list)
    furniture: list[FurnitureFootprint] = field(default_factory=list)
    envelope: Optional[Envelope] = None
    topology: list[TopologyEdge] = field(default_factory=list)
    walls: list[WallSegment] = field(default_factory=list)
    openings: list[Opening] = field(default_factory=list)

    def room_by_id(self, rid: str) -> Optional[PlacedRoom]:
        return next((r for r in self.rooms if r.id == rid), None)


@dataclass
class ValidationIssue:
    type: str
    room: str
    message: str
    severity: str = "error"

    def as_dict(self) -> dict:
        return {
            "type": self.type,
            "room": self.room,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class ValidationReport:
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return len(self.errors) == 0

    def as_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": [e.as_dict() for e in self.errors],
            "warnings": [w.as_dict() for w in self.warnings],
        }


@dataclass
class SolveResult:
    status: SolveStatus
    layout: Optional[Layout] = None
    reason: str = ""
    reason_code: str = ""
    conflicts: list[dict] = field(default_factory=list)
    validation: Optional[ValidationReport] = None
    plans: list[dict] = field(default_factory=list)
    validated: bool = False
    quality_score: Optional[dict] = None
