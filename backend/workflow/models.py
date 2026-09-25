"""Workflow entities. Persistence is MemoryStore or Supabase, not SQLAlchemy."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from typing import Any


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FieldRef:
    def __init__(self, model: type, name: str):
        self.model = model
        self.name = name

    def __eq__(self, other: Any):
        return ("eq", self.model, self.name, other)

    def __ne__(self, other: Any):
        return ("ne", self.model, self.name, other)

    def in_(self, values: Any):
        return ("in", self.model, self.name, values)

    def isnot(self, other: Any):
        return ("isnot", self.model, self.name, other)

    def desc(self):
        return ("desc", self.model, self.name)

    def asc(self):
        return ("asc", self.model, self.name)


def entity(cls: type) -> type:
    cls = dataclass(cls)
    for f in fields(cls):
        setattr(cls, f.name, FieldRef(cls, f.name))
    return cls


@entity
class User:
    id: str = field(default_factory=_uuid)
    email: str = ""
    # MemoryStore/test login only. Supabase Auth owns passwords; never written to profiles.
    password_hash: str = ""
    role: str = "CLIENT"
    approved: bool = True
    suspended: bool = False
    deleted_at: datetime | None = None
    full_name: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)


@entity
class Project:
    id: str = field(default_factory=_uuid)
    name: str = ""
    client_id: str | None = None
    architect_id: str | None = None
    invitation_id: str | None = None
    status: str = "DRAFT"
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)


@entity
class ClientBrief:
    id: str = field(default_factory=_uuid)
    project_id: str = ""
    questionnaire: str = "{}"
    specification: str = "{}"
    updated_at: datetime = field(default_factory=_now)


@entity
class SiteConstraint:
    id: str = field(default_factory=_uuid)
    project_id: str = ""
    lot_shape: str | None = None
    lot_width: float | None = None
    lot_depth: float | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)


@entity
class DesignDocument:
    id: str = field(default_factory=_uuid)
    project_id: str = ""
    stage: str = "CLIENT_BRIEF"
    current_revision_id: str | None = None
    working_scene_document: str | None = None
    working_updated_at: datetime | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)


@entity
class Revision:
    id: str = field(default_factory=_uuid)
    design_document_id: str = ""
    version: int = 1
    source_revision_id: str | None = None
    scene_document: str = "{}"
    floor_plan: str = "{}"
    created_by: str = ""
    source_type: str = "AI_GENERATED"
    created_at: datetime = field(default_factory=_now)


@entity
class AICandidate:
    id: str = field(default_factory=_uuid)
    project_id: str = ""
    generation_job_id: str | None = None
    revision_id: str = ""
    selected_by_client: bool = False
    created_at: datetime = field(default_factory=_now)


@entity
class GenerationJob:
    id: str = field(default_factory=_uuid)
    project_id: str = ""
    requested_by: str = ""
    source_revision_id: str | None = None
    source_brief_id: str | None = None
    specification: str = "{}"
    status: str = "PENDING"
    result_candidate_id: str | None = None
    created_at: datetime = field(default_factory=_now)
    completed_at: datetime | None = None


@entity
class Comment:
    id: str = field(default_factory=_uuid)
    project_id: str = ""
    stage: str | None = None
    revision_id: str | None = None
    author_id: str = ""
    object_id: str | None = None
    body: str = ""
    x: float | None = None
    y: float | None = None
    created_at: datetime = field(default_factory=_now)


@entity
class Approval:
    id: str = field(default_factory=_uuid)
    project_id: str = ""
    revision_id: str | None = None
    actor_id: str = ""
    kind: str = ""
    created_at: datetime = field(default_factory=_now)


@entity
class AuditEvent:
    id: str = field(default_factory=_uuid)
    actor_id: str | None = None
    project_id: str | None = None
    revision_id: str | None = None
    event_type: str = ""
    target: str | None = None
    metadata_json: str = "{}"
    created_at: datetime = field(default_factory=_now)


@entity
class Notification:
    id: str = field(default_factory=_uuid)
    user_id: str = ""
    project_id: str | None = None
    kind: str = ""
    message: str = ""
    read: bool = False
    created_at: datetime = field(default_factory=_now)


@entity
class Invitation:
    id: str = field(default_factory=_uuid)
    architect_id: str = ""
    project_id: str | None = None
    project_name: str | None = None
    email: str = ""
    status: str = "PENDING"
    token_hash: str = ""
    expires_at: datetime = field(default_factory=_now)
    created_at: datetime = field(default_factory=_now)
    accepted_at: datetime | None = None
    accepted_user_id: str | None = None
    auth_user_id: str | None = None


@entity
class ArchitectApplication:
    id: str = field(default_factory=_uuid)
    email: str = ""
    full_name: str = ""
    information: str | None = None
    status: str = "PENDING_APPROVAL"
    invited_by: str = ""
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    token_hash: str | None = None
    expires_at: datetime | None = None
    accepted_user_id: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)


@entity
class Inquiry:
    id: str = field(default_factory=_uuid)
    name: str = ""
    email: str = ""
    message: str = ""
    created_at: datetime = field(default_factory=_now)


TABLES = {
    User: "profiles",
    Project: "projects",
    ClientBrief: "client_briefs",
    SiteConstraint: "site_constraints",
    DesignDocument: "design_documents",
    Revision: "revisions",
    AICandidate: "ai_candidates",
    GenerationJob: "generation_jobs",
    Comment: "comments",
    Approval: "approvals",
    AuditEvent: "audit_events",
    Notification: "notifications",
    Invitation: "invitations",
    Inquiry: "inquiries",
    ArchitectApplication: "architect_applications",
}
