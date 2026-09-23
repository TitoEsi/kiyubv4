"""Canonical room relationship graph compiled from ArchitecturalProgram.

Not professional architectural approval. Not a second generation pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .architectural_program import ArchitecturalProgram
from .models import TopologyEdge
from .spatial_plan import SemanticRelation


@dataclass
class GraphEdge:
    room_a: str
    room_b: str
    kind: str  # required_adjacency | preferred_adjacency | forbidden_adjacency | access | service
    topo_relation: str
    hard: bool = False
    choice_group: str | None = None
    semantic_kind: str = "near"
    semantic_strength: str = "preferred"


@dataclass
class RoomGraph:
    edges: list[GraphEdge] = field(default_factory=list)

    def topology_edges(self) -> list[TopologyEdge]:
        out: list[TopologyEdge] = []
        seen: set[tuple] = set()
        for e in self.edges:
            key = (e.room_a, e.room_b, e.topo_relation, e.choice_group, e.hard)
            if key in seen:
                continue
            seen.add(key)
            out.append(TopologyEdge(
                room_a=e.room_a,
                room_b=e.room_b,
                relation=e.topo_relation,
                hard=e.hard,
                choice_group=e.choice_group,
            ))
        return out

    def semantic_relations(self) -> list[SemanticRelation]:
        rel: list[SemanticRelation] = []
        seen: set[tuple] = set()
        for e in self.edges:
            if e.kind == "access" and e.choice_group and e.topo_relation != "outside_access":
                continue
            key = (e.room_a, e.room_b, e.semantic_kind, e.semantic_strength)
            if key in seen:
                continue
            seen.add(key)
            rel.append(SemanticRelation(e.room_a, e.room_b, e.semantic_kind, e.semantic_strength))
        return rel


def _first(arch: ArchitecturalProgram, room_type: str) -> str | None:
    sp = arch.first(room_type)
    return sp.id if sp else None


def _ids(arch: ArchitecturalProgram, *types: str) -> list[str]:
    out: list[str] = []
    for t in types:
        out.extend(s.id for s in arch.by_type(t))
    return out


def build_room_graph(arch: ArchitecturalProgram) -> RoomGraph:
    """Single source for topology.py and planning_graph.py."""
    edges: list[GraphEdge] = []

    def add(
        a: str | None,
        b: str | None,
        kind: str,
        topo: str,
        hard: bool = False,
        group: str | None = None,
        semantic_kind: str | None = None,
        semantic_strength: str | None = None,
    ) -> None:
        if not a or not b or a == b:
            return
        sk = semantic_kind or topo
        ss = semantic_strength or ("required" if hard else "preferred")
        if kind == "forbidden_adjacency":
            ss = "avoid"
            sk = "avoid"
        edges.append(GraphEdge(
            room_a=a, room_b=b, kind=kind,
            topo_relation=topo, hard=hard, choice_group=group,
            semantic_kind=sk, semantic_strength=ss,
        ))

    foyer = _first(arch, "foyer")
    hall = _first(arch, "hallway")
    living = _first(arch, "living_room")
    dining = _first(arch, "dining_room")
    kitchen = _first(arch, "kitchen")
    master = _first(arch, "master_bedroom")
    ensuite = _first(arch, "ensuite_bathroom")
    closet = _first(arch, "walk_in_closet") or _first(arch, "closet")
    garage = _first(arch, "garage")
    laundry = _first(arch, "laundry_room")
    mud = _first(arch, "mudroom")

    add(foyer, hall, "required_adjacency", "connected", hard=True, semantic_kind="connected", semantic_strength="required")
    if living:
        add(living, hall, "access", "accessed_by", hard=True, group="living_circ", semantic_kind="accessed_by", semantic_strength="required")
        add(living, foyer, "access", "accessed_by", hard=True, group="living_circ", semantic_kind="accessed_by", semantic_strength="preferred")
    add(kitchen, dining, "required_adjacency", "connected", hard=True, semantic_kind="connected", semantic_strength="required")
    add(living, dining, "preferred_adjacency", "adjacent", hard=False, semantic_kind="near", semantic_strength="preferred")
    add(kitchen, living, "preferred_adjacency", "adjacent", hard=False, semantic_kind="near", semantic_strength="preferred")
    if kitchen:
        add(kitchen, hall, "access", "accessed_by", hard=True, group="kitchen_circ")
        add(kitchen, living, "access", "accessed_by", hard=True, group="kitchen_circ")
    for bid in _ids(arch, "bedroom"):
        add(bid, hall, "access", "accessed_by", hard=True, semantic_kind="accessed_by", semantic_strength="required")
    if master:
        add(master, hall, "access", "accessed_by", hard=True, semantic_kind="accessed_by", semantic_strength="required")
    for bath_id in _ids(arch, "bathroom") + _ids(arch, "half_bath"):
        add(bath_id, hall, "access", "accessed_by", hard=True)
    add(ensuite, master, "required_adjacency", "connected", hard=True, semantic_kind="connected", semantic_strength="required")
    add(closet, master, "required_adjacency", "connected", hard=True, semantic_kind="connected", semantic_strength="required")
    add(garage, laundry, "service", "near", hard=False)
    add(garage, kitchen, "service", "near", hard=False)
    add(garage, foyer, "service", "near", hard=False)
    add(laundry, hall, "access", "accessed_by", hard=bool(laundry and hall), semantic_kind="accessed_by", semantic_strength="required")
    add(laundry, kitchen, "service", "near", hard=False)
    for oid in _ids(arch, "patio", "deck"):
        group = f"outside_{oid}"
        for target in (living, dining, kitchen):
            add(target, oid, "access", "outside_access", hard=True, group=group, semantic_kind="outside_access", semantic_strength="preferred")
    office = _first(arch, "home_office")
    add(office, hall or foyer, "access", "accessed_by", hard=True)
    if mud:
        add(mud, garage, "preferred_adjacency", "connected", hard=False, semantic_kind="connected", semantic_strength="preferred")
        add(mud, kitchen, "service", "near", hard=False)

    add(garage, living, "forbidden_adjacency", "separated", hard=True)
    add(garage, dining, "forbidden_adjacency", "separated", hard=True)
    for bid in _ids(arch, "bedroom", "master_bedroom"):
        add(bid, garage, "forbidden_adjacency", "separated", hard=True)
        add(bid, kitchen, "forbidden_adjacency", "separated", hard=True)
        add(bid, foyer, "forbidden_adjacency", "separated", hard=True)
    for bath in _ids(arch, "bathroom", "ensuite_bathroom", "half_bath"):
        add(bath, foyer, "forbidden_adjacency", "separated", hard=True)
        add(bath, living, "forbidden_adjacency", "separated", hard=True)

    by_type = {s.room_type: s.id for s in arch.spaces}
    seen_pairs = {(min(e.room_a, e.room_b), max(e.room_a, e.room_b), e.kind) for e in edges}
    for space in arch.spaces:
        for ntype in space.required_neighbors:
            nid = by_type.get(ntype)
            key = (min(space.id, nid or ""), max(space.id, nid or ""), "required_adjacency")
            if nid and key not in seen_pairs:
                add(space.id, nid, "required_adjacency", "connected", hard=True, semantic_kind="connected", semantic_strength="required")
                seen_pairs.add(key)
        for ntype in space.preferred_neighbors:
            nid = by_type.get(ntype)
            key = (min(space.id, nid or ""), max(space.id, nid or ""), "preferred_adjacency")
            if nid and key not in seen_pairs:
                add(space.id, nid, "preferred_adjacency", "near", hard=False)
                seen_pairs.add(key)
        for ntype in space.prohibited_neighbors:
            nid = by_type.get(ntype)
            key = (min(space.id, nid or ""), max(space.id, nid or ""), "forbidden_adjacency")
            if nid and key not in seen_pairs:
                add(space.id, nid, "forbidden_adjacency", "separated", hard=False)
                seen_pairs.add(key)

    return RoomGraph(edges=edges)
