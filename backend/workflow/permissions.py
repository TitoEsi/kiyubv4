"""Centralized workflow permissions. Frontend mirrors these names; API is the security boundary."""
from __future__ import annotations

from dataclasses import dataclass

from .state import ROLES

CLIENT = "CLIENT"
ARCHITECT = "ARCHITECT"
MAIN_ADMIN = "MAIN_ADMIN"
IT_PERSONNEL = "IT_PERSONNEL"


@dataclass(frozen=True)
class Actor:
    id: str
    role: str
    approved: bool = True


def _assigned(actor: Actor, project: dict) -> bool:
    if actor.role == CLIENT:
        return project.get("client_id") == actor.id
    if actor.role == ARCHITECT:
        return project.get("architect_id") == actor.id
    if actor.role in (MAIN_ADMIN, IT_PERSONNEL):
        return True
    return False


def can_view_project(actor: Actor, project: dict) -> bool:
    if actor.role not in ROLES:
        return False
    if actor.role in (MAIN_ADMIN, IT_PERSONNEL):
        return True
    return _assigned(actor, project)


def can_edit_design(actor: Actor, project: dict) -> bool:
    if actor.role != ARCHITECT or not actor.approved:
        return False
    if project.get("status") == "PUBLISHED":
        return False
    return project.get("architect_id") == actor.id


def can_generate(actor: Actor, project: dict) -> bool:
    if project.get("status") == "PUBLISHED":
        return False
    if actor.role == CLIENT:
        return project.get("client_id") == actor.id
    if actor.role == ARCHITECT and actor.approved:
        if project.get("architect_id") != actor.id:
            return False
        # First generation is the client's; architects may generate only after a plan exists.
        if project.get("has_floor_plan") is False:
            return False
        return True
    return False


def can_open_architect_canvas(actor: Actor, project: dict) -> bool:
    if actor.role != ARCHITECT or not actor.approved:
        return False
    if project.get("architect_id") != actor.id:
        return False
    return bool(project.get("has_floor_plan"))


def can_comment(actor: Actor, project: dict) -> bool:
    if actor.role in (CLIENT, ARCHITECT):
        return _assigned(actor, project)
    return False


def can_mutate_comment(actor: Actor, project: dict, author_id: str) -> bool:
    if actor.id == author_id:
        return can_comment(actor, project)
    return actor.role == ARCHITECT and actor.approved and project.get("architect_id") == actor.id


def can_select_candidate(actor: Actor, project: dict) -> bool:
    return actor.role == CLIENT and project.get("client_id") == actor.id and project.get("status") != "PUBLISHED"


def can_request_revision(actor: Actor, project: dict) -> bool:
    return (
        actor.role == CLIENT
        and project.get("client_id") == actor.id
        and project.get("status") == "FOR_CHECKING"
    )


def can_approve(actor: Actor, project: dict) -> bool:
    if project.get("status") == "PUBLISHED":
        return False
    if actor.role == CLIENT:
        return project.get("client_id") == actor.id and project.get("status") == "FOR_CHECKING"
    if actor.role == ARCHITECT and actor.approved:
        return project.get("architect_id") == actor.id and project.get("status") == "FOR_CHECKING"
    return False


def can_publish(actor: Actor, project: dict) -> bool:
    return (
        actor.role == ARCHITECT
        and actor.approved
        and project.get("architect_id") == actor.id
        and project.get("status") == "APPROVED"
    )


def can_manage_accounts(actor: Actor) -> bool:
    return actor.role in (MAIN_ADMIN, IT_PERSONNEL)


def can_view_audit(actor: Actor) -> bool:
    return actor.role in (MAIN_ADMIN, IT_PERSONNEL, ARCHITECT)


def can_update_brief(actor: Actor, project: dict) -> bool:
    if project.get("status") == "PUBLISHED":
        return False
    if actor.role == CLIENT:
        return project.get("client_id") == actor.id
    if actor.role == ARCHITECT:
        return project.get("architect_id") == actor.id
    return False


def can_accept_candidate(actor: Actor, project: dict) -> bool:
    return can_edit_design(actor, project)


def can_create_project(actor: Actor) -> bool:
    return actor.role in (ARCHITECT, MAIN_ADMIN) and (actor.role != ARCHITECT or actor.approved)


def can_submit_review(actor: Actor, project: dict) -> bool:
    if project.get("status") != "IN_PROGRESS":
        return False
    if actor.role == ARCHITECT and actor.approved and project.get("architect_id") == actor.id:
        return True
    if actor.role == CLIENT and project.get("client_id") == actor.id and project.get("has_floor_plan"):
        return True
    return False


def can_view_inquiries(actor: Actor) -> bool:
    return actor.role in (MAIN_ADMIN, IT_PERSONNEL)


# Names mirrored by frontend/src/workflow/permissions.ts
canViewProject = can_view_project
canEditDesign = can_edit_design
canGenerate = can_generate
canComment = can_comment
canSelectCandidate = can_select_candidate
canRequestRevision = can_request_revision
canApprove = can_approve
canPublish = can_publish
canManageAccounts = can_manage_accounts
canViewAudit = can_view_audit
canOpenArchitectCanvas = can_open_architect_canvas
canSubmitReview = can_submit_review
canViewInquiries = can_view_inquiries
