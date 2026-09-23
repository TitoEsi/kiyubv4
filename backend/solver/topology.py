"""Spatial topology: relationships exist before coordinates are chosen."""

from __future__ import annotations

from .architectural_program import from_room_program
from .models import RoomProgram, TopologyEdge
from .room_graph import build_room_graph

HARD_WALLSHARE_RELATIONS = frozenset({"connected", "accessed_by", "outside_access"})


def build_topology(program: RoomProgram) -> list[TopologyEdge]:
    arch = from_room_program(program)
    return build_room_graph(arch).topology_edges()


def required_access_pairs(edges: list[TopologyEdge]) -> list[tuple[str, str]]:
    kinds = HARD_WALLSHARE_RELATIONS
    return [(e.room_a, e.room_b) for e in edges if e.hard and e.relation in kinds]


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def hard_unconditional_pairs(edges: list[TopologyEdge]) -> set[tuple[str, str]]:
    """Hard wall-share pairs with no OR group (must share a wall with that exact room)."""
    return {
        _pair_key(e.room_a, e.room_b)
        for e in edges
        if e.hard and not e.choice_group and e.relation in HARD_WALLSHARE_RELATIONS
    }


def choice_groups(edges: list[TopologyEdge]) -> dict[str, list[TopologyEdge]]:
    groups: dict[str, list[TopologyEdge]] = {}
    for e in edges:
        if e.choice_group:
            groups.setdefault(e.choice_group, []).append(e)
    return groups
