"""Persist the workflow scene summary alongside FloorPlan.

All geometry is meters (``"units": "metric"``). Input plans are normalized first, so a
feet-native engine plan is converted once at this boundary.
"""
from __future__ import annotations

from typing import Any

from generation_units import METRIC, normalize_floor_plan


def floor_plan_to_scene_document(plan: dict[str, Any] | None) -> dict[str, Any]:
    plan = normalize_floor_plan(plan or {}) or {}
    rooms = plan.get("rooms") or []
    walls = plan.get("walls") or []
    doors = plan.get("doors") or []
    windows = plan.get("windows") or []
    stairs = plan.get("stairs") or []
    metadata = plan.get("metadata") or {}
    envelope = plan.get("envelope") or {}
    lot = envelope.get("lot") or {}
    width = float(envelope.get("width") or lot.get("width") or plan.get("totalWidth") or 0)
    depth = float(envelope.get("depth") or lot.get("depth") or plan.get("totalHeight") or 0)
    return {
        "schemaVersion": "2.0",
        "source": "kiyub-workflow",
        "planId": plan.get("id"),
        "units": METRIC,
        "envelope": {"width": width, "depth": depth},
        "rooms": [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "type": r.get("type"),
                "x": r.get("x"),
                "y": r.get("y"),
                "width": r.get("width"),
                "height": r.get("height"),
            }
            for r in rooms
        ],
        "walls": walls,
        "openings": {
            "doors": doors,
            "windows": windows,
        },
        "stairs": stairs,
        "metadata": metadata,
        "engine": {
            "source": metadata.get("source"),
            "generator": metadata.get("generator"),
        },
    }
