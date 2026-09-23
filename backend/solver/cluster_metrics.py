"""Post-solve cluster cohesion and building-mass occupancy. Optimization metrics only."""

from __future__ import annotations

from .building_mass import BuildingMass
from .models import Layout, PlacedRoom
from .room_rules import OUTDOOR_TYPES
from .spatial_plan import RoomCluster, SpatialPlan

OCCUPANCY_LO = 0.62
OCCUPANCY_TARGET = 0.78
OCCUPANCY_HI = 0.92


def _union(room: PlacedRoom) -> int:
    from .footprint import union_area
    return union_area(room)


def _placed(layout: Layout, ids: list[str]) -> list[PlacedRoom]:
    out: list[PlacedRoom] = []
    for rid in ids:
        room = layout.room_by_id(rid)
        if room:
            out.append(room)
    return out


def cluster_cohesion(layout: Layout, cluster: RoomCluster) -> float:
    """sum(room areas) / bounding-box area. 1.0 = perfectly packed. Patio cluster ignored as exterior."""
    rooms = _placed(layout, cluster.room_ids)
    if cluster.zone == "exterior" or cluster.id == "exterior":
        return 1.0
    rooms = [r for r in rooms if r.type not in OUTDOOR_TYPES]
    if len(rooms) < 2:
        return 1.0
    occ = sum(_union(r) for r in rooms)
    min_x = min(r.x for r in rooms)
    max_x = max(r.x2 for r in rooms)
    min_y = min(r.y for r in rooms)
    max_y = max(r.y2 for r in rooms)
    bbox = max(1, (max_x - min_x) * (max_y - min_y))
    return min(1.0, occ / bbox)


def analyze_clusters(layout: Layout, spatial: SpatialPlan | None) -> dict:
    if not spatial:
        return {"mean_cohesion": 0.0, "clusters": []}
    items = []
    for cl in spatial.clusters:
        coh = cluster_cohesion(layout, cl)
        rooms = _placed(layout, cl.room_ids)
        occ = sum(_union(r) for r in rooms if r.type not in OUTDOOR_TYPES)
        items.append({
            "id": cl.id,
            "cohesion": round(coh, 4),
            "room_count": len(cl.room_ids),
            "occupied_area": occ,
            "preferred_area": cl.preferred_area,
            "position": cl.preferred_position,
        })
    mean = sum(i["cohesion"] for i in items) / len(items) if items else 0.0
    return {"mean_cohesion": round(mean, 4), "clusters": items}


def occupied_room_area_sum(layout: Layout) -> int:
    """Global non-outdoor union sum. Diagnostic only — not occupancy."""
    return sum(_union(r) for r in layout.rooms if r.type not in OUTDOOR_TYPES)


def mass_occupancy(layout: Layout, mass: BuildingMass | None, residual=None) -> float:
    """ROOM + CIRCULATION 1-ft cells inside BuildingMass / mass.area.

    Patio/deck cells are EXTERIOR and are not occupancy.
    Foyer/hallway cells are occupancy (intentional circulation).
    Rooms that overshoot the mass only count their painted cells inside it.
    Overlaps paint once. Walls are not subtracted.
    """
    if not mass or mass.area <= 0:
        return 0.0
    if residual is None:
        from .residual import analyze_residual
        residual = analyze_residual(layout, mass)
    filled = residual.room_cells_in_mass + residual.circulation_cells_in_mass
    return filled / mass.area


def occupancy_score(occupancy: float) -> int:
    if occupancy <= 0:
        return 40
    if occupancy < OCCUPANCY_LO:
        return max(0, min(100, int(100 * occupancy / OCCUPANCY_LO)))
    if occupancy > OCCUPANCY_HI:
        over = (occupancy - OCCUPANCY_HI) / max(0.01, 1.05 - OCCUPANCY_HI)
        return max(0, min(100, int(100 - 80 * over)))
    # Peak at TARGET within [LO, HI]
    span = max(OCCUPANCY_HI - OCCUPANCY_LO, 1e-6)
    dist = abs(occupancy - OCCUPANCY_TARGET) / span
    return max(0, min(100, int(100 - 40 * dist)))
