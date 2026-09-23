"""Furniture template catalog for usability analysis.

Does not place furniture into FloorPlan. Does not render.
Sizes are placeholders, not code-verified clearances.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FurnitureTemplate:
    id: str
    room_type: str
    kind: str
    width: float
    depth: float
    required_clearance: float
    preferred_position: str
    category: str = "furniture"
    placement_rules: str = "wall"
    orientation_options: tuple[str, ...] = ("wh", "hw")


FURNITURE_TEMPLATES: tuple[FurnitureTemplate, ...] = (
    FurnitureTemplate("bed", "bedroom", "bed", 7.0, 5.0, 3.0, "wall", "furniture", "wall", ("wh", "hw")),
    FurnitureTemplate("wardrobe", "bedroom", "wardrobe", 4.0, 2.0, 2.0, "wall", "storage", "wall", ("wh", "hw")),
    FurnitureTemplate("nightstand", "bedroom", "nightstand", 2.0, 1.5, 1.5, "wall", "furniture", "wall", ("wh",)),
    FurnitureTemplate("master_bed", "master_bedroom", "bed", 7.0, 6.0, 3.0, "wall", "furniture", "wall", ("wh", "hw")),
    FurnitureTemplate("master_wardrobe", "master_bedroom", "wardrobe", 6.0, 2.0, 2.0, "wall", "storage", "wall", ("wh", "hw")),
    FurnitureTemplate("master_nightstand", "master_bedroom", "nightstand", 2.0, 1.5, 1.5, "wall", "furniture", "wall", ("wh",)),
    FurnitureTemplate("sofa", "living_room", "sofa", 7.0, 3.0, 3.0, "wall", "furniture", "wall", ("wh", "hw")),
    FurnitureTemplate("coffee_table", "living_room", "coffee_table", 4.0, 2.0, 2.0, "center", "furniture", "center", ("wh", "hw")),
    FurnitureTemplate("media_wall", "living_room", "media_wall", 6.0, 1.5, 3.0, "wall", "furniture", "wall", ("wh",)),
    FurnitureTemplate("dining_table", "dining_room", "dining_table", 6.0, 3.5, 3.0, "center", "furniture", "center", ("wh", "hw")),
    FurnitureTemplate("kitchen_counter", "kitchen", "counter", 8.0, 2.0, 4.0, "wall", "fixture", "wall", ("wh", "hw")),
    FurnitureTemplate("refrigerator", "kitchen", "refrigerator", 3.0, 2.5, 3.0, "wall", "fixture", "wall", ("wh", "hw")),
    FurnitureTemplate("stove", "kitchen", "stove", 3.0, 2.5, 3.0, "wall", "fixture", "wall", ("wh", "hw")),
    FurnitureTemplate("toilet", "bathroom", "toilet", 2.0, 2.5, 2.0, "wall", "fixture", "wall", ("wh", "hw")),
    FurnitureTemplate("lavatory", "bathroom", "lavatory", 2.5, 2.0, 2.0, "wall", "fixture", "wall", ("wh", "hw")),
    FurnitureTemplate("shower", "bathroom", "shower", 3.0, 3.0, 2.0, "corner", "fixture", "corner", ("wh",)),
    FurnitureTemplate("ensuite_toilet", "ensuite_bathroom", "toilet", 2.0, 2.5, 2.0, "wall", "fixture", "wall", ("wh", "hw")),
    FurnitureTemplate("ensuite_lavatory", "ensuite_bathroom", "lavatory", 2.5, 2.0, 2.0, "wall", "fixture", "wall", ("wh", "hw")),
    FurnitureTemplate("ensuite_shower", "ensuite_bathroom", "shower", 3.0, 3.0, 2.0, "corner", "fixture", "corner", ("wh",)),
    FurnitureTemplate("closet_storage", "walk_in_closet", "storage", 4.0, 2.0, 2.0, "wall", "storage", "wall", ("wh", "hw")),
    FurnitureTemplate("closet_rod", "closet", "storage", 3.0, 2.0, 2.0, "wall", "storage", "wall", ("wh", "hw")),
    FurnitureTemplate("vehicle", "garage", "vehicle", 8.0, 16.0, 3.0, "center", "vehicle", "center", ("wh",)),
    FurnitureTemplate("mud_storage", "mudroom", "storage", 3.0, 2.0, 2.0, "wall", "storage", "wall", ("wh", "hw")),
)


def templates_for(room_type: str) -> list[FurnitureTemplate]:
    return [t for t in FURNITURE_TEMPLATES if t.room_type == room_type]
