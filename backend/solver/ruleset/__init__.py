"""Modular architectural ruleset. PASS / FAIL / WARNING / UNKNOWN.

Unverified code claims stay UNKNOWN. Never sets irc_compliant true.
Not professional architectural approval. Not NBC or IRC certification.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..models import Layout, RoomProgram
from .result import RuleResult, RuleStatus

__all__ = ["ArchitecturalRuleSet", "RuleResult", "RuleStatus", "default_ruleset"]


@dataclass
class ArchitecturalRuleSet:
    name: str
    modules: list = field(default_factory=list)

    def evaluate(self, layout: Layout, program: RoomProgram) -> list[RuleResult]:
        out: list[RuleResult] = []
        for mod in self.modules:
            out.extend(mod.evaluate(layout, program))
        return out

    def as_dict(self, results: list[RuleResult]) -> dict:
        counts = {"PASS": 0, "FAIL": 0, "WARNING": 0, "UNKNOWN": 0}
        for r in results:
            counts[r.status] = counts.get(r.status, 0) + 1
        return {
            "name": self.name,
            "irc_compliant": False,
            "counts": counts,
            "results": [r.as_dict() for r in results],
            "note": (
                "Modular planning checks. UNKNOWN means unverified. "
                "Not NBC/IRC legal compliance."
            ),
        }


def default_ruleset() -> ArchitecturalRuleSet:
    from . import common, philippines, residential
    return ArchitecturalRuleSet(
        name="kiyub_phase22_residential",
        modules=[common, residential, philippines],
    )
