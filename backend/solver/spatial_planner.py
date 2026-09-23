"""Deterministic spatial planner. Semantic organization, not x/y/width/height."""

from __future__ import annotations

from .architectural_program import ArchitecturalProgram, from_room_program
from .models import RoomProgram, TopologyEdge
from .planning_graph import build_planning_graph
from .room_rules import BEDROOM_TYPES
from .site_plan import plan_access
from .spatial_plan import (
    CirculationEdge,
    CirculationGraph,
    CirculationNode,
    ClusterRelation,
    LayoutStrategy,
    RoomBlock,
    RoomCluster,
    SemanticRelation,
    SpatialPlan,
    ZoneBand,
)

STRATEGIES: dict[str, LayoutStrategy] = {
    "public_private_split": LayoutStrategy(
        name="public_private_split",
        description="Public toward the front, private toward the rear.",
        bands=[
            ZoneBand("public", "y", 0.0, 0.45),
            ZoneBand("circulation", "y", 0.15, 0.55),
            ZoneBand("private", "y", 0.40, 0.90),
            ZoneBand("service", "x", 0.0, 0.45),
            ZoneBand("exterior", "y", 0.70, 1.0),
        ],
        anchors=["foyer", "hallway", "living_room"],
    ),
    "central_spine": LayoutStrategy(
        name="central_spine",
        description="Hallway as organizing spine between public and private.",
        bands=[
            ZoneBand("public", "y", 0.0, 0.40),
            ZoneBand("circulation", "y", 0.20, 0.70),
            ZoneBand("private", "y", 0.40, 0.90),
            ZoneBand("service", "x", 0.0, 0.40),
            ZoneBand("exterior", "y", 0.75, 1.0),
        ],
        anchors=["foyer", "hallway", "living_room", "kitchen"],
    ),
    "linear": LayoutStrategy(
        name="linear",
        description="Spaces sequenced front to rear along the lot depth.",
        bands=[
            ZoneBand("public", "y", 0.0, 0.35),
            ZoneBand("circulation", "y", 0.25, 0.60),
            ZoneBand("private", "y", 0.45, 0.85),
            ZoneBand("service", "y", 0.0, 0.50),
            ZoneBand("exterior", "y", 0.80, 1.0),
        ],
        anchors=["foyer", "living_room", "hallway"],
    ),
    "service_side": LayoutStrategy(
        name="service_side",
        description="Garage and service rooms along one side of the envelope.",
        bands=[
            ZoneBand("service", "x", 0.0, 0.40),
            ZoneBand("public", "x", 0.30, 1.0),
            ZoneBand("public", "y", 0.0, 0.45),
            ZoneBand("private", "y", 0.40, 0.90),
            ZoneBand("circulation", "x", 0.25, 0.70),
            ZoneBand("exterior", "y", 0.70, 1.0),
        ],
        anchors=["garage", "kitchen", "hallway"],
    ),
    "patio_oriented": LayoutStrategy(
        name="patio_oriented",
        description="Public rooms organized toward a rear patio.",
        bands=[
            ZoneBand("public", "y", 0.15, 0.75),
            ZoneBand("circulation", "y", 0.0, 0.55),
            ZoneBand("private", "y", 0.25, 0.80),
            ZoneBand("service", "x", 0.0, 0.45),
            ZoneBand("exterior", "y", 0.70, 1.0),
        ],
        anchors=["foyer", "living_room", "kitchen", "patio"],
    ),
    "cluster": LayoutStrategy(
        name="cluster",
        description="Public, private, and service rooms grouped as cohesive clusters.",
        bands=[
            ZoneBand("public", "y", 0.10, 0.55),
            ZoneBand("private", "x", 0.48, 1.00),
            ZoneBand("private", "y", 0.35, 0.90),
            ZoneBand("service", "x", 0.00, 0.38),
            ZoneBand("circulation", "y", 0.15, 0.65),
            ZoneBand("exterior", "y", 0.75, 1.0),
        ],
        anchors=["living_room", "master_bedroom", "garage", "hallway"],
    ),
    "rear_private": LayoutStrategy(
        name="rear_private",
        description="Arrival and public at the front; private rooms protected toward the rear.",
        bands=[
            ZoneBand("public", "y", 0.0, 0.42),
            ZoneBand("circulation", "y", 0.18, 0.62),
            ZoneBand("private", "y", 0.50, 1.00),
            ZoneBand("service", "x", 0.0, 0.38),
            ZoneBand("exterior", "y", 0.72, 1.0),
        ],
        anchors=["foyer", "living_room", "hallway"],
    ),
    "living_core": LayoutStrategy(
        name="living_core",
        description="Living-dining-kitchen as the organizing core; private and service around it.",
        bands=[
            ZoneBand("public", "y", 0.18, 0.68),
            ZoneBand("public", "x", 0.22, 0.78),
            ZoneBand("circulation", "y", 0.08, 0.55),
            ZoneBand("private", "x", 0.55, 1.00),
            ZoneBand("service", "x", 0.0, 0.36),
            ZoneBand("exterior", "y", 0.72, 1.0),
        ],
        anchors=["living_room", "kitchen", "hallway"],
    ),
}


