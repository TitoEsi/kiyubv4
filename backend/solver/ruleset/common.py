"""Geometry validity checks. Engine constraints, not building code."""
from __future__ import annotations

from ..models import Layout, RoomProgram
from ..validator import validate
from .result import RuleResult


def evaluate(layout: Layout, program: RoomProgram) -> list[RuleResult]:
    report = validate(layout, program)
    results: list[RuleResult] = []
    if report.valid:
        results.append(RuleResult(
            "engine_validity", "PASS",
            "Layout passes KIYUB hard geometry/relationship checks.",
            source="validator.py",
            module="common",
        ))
    else:
        for err in report.errors:
            results.append(RuleResult(
                err.type, "FAIL", err.message,
                source="validator.py",
                module="common",
            ))
    for warn in report.warnings:
        results.append(RuleResult(
            warn.type, "WARNING", warn.message,
            source="validator.py",
            module="common",
        ))
    return results
