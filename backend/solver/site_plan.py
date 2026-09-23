"""Site interpretation and access zones. Not room coordinates and not a FloorPlan room."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Envelope, PlacedRoom, RoomProgram


@dataclass
class AccessZone:
    """Envelope-relative access band. Not a generated program room."""

    kind: str  # driveway | front_walk | street
    x: int
    y: int
    width: int
    depth: int
    frontage: str  # front | left | right | rear

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "depth": self.depth,
            "frontage": self.frontage,
        }

    def overlaps_room(self, room: PlacedRoom) -> bool:
        return (
            room.x < self.x + self.width
            and room.x2 > self.x
            and room.y < self.y + self.depth
            and room.y2 > self.y
        )

    def touches_room(self, room: PlacedRoom) -> bool:
        if self.overlaps_room(room):
            return True
        share_x = min(room.x2, self.x + self.width) - max(room.x, self.x)
        share_y = min(room.y2, self.y + self.depth) - max(room.y, self.y)
        if room.y2 == self.y or self.y + self.depth == room.y:
            return share_x >= 3
        if room.x2 == self.x or self.x + self.width == room.x:
            return share_y >= 3
        return False


@dataclass
class SiteInterpretation:
    lot_shape: str
    access: str  # front
    street_edge: str  # y0
    vehicle_frontage: str  # front
    pedestrian_frontage: str
    rear_outdoor: bool
    envelope_width: int
    envelope_depth: int

    def as_dict(self) -> dict:
        return {
            "lot_shape": self.lot_shape,
            "access": self.access,
            "street_edge": self.street_edge,
            "vehicle_frontage": self.vehicle_frontage,
            "pedestrian_frontage": self.pedestrian_frontage,
            "rear_outdoor": self.rear_outdoor,
        }


@dataclass
class AccessPlan:
    site: SiteInterpretation
    driveway: AccessZone
    front_walk: AccessZone
    street: AccessZone
    garage_allowed_edges: tuple[str, ...] = ("front", "left", "right")

    def as_dict(self) -> dict:
        return {
            "site": self.site.as_dict(),
            "driveway": self.driveway.as_dict(),
            "front_walk": self.front_walk.as_dict(),
            "street": self.street.as_dict(),
            "garage_allowed_edges": list(self.garage_allowed_edges),
        }


def interpret_site(program: RoomProgram, envelope: Envelope | None = None) -> SiteInterpretation:
    env = envelope or program.envelope
    return SiteInterpretation(
        lot_shape="rectangle",
        access="front",
        street_edge="y0",
        vehicle_frontage="front",
        pedestrian_frontage="front",
        rear_outdoor=bool(program.outdoor_requested),
        envelope_width=env.width,
        envelope_depth=env.depth,
    )


def plan_access(program: RoomProgram, envelope: Envelope | None = None) -> AccessPlan:
    """STREET → driveway / walk → garage / foyer. Zones only; no extra rooms."""
    env = envelope or program.envelope
    site = interpret_site(program, env)
    drive_w = min(env.width, max(12, env.width // 3))
    drive_d = min(8, max(4, env.depth // 12))
    walk_w = min(8, max(4, env.width // 8))
    street = AccessZone("street", 0, 0, env.width, 0, "front")
    driveway = AccessZone("driveway", 0, 0, drive_w, drive_d, "front")
    front_walk = AccessZone(
        "front_walk",
        max(0, (env.width - walk_w) // 2),
        0,
        walk_w,
        max(3, drive_d // 2),
        "front",
    )
    return AccessPlan(
        site=site,
        driveway=driveway,
        front_walk=front_walk,
        street=street,
        garage_allowed_edges=("front", "left", "right"),
    )


def garage_touches_vehicle_frontage(room: PlacedRoom, envelope: Envelope) -> bool:
    """Front (y==0) or a side edge. Not an interior-only room."""
    if room.y == 0:
        return True
    if room.x == 0:
        return True
    if room.x2 == envelope.width:
        return True
    return False


def garage_is_central_interior(room: PlacedRoom, envelope: Envelope) -> bool:
    if garage_touches_vehicle_frontage(room, envelope):
        return False
    cx = room.x + room.width / 2.0
    cy = room.y + room.depth / 2.0
    return (
        0.30 * envelope.width < cx < 0.70 * envelope.width
        and 0.30 * envelope.depth < cy < 0.70 * envelope.depth
    )