COMPETITION_STRATEGIES: tuple[str, ...] = (
    "patio_oriented",
    "central_spine",
    "linear",
    "service_side",
    "cluster",
)

# Extra SpatialPlan archetypes. Not in COMPETITION_STRATEGIES order.
EXTRA_STRATEGIES: tuple[str, ...] = (
    "rear_private",
    "living_core",
)


def default_strategy_name(program: RoomProgram) -> str:
    if program.outdoor_requested:
        return "patio_oriented"
    return "central_spine"


def _first_id(arch: ArchitecturalProgram, room_type: str) -> str | None:
    sp = arch.first(room_type)
    return sp.id if sp else None


def _ids(arch: ArchitecturalProgram, *types: str) -> list[str]:
    out: list[str] = []
    for t in types:
        out.extend(s.id for s in arch.by_type(t))
    return out


# Mass-relative preferred regions. Not lot coordinates. Not hard rectangles.
CLUSTER_GUIDANCE: dict[str, dict[str, dict]] = {
    "patio_oriented": {
        "arrival": {"position": "front", "cx": 0.22, "cy": 0.12, "band": ZoneBand("arrival", "y", 0.00, 0.28), "weight": 2},
        "public": {"position": "mid/rear toward patio", "cx": 0.50, "cy": 0.62, "band": ZoneBand("public", "y", 0.28, 1.00), "weight": 2},
        "private": {"position": "side/rear", "cx": 0.72, "cy": 0.38, "band": ZoneBand("private", "x", 0.40, 1.00), "weight": 2},
        "primary_suite": {"position": "private side", "cx": 0.78, "cy": 0.42, "band": ZoneBand("private", "x", 0.45, 1.00), "weight": 3},
        "service": {"position": "front/side arrival", "cx": 0.20, "cy": 0.18, "band": ZoneBand("service", "x", 0.00, 0.48), "weight": 2},
        "circulation": {"position": "spine", "cx": 0.48, "cy": 0.40, "band": ZoneBand("circulation", "y", 0.00, 0.62), "weight": 1},
        "exterior": {"position": "rear exterior", "cx": 0.50, "cy": 1.05, "band": None, "weight": 1},
    },
    "central_spine": {
        "arrival": {"position": "front", "cx": 0.28, "cy": 0.10, "band": ZoneBand("arrival", "y", 0.00, 0.28), "weight": 2},
        "public": {"position": "front/center", "cx": 0.50, "cy": 0.28, "band": ZoneBand("public", "y", 0.00, 0.48), "weight": 2},
        "private": {"position": "rear/side", "cx": 0.70, "cy": 0.68, "band": ZoneBand("private", "y", 0.40, 1.00), "weight": 2},
        "primary_suite": {"position": "private side", "cx": 0.78, "cy": 0.70, "band": ZoneBand("private", "y", 0.42, 1.00), "weight": 3},
        "service": {"position": "front/side arrival", "cx": 0.20, "cy": 0.18, "band": ZoneBand("service", "x", 0.00, 0.42), "weight": 2},
        "circulation": {"position": "spine", "cx": 0.50, "cy": 0.50, "band": ZoneBand("circulation", "y", 0.18, 0.72), "weight": 1},
        "exterior": {"position": "rear exterior", "cx": 0.50, "cy": 1.05, "band": None, "weight": 1},
    },
    "linear": {
        "arrival": {"position": "front sequence", "cx": 0.40, "cy": 0.08, "band": ZoneBand("arrival", "y", 0.00, 0.22), "weight": 2},
        "public": {"position": "front sequence", "cx": 0.50, "cy": 0.22, "band": ZoneBand("public", "y", 0.00, 0.38), "weight": 2},
        "private": {"position": "rear sequence", "cx": 0.50, "cy": 0.72, "band": ZoneBand("private", "y", 0.48, 1.00), "weight": 2},
        "primary_suite": {"position": "rear of sequence", "cx": 0.55, "cy": 0.78, "band": ZoneBand("private", "y", 0.52, 1.00), "weight": 3},
        "service": {"position": "front sequence", "cx": 0.28, "cy": 0.16, "band": ZoneBand("service", "y", 0.00, 0.40), "weight": 2},
        "circulation": {"position": "depth spine", "cx": 0.50, "cy": 0.45, "band": ZoneBand("circulation", "y", 0.20, 0.70), "weight": 1},
        "exterior": {"position": "rear exterior", "cx": 0.50, "cy": 1.05, "band": None, "weight": 1},
    },
    "service_side": {
        "arrival": {"position": "service-side front", "cx": 0.18, "cy": 0.12, "band": ZoneBand("arrival", "x", 0.00, 0.40), "weight": 2},
        "public": {"position": "opposite service side", "cx": 0.68, "cy": 0.40, "band": ZoneBand("public", "x", 0.40, 1.00), "weight": 2},
        "private": {"position": "rear opposite service", "cx": 0.70, "cy": 0.70, "band": ZoneBand("private", "y", 0.40, 1.00), "weight": 2},
        "primary_suite": {"position": "private opposite service", "cx": 0.78, "cy": 0.68, "band": ZoneBand("private", "x", 0.45, 1.00), "weight": 3},
        "service": {"position": "garage side front", "cx": 0.16, "cy": 0.20, "band": ZoneBand("service", "x", 0.00, 0.38), "weight": 3},
        "circulation": {"position": "between sides", "cx": 0.42, "cy": 0.45, "band": ZoneBand("circulation", "x", 0.22, 0.68), "weight": 1},
        "exterior": {"position": "rear exterior", "cx": 0.50, "cy": 1.05, "band": None, "weight": 1},
    },
    "cluster": {
        "arrival": {"position": "front cluster edge", "cx": 0.22, "cy": 0.12, "band": ZoneBand("arrival", "y", 0.00, 0.26), "weight": 3},
        "public": {"position": "public cluster", "cx": 0.42, "cy": 0.38, "band": ZoneBand("public", "y", 0.08, 0.52), "weight": 4},
        "private": {"position": "private cluster", "cx": 0.78, "cy": 0.62, "band": ZoneBand("private", "x", 0.50, 1.00), "weight": 4},
        "primary_suite": {"position": "inside private cluster", "cx": 0.82, "cy": 0.58, "band": ZoneBand("private", "x", 0.52, 1.00), "weight": 4},
        "service": {"position": "service cluster front", "cx": 0.16, "cy": 0.18, "band": ZoneBand("service", "x", 0.00, 0.36), "weight": 4},
        "circulation": {"position": "between clusters", "cx": 0.48, "cy": 0.45, "band": ZoneBand("circulation", "y", 0.12, 0.62), "weight": 2},
        "exterior": {"position": "rear exterior", "cx": 0.50, "cy": 1.05, "band": None, "weight": 1},
    },
    "rear_private": {
        "arrival": {"position": "front", "cx": 0.28, "cy": 0.10, "band": ZoneBand("arrival", "y", 0.00, 0.26), "weight": 2},
        "public": {"position": "front public", "cx": 0.48, "cy": 0.26, "band": ZoneBand("public", "y", 0.00, 0.42), "weight": 2},
        "private": {"position": "rear private", "cx": 0.62, "cy": 0.78, "band": ZoneBand("private", "y", 0.50, 1.00), "weight": 3},
        "primary_suite": {"position": "rear private", "cx": 0.72, "cy": 0.82, "band": ZoneBand("private", "y", 0.52, 1.00), "weight": 3},
        "service": {"position": "front/side", "cx": 0.18, "cy": 0.20, "band": ZoneBand("service", "x", 0.00, 0.38), "weight": 2},
        "circulation": {"position": "mid spine", "cx": 0.50, "cy": 0.48, "band": ZoneBand("circulation", "y", 0.18, 0.62), "weight": 1},
        "exterior": {"position": "rear exterior", "cx": 0.50, "cy": 1.05, "band": None, "weight": 1},
    },
    "living_core": {
        "arrival": {"position": "front edge of core", "cx": 0.30, "cy": 0.12, "band": ZoneBand("arrival", "y", 0.00, 0.24), "weight": 2},
        "public": {"position": "central living core", "cx": 0.50, "cy": 0.48, "band": ZoneBand("public", "y", 0.18, 0.68), "weight": 4},
        "private": {"position": "side of core", "cx": 0.78, "cy": 0.55, "band": ZoneBand("private", "x", 0.55, 1.00), "weight": 3},
        "primary_suite": {"position": "quiet side of core", "cx": 0.82, "cy": 0.52, "band": ZoneBand("private", "x", 0.58, 1.00), "weight": 3},
        "service": {"position": "service flank", "cx": 0.16, "cy": 0.32, "band": ZoneBand("service", "x", 0.00, 0.36), "weight": 2},
        "circulation": {"position": "around core", "cx": 0.46, "cy": 0.36, "band": ZoneBand("circulation", "y", 0.08, 0.55), "weight": 1},
        "exterior": {"position": "rear exterior", "cx": 0.50, "cy": 1.05, "band": None, "weight": 1},
    },
}


