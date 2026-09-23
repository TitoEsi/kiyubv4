"""Spatial organization models. Relative bands and graphs, not room coordinates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RelationKind = Literal[
    "wall_adjacent", "connected", "accessed_by", "outside_access",
    "near", "separated", "preferred", "avoid",
]
RelationStrength = Literal["required", "preferred", "neutral", "avoid"]
Axis = Literal["x", "y"]


@dataclass
class SemanticRelation:
    room_a: str
    room_b: str
    kind: RelationKind
    strength: RelationStrength = "preferred"


@dataclass
class ZoneBand:
    """Fractional envelope band. Not absolute coordinates."""

    zone: str
    axis: Axis
    lo_frac: float
    hi_frac: float


@dataclass
class LayoutStrategy:
    name: str
    description: str
    bands: list[ZoneBand]
    circulation_axis: Axis = "y"
    anchors: list[str] = field(default_factory=list)


@dataclass
class CirculationNode:
    room_id: str
    role: str  # entry | foyer | hall | branch | leaf


@dataclass
class CirculationEdge:
    room_a: str
    room_b: str


@dataclass
class CirculationGraph:
    nodes: list[CirculationNode]
    edges: list[CirculationEdge]
    min_width: int = 4
    preferred_width: int = 4
    max_length_hint: int = 24


@dataclass
class CirculationSegment:
    """Realized foyer/hallway rectangle. Not a hardcoded corridor shape."""

    room_id: str
    role: str
    width: int
    length: int
    area: int


@dataclass
class ClusterRelation:
    cluster_a: str
    cluster_b: str
    kind: str  # separated | connected | preferred | outside_access | accessed_by
    strength: RelationStrength = "preferred"


@dataclass
class RoomCluster:
    name: str
    room_ids: list[str]
    id: str = ""
    zone: str = ""
    preferred_area: int = 0
    min_area: int = 0
    anchor: str | None = None
    preferred_position: str = ""
    cohesion_weight: int = 1
    cx_frac: float = 0.5
    cy_frac: float = 0.5
    band: ZoneBand | None = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = self.name

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "zone": self.zone,
            "room_ids": list(self.room_ids),
            "preferred_area": self.preferred_area,
            "min_area": self.min_area,
            "anchor": self.anchor,
            "preferred_position": self.preferred_position,
            "cohesion_weight": self.cohesion_weight,
            "cx_frac": self.cx_frac,
            "cy_frac": self.cy_frac,
        }


@dataclass
class RoomBlock:
    """Block-level organization before exact room coordinates."""

    id: str
    zone: str
    room_ids: list[str]
    region: str = ""
    cx_frac: float = 0.5
    cy_frac: float = 0.5
    band: ZoneBand | None = None

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "zone": self.zone,
            "room_ids": list(self.room_ids),
            "region": self.region,
            "cx_frac": self.cx_frac,
            "cy_frac": self.cy_frac,
        }


@dataclass
class SpatialPlan:
    strategy: LayoutStrategy
    zones: dict[str, list[str]]
    relations: list[SemanticRelation]
    circulation: CirculationGraph
    clusters: list[RoomCluster]
    anchors: dict[str, str]
    preferred_edges: list[tuple[str, str, str]] = field(default_factory=list)
    cluster_relations: list[ClusterRelation] = field(default_factory=list)
    blocks: list[RoomBlock] = field(default_factory=list)
    access: object | None = None
    planning_zones: dict[str, list[str]] = field(default_factory=dict)

    def zone_ids(self, zone: str) -> list[str]:
        return list(self.zones.get(zone, []))
