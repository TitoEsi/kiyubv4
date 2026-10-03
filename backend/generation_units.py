"""KIYUB unit boundary.

Canonical rule: outside the generation engine, every architectural length is meters and
every area is square meters. Stored and API FloorPlan / scene documents are meters and
tagged ``"units": "metric"``.

The generation engine (solver/, moe/, HouseGAN, room rules, OR-Tools integer-foot grid,
scoring.py, the chat prompt and its plan edits) is feet-native. Those modules keep their
feet constants and must only be reached through this adapter:

    meters  --to_feet-->  feet-native engine  --to_metric-->  meters

``solver/envelope.py`` also converts the meters lot into the feet envelope at the engine
entry; it is part of the same boundary.

Legacy data (FloorPlans without ``units``, scene documents with ``"units": "ft"``, comment
pins without ``coord_units``) is feet and is normalized here on read and on write.
"""
from __future__ import annotations

import copy
from typing import Any, Callable

M_PER_FT = 0.3048
METRIC = "metric"
LEGACY_FEET = "ft"

UNIT_METERS = {"m": 1.0, "ft": M_PER_FT, "cm": 0.01, "mm": 0.001, "in": 0.0254}
UNIT_DECIMALS = {"m": 2, "ft": 2, "cm": 1, "mm": 0, "in": 1}
AREA_DECIMALS = {"m": 2, "ft": 2, "cm": 0, "mm": 0, "in": 0}


def ft_to_m(v: float) -> float:
    return float(v) * M_PER_FT


def m_to_ft(v: float) -> float:
    return float(v) / M_PER_FT


def ft2_to_m2(v: float) -> float:
    return float(v) * M_PER_FT * M_PER_FT


def m2_to_ft2(v: float) -> float:
    return float(v) / (M_PER_FT * M_PER_FT)


def _round(value: float, decimals: int) -> str:
    rounded = round(float(value), decimals)
    if rounded == 0:
        rounded = 0.0
    text = f"{rounded:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def format_measurement(meters: float, unit: str = "m") -> str:
    unit = unit if unit in UNIT_METERS else "m"
    return f"{_round(meters / UNIT_METERS[unit], UNIT_DECIMALS[unit])} {unit}"


def format_dimensions(width_m: float, depth_m: float, unit: str = "m") -> str:
    unit = unit if unit in UNIT_METERS else "m"
    f = UNIT_METERS[unit]
    d = UNIT_DECIMALS[unit]
    return f"{_round(width_m / f, d)} × {_round(depth_m / f, d)} {unit}"


def format_area(square_meters: float, unit: str = "m") -> str:
    unit = unit if unit in UNIT_METERS else "m"
    f = UNIT_METERS[unit]
    return f"{_round(square_meters / (f * f), AREA_DECIMALS[unit])} {unit}²"


# ── FloorPlan geometry walk ──────────────────────────────────────────────────

_PT = ("x", "y")
_SEG = ("x1", "y1", "x2", "y2")
_RECT = ("x", "y", "width", "height")


def _scale_keys(obj: Any, keys: tuple[str, ...], fn: Callable[[float], float]) -> None:
    if not isinstance(obj, dict):
        return
    for k in keys:
        v = obj.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            obj[k] = fn(v)


def _convert_plan(plan: dict, fn: Callable[[float], float]) -> dict:
    out = copy.deepcopy(plan)
    _scale_keys(out, ("totalWidth", "totalHeight", "ceilingHeight"), fn)
    _scale_keys(out.get("envelope"), ("width", "depth"), fn)
    for room in out.get("rooms") or []:
        _scale_keys(room, _RECT, fn)
        fp = room.get("footprint") if isinstance(room, dict) else None
        if isinstance(fp, dict):
            for part in fp.get("parts") or []:
                _scale_keys(part, _RECT, fn)
            _scale_keys(fp.get("centroid"), _PT, fn)
            for s in fp.get("boundary") or []:
                _scale_keys(s, _SEG, fn)
    for door in out.get("doors") or []:
        _scale_keys(door, _PT, fn)
    for wall in out.get("walls") or []:
        _scale_keys(wall, _SEG, fn)
    for op in out.get("openings") or []:
        _scale_keys(op, ("x", "y", "width", "height", "sillHeight"), fn)
    for item in out.get("furniture") or []:
        _scale_keys(item, ("x", "y", "width", "depth"), fn)
    return out


