"""Configurable residential planning assumptions.

Not Philippine building-code values and not professional architectural approval.
irc_compliant remains false unless a separate regulatory validator establishes it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


PLANNING_ZONES = (
    "arrival",
    "public",
    "private",
    "service",
    "circulation",
    "outdoor",
)

# Default generated types for a typical Philippine single-family program.
# mudroom is intentionally absent. Keep ROOM_RULES support for custom rooms.
DEFAULT_GENERATED_TYPES = frozenset({
    "living_room", "kitchen", "dining_room", "foyer", "hallway",
    "master_bedroom", "bedroom", "ensuite_bathroom", "bathroom", "half_bath",
    "walk_in_closet", "laundry_room", "garage", "patio", "deck", "home_office",
})

# Per-type planning metadata. Sizes stay in ROOM_RULES.
ROOM_PROFILES: dict[str, dict] = {
    "living_room": {
        "planning_zones": ["public"],
        "privacy_level": "public",
        "access_type": "circulation",
        "preferred_frontage": "rear",
        "allowed_frontage": ("front", "side", "rear"),
        "requires_exterior_access": False,
        "requires_vehicle_access": False,
        "preferred_neighbors": ("dining_room", "kitchen", "foyer", "patio"),
        "required_neighbors": (),
        "prohibited_neighbors": ("garage",),
        "preferred_orientation": "rear_outdoor",
        "service_dependency": None,
        "outdoor_relationship": "strong",
        "light_ventilation_requirement": "preferred",
    },
    "dining_room": {
        "planning_zones": ["public"],
        "privacy_level": "public",
        "access_type": "circulation",
        "preferred_frontage": "rear",
        "allowed_frontage": ("side", "rear"),
        "requires_exterior_access": False,
        "requires_vehicle_access": False,
        "preferred_neighbors": ("living_room", "kitchen", "patio"),
        "required_neighbors": ("kitchen",),
        "prohibited_neighbors": ("garage",),
        "preferred_orientation": "rear_outdoor",
        "service_dependency": None,
        "outdoor_relationship": "strong",
        "light_ventilation_requirement": "preferred",
    },
    "kitchen": {
        "planning_zones": ["public", "service"],
        "privacy_level": "semi_public",
        "access_type": "circulation",
        "preferred_frontage": "side",
        "allowed_frontage": ("side", "rear", "front"),
        "requires_exterior_access": False,
        "requires_vehicle_access": False,
        "preferred_neighbors": ("dining_room", "living_room", "laundry_room", "patio"),
        "required_neighbors": ("dining_room",),
        "prohibited_neighbors": (),
        "preferred_orientation": "service_side",
        "service_dependency": "wet_core",
        "outdoor_relationship": "preferred",
        "light_ventilation_requirement": "preferred",
    },
    "foyer": {
        "planning_zones": ["arrival"],
        "privacy_level": "arrival",
        "access_type": "entry",
        "preferred_frontage": "front",
        "allowed_frontage": ("front",),
        "requires_exterior_access": True,
        "requires_vehicle_access": False,
        "preferred_neighbors": ("hallway", "living_room"),
        "required_neighbors": ("hallway",),
        "prohibited_neighbors": (),
        "preferred_orientation": "street",
        "service_dependency": None,
        "outdoor_relationship": "street",
        "light_ventilation_requirement": "optional",
    },
    "hallway": {
        "planning_zones": ["circulation"],
        "privacy_level": "circulation",
        "access_type": "distribution",
        "preferred_frontage": "interior",
        "allowed_frontage": ("interior", "side"),
        "requires_exterior_access": False,
        "requires_vehicle_access": False,
        "preferred_neighbors": ("foyer", "bedroom", "bathroom", "living_room"),
        "required_neighbors": (),
        "prohibited_neighbors": (),
        "preferred_orientation": "spine",
        "service_dependency": None,
        "outdoor_relationship": None,
        "light_ventilation_requirement": "optional",
    },
    "master_bedroom": {
        "planning_zones": ["private"],
        "privacy_level": "private",
        "access_type": "circulation",
        "preferred_frontage": "side",
        "allowed_frontage": ("side", "rear"),
        "requires_exterior_access": False,
        "requires_vehicle_access": False,
        "preferred_neighbors": ("ensuite_bathroom", "walk_in_closet", "hallway"),
        "required_neighbors": ("ensuite_bathroom", "walk_in_closet"),
        "prohibited_neighbors": ("garage", "kitchen"),
        "preferred_orientation": "quiet",
        "service_dependency": None,
        "outdoor_relationship": "optional",
        "light_ventilation_requirement": "preferred",
    },
    "bedroom": {
        "planning_zones": ["private"],
        "privacy_level": "private",
        "access_type": "circulation",
        "preferred_frontage": "side",
        "allowed_frontage": ("side", "rear"),
        "requires_exterior_access": False,
        "requires_vehicle_access": False,
        "preferred_neighbors": ("bathroom", "hallway", "bedroom"),
        "required_neighbors": (),
        "prohibited_neighbors": ("garage", "kitchen"),
        "preferred_orientation": "quiet",
        "service_dependency": None,
        "outdoor_relationship": "optional",
        "light_ventilation_requirement": "preferred",
    },
    "ensuite_bathroom": {
        "planning_zones": ["private", "service"],
        "privacy_level": "private",
        "access_type": "suite",
        "preferred_frontage": "interior",
        "allowed_frontage": ("interior", "side"),
        "requires_exterior_access": False,
        "requires_vehicle_access": False,
        "preferred_neighbors": ("master_bedroom",),
        "required_neighbors": ("master_bedroom",),
        "prohibited_neighbors": ("foyer", "living_room"),
        "preferred_orientation": "wet_core",
        "service_dependency": "wet_core",
        "outdoor_relationship": None,
        "light_ventilation_requirement": "optional",
    },
    "bathroom": {
        "planning_zones": ["private", "service"],
        "privacy_level": "private",
        "access_type": "circulation",
        "preferred_frontage": "interior",
        "allowed_frontage": ("interior", "side"),
        "requires_exterior_access": False,
        "requires_vehicle_access": False,
        "preferred_neighbors": ("hallway", "bedroom"),
        "required_neighbors": (),
        "prohibited_neighbors": ("foyer",),
        "preferred_orientation": "wet_core",
        "service_dependency": "wet_core",
        "outdoor_relationship": None,
        "light_ventilation_requirement": "optional",
    },
    "half_bath": {
        "planning_zones": ["private", "service"],
        "privacy_level": "semi_private",
        "access_type": "circulation",
        "preferred_frontage": "interior",
        "allowed_frontage": ("interior",),
        "requires_exterior_access": False,
        "requires_vehicle_access": False,
        "preferred_neighbors": ("hallway",),
        "required_neighbors": (),
        "prohibited_neighbors": ("foyer",),
        "preferred_orientation": "wet_core",
        "service_dependency": "wet_core",
        "outdoor_relationship": None,
        "light_ventilation_requirement": "optional",
    },
    "walk_in_closet": {
        "planning_zones": ["private"],
        "privacy_level": "private",
        "access_type": "suite",
        "preferred_frontage": "interior",
        "allowed_frontage": ("interior",),
        "requires_exterior_access": False,
        "requires_vehicle_access": False,
        "preferred_neighbors": ("master_bedroom",),
        "required_neighbors": ("master_bedroom",),
        "prohibited_neighbors": (),
        "preferred_orientation": "suite",
        "service_dependency": None,
        "outdoor_relationship": None,
        "light_ventilation_requirement": "optional",
    },
    "closet": {
        "planning_zones": ["private"],
        "privacy_level": "private",
        "access_type": "suite",
        "preferred_frontage": "interior",
        "allowed_frontage": ("interior",),
        "requires_exterior_access": False,
        "requires_vehicle_access": False,
        "preferred_neighbors": ("bedroom",),
        "required_neighbors": (),
        "prohibited_neighbors": (),
        "preferred_orientation": "suite",
        "service_dependency": None,
        "outdoor_relationship": None,
        "light_ventilation_requirement": "optional",
    },
    "laundry_room": {
        "planning_zones": ["service"],
        "privacy_level": "service",
        "access_type": "circulation",
        "preferred_frontage": "side",
        "allowed_frontage": ("side", "front"),
        "requires_exterior_access": False,
        "requires_vehicle_access": False,
        "preferred_neighbors": ("kitchen", "hallway", "garage"),
        "required_neighbors": (),
        "prohibited_neighbors": (),
        "preferred_orientation": "service_side",
        "service_dependency": "wet_core",
        "outdoor_relationship": None,
        "light_ventilation_requirement": "optional",
    },
    "garage": {
        "planning_zones": ["arrival", "service"],
        "privacy_level": "service",
        "access_type": "vehicle",
        "preferred_frontage": "front",
        "allowed_frontage": ("front", "side"),
        "requires_exterior_access": True,
        "requires_vehicle_access": True,
        "preferred_neighbors": ("foyer", "laundry_room", "kitchen"),
        "required_neighbors": (),
        "prohibited_neighbors": ("bedroom", "master_bedroom"),
        "preferred_orientation": "street",
        "service_dependency": "vehicle",
        "outdoor_relationship": "driveway",
        "light_ventilation_requirement": "optional",
    },
    "mudroom": {
        "planning_zones": ["service"],
        "privacy_level": "service",
        "access_type": "circulation",
        "preferred_frontage": "side",
        "allowed_frontage": ("side", "front"),
        "requires_exterior_access": False,
        "requires_vehicle_access": False,
        "preferred_neighbors": ("garage", "laundry_room", "kitchen"),
        "required_neighbors": (),
        "prohibited_neighbors": (),
        "preferred_orientation": "service_side",
        "service_dependency": "optional_custom",
        "outdoor_relationship": None,
        "light_ventilation_requirement": "optional",
    },
    "patio": {
        "planning_zones": ["outdoor"],
        "privacy_level": "outdoor",
        "access_type": "exterior",
        "preferred_frontage": "rear",
        "allowed_frontage": ("rear", "side"),
        "requires_exterior_access": True,
        "requires_vehicle_access": False,
        "preferred_neighbors": ("living_room", "dining_room", "kitchen"),
        "required_neighbors": (),
        "prohibited_neighbors": (),
        "preferred_orientation": "rear_yard",
        "service_dependency": None,
        "outdoor_relationship": "required",
        "light_ventilation_requirement": "open",
    },
    "deck": {
        "planning_zones": ["outdoor"],
        "privacy_level": "outdoor",
        "access_type": "exterior",
        "preferred_frontage": "rear",
        "allowed_frontage": ("rear", "side"),
        "requires_exterior_access": True,
        "requires_vehicle_access": False,
        "preferred_neighbors": ("living_room", "dining_room"),
        "required_neighbors": (),
        "prohibited_neighbors": (),
        "preferred_orientation": "rear_yard",
        "service_dependency": None,
        "outdoor_relationship": "required",
        "light_ventilation_requirement": "open",
    },
    "home_office": {
        "planning_zones": ["public"],
        "privacy_level": "semi_private",
        "access_type": "circulation",
        "preferred_frontage": "front",
        "allowed_frontage": ("front", "side"),
        "requires_exterior_access": False,
        "requires_vehicle_access": False,
        "preferred_neighbors": ("foyer", "hallway"),
        "required_neighbors": (),
        "prohibited_neighbors": ("garage",),
        "preferred_orientation": "quiet",
        "service_dependency": None,
        "outdoor_relationship": "optional",
        "light_ventilation_requirement": "preferred",
    },
}

PHILIPPINE_RESIDENTIAL_DEFAULTS: dict = {
    "name": "philippine_single_family",
    "auto_generate_mudroom": False,
    "laundry_is_service": True,
    "garage_is_arrival_service": True,
    "garage_requires_vehicle_access": True,
    "foyer_is_arrival": True,
    "living_dining_kitchen_related": True,
    "bedrooms_private_cluster": True,
    "primary_suite_privacy": True,
    "wet_service_compactness": True,
    "rear_outdoor_to_public": True,
    "service_not_through_bedrooms": True,
    "habitable_exterior_exposure": "preferred",
    "patio_is_outdoor_not_interior": True,
    "irc_compliant": False,
    "note": (
        "Configurable planning assumptions for single-family houses. "
        "Not professional architectural approval or code compliance."
    ),
}


@dataclass
class RoomPlanningProfile:
    planning_zones: list[str] = field(default_factory=lambda: ["public"])
    privacy_level: str = "public"
    access_type: str = "circulation"
    preferred_frontage: str = "interior"
    allowed_frontage: tuple[str, ...] = ("interior",)
    requires_exterior_access: bool = False
    requires_vehicle_access: bool = False
    preferred_neighbors: tuple[str, ...] = ()
    required_neighbors: tuple[str, ...] = ()
    prohibited_neighbors: tuple[str, ...] = ()
    preferred_orientation: str | None = None
    service_dependency: str | None = None
    outdoor_relationship: str | None = None
    light_ventilation_requirement: str = "optional"

    @classmethod
    def for_type(cls, room_type: str) -> "RoomPlanningProfile":
        raw = ROOM_PROFILES.get(room_type) or {
            "planning_zones": ["public"],
            "privacy_level": "public",
            "access_type": "circulation",
            "preferred_frontage": "interior",
            "allowed_frontage": ("interior",),
        }
        return cls(**{k: v for k, v in raw.items() if k in cls.__dataclass_fields__})


def profile_defaults() -> dict:
    return dict(PHILIPPINE_RESIDENTIAL_DEFAULTS)
