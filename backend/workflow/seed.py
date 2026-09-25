"""Seed one user per role plus an idempotent architect–client demo relationship."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

from .auth import provision_user
from .generate import _stub_plan
from .models import AICandidate, Comment, DesignDocument, Invitation, Project, Revision, User
from .repositories.base import MemoryStore as Session
from .scene import floor_plan_to_scene_document

SEED_USERS = (
    ("client@kiyub.local", "clientpass", "CLIENT", True),
    ("architect@kiyub.local", "architectpass", "ARCHITECT", True),
    ("admin@kiyub.local", "adminpass", "MAIN_ADMIN", True),
    ("it@kiyub.local", "itpass", "IT_PERSONNEL", True),
)

SEED_CLIENT_EMAIL = "client@kiyub.local"
SEED_ARCHITECT_EMAIL = "architect@kiyub.local"
READY_PROJECT_NAME = "Seed Residence"
WAITING_PROJECT_NAME = "Awaiting Plan"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def seed_users(db: Session) -> list[User]:
    created: list[User] = []
    for email, password, role, approved in SEED_USERS:
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            user = provision_user(db, email, password, role, approved)
            created.append(user)
    db.commit()
    seed_collaboration(db)
    return created


def seed_collaboration(db: Session) -> None:
    architect = db.query(User).filter(User.email == SEED_ARCHITECT_EMAIL).one_or_none()
    client = db.query(User).filter(User.email == SEED_CLIENT_EMAIL).one_or_none()
    if architect is None or client is None:
        return
    ready = _ensure_project(db, architect, client, READY_PROJECT_NAME)
    _ensure_accepted_invitation(db, ready, architect, client)
    _ensure_stub_floor_plan(db, ready, client)
    _ensure_client_pin(db, ready, client)
    waiting = _ensure_project(db, architect, client, WAITING_PROJECT_NAME)
    _ensure_accepted_invitation(db, waiting, architect, client)
    db.commit()


def _ensure_project(db: Session, architect: User, client: User, name: str) -> Project:
    project = (
        db.query(Project)
        .filter(Project.architect_id == architect.id, Project.name == name)
        .one_or_none()
    )
    if project is None:
        project = Project(name=name, architect_id=architect.id, client_id=client.id, status="DRAFT")
        db.add(project)
        db.flush()
        db.add(DesignDocument(project_id=project.id, stage="CLIENT_BRIEF"))
        db.flush()
    elif project.client_id is None:
        project.client_id = client.id
    return project


def _ensure_accepted_invitation(db: Session, project: Project, architect: User, client: User) -> None:
    existing = (
        db.query(Invitation)
        .filter(
            Invitation.project_id == project.id,
            Invitation.email == client.email,
            Invitation.status == "ACCEPTED",
        )
        .one_or_none()
    )
    if existing:
        if not project.invitation_id:
            project.invitation_id = existing.id
            db.touch(project)
        return
    token = secrets.token_urlsafe(32)
    inv = Invitation(
        architect_id=architect.id,
        project_id=project.id,
        project_name=project.name,
        email=client.email,
        status="ACCEPTED",
        token_hash=_hash_invite_token(token),
        expires_at=_now() + timedelta(days=7),
        accepted_at=_now(),
        accepted_user_id=client.id,
    )
    db.add(inv)
    db.flush()
    db.commit()
    project.invitation_id = inv.id
    db.touch(project)


def _ensure_stub_floor_plan(db: Session, project: Project, client: User) -> None:
    if db.query(AICandidate).filter(AICandidate.project_id == project.id).first():
        return
    doc = db.query(DesignDocument).filter(DesignDocument.project_id == project.id).one_or_none()
    if doc is None:
        doc = DesignDocument(project_id=project.id, stage="AI_PROPOSAL")
        db.add(doc)
        db.flush()
    plan = _stub_plan(0)
    last = (
        db.query(Revision)
        .filter(Revision.design_document_id == doc.id)
        .order_by(Revision.version.desc())
        .first()
    )
    rev = Revision(
        design_document_id=doc.id,
        version=(last.version + 1) if last else 1,
        scene_document=json.dumps(floor_plan_to_scene_document(plan)),
        floor_plan=json.dumps(plan),
        created_by=client.id,
        source_type="AI_GENERATED",
    )
    db.add(rev)
    db.flush()
    db.add(AICandidate(project_id=project.id, revision_id=rev.id, selected_by_client=True))
    doc.stage = "AI_PROPOSAL"
    if project.status == "DRAFT":
        project.status = "IN_PROGRESS"
    db.flush()


def _ensure_client_pin(db: Session, project: Project, client: User) -> None:
    if db.query(Comment).filter(Comment.project_id == project.id, Comment.author_id == client.id).first():
        return
    db.add(
        Comment(
            project_id=project.id,
            author_id=client.id,
            body="Please move this door closer to the hallway.",
            object_id="living-0",
            x=9.0,
            y=7.0,
            stage="AI_PROPOSAL",
        )
    )
    db.flush()