BLOCK_GUIDANCE: dict[str, dict[str, dict]] = {
    "patio_oriented": {
        "arrival": {"region": "front/side", "cx": 0.22, "cy": 0.12, "band": ZoneBand("arrival", "y", 0.00, 0.28)},
        "public": {"region": "mid/rear toward patio", "cx": 0.55, "cy": 0.62, "band": ZoneBand("public", "y", 0.28, 0.85)},
        "private": {"region": "side, off public flow", "cx": 0.78, "cy": 0.40, "band": ZoneBand("private", "x", 0.48, 1.00)},
        "service": {"region": "front/side with garage", "cx": 0.20, "cy": 0.32, "band": ZoneBand("service", "x", 0.00, 0.42)},
    },
    "central_spine": {
        "arrival": {"region": "front", "cx": 0.28, "cy": 0.10, "band": ZoneBand("arrival", "y", 0.00, 0.28)},
        "public": {"region": "front/center branch", "cx": 0.52, "cy": 0.30, "band": ZoneBand("public", "y", 0.00, 0.48)},
        "private": {"region": "rear branch", "cx": 0.70, "cy": 0.70, "band": ZoneBand("private", "y", 0.42, 1.00)},
        "service": {"region": "arrival/service branch", "cx": 0.20, "cy": 0.38, "band": ZoneBand("service", "x", 0.00, 0.40)},
    },
    "linear": {
        "arrival": {"region": "front sequence", "cx": 0.40, "cy": 0.08, "band": ZoneBand("arrival", "y", 0.00, 0.22)},
        "public": {"region": "front-mid sequence", "cx": 0.50, "cy": 0.28, "band": ZoneBand("public", "y", 0.08, 0.42)},
        "private": {"region": "rear sequence", "cx": 0.50, "cy": 0.75, "band": ZoneBand("private", "y", 0.48, 1.00)},
        "service": {"region": "front/mid sequence", "cx": 0.28, "cy": 0.22, "band": ZoneBand("service", "y", 0.00, 0.45)},
    },
    "service_side": {
        "arrival": {"region": "service-side front", "cx": 0.18, "cy": 0.12, "band": ZoneBand("arrival", "x", 0.00, 0.40)},
        "public": {"region": "opposite service side", "cx": 0.70, "cy": 0.38, "band": ZoneBand("public", "x", 0.40, 1.00)},
        "private": {"region": "rear, protected", "cx": 0.72, "cy": 0.72, "band": ZoneBand("private", "y", 0.42, 1.00)},
        "service": {"region": "one side with garage", "cx": 0.16, "cy": 0.38, "band": ZoneBand("service", "x", 0.00, 0.38)},
    },
    "cluster": {
        "arrival": {"region": "front cluster edge", "cx": 0.22, "cy": 0.12, "band": ZoneBand("arrival", "y", 0.00, 0.26)},
        "public": {"region": "compact public cluster", "cx": 0.42, "cy": 0.36, "band": ZoneBand("public", "y", 0.08, 0.52)},
        "private": {"region": "compact private cluster", "cx": 0.78, "cy": 0.62, "band": ZoneBand("private", "x", 0.50, 1.00)},
        "service": {"region": "compact service cluster", "cx": 0.16, "cy": 0.40, "band": ZoneBand("service", "x", 0.00, 0.36)},
    },
    "rear_private": {
        "arrival": {"region": "front", "cx": 0.28, "cy": 0.10, "band": ZoneBand("arrival", "y", 0.00, 0.26)},
        "public": {"region": "front public", "cx": 0.48, "cy": 0.26, "band": ZoneBand("public", "y", 0.00, 0.42)},
        "private": {"region": "rear private", "cx": 0.62, "cy": 0.78, "band": ZoneBand("private", "y", 0.50, 1.00)},
        "service": {"region": "front/side", "cx": 0.18, "cy": 0.32, "band": ZoneBand("service", "x", 0.00, 0.38)},
    },
    "living_core": {
        "arrival": {"region": "front of core", "cx": 0.30, "cy": 0.12, "band": ZoneBand("arrival", "y", 0.00, 0.24)},
        "public": {"region": "central living core", "cx": 0.50, "cy": 0.48, "band": ZoneBand("public", "y", 0.18, 0.68)},
        "private": {"region": "side of core", "cx": 0.78, "cy": 0.55, "band": ZoneBand("private", "x", 0.55, 1.00)},
        "service": {"region": "service flank", "cx": 0.16, "cy": 0.32, "band": ZoneBand("service", "x", 0.00, 0.36)},
    },
}


