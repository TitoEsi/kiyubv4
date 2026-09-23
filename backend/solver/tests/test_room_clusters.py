"""Room cluster organization tests. Not professional architectural approval."""

from __future__ import annotations

from solver.building_mass import BuildingMass, plan_building_mass
from solver.cluster_metrics import cluster_cohesion, mass_occupancy
from solver.models import Envelope, Layout, PlacedRoom
from solver.residual import analyze_residual
from solver.room_program import envelope_from_constraints, from_constraints
from solver.spatial_plan import RoomCluster as PlanCluster
from solver.spatial_planner import plan
from solver.solver import solve
from solver.room_rules import BEDROOM_TYPES


LIVE_CONSTRAINTS = {
    "lotShape": "rectangle",
    "lotWidth": 20,
    "lotDepth": 30,
    "bedrooms": 3,
    "bathrooms": 2,
    "openPlan": False,
    "primarySuite": True,
    "homeOffice": False,
    "formalDining": False,
    "garage": "2car",
    "laundry": "room",
    "outdoor": "patio",
    "sqft": 1800,
    "stories": 1,
    "style": "modern",
    "ceilingHeight": "standard",
}


def _live():
    env = envelope_from_constraints(LIVE_CONSTRAINTS)
    program = from_constraints(LIVE_CONSTRAINTS, env)
    return env, program


def test_live_clusters_generated():
    _, program = _live()
    spatial = plan(program)
    names = {c.id for c in spatial.clusters}
    assert names >= {"public", "private", "primary_suite", "service", "circulation", "exterior"}
    assert spatial.cluster_relations


def test_primary_suite_clustering():
    _, program = _live()
    spatial = plan(program)
    suite = next(c for c in spatial.clusters if c.id == "primary_suite")
    types = {r.id: r.type for r in program.rooms}
    have = {types[i] for i in suite.room_ids}
    assert have == {"master_bedroom", "ensuite_bathroom", "walk_in_closet"}


def test_service_clustering_excludes_kitchen():
    _, program = _live()
    spatial = plan(program)
    service = next(c for c in spatial.clusters if c.id == "service")
    types = {r.id: r.type for r in program.rooms}
    have = {types[i] for i in service.room_ids}
    assert have == {"garage", "laundry_room"}
    assert "kitchen" not in have
    assert "mudroom" not in have


def test_public_clustering():
    _, program = _live()
    spatial = plan(program)
    public = next(c for c in spatial.clusters if c.id == "public")
    types = {r.id: r.type for r in program.rooms}
    have = {types[i] for i in public.room_ids}
    assert {"living_room", "kitchen"} <= have
    assert "garage" not in have


def test_cluster_cohesion_packed_vs_scattered():
    env = Envelope(width=40, depth=40)
    packed = [
        PlacedRoom("a", "bedroom", "A", 0, 0, 10, 10, "private"),
        PlacedRoom("b", "bedroom", "B", 10, 0, 10, 10, "private"),
    ]
    scattered = [
        PlacedRoom("a", "bedroom", "A", 0, 0, 10, 10, "private"),
        PlacedRoom("b", "bedroom", "B", 30, 30, 10, 10, "private"),
    ]
    cl = PlanCluster(name="private", room_ids=["a", "b"], id="private", zone="private")
    packed_c = cluster_cohesion(Layout(rooms=packed, envelope=env), cl)
    scattered_c = cluster_cohesion(Layout(rooms=scattered, envelope=env), cl)
    assert 0 < packed_c <= 1
    assert 0 < scattered_c <= packed_c
    assert packed_c > scattered_c


def test_mass_occupancy_excludes_patio():
    env = Envelope(width=20, depth=20)
    mass = BuildingMass(x=0, y=0, width=10, depth=10, preferred_area=100, min_area=50)
    rooms = [
        PlacedRoom("l", "living_room", "Living", 0, 0, 10, 8, "public"),
        PlacedRoom("p", "patio", "Patio", 0, 10, 8, 8, "outdoor"),
    ]
    occ = mass_occupancy(Layout(rooms=rooms, envelope=env), mass)
    assert occ == 80 / 100
    assert occ != (80 + 64) / 100


def test_internal_residual_and_site_remain_distinct():
    env, program = _live()
    spatial = plan(program)
    mass = plan_building_mass(program, env, spatial)
    # Synthetic hole inside mass plus empty site beside it.
    rooms = [
        PlacedRoom("l", "living_room", "L", mass.x, mass.y, 8, 8, "public"),
        PlacedRoom("h", "hallway", "H", mass.x + 8, mass.y, 4, 8, "circulation"),
    ]
    layout = Layout(rooms=rooms, envelope=env)
    report = analyze_residual(layout, mass)
    assert report.building_residual_area > 0
    assert report.site_open_space_area > 0
    assert report.residual_area == report.building_residual_area


def test_live_20x30_valid_with_clusters():
    env, program = _live()
    spatial = plan(program)
    mass = plan_building_mass(program, env, spatial)
    result = solve(
        program, env, time_limit_s=15,
        spatial_plan=spatial, building_mass=mass, use_clusters=True,
    )
    assert result.status == "valid", result.reason
    assert result.validated is True
    q = result.quality_score
    assert q
    assert "cluster_cohesion" in q["categories"]
    assert "mass_occupancy" in q["categories"]
    assert q["clusters"]
    beds = [r for r in result.layout.rooms if r.type in BEDROOM_TYPES]
    assert len(beds) == 3
    assert any(r.type == "garage" for r in result.layout.rooms)
    assert any(r.type == "patio" for r in result.layout.rooms)
    assert q["building_residual_area"] >= 0
    assert q["site_open_space_area"] >= 0
    assert "not professional" in q["note"].lower()
