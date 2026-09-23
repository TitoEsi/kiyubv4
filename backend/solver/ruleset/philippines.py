"""Philippine planning notes. Unverified NBC items stay UNKNOWN.

PHILIPPINE_RESIDENTIAL_DEFAULTS is a planning profile, not a code certificate.
Never sets irc_compliant true.
"""
from __future__ import annotations

from ..models import Layout, RoomProgram
from ..planning_profile import PHILIPPINE_RESIDENTIAL_DEFAULTS
from .result import RuleResult


def evaluate(layout: Layout, program: RoomProgram) -> list[RuleResult]:
    results = [
        RuleResult(
            "nbc_setbacks", "UNKNOWN",
            "Buildable envelope uses placeholder 5 ft setbacks, not verified NBC setbacks.",
            source="envelope.py SETBACK_* placeholders",
            module="philippines",
        ),
        RuleResult(
            "nbc_room_minima", "UNKNOWN",
            "ROOM_RULES sizes are packing placeholders, not Philippine NBC values.",
            source="room_rules.py",
            module="philippines",
        ),
        RuleResult(
            "nbc_light_ventilation", "UNKNOWN",
            "Window placement is a daylight heuristic, not NBC light-and-ventilation compliance.",
            source="openings.py",
            module="philippines",
        ),
        RuleResult(
            "irc_compliant", "UNKNOWN",
            "irc_compliant remains false. Heuristics do not establish IRC or NBC compliance.",
            source="planning_profile.PHILIPPINE_RESIDENTIAL_DEFAULTS",
            module="philippines",
        ),
    ]
    if PHILIPPINE_RESIDENTIAL_DEFAULTS.get("irc_compliant"):
        results.append(RuleResult(
            "irc_flag_misuse", "FAIL",
            "Planning profile must not claim irc_compliant from heuristics.",
            source="planning_profile.py",
            module="philippines",
        ))
    _ = layout, program
    return results
