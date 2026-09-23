"""RoomProgram from generation constraints. Does not drop requested bedroom/bath counts."""

from __future__ import annotations

from .models import Envelope, RoomProgram, RoomSpec
from .room_rules import BATH_TYPES, BEDROOM_TYPES, ZONE_BY_TYPE, rule_for


def envelope_from_constraints(constraints: dict) -> Envelope:
    """Reuse the shared lot envelope (placeholder setbacks)."""
    from .envelope import compute_buildable_envelope

    raw = compute_buildable_envelope(constraints)
    return Envelope(
        width=max(1, int(raw["buildable_width"])),
        depth=max(1, int(raw["buildable_depth"])),
        lot_width_ft=float(raw["lot_width_ft"]),
        lot_depth_ft=float(raw["lot_depth_ft"]),
        buildable_width=float(raw["buildable_width"]),
        buildable_depth=float(raw["buildable_depth"]),
    )


def _spec(rid: str, rtype: str, name: str, scale: float = 1.0) -> RoomSpec:
    rule = rule_for(rtype)
    mw = max(1, int(round(rule["min_width"] * scale)))
    md = max(1, int(round(rule["min_depth"] * scale)))
    pw = max(mw, int(round(rule["preferred_width"] * scale)))
    pd = max(md, int(round(rule["preferred_depth"] * scale)))
    pref_area = max(pw * pd, int(round(rule.get("preferred_area", pw * pd) * scale * scale)))
    max_area = max(pref_area, int(round(rule.get("max_area", pref_area * 1.8) * scale * scale)))
    return RoomSpec(
        id=rid,
        type=rtype,
        name=name,
        min_width=mw,
        min_depth=md,
        preferred_width=pw,
        preferred_depth=pd,
        required=True,
        zone=ZONE_BY_TYPE.get(rtype, "public"),
        max_aspect_ratio=float(rule.get("max_aspect_ratio") or 2.8),
        max_area=max_area,
        preferred_area=pref_area,
    )


def from_constraints(constraints: dict, envelope: Envelope | None = None) -> RoomProgram:
    bedrooms = int(constraints.get("bedrooms", 3))
    bathrooms = int(constraints.get("bathrooms", 2))
    open_plan = bool(constraints.get("openPlan") or constraints.get("open_plan", False))
    primary_suite = constraints.get("primarySuite", True)
    home_office = bool(constraints.get("homeOffice", False))
    formal_dining = bool(constraints.get("formalDining", False))
    garage = constraints.get("garage", "2car")
    laundry = constraints.get("laundry", "room")
    outdoor = constraints.get("outdoor", "patio")

    env = envelope or envelope_from_constraints(constraints)
    rooms: list[RoomSpec] = []
    n = 0

    def add(rtype: str, name: str | None = None, scale: float = 1.0) -> RoomSpec:
        nonlocal n
        spec = _spec(f"p{n}", rtype, name or rtype.replace("_", " ").title(), scale)
        n += 1
        rooms.append(spec)
        return spec

    add("living_room", "Great Room" if open_plan else "Living Room")
    add("kitchen")
    if not (open_plan and not formal_dining):
        add("dining_room", "Formal Dining" if formal_dining else "Dining Area")

    add("foyer", "Entry Foyer")
    add("hallway", "Main Hallway")

    if primary_suite:
        add("master_bedroom", "Primary Suite")
        add("ensuite_bathroom", "Primary Bath")
        add("walk_in_closet", "Primary Closet")
    else:
        add("master_bedroom", "Primary Bedroom")
        add("bathroom", "Primary Bath")

    extra_beds = max(0, bedrooms - 1)
    for i in range(extra_beds):
        add("bedroom", f"Bedroom {i + 2}")

    # Preserve requested bathroom count: ensuite/primary bath already counts as 1.
    already = 1 if bedrooms >= 1 or primary_suite else 0
    shared = max(0, bathrooms - already)
    for i in range(shared):
        add("bathroom" if i == 0 else "half_bath", "Shared Bath" if i == 0 else f"Half Bath {i}")

    if home_office:
        add("home_office")

    if laundry == "room":
        add("laundry_room", "Laundry Room")
    elif laundry == "closet":
        add("laundry_room", "Laundry Closet", scale=0.7)

    if garage == "1car":
        add("garage", "1-Car Garage", scale=0.7)
    elif garage == "2car":
        add("garage", "2-Car Garage")
    elif garage == "3car":
        add("garage", "3-Car Garage", scale=1.2)

    if outdoor in ("patio", "both"):
        add("patio", "Rear Patio")
    if outdoor in ("deck", "both"):
        add("deck", "Rear Deck")

    bed_count = sum(1 for r in rooms if r.type in BEDROOM_TYPES)
    bath_count = sum(1 for r in rooms if r.type in BATH_TYPES)
    if bed_count != bedrooms:
        raise ValueError(
            f"RoomProgram bedroom count {bed_count} != requested {bedrooms}"
        )
    if bath_count != bathrooms:
        raise ValueError(
            f"RoomProgram bathroom count {bath_count} != requested {bathrooms}"
        )

    return RoomProgram(
        rooms=rooms,
        envelope=env,
        outdoor_requested=outdoor not in (None, "none", ""),
        bedrooms_requested=bedrooms,
        bathrooms_requested=bathrooms,
    )


def prototype_two_bedroom(envelope: Envelope) -> RoomProgram:
    """Standalone milestone program: living, dining, kitchen, 2 bedrooms, 1 bath + circulation."""
    rooms = [
        _spec("p0", "living_room", "Living Room"),
        _spec("p1", "dining_room", "Dining Area"),
        _spec("p2", "kitchen", "Kitchen"),
        _spec("p3", "bedroom", "Bedroom 1"),
        _spec("p4", "bedroom", "Bedroom 2"),
        _spec("p5", "bathroom", "Bathroom"),
        _spec("p6", "foyer", "Entry Foyer"),
        _spec("p7", "hallway", "Main Hallway"),
    ]
    return RoomProgram(
        rooms=rooms,
        envelope=envelope,
        outdoor_requested=False,
        bedrooms_requested=2,
        bathrooms_requested=1,
    )