def _guidance_for(strategy_name: str, cluster_id: str) -> dict:
    table = CLUSTER_GUIDANCE.get(strategy_name) or CLUSTER_GUIDANCE["central_spine"]
    return table.get(cluster_id) or {"position": "", "cx": 0.5, "cy": 0.5, "band": None, "weight": 1}


def _cluster_areas(arch: ArchitecturalProgram, ids: list[str]) -> tuple[int, int]:
    by_id = {s.id: s for s in arch.spaces}
    pref = sum(by_id[i].preferred_area for i in ids if i in by_id)
    mn = sum(by_id[i].min_area for i in ids if i in by_id)
    return pref, mn


def _make_cluster(
    arch: ArchitecturalProgram,
    cid: str,
    zone: str,
    ids: list[str],
    strategy_name: str,
    anchor: str | None = None,
) -> RoomCluster | None:
    if not ids:
        return None
    g = _guidance_for(strategy_name, cid)
    pref, mn = _cluster_areas(arch, ids)
    return RoomCluster(
        name=cid,
        room_ids=ids,
        id=cid,
        zone=zone,
        preferred_area=pref,
        min_area=mn,
        anchor=anchor,
        preferred_position=g["position"],
        cohesion_weight=int(g["weight"]),
        cx_frac=float(g["cx"]),
        cy_frac=float(g["cy"]),
        band=g["band"],
    )


