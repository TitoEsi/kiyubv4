"""Post-solve circulation analysis. Semantic graph + realized foyer/hallway geometry.

Reachability and circulation_ratio feed validator hard checks and quality.py.
Not professional architectural approval.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from .doors import _shared_segment
from .models import Layout, RoomProgram
from .room_rules import BATH_TYPES, BEDROOM_TYPES, CIRCULATION_TYPES, OCCUPIED_TYPES, OUTDOOR_TYPES
from .spatial_plan import CirculationEdge, CirculationGraph, CirculationNode, CirculationSegment, SpatialPlan

REQUIRED_REACH_TYPES = BEDROOM_TYPES | BATH_TYPES | {
    "kitchen", "living_room", "dining_room", "laundry_room", "home_office",
}


@dataclass
class CirculationAnalysis:
    graph: CirculationGraph
    segments: list[CirculationSegment]
    entry_id: str | None = None
    foyer_id: str | None = None
    hall_id: str | None = None
    branches: list[str] = field(default_factory=list)
    connected_rooms: list[str] = field(default_factory=list)
    dead_ends: list[str] = field(default_factory=list)
    width: int = 0
    area: int = 0
    length: int = 0
    efficiency: float = 0.0
    enclosed_floor_area: int = 0
    circulation_ratio: float = 0.0
    reachable_required: list[str] = field(default_factory=list)
    unreachable_required: list[str] = field(default_factory=list)
    fragmentation: int = 0

    def as_dict(self) -> dict:
        return {
            "circulation_area": self.area,
            "enclosed_floor_area": self.enclosed_floor_area,
            "circulation_ratio": round(self.circulation_ratio, 4),
            "circulation_length": self.length,
            "circulation_width": self.width,
            "circulation_efficiency": round(self.efficiency, 4),
            "dead_end_count": len(self.dead_ends),
            "dead_ends": list(self.dead_ends),
            "reachable_count": len(self.reachable_required),
            "unreachable_count": len(self.unreachable_required),
            "unreachable": list(self.unreachable_required),
            "fragmentation": self.fragmentation,
            "entry_id": self.entry_id,
            "foyer_id": self.foyer_id,
            "hall_id": self.hall_id,
        }


def _adj(graph: dict[str, set[str]], a: str, b: str) -> None:
    if a == b:
        return
    graph[a].add(b)
    graph[b].add(a)


def _role_for(room_type: str, foyer_id: str | None, hall_id: str | None, rid: str) -> str:
    if rid == foyer_id:
        return "entry" if room_type == "foyer" else "foyer"
    if room_type == "foyer":
        return "foyer"
    if rid == hall_id or room_type == "hallway":
        return "hall" if rid == hall_id else "branch"
    return "leaf"


def analyze_circulation(
    layout: Layout,
    program: RoomProgram,
    spatial: SpatialPlan | None = None,
) -> CirculationAnalysis:
    rooms = {r.id: r for r in layout.rooms}
    types = {r.id: r.type for r in layout.rooms}
    foyer = next((r.id for r in layout.rooms if r.type == "foyer"), None)
    halls = [r.id for r in layout.rooms if r.type == "hallway"]
    hall = halls[0] if halls else None
    entry = foyer or hall

    graph: dict[str, set[str]] = defaultdict(set)
    if spatial:
        for e in spatial.circulation.edges:
            if e.room_a in rooms and e.room_b in rooms:
                _adj(graph, e.room_a, e.room_b)
        for rel in spatial.relations:
            if rel.kind in ("accessed_by", "connected", "outside_access") and rel.room_a in rooms and rel.room_b in rooms:
                _adj(graph, rel.room_a, rel.room_b)
    for d in layout.doors:
        if d.room_a in rooms and d.room_b in rooms:
            _adj(graph, d.room_a, d.room_b)
    for e in layout.topology or []:
        if e.relation in ("accessed_by", "connected", "outside_access") and e.room_a in rooms and e.room_b in rooms:
            _adj(graph, e.room_a, e.room_b)

    nodes: list[CirculationNode] = []
    edges: list[CirculationEdge] = []
    seen_e: set[tuple[str, str]] = set()
    branches: list[str] = []
    for r in layout.rooms:
        role = _role_for(r.type, foyer, hall, r.id)
        if role == "branch":
            branches.append(r.id)
        nodes.append(CirculationNode(r.id, role))
    for a, nbs in graph.items():
        for b in nbs:
            key = tuple(sorted((a, b)))
            if key in seen_e:
                continue
            seen_e.add(key)
            edges.append(CirculationEdge(a, b))

    circ_rooms = [r for r in layout.rooms if r.type in CIRCULATION_TYPES]
    segments: list[CirculationSegment] = []
    for r in circ_rooms:
        role = _role_for(r.type, foyer, hall, r.id)
        w = min(r.width, r.depth)
        length = max(r.width, r.depth)
        segments.append(CirculationSegment(r.id, role, w, length, r.width * r.depth))

    area = sum(s.area for s in segments)
    length = sum(s.length for s in segments)
    width = min((s.width for s in segments), default=0)
    from .footprint import union_area
    enclosed = sum(union_area(r) for r in layout.rooms if r.type not in OUTDOOR_TYPES)
    ratio = (area / enclosed) if enclosed else 0.0

    occupied = [r for r in layout.rooms if r.type in OCCUPIED_TYPES]
    served = 0
    connected_rooms: list[str] = []
    for r in occupied:
        if any(n in graph[r.id] and types.get(n) in CIRCULATION_TYPES for n in graph[r.id]) or r.id in graph[entry or ""]:
            served += 1
            connected_rooms.append(r.id)
        elif r.id in graph and graph[r.id]:
            served += 1
            connected_rooms.append(r.id)
    efficiency = served / max(area, 1)

    dead_ends: list[str] = []
    for r in circ_rooms:
        if r.type == "foyer":
            continue
        nbs = graph.get(r.id, set())
        serves_leaf = any(
            types.get(n) in OCCUPIED_TYPES or types.get(n) in ("garage", "walk_in_closet")
            for n in nbs
        )
        shares_occupied = False
        for other in occupied:
            if _shared_segment(r, other) is not None:
                shares_occupied = True
                break
        degree = len(nbs)
        if (degree <= 1 and not serves_leaf) or (not shares_occupied and not serves_leaf):
            dead_ends.append(r.id)

    seeds = [s for s in (entry, foyer, hall) if s]
    seen: set[str] = set()
    q = deque(seeds)
    while q:
        cur = q.popleft()
        if cur in seen:
            continue
        seen.add(cur)
        for nxt in graph.get(cur, ()):
            if nxt not in seen:
                q.append(nxt)

    required = [r.id for r in layout.rooms if r.type in REQUIRED_REACH_TYPES]
    reachable = [rid for rid in required if rid in seen]
    unreachable = [rid for rid in required if rid not in seen]

    fragmentation = max(0, len(circ_rooms) - 2)

    return CirculationAnalysis(
        graph=CirculationGraph(nodes=nodes, edges=edges, min_width=width or 4),
        segments=segments,
        entry_id=entry,
        foyer_id=foyer,
        hall_id=hall,
        branches=branches,
        connected_rooms=connected_rooms,
        dead_ends=dead_ends,
        width=width,
        area=area,
        length=length,
        efficiency=efficiency,
        enclosed_floor_area=int(enclosed),
        circulation_ratio=ratio,
        reachable_required=reachable,
        unreachable_required=unreachable,
        fragmentation=fragmentation,
    )


def log_circulation(analysis: CirculationAnalysis) -> None:
    print(
        f"[KIYUB CIRCULATION] area={analysis.area} length={analysis.length} "
        f"width={analysis.width} efficiency={analysis.efficiency:.3f}"
    )
    print(
        f"[KIYUB CIRCULATION] reachable={len(analysis.reachable_required)} "
        f"unreachable={len(analysis.unreachable_required)} dead_ends={len(analysis.dead_ends)}"
    )
    print("[KIYUB CIRCULATION] Heuristic circulation graph, not professional architectural approval.")