def is_metric(data: Any) -> bool:
    return isinstance(data, dict) and data.get("units") == METRIC


def floor_plan_to_metric(plan: dict) -> dict:
    """Engine (feet) FloorPlan -> canonical meters FloorPlan."""
    if not isinstance(plan, dict) or not plan or is_metric(plan):
        return plan
    out = _convert_plan(plan, ft_to_m)
    out["units"] = METRIC
    return out


def floor_plan_to_feet(plan: dict) -> dict:
    """Canonical meters FloorPlan -> feet, only for feet-native engine consumers."""
    plan = normalize_floor_plan(plan)
    if not isinstance(plan, dict) or not plan:
        return plan
    out = _convert_plan(plan, m_to_ft)
    out.pop("units", None)
    return out


def normalize_floor_plan(plan: Any) -> Any:
    """Legacy plans have no ``units`` key and are feet. Idempotent for metric plans."""
    if not isinstance(plan, dict) or not plan or is_metric(plan):
        return plan
    return floor_plan_to_metric(plan)


def is_backend_scene_document(doc: Any) -> bool:
    return isinstance(doc, dict) and "schemaVersion" in doc and "version" not in doc


def normalize_scene_document(doc: Any) -> Any:
    """Backend workflow scene docs tagged ``"units": "ft"`` -> meters.

    Only the feet geometry is converted; ``site`` was always written in meters.
    Frontend SceneDocument v2 (``"units": "metric"``) is returned unchanged.
    """
    if not isinstance(doc, dict) or doc.get("units") != LEGACY_FEET:
        return doc
    out = copy.deepcopy(doc)
    for room in out.get("rooms") or []:
        _scale_keys(room, _RECT, ft_to_m)
        fp = room.get("footprint") if isinstance(room, dict) else None
        if isinstance(fp, dict):
            for part in fp.get("parts") or []:
                _scale_keys(part, _RECT, ft_to_m)
    for wall in out.get("walls") or []:
        _scale_keys(wall, _SEG, ft_to_m)
    openings = out.get("openings")
    if isinstance(openings, dict):
        for key in ("doors", "windows"):
            for op in openings.get(key) or []:
                _scale_keys(op, ("x", "y", "width", "height", "sillHeight"), ft_to_m)
    env = out.get("envelope")
    if isinstance(env, dict):
        _scale_keys(env, ("width", "depth"), ft_to_m)
    out["units"] = METRIC
    return out


def normalize_comment_coords(x: float | None, y: float | None, coord_units: str | None) -> tuple[float | None, float | None]:
    if coord_units == METRIC:
        return x, y
    return (ft_to_m(x) if x is not None else None, ft_to_m(y) if y is not None else None)


def _normalize_area_section(section: Any) -> Any:
    if not isinstance(section, dict) or "livingAreaSqft" not in section:
        return section
    out = dict(section)
    m2 = living_area_m2(out)
    out.pop("livingAreaSqft", None)
    if m2 is not None:
        out["livingAreaM2"] = m2
    return out


def normalize_questionnaire(questionnaire: Any) -> Any:
    """Legacy ``house.livingAreaSqft`` (ft²) -> ``house.livingAreaM2`` (m²)."""
    if not isinstance(questionnaire, dict):
        return questionnaire
    out = dict(questionnaire)
    if "house" in out:
        out["house"] = _normalize_area_section(out["house"])
    return out


def normalize_specification(specification: Any) -> Any:
    """Legacy ``building.livingAreaSqft`` (ft²) -> ``building.livingAreaM2`` (m²)."""
    if not isinstance(specification, dict):
        return specification
    out = dict(specification)
    if "building" in out:
        out["building"] = _normalize_area_section(out["building"])
    return out


def living_area_m2(source: dict | None) -> float | None:
    """Reads canonical ``livingAreaM2`` or converts a legacy ``livingAreaSqft``."""
    if not isinstance(source, dict):
        return None
    m2 = source.get("livingAreaM2")
    if isinstance(m2, (int, float)) and m2 > 0:
        return float(m2)
    sqft = source.get("livingAreaSqft")
    if isinstance(sqft, (int, float)) and sqft > 0:
        return ft2_to_m2(sqft)
    return None