def _build_clusters(arch: ArchitecturalProgram, strategy_name: str = "central_spine") -> list[RoomCluster]:
    clusters: list[RoomCluster] = []
    primary = _ids(arch, "master_bedroom", "ensuite_bathroom", "walk_in_closet")
    c = _make_cluster(arch, "primary_suite", "private", primary, strategy_name, _first_id(arch, "master_bedroom"))
    if c:
        clusters.append(c)
    public = _ids(arch, "living_room", "dining_room", "kitchen")
    c = _make_cluster(arch, "public", "public", public, strategy_name, _first_id(arch, "living_room"))
    if c:
        clusters.append(c)
    private = _ids(arch, "bedroom", "bathroom", "half_bath", "master_bedroom")
    c = _make_cluster(arch, "private", "private", private, strategy_name, _first_id(arch, "bedroom"))
    if c:
        clusters.append(c)
    service = _ids(arch, "garage", "laundry_room", "mudroom")
    c = _make_cluster(arch, "service", "service", service, strategy_name, _first_id(arch, "garage"))
    if c:
        clusters.append(c)
    arrival = _ids(arch, "foyer", "garage")
    c = _make_cluster(arch, "arrival", "arrival", arrival, strategy_name, _first_id(arch, "foyer"))
    if c:
        clusters.append(c)
    circ = _ids(arch, "hallway")
    c = _make_cluster(arch, "circulation", "circulation", circ, strategy_name, _first_id(arch, "hallway"))
    if c:
        clusters.append(c)
    exterior = _ids(arch, "patio", "deck")
    c = _make_cluster(arch, "exterior", "exterior", exterior, strategy_name, _first_id(arch, "patio"))
    if c:
        clusters.append(c)
    return clusters


