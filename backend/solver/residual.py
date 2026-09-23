"""Geometric residual-space detection on the integer-foot envelope.

1-ft raster. Empty cells that are not rooms, not intentional
circulation (foyer/hallway), and not exterior (patio/deck) are residual.

This is not envelope_area minus room_area, and it is not the global
sum of room rectangles. Walls are not modeled: a painted cell is the
whole room rectangle clipped to the envelope.

Fill identity inside BuildingMass (when the mass sits in the envelope
and outdoor rooms do not overlap it):

    mass.area = room_cells + circulation_cells + exterior_cells + residual

Each footprint part is painted. The L-void stays EMPTY. The bounding
box is not occupancy.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .building_mass import BuildingMass
from .models import Layout, PlacedRoom
from .room_rules import CIRCULATION_TYPES, OUTDOOR_TYPES

EMPTY = 0
ROOM = 1
CIRCULATION = 2
EXTERIOR = 3

NARROW_FT = 3
OPENING_FT = 4


@dataclass
class ResidualRegion:
    x: int
    y: int
    width: int
    depth: int
    area: int
    min_width: int
    isolated: bool
    narrow: bool
    narrow_area: int = 0
    kind: str = "residual"  # residual | building | site

    def as_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "depth": self.depth,
            "area": self.area,
            "min_width": self.min_width,
            "isolated": self.isolated,
            "narrow": self.narrow,
            "narrow_area": self.narrow_area,
            "kind": self.kind,
        }


@dataclass
class ResidualReport:
    residual_area: int = 0
    residual_region_count: int = 0
    largest_residual_region: int = 0
    narrow_residual_area: int = 0
    isolated_residual_regions: int = 0
    regions: list[ResidualRegion] = field(default_factory=list)
    envelope_area: int = 0
    building_residual_area: int = 0
    building_residual_region_count: int = 0
    site_open_space_area: int = 0
    site_open_region_count: int = 0
    room_cells_in_mass: int = 0
    circulation_cells_in_mass: int = 0
    exterior_cells_in_mass: int = 0
    occupied_room_area_sum: int = 0

    def as_dict(self) -> dict:
        return {
            "residual_area": self.residual_area,
            "residual_region_count": self.residual_region_count,
            "largest_residual_region": self.largest_residual_region,
            "narrow_residual_area": self.narrow_residual_area,
            "isolated_residual_regions": self.isolated_residual_regions,
            "envelope_area": self.envelope_area,
            "building_residual_area": self.building_residual_area,
            "building_residual_region_count": self.building_residual_region_count,
            "site_open_space_area": self.site_open_space_area,
            "site_open_region_count": self.site_open_region_count,
            "room_cells_in_mass": self.room_cells_in_mass,
            "circulation_cells_in_mass": self.circulation_cells_in_mass,
            "exterior_cells_in_mass": self.exterior_cells_in_mass,
            "occupied_room_area_sum": self.occupied_room_area_sum,
            "regions": [r.as_dict() for r in self.regions[:12]],
        }


def _label_for(room: PlacedRoom) -> int:
    if room.type in CIRCULATION_TYPES:
        return CIRCULATION
    if room.type in OUTDOOR_TYPES:
        return EXTERIOR
    return ROOM


def _paint(grid: list[list[int]], room: PlacedRoom, w: int, d: int) -> None:
    label = _label_for(room)
    for p in room.parts():
        x0 = max(0, p.x)
        y0 = max(0, p.y)
        x1 = min(w, p.x2)
        y1 = min(d, p.y2)
        for y in range(y0, y1):
            row = grid[y]
            for x in range(x0, x1):
                row[x] = label


def _run_lengths(cells: set[tuple[int, int]], x: int, y: int) -> tuple[int, int]:
    hx = 1
    nx = x + 1
    while (nx, y) in cells:
        hx += 1
        nx += 1
    nx = x - 1
    while (nx, y) in cells:
        hx += 1
        nx -= 1
    vy = 1
    ny = y + 1
    while (x, ny) in cells:
        vy += 1
        ny += 1
    ny = y - 1
    while (x, ny) in cells:
        vy += 1
        ny -= 1
    return hx, vy


def _narrow_cells(cells: set[tuple[int, int]]) -> int:
    """Cells that cannot sit inside an OPENING_FT x OPENING_FT block of the region."""
    if not cells:
        return 0
    k = OPENING_FT
    covered: set[tuple[int, int]] = set()
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    for y in range(min_y, max_y - k + 2):
        for x in range(min_x, max_x - k + 2):
            block = [(x + dx, y + dy) for dy in range(k) for dx in range(k)]
            if all(p in cells for p in block):
                covered.update(block)
    return len(cells) - len(covered)


def _touches_circulation(cells: set[tuple[int, int]], grid: list[list[int]], w: int, d: int) -> bool:
    for x, y in cells:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < d and grid[ny][nx] == CIRCULATION:
                return True
    return False


def _flood(
    grid: list[list[int]],
    w: int,
    d: int,
    seen: list[list[bool]],
    predicate,
    kind: str,
) -> list[ResidualRegion]:
    regions: list[ResidualRegion] = []
    for y in range(d):
        for x in range(w):
            if grid[y][x] != EMPTY or seen[y][x] or not predicate(x, y):
                continue
            q = deque([(x, y)])
            seen[y][x] = True
            cells: set[tuple[int, int]] = set()
            while q:
                cx, cy = q.popleft()
                cells.add((cx, cy))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if (
                        0 <= nx < w and 0 <= ny < d
                        and not seen[ny][nx]
                        and grid[ny][nx] == EMPTY
                        and predicate(nx, ny)
                    ):
                        seen[ny][nx] = True
                        q.append((nx, ny))
            xs = [c[0] for c in cells]
            ys = [c[1] for c in cells]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            min_w = min(min(_run_lengths(cells, cx, cy)) for cx, cy in cells)
            narrow_area = _narrow_cells(cells)
            isolated = not _touches_circulation(cells, grid, w, d)
            narrow = min_w <= NARROW_FT or narrow_area > 0
            regions.append(ResidualRegion(
                x=min_x,
                y=min_y,
                width=max_x - min_x + 1,
                depth=max_y - min_y + 1,
                area=len(cells),
                min_width=min_w,
                isolated=isolated,
                narrow=narrow,
                narrow_area=narrow_area,
                kind=kind,
            ))
    return regions


def _count_labels(grid: list[list[int]], w: int, d: int, predicate) -> tuple[int, int, int, int]:
    room = circ = ext = empty = 0
    for y in range(d):
        row = grid[y]
        for x in range(w):
            if not predicate(x, y):
                continue
            v = row[x]
            if v == ROOM:
                room += 1
            elif v == CIRCULATION:
                circ += 1
            elif v == EXTERIOR:
                ext += 1
            else:
                empty += 1
    return room, circ, ext, empty


def _occupied_room_area_sum(layout: Layout) -> int:
    from .footprint import union_area
    return sum(union_area(r) for r in layout.rooms if r.type not in OUTDOOR_TYPES)


def analyze_residual(layout: Layout, building_mass: BuildingMass | None = None) -> ResidualReport:
    env = layout.envelope
    if not env or env.width <= 0 or env.depth <= 0:
        return ResidualReport()
    w, d = env.width, env.depth
    grid = [[EMPTY] * w for _ in range(d)]
    for room in layout.rooms:
        _paint(grid, room, w, d)

    seen = [[False] * w for _ in range(d)]
    occ_sum = _occupied_room_area_sum(layout)
    if building_mass:
        building = _flood(grid, w, d, seen, building_mass.contains_cell, "building")
        site = _flood(grid, w, d, seen, lambda x, y: not building_mass.contains_cell(x, y), "site")
        b_area = sum(r.area for r in building)
        s_area = sum(r.area for r in site)
        room_c, circ_c, ext_c, _empty_c = _count_labels(grid, w, d, building_mass.contains_cell)
        regions = sorted(building + site, key=lambda r: r.area, reverse=True)
        return ResidualReport(
            residual_area=b_area,
            residual_region_count=len(building),
            largest_residual_region=max((r.area for r in building), default=0),
            narrow_residual_area=sum(r.narrow_area for r in building),
            isolated_residual_regions=sum(1 for r in building if r.isolated),
            regions=regions,
            envelope_area=env.area,
            building_residual_area=b_area,
            building_residual_region_count=len(building),
            site_open_space_area=s_area,
            site_open_region_count=len(site),
            room_cells_in_mass=room_c,
            circulation_cells_in_mass=circ_c,
            exterior_cells_in_mass=ext_c,
            occupied_room_area_sum=occ_sum,
        )

    regions = _flood(grid, w, d, seen, lambda _x, _y: True, "residual")
    residual_area = sum(r.area for r in regions)
    room_c, circ_c, ext_c, _empty_c = _count_labels(grid, w, d, lambda _x, _y: True)
    return ResidualReport(
        residual_area=residual_area,
        residual_region_count=len(regions),
        largest_residual_region=max((r.area for r in regions), default=0),
        narrow_residual_area=sum(r.narrow_area for r in regions),
        isolated_residual_regions=sum(1 for r in regions if r.isolated),
        regions=sorted(regions, key=lambda r: r.area, reverse=True),
        envelope_area=env.area,
        building_residual_area=residual_area,
        building_residual_region_count=len(regions),
        site_open_space_area=0,
        site_open_region_count=0,
        room_cells_in_mass=room_c,
        circulation_cells_in_mass=circ_c,
        exterior_cells_in_mass=ext_c,
        occupied_room_area_sum=occ_sum,
    )


def log_residual(report: ResidualReport) -> None:
    print(
        f"[KIYUB RESIDUAL] area={report.residual_area} regions={report.residual_region_count} "
        f"largest={report.largest_residual_region} narrow={report.narrow_residual_area} "
        f"isolated={report.isolated_residual_regions}"
    )
    print("[KIYUB RESIDUAL] Geometric leftover detection, not professional architectural approval.")
