"""Centralized workflow permissions. Frontend mirrors these names; API is the security boundary."""
from __future__ import annotations

from dataclasses import dataclass

from .state import ROLES

CLIENT = "CLIENT"
ARCHITECT = "ARCHITECT"
ADMIN = "ADMIN"


@dataclass(frozen=True)
class Actor:
    id: str
    role: str
    approved: bool = True
    suspended: bool = False


def is_admin(actor: Actor) -> bool:
    return actor.role == ADMIN


def _assigned(actor: Actor, project: dict) -> bool:
    if actor.role == CLIENT:
        return project.get("client_id") == actor.id
    if actor.role == ARCHITECT:
        return project.get("architect_id") == actor.id
    if is_admin(actor):
        return True
    return False


def can_view_project(actor: Actor, project: dict) -> bool:
    if actor.role not in ROLES:
        return False
    if is_admin(actor):
        return True
    return _assigned(actor, project)


def can_edit_design(actor: Actor, project: dict) -> bool:
    if actor.role != ARCHITECT or not actor.approved:
        return False
    if project.get("status") == "PUBLISHED":
        return False
    return project.get("architect_id") == actor.id


def can_view_drafts(actor: Actor, project: dict) -> bool:
    """Read access to unsubmitted design state. Admin may inspect but never write."""
    return can_edit_design(actor, project) or is_admin(actor)


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


def can_resolve_comment(actor: Actor, project: dict) -> bool:
    return actor.role == ARCHITECT and actor.approved and project.get("architect_id") == actor.id


def can_restore_version(actor: Actor, project: dict) -> bool:
    return can_edit_design(actor, project) and project.get("status") in ("IN_PROGRESS", "FOR_CHECKING", "FOR_REVISION")


def can_select_candidate(actor: Actor, project: dict) -> bool:
    return actor.role == CLIENT and project.get("client_id") == actor.id and project.get("status") != "PUBLISHED"


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
    return is_admin(actor)


def can_suspend_accounts(actor: Actor) -> bool:
    return is_admin(actor)


def can_delete_accounts(actor: Actor) -> bool:
    return is_admin(actor)


def can_assign_projects(actor: Actor) -> bool:
    return is_admin(actor)


def can_review_architect_applications(actor: Actor) -> bool:
    return is_admin(actor)


def can_use_studio(actor: Actor) -> bool:
    return is_admin(actor)


def can_view_audit(actor: Actor) -> bool:
    return actor.role in ROLES


def can_update_brief(actor: Actor, project: dict) -> bool:
    if project.get("status") == "PUBLISHED":
        return False
    if actor.role == CLIENT:
        return project.get("client_id") == actor.id
    if actor.role == ARCHITECT:
        return project.get("architect_id") == actor.id
    return False


def can_create_project(actor: Actor) -> bool:
    return is_admin(actor)


def can_submit_review(actor: Actor, project: dict) -> bool:
    if actor.role == ARCHITECT and actor.approved and project.get("architect_id") == actor.id:
        return project.get("status") in ("IN_PROGRESS", "FOR_CHECKING")
    if project.get("status") != "IN_PROGRESS":
        return False
    if actor.role == CLIENT and project.get("client_id") == actor.id and project.get("has_floor_plan"):
        return True
    return False


def can_view_inquiries(actor: Actor) -> bool:
    return is_admin(actor)


# Names mirrored by frontend/src/workflow/permissions.ts
canViewProject = can_view_project
canEditDesign = can_edit_design
canViewDrafts = can_view_drafts
canGenerate = can_generate
canComment = can_comment
canSelectCandidate = can_select_candidate
canApprove = can_approve
canPublish = can_publish
canManageAccounts = can_manage_accounts
canViewAudit = can_view_audit
canOpenArchitectCanvas = can_open_architect_canvas
canSubmitReview = can_submit_review
canViewInquiries = can_view_inquiries