def _build_cluster_relations(clusters: list[RoomCluster]) -> list[ClusterRelation]:
    have = {c.id for c in clusters}
    spec = [
        ("arrival", "public", "connected", "preferred"),
        ("arrival", "service", "connected", "preferred"),
        ("public", "private", "separated", "preferred"),
        ("public", "service", "connected", "preferred"),
        ("service", "public", "preferred", "preferred"),
        ("private", "circulation", "accessed_by", "required"),
        ("public", "circulation", "connected", "preferred"),
        ("public", "exterior", "outside_access", "preferred"),
        ("primary_suite", "private", "preferred", "preferred"),
        ("primary_suite", "circulation", "accessed_by", "preferred"),
        ("service", "circulation", "connected", "preferred"),
        ("arrival", "circulation", "connected", "required"),
    ]
    out: list[ClusterRelation] = []
    seen: set[tuple[str, str, str]] = set()
    for a, b, kind, strength in spec:
        if a not in have or b not in have or a == b:
            continue
        key = (a, b, kind)
        if key in seen:
            continue
        seen.add(key)
        out.append(ClusterRelation(a, b, kind, strength))  # type: ignore[arg-type]
    return out


def _build_circulation(arch: ArchitecturalProgram) -> CirculationGraph:
    foyer = _first_id(arch, "foyer")
    hall = _first_id(arch, "hallway")
    garage = _first_id(arch, "garage")
    nodes: list[CirculationNode] = []
    edges: list[CirculationEdge] = []
    if foyer:
        nodes.append(CirculationNode(foyer, "entry"))
    if hall:
        nodes.append(CirculationNode(hall, "hall"))
    if foyer and hall:
        edges.append(CirculationEdge(foyer, hall))
    if garage:
        nodes.append(CirculationNode(garage, "arrival"))
        if foyer:
            edges.append(CirculationEdge(foyer, garage))
    public_types = ("living_room", "kitchen", "dining_room")
    private_types = ("bedroom", "master_bedroom", "bathroom", "half_bath")
    service_types = ("laundry_room", "home_office")
    for sp in arch.spaces:
        if sp.room_type in public_types:
            nodes.append(CirculationNode(sp.id, "public"))
            target = hall or foyer
            if target:
                edges.append(CirculationEdge(target, sp.id))
        elif sp.room_type in private_types:
            nodes.append(CirculationNode(sp.id, "private"))
            target = hall or foyer
            if target:
                edges.append(CirculationEdge(target, sp.id))
        elif sp.room_type in service_types:
            nodes.append(CirculationNode(sp.id, "service"))
            target = hall or foyer
            if target:
                edges.append(CirculationEdge(target, sp.id))
    return CirculationGraph(nodes=nodes, edges=edges)


def _build_relations(arch: ArchitecturalProgram) -> list[SemanticRelation]:
    return build_planning_graph(arch)


