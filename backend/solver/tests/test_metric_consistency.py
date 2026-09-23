"""Raster occupancy vs residual identity. Not professional architectural approval."""

from __future__ import annotations

from solver.building_mass import BuildingMass
from solver.cluster_metrics import mass_occupancy, occupied_room_area_sum
from solver.models import Envelope, Layout, PlacedRoom
from solver.residual import analyze_residual


def _mass() -> tuple[Envelope, BuildingMass]:
    env = Envelope(width=60, depth=60)
    mass = BuildingMass(x=5, y=5, width=40, depth=50, preferred_area=2000, min_area=1000)
    return env, mass


def test_known_rectangles_match_documented_formulas():
    env, mass = _mass()
    rooms = [
        PlacedRoom("l", "living_room", "Living", 5, 5, 20, 20, "public"),
        PlacedRoom("h", "hallway", "Hall", 25, 5, 4, 20, "circulation"),
        PlacedRoom("p", "patio", "Patio", 5, 55, 10, 5, "outdoor"),
    ]
    layout = Layout(rooms=rooms, envelope=env)
    report = analyze_residual(layout, mass)
    occ = mass_occupancy(layout, mass, report)
    assert report.room_cells_in_mass == 400
    assert report.circulation_cells_in_mass == 80
    assert report.exterior_cells_in_mass == 0
    assert report.building_residual_area == 2000 - 400 - 80
    assert occ == (400 + 80) / 2000
    assert occupied_room_area_sum(layout) == 400 + 80
    assert mass.area == (
        report.room_cells_in_mass
        + report.circulation_cells_in_mass
        + report.exterior_cells_in_mass
        + report.building_residual_area
    )


def test_site_open_space_not_in_building_residual():
    env = Envelope(width=80, depth=60)
    mass = BuildingMass(x=5, y=5, width=40, depth=50, preferred_area=2000, min_area=1000)
    rooms = [
        PlacedRoom("l", "living_room", "Living", 5, 5, 20, 20, "public"),
    ]
    report = analyze_residual(Layout(rooms=rooms, envelope=env), mass)
    assert report.building_residual_area == 2000 - 400
    assert report.site_open_space_area > 0
    assert report.residual_area == report.building_residual_area
    assert report.site_open_space_area != report.building_residual_area
    kinds = {r.kind for r in report.regions}
    assert "building" in kinds and "site" in kinds


def test_enclosed_hole_is_building_residual():
    env = Envelope(width=20, depth=20)
    mass = BuildingMass(x=0, y=0, width=20, depth=20, preferred_area=400, min_area=200)
    rooms = [
        PlacedRoom("t", "living_room", "Top", 0, 0, 20, 6, "public"),
        PlacedRoom("b", "kitchen", "Bottom", 0, 14, 20, 6, "public"),
        PlacedRoom("l", "bedroom", "Left", 0, 6, 6, 8, "private"),
        PlacedRoom("r", "bathroom", "Right", 14, 6, 6, 8, "private"),
    ]
    report = analyze_residual(Layout(rooms=rooms, envelope=env), mass)
    assert report.building_residual_area == 64
    assert report.largest_residual_region == 64
    assert report.site_open_space_area == 0
    occ = mass_occupancy(Layout(rooms=rooms, envelope=env), mass, report)
    assert occ == (400 - 64) / 400


def test_completely_filled_mass():
    env = Envelope(width=20, depth=20)
    mass = BuildingMass(x=0, y=0, width=20, depth=20, preferred_area=400, min_area=200)
    rooms = [PlacedRoom("l", "living_room", "L", 0, 0, 20, 20, "public")]
    report = analyze_residual(Layout(rooms=rooms, envelope=env), mass)
    assert report.building_residual_area == 0
    assert mass_occupancy(Layout(rooms=rooms, envelope=env), mass, report) == 1.0


def test_intentional_hallway_is_occupancy_not_residual():
    env = Envelope(width=20, depth=20)
    mass = BuildingMass(x=0, y=0, width=20, depth=20, preferred_area=400, min_area=200)
    rooms = [
        PlacedRoom("l", "living_room", "L", 0, 0, 16, 20, "public"),
        PlacedRoom("h", "hallway", "H", 16, 0, 4, 20, "circulation"),
    ]
    report = analyze_residual(Layout(rooms=rooms, envelope=env), mass)
    assert report.circulation_cells_in_mass == 80
    assert report.room_cells_in_mass == 320
    assert report.building_residual_area == 0
    occ = mass_occupancy(Layout(rooms=rooms, envelope=env), mass, report)
    assert occ == 1.0


def test_global_room_sum_differs_when_room_overshoots_mass():
    env = Envelope(width=40, depth=20)
    mass = BuildingMass(x=0, y=0, width=20, depth=20, preferred_area=400, min_area=200)
    rooms = [PlacedRoom("l", "living_room", "L", 0, 0, 30, 10, "public")]
    layout = Layout(rooms=rooms, envelope=env)
    report = analyze_residual(layout, mass)
    assert occupied_room_area_sum(layout) == 300
    assert report.room_cells_in_mass == 200
    occ = mass_occupancy(layout, mass, report)
    assert occ == 200 / 400
    assert occupied_room_area_sum(layout) != int(round(occ * mass.area))
    assert report.building_residual_area == 200
