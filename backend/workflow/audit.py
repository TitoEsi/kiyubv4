"""Audit + in-app notifications."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from .models import AuditEvent, Notification, Project, User


def log_event(
    db: Session,
    *,
    event_type: str,
    actor_id: str | None = None,
    project_id: str | None = None,
    revision_id: str | None = None,
    target: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    ev = AuditEvent(
        actor_id=actor_id,
        project_id=project_id,
        revision_id=revision_id,
        event_type=event_type,
        target=target,
        metadata_json=json.dumps(metadata or {}),
    )
    db.add(ev)
    return ev


def notify(db: Session, user_id: str | None, kind: str, message: str, project_id: str | None = None) -> None:
    if not user_id:
        return
    db.add(Notification(user_id=user_id, kind=kind, message=message, project_id=project_id))


def notify_project_roles(db: Session, project: Project, kind: str, message: str, skip_id: str | None = None) -> None:
    for uid in (project.client_id, project.architect_id):
        if uid and uid != skip_id:
            notify(db, uid, kind, message, project.id)


def notify_it(db: Session, kind: str, message: str, project_id: str | None = None) -> None:
    for user in db.query(User).filter(User.role == "IT_PERSONNEL").all():
        notify(db, user.id, kind, message, project_id)