def _preferred_edges(
    arch: ArchitecturalProgram,
    clusters: list[RoomCluster],
    strategy_name: str = "",
) -> list[tuple[str, str, str]]:
    living = _first_id(arch, "living_room")
    dining = _first_id(arch, "dining_room")
    kitchen = _first_id(arch, "kitchen")
    laundry = _first_id(arch, "laundry_room")
    foyer = _first_id(arch, "foyer")
    hall = _first_id(arch, "hallway")
    garage = _first_id(arch, "garage")
    edges: list[tuple[str, str, str]] = []
    if living and dining:
        edges.append((living, dining, "adjacent"))
    if kitchen and living:
        edges.append((kitchen, living, "adjacent"))
    if laundry and kitchen:
        edges.append((laundry, kitchen, "near"))
    if garage and foyer:
        edges.append((garage, foyer, "near"))
    master = _first_id(arch, "master_bedroom")
    if master and hall:
        edges.append((master, hall, "adjacent"))
    if strategy_name == "linear":
        if foyer and living:
            edges.append((foyer, living, "near"))
        if living and hall:
            edges.append((living, hall, "near"))
        if hall and master:
            edges.append((hall, master, "near"))
    seen = {tuple(sorted((a, b))) for a, b, _ in edges}
    for cluster in clusters:
        ids = cluster.room_ids
        for a, b in zip(ids, ids[1:]):
            key = tuple(sorted((a, b)))
            if a != b and key not in seen:
                edges.append((a, b, "near"))
                seen.add(key)
    return edges


def _planning_zones(arch: ArchitecturalProgram) -> dict[str, list[str]]:
    zones: dict[str, list[str]] = {}
    for s in arch.spaces:
        for z in s.planning_zones:
            zones.setdefault(z, []).append(s.id)
    return zones


def _build_blocks(arch: ArchitecturalProgram, strategy_name: str) -> list[RoomBlock]:
    table = BLOCK_GUIDANCE.get(strategy_name) or BLOCK_GUIDANCE["central_spine"]
    mapping = {
        "arrival": [s.id for s in arch.by_planning_zone("arrival")],
        "public": [s.id for s in arch.by_planning_zone("public") if s.room_type != "home_office"]
        or _ids(arch, "living_room", "dining_room", "kitchen"),
        "private": [s.id for s in arch.by_planning_zone("private")],
        "service": [s.id for s in arch.spaces if "service" in s.planning_zones and s.room_type != "bathroom"
                    and s.room_type != "ensuite_bathroom" and s.room_type != "half_bath"]
        or _ids(arch, "garage", "laundry_room"),
    }
    kitchen = _first_id(arch, "kitchen")
    if kitchen and kitchen not in mapping["service"] and strategy_name == "service_side":
        mapping["service"].append(kitchen)
    blocks: list[RoomBlock] = []
    for bid, ids in mapping.items():
        uniq = list(dict.fromkeys(ids))
        if not uniq:
            continue
        g = table.get(bid) or {"region": "", "cx": 0.5, "cy": 0.5, "band": None}
        blocks.append(RoomBlock(
            id=bid,
            zone=bid,
            room_ids=uniq,
            region=str(g.get("region") or ""),
            cx_frac=float(g.get("cx") or 0.5),
            cy_frac=float(g.get("cy") or 0.5),
            band=g.get("band"),
        ))
    return blocks


def _zones(arch: ArchitecturalProgram) -> dict[str, list[str]]:
    zones: dict[str, list[str]] = {}
    for s in arch.spaces:
        zones.setdefault(s.zone, []).append(s.id)
    return zones


def _plan_from_arch(arch: ArchitecturalProgram, name: str, program: RoomProgram | None = None) -> SpatialPlan:
    strategy = STRATEGIES.get(name) or STRATEGIES["central_spine"]
    zones = _zones(arch)
    anchors: dict[str, str] = {}
    for key in ("foyer", "hallway", "living_room", "kitchen", "patio", "garage"):
        rid = _first_id(arch, key)
        if rid:
            anchors[key] = rid
    clusters = _build_clusters(arch, name)
    access = plan_access(program, program.envelope) if program else None
    return SpatialPlan(
        strategy=strategy,
        zones=zones,
        relations=_build_relations(arch),
        circulation=_build_circulation(arch),
        clusters=clusters,
        anchors=anchors,
        preferred_edges=_preferred_edges(arch, clusters, name),
        cluster_relations=_build_cluster_relations(clusters),
        blocks=_build_blocks(arch, name),
        access=access,
        planning_zones=_planning_zones(arch),
    )


def plan(program: RoomProgram, strategy_name: str | None = None) -> SpatialPlan:
    arch = from_room_program(program)
    name = strategy_name or default_strategy_name(program)
    return _plan_from_arch(arch, name, program)


