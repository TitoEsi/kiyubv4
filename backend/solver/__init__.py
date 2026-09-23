"""Architectural layout solver (OR-Tools CP-SAT). Prototype constraints, not building-code compliance.

Do not import pipeline/solver here — envelope and models must load without ortools.
"""

from .models import Envelope, Layout, SolveResult, ValidationIssue, ValidationReport

__all__ = [
    "Envelope",
    "Layout",
    "SolveResult",
    "ValidationIssue",
    "ValidationReport",
    "refine_generation",
    "solve",
]


def __getattr__(name: str):
    if name == "refine_generation":
        from .pipeline import refine_generation
        return refine_generation
    if name == "solve":
        from .solver import solve
        return solve
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
