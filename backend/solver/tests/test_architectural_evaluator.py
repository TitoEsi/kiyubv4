"""Architectural evaluator metric tests. Not professional architectural approval."""

from __future__ import annotations

from solver.models import Envelope, Layout, PlacedRoom, RoomProgram, RoomSpec
from solver.quality import score_layout
from solver.room_rules import ZONE_BY_TYPE, aspect_ratio


def _spec(rid, rtype, name, w, d, zone=None) -> RoomSpec:
    return RoomSpec(
        id=rid, type=rtype, name=name,
        min_width=w, min_depth=d, preferred_width=w, preferred_depth=d,
        required=True, zone=zone or ZONE_BY_TYPE.get(rtype, "public"),
        preferred_area=w * d, max_area=w * d * 2, max_aspect_ratio=2.2 if "bedroom" in rtype else 2.8,
    )


def _program(specs: list[RoomSpec], env: Envelope) -> RoomProgram:
    beds = sum(1 for s in specs if s.type in ("bedroom", "master_bedroom"))
    baths = sum(1 for s in specs if "bath" in s.type)
    return RoomProgram(rooms=specs, envelope=env, bedrooms_requested=beds, bathrooms_requested=baths)


def test_reasonable_rectangle_beats_extreme_bedroom():
    env = Envelope(width=40, depth=40)
    good_spec = _spec("b", "bedroom", "Bedroom", 11, 12)
    bad_spec = _spec("b", "bedroom", "Bedroom", 11, 12)
    good = Layout(rooms=[
        PlacedRoom("b", "bedroom", "Bedroom", 0, 0, 11, 12, "private"),
        PlacedRoom("h", "hallway", "Hall", 11, 0, 4, 12, "circulation"),
    ], envelope=env)
    bad = Layout(rooms=[
        PlacedRoom("b", "bedroom", "Bedroom", 0, 0, 4, 21, "private"),
        PlacedRoom("h", "hallway", "Hall", 4, 0, 4, 21, "circulation"),
    ], envelope=env)
    g = score_layout(good, _program([good_spec], env))
    b = score_layout(bad, _program([bad_spec], env))
    assert aspect_ratio(11, 12) < aspect_ratio(4, 21)
    assert g["categories"]["room_proportion"] > b["categories"]["room_proportion"]
    assert "b" in (b.get("diagnostics") or {}).get("poor_aspect_ratios", [])


def test_exterior_bedroom_beats_interior_bedroom():
    env = Envelope(width=30, depth=30)
    spec = _spec("b", "bedroom", "Bedroom", 12, 12)
    hall = _spec("h", "hallway", "Hall", 4, 12)
    exterior = Layout(rooms=[
        PlacedRoom("b", "bedroom", "Bedroom", 0, 0, 12, 12, "private"),
        PlacedRoom("h", "hallway", "Hall", 12, 0, 4, 12, "circulation"),
    ], envelope=env)
    buried = Layout(rooms=[
        PlacedRoom("b", "bedroom", "Bedroom", 9, 9, 12, 12, "private"),
        PlacedRoom("h", "hallway", "Hall", 21, 9, 4, 12, "circulation"),
    ], envelope=env)
    g = score_layout(exterior, _program([spec, hall], env))
    b = score_layout(buried, _program([spec, hall], env))
    assert g["categories"]["daylight_potential"] > b["categories"]["daylight_potential"]
    assert "b" in (b.get("diagnostics") or {}).get("daylight_problems", [])


def test_usable_room_beats_furniture_impossible_room():
    env = Envelope(width=30, depth=30)
    spec = _spec("b", "bedroom", "Bedroom", 12, 12)
    usable = Layout(rooms=[
        PlacedRoom("b", "bedroom", "Bedroom", 0, 0, 12, 12, "private"),
    ], envelope=env)
    tiny = Layout(rooms=[
        PlacedRoom("b", "bedroom", "Bedroom", 0, 0, 9, 10, "private"),
    ], envelope=env)
    g = score_layout(usable, _program([spec], env))
    b = score_layout(tiny, _program([spec], env))
    assert g["furniture_clearance_score"] >= b["furniture_clearance_score"]
    assert g["room_usability_score"] >= b["room_usability_score"]


def test_useful_utilization_beats_meaningless_packing():
    env = Envelope(width=40, depth=40)
    living = _spec("l", "living_room", "Living", 14, 16)
    useful = Layout(rooms=[
        PlacedRoom("l", "living_room", "Living", 0, 0, 16, 18, "public"),
        PlacedRoom("h", "hallway", "Hall", 16, 0, 4, 18, "circulation"),
    ], envelope=env)
    packed = Layout(rooms=[
        PlacedRoom("l", "living_room", "Living", 0, 0, 10, 12, "public"),
        PlacedRoom("h", "hallway", "Hall", 10, 0, 4, 36, "circulation"),
        PlacedRoom("x", "closet", "Dead", 14, 0, 3, 36, "private"),
    ], envelope=env)
    g = score_layout(useful, _program([living], env))
    b = score_layout(packed, _program([living], env))
    assert g["categories"]["site_utilization"] >= b["categories"]["site_utilization"] or (
        g["categories"]["room_proportion"] > b["categories"]["room_proportion"]
    )


def test_evaluator_selects_higher_quality_valid_candidate():
    env = Envelope(width=40, depth=40)
    spec = _spec("b", "bedroom", "Bedroom", 11, 12)
    good = score_layout(Layout(rooms=[
        PlacedRoom("b", "bedroom", "Bedroom", 0, 0, 11, 12, "private"),
        PlacedRoom("h", "hallway", "Hall", 11, 0, 4, 12, "circulation"),
    ], envelope=env), _program([spec], env))
    bad = score_layout(Layout(rooms=[
        PlacedRoom("b", "bedroom", "Bedroom", 8, 8, 4, 22, "private"),
        PlacedRoom("h", "hallway", "Hall", 12, 8, 4, 22, "circulation"),
    ], envelope=env), _program([spec], env))
    assert good["overall"] > bad["overall"]


def test_reasonable_circulation_beats_awkward_corridor():
    env = Envelope(width=40, depth=40)
    specs = [
        _spec("l", "living_room", "Living", 14, 16),
        _spec("h", "hallway", "Hall", 4, 16),
    ]
    good = Layout(rooms=[
        PlacedRoom("l", "living_room", "Living", 0, 0, 14, 16, "public"),
        PlacedRoom("h", "hallway", "Hall", 14, 0, 4, 16, "circulation"),
    ], envelope=env, topology=[])
    awkward = Layout(rooms=[
        PlacedRoom("l", "living_room", "Living", 0, 0, 14, 16, "public"),
        PlacedRoom("h", "hallway", "Hall", 20, 0, 4, 36, "circulation"),
    ], envelope=env, topology=[])
    from solver.models import TopologyEdge
    good.topology = [TopologyEdge("l", "h", "accessed_by", hard=True)]
    awkward.topology = [TopologyEdge("l", "h", "accessed_by", hard=True)]
    g = score_layout(good, _program(specs, env))
    b = score_layout(awkward, _program(specs, env))
    assert g["categories"]["circulation"] >= b["categories"]["circulation"] or (
        (g.get("circulation") or {}).get("circulation_length", 99)
        <= (b.get("circulation") or {}).get("circulation_length", 0)
    )
