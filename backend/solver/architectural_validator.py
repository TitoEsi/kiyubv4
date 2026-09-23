"""Architectural planning diagnostics. Not building-code compliance.

ERROR: fundamental feasibility (missing vehicle access, dropped rooms, isolated required).
WARNING / PREFERENCE: organization quality. Do not flip validated.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from .doors import _shared_segment
from .models import Layout, PlacedRoom, RoomProgram
from .planning_profile import PHILIPPINE_RESIDENTIAL_DEFAULTS
from .room_rules import BATH_TYPES, BEDROOM_TYPES, CIRCULATION_TYPES
from .site_plan import AccessPlan, garage_is_central_interior, garage_touches_vehicle_frontage
from .spatial_plan import SpatialPlan


@dataclass
class PlanningIssue:
    code: str
    severity: str  # error | warning | preference
    room: str
    message: str

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "room": self.room,
            "message": self.message,
        }


@dataclass
class PlanningReport:
    issues: list[PlanningIssue] = field(default_factory=list)
    vehicle_access_valid: bool = True
    arrival_valid: bool = True
    public_cohesion: float = 1.0
    private_cohesion: float = 1.0
    service_cohesion: float = 1.0
    public_private_separation: float = 1.0
    outdoor_relationship: bool = True
    mudroom_default_generated: bool = False

    @property
    def errors(self) -> list[PlanningIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def valid(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {
            "valid": self.valid,
            "vehicle_access_valid": self.vehicle_access_valid,
            "arrival_valid": self.arrival_valid,
            "public_cohesion": round(self.public_cohesion, 3),
            "private_cohesion": round(self.private_cohesion, 3),
            "service_cohesion": round(self.service_cohesion, 3),
            "public_private_separation": round(self.public_private_separation, 3),
            "outdoor_relationship": self.outdoor_relationship,
            "mudroom_default_generated": self.mudroom_default_generated,
            "issues": [i.as_dict() for i in self.issues],
            "note": "Architectural planning diagnostics. Not professional architectural approval.",
        }


def _door_graph(layout: Layout) -> dict[str, set[str]]:
    g: dict[str, set[str]] = defaultdict(set)
    for d in layout.doors:
        g[d.room_a].add(d.room_b)
        g[d.room_b].add(d.room_a)
    for e in layout.topology or []:
        if e.relation in ("connected", "accessed_by", "outside_access"):
            g[e.room_a].add(e.room_b)
            g[e.room_b].add(e.room_a)
    return g


def _reachable(graph: dict[str, set[str]], seeds: list[str], blocked: set[str] | None = None) -> set[str]:
    blocked = blocked or set()
    seen: set[str] = set()
    q = deque(s for s in seeds if s not in blocked)
    while q:
        cur = q.popleft()
        if cur in seen or cur in blocked:
            continue
        seen.add(cur)
        for nxt in graph.get(cur, ()):
            if nxt not in seen and nxt not in blocked:
                q.append(nxt)
    return seen


def _cohesion(rooms: list[PlacedRoom]) -> float:
    if len(rooms) < 2:
        return 1.0
    hits = 0
    need = 0
    for i, a in enumerate(rooms):
        for b in rooms[i + 1:]:
            need += 1
            if _shared_segment(a, b) is not None:
                hits += 1
    if not need:
        return 1.0
    # Connected component bonus: at least one wall-share in the group.
    return min(1.0, 0.45 + 0.55 * (hits / max(1, len(rooms) - 1)))


def _centroid(room: PlacedRoom) -> tuple[float, float]:
    return (room.x + room.width / 2.0, room.y + room.depth / 2.0)


def _garage_separates(garage: PlacedRoom, a: PlacedRoom, b: PlacedRoom) -> bool:
    if _shared_segment(a, b) is not None:
        return False
    ax, ay = _centroid(a)
    bx, by = _centroid(b)
    gx0, gx1 = garage.x, garage.x2
    gy0, gy1 = garage.y, garage.y2
    # Axis-aligned segment from a to b crosses garage bbox.
    minx, maxx = min(ax, bx), max(ax, bx)
    miny, maxy = min(ay, by), max(ay, by)
    if maxx < gx0 or minx > gx1 or maxy < gy0 or miny > gy1:
        return False
    return True


def analyze_planning(
    layout: Layout,
    program: RoomProgram,
    spatial: SpatialPlan | None = None,
    access: AccessPlan | None = None,
) -> PlanningReport:
    report = PlanningReport()
    env = layout.envelope or program.envelope
    rooms = {r.id: r for r in layout.rooms}
    by_type: dict[str, list[PlacedRoom]] = defaultdict(list)
    for r in layout.rooms:
        by_type[r.type].append(r)

    muds = by_type.get("mudroom") or []
    if muds and not PHILIPPINE_RESIDENTIAL_DEFAULTS.get("auto_generate_mudroom", False):
        report.mudroom_default_generated = True
        report.issues.append(PlanningIssue(
            "mudroom_default_generated", "warning", muds[0].id,
            "Mudroom was generated by default; Philippine program does not auto-add mudroom.",
        ))

    foyer = (by_type.get("foyer") or [None])[0]
    if foyer is None or (env and foyer.y != 0):
        report.arrival_valid = False
        report.issues.append(PlanningIssue(
            "entry_without_clear_arrival", "error" if foyer is None else "warning",
            foyer.id if foyer else "",
            "Entry/foyer is missing or not on the street frontage.",
        ))
    elif foyer:
        report.arrival_valid = True

    garage = (by_type.get("garage") or [None])[0]
    if garage and env:
        veh = garage_touches_vehicle_frontage(garage, env)
        if access and access.driveway.touches_room(garage):
            veh = True
        report.vehicle_access_valid = veh
        if not veh:
            report.issues.append(PlanningIssue(
                "garage_without_vehicle_access", "error", garage.id,
                "Garage has no exterior vehicle-access relationship to street frontage or a side.",
            ))
        if garage_is_central_interior(garage, env):
            report.issues.append(PlanningIssue(
                "garage_inside_central_zone", "warning", garage.id,
                "Garage sits in the central interior of the house.",
            ))
        living = (by_type.get("living_room") or [None])[0]
        dining = (by_type.get("dining_room") or [None])[0]
        kitchen = (by_type.get("kitchen") or [None])[0]
        public_pairs = [(living, dining), (living, kitchen), (dining, kitchen)]
        if any(a and b and _garage_separates(garage, a, b) for a, b in public_pairs):
            report.issues.append(PlanningIssue(
                "garage_separates_public_spaces", "warning", garage.id,
                "Garage separates main public rooms.",
            ))

    public = [r for r in layout.rooms if r.type in ("living_room", "dining_room", "kitchen")]
    private = [r for r in layout.rooms if r.type in BEDROOM_TYPES]
    service = [r for r in layout.rooms if r.type in ("garage", "laundry_room")]
    report.public_cohesion = _cohesion(public)
    report.private_cohesion = _cohesion(private)
    report.service_cohesion = _cohesion(service)
    if report.public_cohesion < 0.35:
        report.issues.append(PlanningIssue(
            "public_zone_fragmented", "warning", "",
            "Public rooms are not a coherent group.",
        ))
    if report.private_cohesion < 0.35:
        report.issues.append(PlanningIssue(
            "private_zone_fragmented", "warning", "",
            "Bedrooms are not a coherent private group.",
        ))
    if service and report.service_cohesion < 0.2:
        report.issues.append(PlanningIssue(
            "service_zone_fragmented", "preference", "",
            "Service rooms are scattered.",
        ))

    if public and private:
        pub_cy = sum(_centroid(r)[1] for r in public) / len(public)
        priv_cy = sum(_centroid(r)[1] for r in private) / len(private)
        report.public_private_separation = min(1.0, abs(priv_cy - pub_cy) / max(8.0, (env.depth if env else 20) * 0.15))

    patio = (by_type.get("patio") or by_type.get("deck") or [None])[0]
    if patio and public:
        report.outdoor_relationship = any(_shared_segment(patio, r) is not None for r in public)
        if not report.outdoor_relationship:
            report.issues.append(PlanningIssue(
                "patio_without_public_relationship", "warning", patio.id,
                "Patio/deck has no wall relationship to a public room.",
            ))
    elif program.outdoor_requested and not patio:
        report.outdoor_relationship = False

    graph = _door_graph(layout)
    seeds = [r.id for r in layout.rooms if r.type in CIRCULATION_TYPES]
    if not seeds and foyer:
        seeds = [foyer.id]
    garage_ids = {garage.id} if garage else set()
    from_entry = _reachable(graph, seeds)
    without_garage = _reachable(graph, seeds, blocked=garage_ids)
    private_ids = {r.id for r in layout.rooms if r.type in BEDROOM_TYPES | BATH_TYPES | {"walk_in_closet"}}
    for r in layout.rooms:
        if r.type not in ("bedroom", "master_bedroom", "bathroom", "kitchen", "living_room", "laundry_room"):
            continue
        if r.id not in from_entry:
            report.issues.append(PlanningIssue(
                "isolated_required_room", "error", r.id,
                f"{r.name} is not reachable from entry/circulation.",
            ))
        if r.type in BEDROOM_TYPES and r.id not in without_garage and r.id in from_entry:
            report.issues.append(PlanningIssue(
                "bedroom_access_through_private_room", "warning", r.id,
                f"{r.name} requires traversal through the garage.",
            ))
        # Only-through-another-bedroom
        other_private = private_ids - {r.id}
        if r.type in BEDROOM_TYPES:
            bypass = _reachable(graph, seeds, blocked=other_private)
            if r.id not in bypass and r.id in from_entry:
                report.issues.append(PlanningIssue(
                    "bedroom_access_through_private_room", "warning", r.id,
                    f"{r.name} is only reachable through another private room.",
                ))

    beds = sum(1 for r in layout.rooms if r.type in BEDROOM_TYPES)
    baths = sum(1 for r in layout.rooms if r.type in BATH_TYPES)
    if beds != program.bedrooms_requested:
        report.issues.append(PlanningIssue(
            "isolated_required_room", "error", "",
            f"Requested {program.bedrooms_requested} bedrooms, layout has {beds}.",
        ))
    if baths != program.bathrooms_requested:
        report.issues.append(PlanningIssue(
            "isolated_required_room", "error", "",
            f"Requested {program.bathrooms_requested} bathrooms, layout has {baths}.",
        ))

    _ = spatial
    return report