def cheap_filter_candidates(plans: list[SpatialPlan], program: RoomProgram) -> list[SpatialPlan]:
    """Drop SpatialPlans missing required rooms or with private rooms in the service zone.

    Cheap feasibility only. Does not run CP-SAT.
    """
    required = {s.id for s in program.rooms if s.required}
    types = {s.id: s.type for s in program.rooms}
    kept: list[SpatialPlan] = []
    for spatial in plans:
        zids = {rid for ids in spatial.zones.values() for rid in ids}
        if required and not required.issubset(zids):
            continue
        service_ids = spatial.zones.get("service") or []
        if any(types.get(rid) in BEDROOM_TYPES for rid in service_ids):
            continue
        kept.append(spatial)
    return kept


def generate_strategy_candidates(program: RoomProgram) -> list[SpatialPlan]:
    """Competition SpatialPlans first, then extra archetypes. Cheap-filtered. Deterministic."""
    arch = from_room_program(program)
    names = list(COMPETITION_STRATEGIES) + [n for n in EXTRA_STRATEGIES if n in STRATEGIES]
    plans = [_plan_from_arch(arch, name, program) for name in names]
    filtered = cheap_filter_candidates(plans, program)
    order = {n: i for i, n in enumerate(names)}
    filtered.sort(key=lambda p: order.get(p.strategy.name, 99))
    return filtered


def strategy_fingerprint(spatial: SpatialPlan) -> tuple:
    bands = tuple(
        (b.zone, b.axis, round(b.lo_frac, 3), round(b.hi_frac, 3))
        for b in spatial.strategy.bands
    )
    clusters = tuple(
        (c.id, round(c.cx_frac, 3), round(c.cy_frac, 3), c.cohesion_weight)
        for c in spatial.clusters
    )
    return (spatial.strategy.name, bands, clusters)


def preferred_topology_edges(spatial: SpatialPlan) -> list[TopologyEdge]:
    """Soft-only edges. Never hard wall-share."""
    return [
        TopologyEdge(a, b, rel, hard=False)
        for a, b, rel in spatial.preferred_edges
    ]


def avoid_topology_edges(spatial: SpatialPlan) -> list[TopologyEdge]:
    """Soft avoid/separated pairs from the planning graph. Not hard constraints."""
    edges: list[TopologyEdge] = []
    seen: set[tuple[str, str]] = set()
    for rel in spatial.relations:
        if rel.kind != "avoid" and rel.strength != "avoid":
            continue
        key = tuple(sorted((rel.room_a, rel.room_b)))
        if key in seen:
            continue
        seen.add(key)
        edges.append(TopologyEdge(rel.room_a, rel.room_b, "separated", hard=False))
    return edges


def log_spatial_plan(spatial: SpatialPlan) -> None:
    print("[KIYUB SPATIAL] strategy", spatial.strategy.name)
    print("[KIYUB SPATIAL]", spatial.strategy.description)
    print("[KIYUB SPATIAL] This is a space-planning heuristic, not professional architectural approval.")
    for zone, ids in spatial.zones.items():
        print(f"[KIYUB SPATIAL] zone {zone}: {len(ids)} spaces")
    print("[KIYUB SPATIAL] clusters", ", ".join(c.name for c in spatial.clusters) or "(none)")
    print("[KIYUB SPATIAL] anchors", ", ".join(spatial.anchors) or "(none)")
    print("[KIYUB SPATIAL] relations", len(spatial.relations), "preferred_edges", len(spatial.preferred_edges))
    print("[KIYUB SPATIAL] circulation nodes", len(spatial.circulation.nodes), "edges", len(spatial.circulation.edges))
    print("[KIYUB SPATIAL] blocks", ", ".join(b.id for b in spatial.blocks) or "(none)")
    log_clusters(spatial)


def log_clusters(spatial: SpatialPlan) -> None:
    print("[KIYUB CLUSTER] count", len(spatial.clusters), "relations", len(spatial.cluster_relations))
    for c in spatial.clusters:
        print(
            f"[KIYUB CLUSTER] {c.id} rooms={len(c.room_ids)} zone={c.zone} "
            f"pref_area={c.preferred_area} pos={c.preferred_position}"
        )
    print("[KIYUB CLUSTER] Soft organization inside BuildingMass, not hard cluster rectangles.")
