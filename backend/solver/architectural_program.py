"""Architectural program semantics derived from RoomProgram.

Sizes come from ROOM_RULES / RoomSpec. Not a second dimensions table.
Not Philippine building-code values.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import RoomProgram, RoomSpec
from .planning_profile import RoomPlanningProfile
from .room_rules import CIRCULATION_TYPES, OUTDOOR_TYPES, ZONE_BY_TYPE, aspect_limit

WET_TYPES = frozenset({
    "kitchen", "bathroom", "ensuite_bathroom", "half_bath", "laundry_room",
})
DAYLIGHT_TYPES = frozenset({
    "living_room", "dining_room", "family_room", "kitchen",
    "master_bedroom", "bedroom", "home_office",
})
EXTERIOR_ACCESS_TYPES = frozenset({"patio", "deck", "living_room"})
PRIVATE_TYPES = frozenset({
    "master_bedroom", "bedroom", "ensuite_bathroom", "bathroom",
    "half_bath", "walk_in_closet", "closet",
})


def semantic_zone(room_type: str) -> str:
    raw = ZONE_BY_TYPE.get(room_type, "public")
    return "exterior" if raw == "outdoor" else raw


@dataclass
class ProgramSpace:
    id: str
    room_type: str
    name: str
    zone: str
    min_width: int
    min_depth: int
    preferred_width: int
    preferred_depth: int
    min_area: int
    preferred_area: int
    max_area: int
    max_aspect_ratio: float
    privacy: str
    daylight: bool
    exterior_access: bool
    wet: bool
    circulation: bool
    planning_zones: list[str]
    privacy_level: str
    access_type: str
    preferred_frontage: str
    allowed_frontage: tuple[str, ...]
    requires_exterior_access: bool
    requires_vehicle_access: bool
    preferred_neighbors: tuple[str, ...]
    required_neighbors: tuple[str, ...]
    prohibited_neighbors: tuple[str, ...]
    preferred_orientation: str | None
    service_dependency: str | None
    outdoor_relationship: str | None
    light_ventilation_requirement: str

    @classmethod
    def from_spec(cls, spec: RoomSpec) -> "ProgramSpace":
        zone = semantic_zone(spec.type)
        profile = RoomPlanningProfile.for_type(spec.type)
        planning_zones = list(profile.planning_zones)
        return cls(
            id=spec.id,
            room_type=spec.type,
            name=spec.name,
            zone=zone,
            min_width=spec.min_width,
            min_depth=spec.min_depth,
            preferred_width=spec.preferred_width,
            preferred_depth=spec.preferred_depth,
            min_area=spec.min_width * spec.min_depth,
            preferred_area=spec.preferred_area or spec.preferred_width * spec.preferred_depth,
            max_area=spec.max_area or int((spec.preferred_width * spec.preferred_depth) * 1.8),
            max_aspect_ratio=spec.max_aspect_ratio or aspect_limit(spec.type),
            privacy=profile.privacy_level,
            daylight=spec.type in DAYLIGHT_TYPES,
            exterior_access=profile.requires_exterior_access or spec.type in OUTDOOR_TYPES,
            wet=spec.type in WET_TYPES,
            circulation=spec.type in CIRCULATION_TYPES,
            planning_zones=planning_zones,
            privacy_level=profile.privacy_level,
            access_type=profile.access_type,
            preferred_frontage=profile.preferred_frontage,
            allowed_frontage=profile.allowed_frontage,
            requires_exterior_access=profile.requires_exterior_access,
            requires_vehicle_access=profile.requires_vehicle_access,
            preferred_neighbors=profile.preferred_neighbors,
            required_neighbors=profile.required_neighbors,
            prohibited_neighbors=profile.prohibited_neighbors,
            preferred_orientation=profile.preferred_orientation,
            service_dependency=profile.service_dependency,
            outdoor_relationship=profile.outdoor_relationship,
            light_ventilation_requirement=profile.light_ventilation_requirement,
        )


@dataclass
class ArchitecturalProgram:
    spaces: list[ProgramSpace]
    bedrooms_requested: int
    bathrooms_requested: int
    outdoor_requested: bool

    def by_zone(self, zone: str) -> list[ProgramSpace]:
        return [s for s in self.spaces if s.zone == zone]

    def by_type(self, room_type: str) -> list[ProgramSpace]:
        return [s for s in self.spaces if s.room_type == room_type]

    def by_planning_zone(self, zone: str) -> list[ProgramSpace]:
        return [s for s in self.spaces if zone in s.planning_zones]

    def first(self, room_type: str) -> ProgramSpace | None:
        found = self.by_type(room_type)
        return found[0] if found else None

    def as_dict(self) -> dict:
        return {
            "room_count": len(self.spaces),
            "bedrooms_requested": self.bedrooms_requested,
            "bathrooms_requested": self.bathrooms_requested,
            "outdoor_requested": self.outdoor_requested,
            "types": [s.room_type for s in self.spaces],
            "zones": sorted({s.zone for s in self.spaces}),
        }


@dataclass
class ProgramValidation:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings}


def validate_program(arch: ArchitecturalProgram, envelope=None) -> ProgramValidation:
    """Check program completeness before generation. Heuristic, not code."""
    errors: list[str] = []
    warnings: list[str] = []
    beds = len(arch.by_type("bedroom")) + len(arch.by_type("master_bedroom"))
    baths = (
        len(arch.by_type("bathroom"))
        + len(arch.by_type("ensuite_bathroom"))
        + len(arch.by_type("half_bath"))
    )
    if beds != arch.bedrooms_requested:
        errors.append(f"Bedroom count {beds} != requested {arch.bedrooms_requested}")
    if baths != arch.bathrooms_requested:
        errors.append(f"Bathroom count {baths} != requested {arch.bathrooms_requested}")
    if not arch.first("living_room") and not arch.first("great_room"):
        errors.append("Program has no living/great room")
    if not arch.first("kitchen"):
        warnings.append("Program has no kitchen")
    if envelope is not None:
        area = sum(s.min_area for s in arch.spaces if not s.circulation)
        env_area = getattr(envelope, "area", 0) or 0
        if env_area and area > env_area:
            errors.append("Minimum program area exceeds buildable envelope")
    return ProgramValidation(ok=not errors, errors=errors, warnings=warnings)


def from_room_program(program: RoomProgram) -> ArchitecturalProgram:
    return ArchitecturalProgram(
        spaces=[ProgramSpace.from_spec(s) for s in program.rooms],
        bedrooms_requested=program.bedrooms_requested,
        bathrooms_requested=program.bathrooms_requested,
        outdoor_requested=program.outdoor_requested,
    )


def from_constraints(constraints: dict, envelope=None) -> ArchitecturalProgram:
    """Derive program spaces from questionnaire constraints, never a hardcoded room list."""
    from .room_program import envelope_from_constraints
    from .room_program import from_constraints as rooms_from_constraints

    env = envelope or envelope_from_constraints(constraints)
    return from_room_program(rooms_from_constraints(constraints, env))
