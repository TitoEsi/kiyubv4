"""Validate HouseGAN candidate boxes and convert them to soft CP-SAT hints.

AI proposes. RoomProgram is canonical. OR-Tools AddHint is soft.
Zone-fallback MOE plans are not HouseGAN candidates.
Not professional architectural approval.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from .models import Envelope, RoomProgram

HOUSEGAN_GENERATOR = "moe+housegan"

HintTuple = tuple[int, int, int, int]


@dataclass
class HintConversion:
    """Source candidate feet → KIYUB envelope integer feet."""

    source: str = "candidate plan feet (totalWidth x totalHeight), origin top-left"
    target: str = "buildable envelope integer feet, origin top-left, y=0 street/front"
    source_width: float = 0.0
    source_depth: float = 0.0
    envelope_width: int = 0
    envelope_depth: int = 0
    scale_x: float = 1.0
    scale_y: float = 1.0


@dataclass
class HintAttempt:
    hints: dict[str, HintTuple] | None
    used: bool
    reason: str
    conversion: HintConversion | None = None
    extras: dict = field(default_factory=dict)


def _finite_positive_box(room: dict) -> bool:
    try:
        x = float(room.get("x", 0))
        y = float(room.get("y", 0))
        w = float(room.get("width", 0))
        h = float(room.get("height", 0))
    except (TypeError, ValueError):
        return False
    if not all(math.isfinite(v) for v in (x, y, w, h)):
        return False
    return w >= 1 and h >= 1


def _is_housegan_plan(plan: dict | None) -> bool:
    if not plan:
        return False
    if plan.get("used_housegan") is True:
        return True
    return plan.get("generator") == HOUSEGAN_GENERATOR


def _source_footprint(plan: dict) -> tuple[float, float] | None:
    w = plan.get("totalWidth")
    h = plan.get("totalHeight")
    if w is None:
        w = plan.get("house_w")
    if h is None:
        h = plan.get("house_h")
    try:
        wf = float(w)
        hf = float(h)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(wf) or not math.isfinite(hf) or wf <= 0 or hf <= 0:
        return None
    return wf, hf


def _scale_box(
    room: dict,
    conversion: HintConversion,
    envelope: Envelope,
) -> HintTuple | None:
    x = float(room["x"])
    y = float(room["y"])
    w = float(room["width"])
    h = float(room["height"])
    hw = max(1, int(round(w * conversion.scale_x)))
    hh = max(1, int(round(h * conversion.scale_y)))
    if hw > envelope.width or hh > envelope.depth:
        return None
    hx = int(round(x * conversion.scale_x))
    hy = int(round(y * conversion.scale_y))
    hx = min(max(0, hx), envelope.width - hw)
    hy = min(max(0, hy), envelope.depth - hh)
    if hx < 0 or hy < 0 or hx + hw > envelope.width or hy + hh > envelope.depth:
        return None
    return (hx, hy, hw, hh)


def hints_from_ai_candidate(
    moe_result: dict | None,
    program: RoomProgram,
    envelope: Envelope,
) -> HintAttempt:
    """Return one hint dict for every compete() strategy, or None if invalid/missing."""
    moe = moe_result or {}
    plans = list(moe.get("plans") or [])
    if not plans:
        return HintAttempt(None, False, "no_candidate_plans")

    plan = next((p for p in plans if _is_housegan_plan(p)), None)
    if plan is None:
        return HintAttempt(None, False, "not_housegan_candidate")

    rooms = list(plan.get("rooms") or [])
    if not rooms:
        return HintAttempt(None, False, "empty_housegan_rooms")

    prog_types = [spec.type for spec in program.rooms]
    cand_types = [r.get("type") for r in rooms]
    if any(t is None or t == "" for t in cand_types):
        return HintAttempt(None, False, "missing_room_type")
    if Counter(prog_types) != Counter(cand_types):
        return HintAttempt(
            None,
            False,
            "type_multiset_mismatch",
            extras={"program": prog_types, "candidate": cand_types},
        )

    if not all(_finite_positive_box(r) for r in rooms):
        return HintAttempt(None, False, "non_finite_or_non_positive_box")

    footprint = _source_footprint(plan)
    if footprint is None:
        return HintAttempt(None, False, "missing_source_footprint")
    src_w, src_h = footprint
    conversion = HintConversion(
        source_width=src_w,
        source_depth=src_h,
        envelope_width=envelope.width,
        envelope_depth=envelope.depth,
        scale_x=envelope.width / src_w,
        scale_y=envelope.depth / src_h,
    )

    unused: dict[str, list[dict]] = {}
    for r in rooms:
        unused.setdefault(str(r.get("type")), []).append(r)

    hints: dict[str, HintTuple] = {}
    for spec in program.rooms:
        bucket = unused.get(spec.type) or []
        if not bucket:
            return HintAttempt(None, False, "unmapped_program_room")
        src = bucket.pop(0)
        box = _scale_box(src, conversion, envelope)
        if box is None:
            return HintAttempt(None, False, "box_outside_envelope")
        hints[spec.id] = box

    leftover = [t for t, bucket in unused.items() if bucket]
    if leftover:
        return HintAttempt(None, False, "unmapped_candidate_rooms")

    if len(hints) != len(program.rooms):
        return HintAttempt(None, False, "incomplete_hint_map")

    print(
        f"[KIYUB AI HINTS] validated {len(hints)} rooms "
        f"scale=({conversion.scale_x:.4f},{conversion.scale_y:.4f}) "
        f"{src_w:.1f}x{src_h:.1f} -> {envelope.width}x{envelope.depth}ft"
    )
    return HintAttempt(hints, True, "validated_housegan", conversion)
