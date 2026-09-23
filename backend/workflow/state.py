"""Controlled project status transitions."""
from __future__ import annotations

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"IN_PROGRESS"}),
    "IN_PROGRESS": frozenset({"FOR_CHECKING"}),
    "FOR_CHECKING": frozenset({"FOR_REVISION", "APPROVED"}),
    "FOR_REVISION": frozenset({"IN_PROGRESS"}),
    "APPROVED": frozenset({"PUBLISHED"}),
    "PUBLISHED": frozenset(),
}

STATUSES = tuple(ALLOWED_TRANSITIONS)
STAGES = ("CLIENT_BRIEF", "AI_PROPOSAL", "ARCHITECT_DESIGN", "FINAL_DESIGN")
ROLES = ("CLIENT", "ARCHITECT", "MAIN_ADMIN", "IT_PERSONNEL")
SOURCE_TYPES = ("AI_GENERATED", "ARCHITECT_EDIT", "REVISION", "PUBLISHED")


class IllegalTransition(ValueError):
    pass


def can_transition(current: str, nxt: str) -> bool:
    return nxt in ALLOWED_TRANSITIONS.get(current, frozenset())


def apply_transition(current: str, nxt: str) -> str:
    if current == nxt:
        return current
    if not can_transition(current, nxt):
        raise IllegalTransition(f"Cannot change status {current} → {nxt}")
    return nxt
