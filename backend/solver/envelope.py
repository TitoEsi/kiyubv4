"""
Buildable envelope from questionnaire lot dimensions.

Placeholder 5 ft setbacks are conceptual only. They are NOT Philippine
building-code setbacks. This is the single lot-envelope implementation
shared by MOE placement and the OR-Tools solver.
"""

from __future__ import annotations

import math

METERS_TO_FEET = 3.28084
SETBACK_SIDE_FT = 5.0
SETBACK_FRONT_FT = 5.0
SETBACK_REAR_FT = 5.0
UNSUPPORTED_LOT_SHAPES = ("l_shape", "irregular")


class LotConstraintError(ValueError):
    """Raised when a lot cannot host the requested floor plan."""

    def __init__(self, message: str, detail: str, field: str = "lotWidth"):
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.field = field

    def as_issue(self) -> dict:
        return {
            "field": self.field,
            "severity": "error",
            "message": self.message,
            "detail": self.detail,
        }


def compute_buildable_envelope(constraints: dict) -> dict:
    """
    Convert questionnaire lot dimensions (meters) into a rectangular
    buildable envelope in feet.
    """
    lot_shape = constraints.get("lotShape", "rectangle") or "rectangle"
    try:
        lot_width_m = float(constraints.get("lotWidth", 20.0))
        lot_depth_m = float(constraints.get("lotDepth", 30.0))
    except (TypeError, ValueError) as exc:
        raise LotConstraintError(
            "Lot dimensions must be numeric.",
            "Enter lot width and depth as numbers greater than zero.",
            "lotWidth",
        ) from exc

    if lot_shape in UNSUPPORTED_LOT_SHAPES:
        label = "L-shaped" if lot_shape == "l_shape" else "irregular"
        raise LotConstraintError(
            f"{label.capitalize()} lots are not yet supported.",
            "True L-shaped and irregular lot geometry is not implemented. "
            "Choose rectangle or square for this phase.",
            "lotShape",
        )

    if lot_width_m <= 0:
        raise LotConstraintError(
            "Lot width must be greater than zero.",
            "Enter a lot width greater than 0 meters.",
            "lotWidth",
        )
    if lot_depth_m <= 0:
        raise LotConstraintError(
            "Lot depth must be greater than zero.",
            "Enter a lot depth greater than 0 meters.",
            "lotDepth",
        )

    lot_width_ft = lot_width_m * METERS_TO_FEET
    lot_depth_ft = lot_depth_m * METERS_TO_FEET

    if lot_shape == "square":
        side = min(lot_width_ft, lot_depth_ft)
        lot_width_ft = lot_depth_ft = side

    buildable_width = lot_width_ft - (SETBACK_SIDE_FT * 2)
    buildable_depth = lot_depth_ft - SETBACK_FRONT_FT - SETBACK_REAR_FT

    if buildable_width <= 0 or buildable_depth <= 0:
        raise LotConstraintError(
            "Lot is too small after setbacks.",
            "Placeholder 5 ft front, rear, and side setbacks leave no buildable "
            "area. Increase lot width and depth. These setbacks are conceptual "
            "only, not Philippine building-code values.",
            "lotWidth",
        )

    max_w = math.floor(buildable_width / 2.0) * 2
    max_h = math.floor(buildable_depth / 2.0) * 2
    if max_w < 2 or max_h < 2:
        raise LotConstraintError(
            "Buildable envelope is too small for generation.",
            f"After setbacks the envelope is {buildable_width:.1f} ft × "
            f"{buildable_depth:.1f} ft, which cannot host a floor plan. "
            "Increase the lot size.",
            "lotWidth",
        )

    return {
        "lot_shape": lot_shape,
        "lot_width_ft": lot_width_ft,
        "lot_depth_ft": lot_depth_ft,
        "buildable_width": buildable_width,
        "buildable_depth": buildable_depth,
        "max_w": float(max_w),
        "max_h": float(max_h),
        "buildable_area": buildable_width * buildable_depth,
    }
