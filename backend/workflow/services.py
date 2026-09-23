"""Project workflow services. Generation results become candidates; never overwrite architect revisions."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, object_session

from . import permissions as perm
from .audit import log_event, notify, notify_it, notify_project_roles
from .generate import brief_to_constraints, run_generation
from .models import (
    AICandidate,
    Approval,
    AuditEvent,
    ClientBrief,
    Comment,
    DesignDocument,
    GenerationJob,
    Inquiry,
    Invitation,
    Notification,
    Project,
    Revision,
    User,
)
from .permissions import Actor
from .scene import floor_plan_to_scene_document
from .state import IllegalTransition, apply_transition

INVITE_TTL_DAYS = 7
CANVAS_LOCKED_DETAIL = "Waiting for the client to generate a floor plan"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _loads(raw: str | None) -> Any:
    if not raw:
        return {}
    return json.loads(raw)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def floor_plan_has_geometry(plan: Any) -> bool:
    if not isinstance(plan, dict):
        return False
    rooms = plan.get("rooms")
    return isinstance(rooms, list) and len(rooms) > 0


def has_generated_floor_plan(db: Session, project: Project) -> bool:
    if db.query(AICandidate.id).filter(AICandidate.project_id == project.id).first():
        return True
    doc = db.query(DesignDocument).filter(DesignDocument.project_id == project.id).one_or_none()
    if not doc or not doc.current_revision_id:
        return False
    rev = db.get(Revision, doc.current_revision_id)
    if rev is None:
        return False
    return floor_plan_has_geometry(_loads(rev.floor_plan))


def generation_status_for(db: Session, project: Project) -> str:
    job = (
        db.query(GenerationJob)
        .filter(GenerationJob.project_id == project.id)
        .order_by(GenerationJob.created_at.desc())
        .first()
    )
    if job is None:
        return "idle"
    st = (job.status or "").upper()
    if st in ("PENDING", "RUNNING"):
        return "running"
    if st == "FAILED":
        return "failed"
    if st == "COMPLETED":
        return "completed"
    return "idle"


def project_as_dict(p: Project, db: Session | None = None) -> dict:
    data = {
        "id": p.id,
        "name": p.name,
        "client_id": p.client_id,
        "architect_id": p.architect_id,
        "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
    if db is not None:
        client = db.get(User, p.client_id) if p.client_id else None
        data["client_email"] = client.email if client else None
        data["has_floor_plan"] = has_generated_floor_plan(db, p)
        data["generation_status"] = generation_status_for(db, p)
        data["client_comment_count"] = client_comment_count(db, p.id)
    return data


def client_comment_count(db: Session, project_id: str) -> int:
    return (
        db.query(Comment)
        .join(User, User.id == Comment.author_id)
        .filter(Comment.project_id == project_id, User.role == "CLIENT")
        .count()
    )


def _require_architect_canvas(db: Session, actor: Actor, project: Project) -> None:
    payload = project_as_dict(project, db)
    if actor.role == "ARCHITECT" and not perm.can_open_architect_canvas(actor, payload):
        raise HTTPException(status.HTTP_403_FORBIDDEN, CANVAS_LOCKED_DETAIL)


def _require_view(db: Session, actor: Actor, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    if not perm.can_view_project(actor, project_as_dict(project)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view this project")
    return project


def _document(db: Session, project: Project) -> DesignDocument:
    doc = db.query(DesignDocument).filter(DesignDocument.project_id == project.id).one_or_none()
    if doc is None:
        doc = DesignDocument(project_id=project.id, stage="CLIENT_BRIEF")
        db.add(doc)
        db.flush()
    return doc


def _set_status(db: Session, project: Project, nxt: str, actor_id: str | None) -> None:
    prev = project.status
    try:
        project.status = apply_transition(project.status, nxt)
    except IllegalTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    project.updated_at = _now()
    if prev != project.status:
        log_event(
            db,
            event_type="STATUS_CHANGED",
            actor_id=actor_id,
            project_id=project.id,
            metadata={"from": prev, "to": project.status},
        )


def _next_version(db: Session, doc_id: str) -> int:
    last = (
        db.query(Revision)
        .filter(Revision.design_document_id == doc_id)
        .order_by(Revision.version.desc())
        .first()
    )
    return (last.version + 1) if last else 1


def _add_revision(
    db: Session,
    *,
    doc: DesignDocument,
    floor_plan: dict,
    created_by: str,
    source_type: str,
    source_revision_id: str | None = None,
    scene_document: dict | None = None,
) -> Revision:
    scene_payload = scene_document if scene_document is not None else floor_plan_to_scene_document(floor_plan)
    rev = Revision(
        design_document_id=doc.id,
        version=_next_version(db, doc.id),
        source_revision_id=source_revision_id,
        scene_document=json.dumps(scene_payload),
        floor_plan=json.dumps(floor_plan),
        created_by=created_by,
        source_type=source_type,
    )
    db.add(rev)
    db.flush()
    return rev


def create_project(db: Session, actor: Actor, name: str, client_id: str | None, architect_id: str | None) -> Project:
    if not perm.can_create_project(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only architects or admins can create projects")
    arch_id = architect_id
    if actor.role == "ARCHITECT":
        arch_id = actor.id
    project = Project(name=name, client_id=client_id, architect_id=arch_id, status="DRAFT")
    db.add(project)
    db.flush()
    _document(db, project)
    log_event(db, event_type="PROJECT_CREATED", actor_id=actor.id, project_id=project.id, target=name)
    if client_id:
        notify(db, client_id, "PROJECT_ASSIGNED", f"You were assigned to project {name}", project.id)
    db.commit()
    db.refresh(project)
    return project


def list_projects(db: Session, actor: Actor) -> list[Project]:
    q = db.query(Project)
    if actor.role == "CLIENT":
        q = q.filter(Project.client_id == actor.id)
    elif actor.role == "ARCHITECT":
        q = q.filter(Project.architect_id == actor.id)
    return q.order_by(Project.updated_at.desc()).all()


def assign_project(db: Session, actor: Actor, project_id: str, client_id: str | None, architect_id: str | None) -> Project:
    project = _require_view(db, actor, project_id)
    if actor.role not in ("ARCHITECT", "MAIN_ADMIN", "IT_PERSONNEL"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot assign this project")
    if client_id is not None:
        project.client_id = client_id
        notify(db, client_id, "PROJECT_ASSIGNED", f"You were assigned to project {project.name}", project.id)
    if architect_id is not None and actor.role in ("MAIN_ADMIN", "IT_PERSONNEL"):
        project.architect_id = architect_id
    project.updated_at = _now()
    log_event(db, event_type="ACCOUNT_MODIFIED", actor_id=actor.id, project_id=project.id, target="assignment")
    db.commit()
    db.refresh(project)
    return project


def save_brief(db: Session, actor: Actor, project_id: str, questionnaire: dict, specification: dict) -> ClientBrief:
    project = _require_view(db, actor, project_id)
    if not perm.can_update_brief(actor, project_as_dict(project)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot update brief")
    brief = db.query(ClientBrief).filter(ClientBrief.project_id == project.id).one_or_none()
    if brief is None:
        brief = ClientBrief(project_id=project.id)
        db.add(brief)
    brief.questionnaire = json.dumps(questionnaire)
    brief.specification = json.dumps(specification or {})
    brief.updated_at = _now()
    doc = _document(db, project)
    if doc.stage == "CLIENT_BRIEF" and project.status == "DRAFT":
        pass
    db.commit()
    db.refresh(brief)
    return brief


def get_brief(db: Session, actor: Actor, project_id: str) -> dict:
    project = _require_view(db, actor, project_id)
    brief = db.query(ClientBrief).filter(ClientBrief.project_id == project.id).one_or_none()
    return {
        "project": project_as_dict(project),
        "questionnaire": _loads(brief.questionnaire) if brief else {},
        "specification": _loads(brief.specification) if brief else {},
    }


def generate_candidates(db: Session, actor: Actor, project_id: str) -> dict:
    project = _require_view(db, actor, project_id)
    payload = project_as_dict(project, db)
    if not perm.can_generate(actor, payload):
        if actor.role == "ARCHITECT" and not payload.get("has_floor_plan"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, CANVAS_LOCKED_DETAIL)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot generate for this project")
    brief = db.query(ClientBrief).filter(ClientBrief.project_id == project.id).one_or_none()
    if brief is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Save a client brief before generating")
    doc = _document(db, project)
    source_revision_id = doc.current_revision_id
    questionnaire = _loads(brief.questionnaire)
    specification = _loads(brief.specification)
    constraints = brief_to_constraints(questionnaire, specification)
    job = GenerationJob(
        project_id=project.id,
        requested_by=actor.id,
        source_revision_id=source_revision_id,
        source_brief_id=brief.id,
        specification=json.dumps(specification or constraints),
        status="RUNNING",
    )
    db.add(job)
    db.flush()
    log_event(
        db,
        event_type="AI_GENERATION_STARTED",
        actor_id=actor.id,
        project_id=project.id,
        target=job.id,
        metadata={"source_revision_id": source_revision_id},
    )
    db.commit()

    try:
        result = run_generation(constraints)
    except Exception as exc:
        job.status = "FAILED"
        job.completed_at = _now()
        log_event(db, event_type="AI_GENERATION_FAILED", actor_id=actor.id, project_id=project.id, target=job.id)
        notify_project_roles(db, project, "AI_GENERATION_FAILED", f"Generation failed for {project.name}", actor.id)
        db.commit()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc

    plans = result.get("plans") or []
    db.refresh(doc)
    # Overwrite safety: never PUT onto current architect revision, even if it changed while the job ran.
    candidates = []
    for plan in plans:
        rev = _add_revision(
            db,
            doc=doc,
            floor_plan=plan,
            created_by=actor.id,
            source_type="AI_GENERATED",
            source_revision_id=job.source_revision_id,
        )
        cand = AICandidate(
            project_id=project.id,
            generation_job_id=job.id,
            revision_id=rev.id,
            selected_by_client=False,
        )
        db.add(cand)
        db.flush()
        candidates.append(cand)

    job.status = "COMPLETED"
    job.completed_at = _now()
    if candidates:
        job.result_candidate_id = candidates[0].id
        doc.stage = "AI_PROPOSAL"
    if project.status == "DRAFT":
        _set_status(db, project, "IN_PROGRESS", actor.id)
    log_event(
        db,
        event_type="AI_GENERATION_COMPLETED",
        actor_id=actor.id,
        project_id=project.id,
        target=job.id,
        metadata={
            "source_revision_id": job.source_revision_id,
            "current_revision_id": doc.current_revision_id,
            "stale": doc.current_revision_id != job.source_revision_id,
            "candidate_count": len(candidates),
        },
    )
    notify_project_roles(
        db,
        project,
        "AI_GENERATION_COMPLETED",
        f"{len(candidates)} AI candidates are ready for {project.name}",
        actor.id,
    )
    db.commit()
    return {
        "job": serialize_job(job),
        "candidates": [serialize_candidate(db, c) for c in candidates],
        "stale_source": doc.current_revision_id != job.source_revision_id,
        "generation": {k: v for k, v in result.items() if k != "plans"},
    }


def list_candidates(db: Session, actor: Actor, project_id: str) -> list[dict]:
    project = _require_view(db, actor, project_id)
    rows = db.query(AICandidate).filter(AICandidate.project_id == project.id).order_by(AICandidate.created_at.desc()).all()
    return [serialize_candidate(db, c) for c in rows]


def select_candidate(db: Session, actor: Actor, project_id: str, candidate_id: str) -> AICandidate:
    project = _require_view(db, actor, project_id)
    if not perm.can_select_candidate(actor, project_as_dict(project)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the assigned client can select a candidate")
    cand = db.get(AICandidate, candidate_id)
    if cand is None or cand.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
    for other in db.query(AICandidate).filter(AICandidate.project_id == project.id).all():
        other.selected_by_client = other.id == cand.id
    log_event(db, event_type="CANDIDATE_SELECTED", actor_id=actor.id, project_id=project.id, revision_id=cand.revision_id)
    notify(db, project.architect_id, "CANDIDATE_SELECTED", f"Client selected a candidate on {project.name}", project.id)
    db.commit()
    db.refresh(cand)
    return cand


def accept_candidate(db: Session, actor: Actor, project_id: str, candidate_id: str) -> Revision:
    project = _require_view(db, actor, project_id)
    _require_architect_canvas(db, actor, project)
    if not perm.can_accept_candidate(actor, project_as_dict(project, db)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the assigned architect can accept a candidate")
    cand = db.get(AICandidate, candidate_id)
    if cand is None or cand.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
    source = db.get(Revision, cand.revision_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate revision missing")
    doc = _document(db, project)
    copy = _add_revision(
        db,
        doc=doc,
        floor_plan=_loads(source.floor_plan),
        created_by=actor.id,
        source_type="ARCHITECT_EDIT",
        source_revision_id=source.id,
    )
    doc.current_revision_id = copy.id
    doc.stage = "ARCHITECT_DESIGN"
    if project.status == "DRAFT":
        _set_status(db, project, "IN_PROGRESS", actor.id)
    log_event(
        db,
        event_type="REVISION_CREATED",
        actor_id=actor.id,
        project_id=project.id,
        revision_id=copy.id,
        metadata={"from_candidate": cand.id, "copied_from": source.id},
    )
    notify(db, project.client_id, "REVISION_CREATED", f"Architect started a design from an AI candidate on {project.name}", project.id)
    db.commit()
    db.refresh(copy)
    return copy


def update_design(
    db: Session,
    actor: Actor,
    revision_id: str,
    floor_plan: dict,
    expected_revision_id: str | None,
    scene_document: dict | None = None,
) -> Revision:
    rev = db.get(Revision, revision_id)
    if rev is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Revision not found")
    doc = db.get(DesignDocument, rev.design_document_id)
    project = db.get(Project, doc.project_id) if doc else None
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    if rev.source_type == "PUBLISHED" or project.status == "PUBLISHED":
        raise HTTPException(status.HTTP_409_CONFLICT, "Published designs cannot be mutated")
    if not perm.can_edit_design(actor, project_as_dict(project, db)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot edit design")
    _require_architect_canvas(db, actor, project)
    if expected_revision_id and doc.current_revision_id and expected_revision_id != doc.current_revision_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Stale revision; reload before saving")
    if rev.source_type == "AI_GENERATED":
        raise HTTPException(status.HTTP_409_CONFLICT, "Accept the candidate before editing; AI revisions are immutable")
    new_rev = _add_revision(
        db,
        doc=doc,
        floor_plan=floor_plan,
        created_by=actor.id,
        source_type="REVISION",
        source_revision_id=rev.id,
        scene_document=scene_document,
    )
    if scene_document is not None:
        doc.working_scene_document = json.dumps(scene_document)
        doc.working_updated_at = datetime.now(timezone.utc)
    doc.current_revision_id = new_rev.id
    log_event(
        db,
        event_type="REVISION_CREATED",
        actor_id=actor.id,
        project_id=project.id,
        revision_id=new_rev.id,
        metadata={"kind": "WALL/ROOM"},
    )
    db.commit()
    db.refresh(new_rev)
    return new_rev


def update_working_design(db: Session, actor: Actor, project_id: str, scene_document: dict) -> dict:
    project = _require_view(db, actor, project_id)
    payload = project_as_dict(project, db)
    if not perm.can_edit_design(actor, payload):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot edit design")
    _require_architect_canvas(db, actor, project)
    if project.status == "PUBLISHED":
        raise HTTPException(status.HTTP_409_CONFLICT, "Published designs cannot be mutated")
    doc = _document(db, project)
    doc.working_scene_document = json.dumps(scene_document)
    doc.working_updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(doc)
    return {
        "working_updated_at": doc.working_updated_at.isoformat() if doc.working_updated_at else None,
    }


def list_revisions(db: Session, actor: Actor, project_id: str) -> list[dict]:
    project = _require_view(db, actor, project_id)
    doc = _document(db, project)
    rows = db.query(Revision).filter(Revision.design_document_id == doc.id).order_by(Revision.version.desc()).all()
    return [serialize_revision(r, current_id=doc.current_revision_id) for r in rows]


def get_revision(db: Session, actor: Actor, revision_id: str) -> dict:
    rev = db.get(Revision, revision_id)
    if rev is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Revision not found")
    doc = db.get(DesignDocument, rev.design_document_id)
    project = db.get(Project, doc.project_id)
    _require_view(db, actor, project.id)
    _require_architect_canvas(db, actor, project)
    return serialize_revision(rev, current_id=doc.current_revision_id, include_payload=True)


def add_comment(
    db: Session,
    actor: Actor,
    project_id: str,
    body: str,
    revision_id: str | None,
    object_id: str | None,
    stage: str | None,
    x: float | None = None,
    y: float | None = None,
) -> Comment:
    project = _require_view(db, actor, project_id)
    if not perm.can_comment(actor, project_as_dict(project)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot comment")
    doc = _document(db, project)
    comment = Comment(
        project_id=project.id,
        stage=stage or doc.stage,
        revision_id=revision_id or doc.current_revision_id,
        author_id=actor.id,
        object_id=object_id,
        body=body,
        x=x,
        y=y,
    )
    db.add(comment)
    log_event(db, event_type="COMMENT_CREATED", actor_id=actor.id, project_id=project.id, revision_id=comment.revision_id)
    notify_project_roles(db, project, "COMMENT_CREATED", f"New comment on {project.name}", actor.id)
    db.commit()
    db.refresh(comment)
    return comment


def list_comments(db: Session, actor: Actor, project_id: str) -> list[dict]:
    project = _require_view(db, actor, project_id)
    rows = db.query(Comment).filter(Comment.project_id == project.id).order_by(Comment.created_at.asc()).all()
    return [serialize_comment(c, db) for c in rows]


def update_comment(db: Session, actor: Actor, project_id: str, comment_id: str, patch: dict) -> Comment:
    project = _require_view(db, actor, project_id)
    comment = db.get(Comment, comment_id)
    if comment is None or comment.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    if not perm.can_mutate_comment(actor, project_as_dict(project), comment.author_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot edit comment")
    if "body" in patch and patch["body"] is not None:
        comment.body = patch["body"]
    if "object_id" in patch:
        comment.object_id = patch["object_id"]
    if "x" in patch:
        comment.x = patch["x"]
    if "y" in patch:
        comment.y = patch["y"]
    db.commit()
    db.refresh(comment)
    return comment


def delete_comment(db: Session, actor: Actor, project_id: str, comment_id: str) -> None:
    project = _require_view(db, actor, project_id)
    comment = db.get(Comment, comment_id)
    if comment is None or comment.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    if not perm.can_mutate_comment(actor, project_as_dict(project), comment.author_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot delete comment")
    db.delete(comment)
    db.commit()


def submit_review(db: Session, actor: Actor, project_id: str) -> Project:
    project = _require_view(db, actor, project_id)
    if project.status == "FOR_CHECKING":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already submitted for checking")
    payload = project_as_dict(project, db)
    if not perm.can_submit_review(actor, payload):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot submit this project for checking")
    _set_status(db, project, "FOR_CHECKING", actor.id)
    if actor.role == "CLIENT":
        notify(db, project.architect_id, "STATUS_CHANGED", f"{project.name} was sent for review", project.id)
    else:
        notify(db, project.client_id, "STATUS_CHANGED", f"{project.name} is ready for your review", project.id)
    db.commit()
    db.refresh(project)
    return project


def request_revision(db: Session, actor: Actor, project_id: str) -> Project:
    project = _require_view(db, actor, project_id)
    if not perm.can_request_revision(actor, project_as_dict(project)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot request revision")
    _set_status(db, project, "FOR_REVISION", actor.id)
    log_event(db, event_type="REVISION_REQUESTED", actor_id=actor.id, project_id=project.id)
    notify(db, project.architect_id, "REVISION_REQUESTED", f"Client requested changes on {project.name}", project.id)
    db.commit()
    db.refresh(project)
    return project


def resume_after_revision(db: Session, actor: Actor, project_id: str) -> Project:
    project = _require_view(db, actor, project_id)
    if not perm.can_edit_design(actor, project_as_dict(project)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the architect can resume design")
    _set_status(db, project, "IN_PROGRESS", actor.id)
    db.commit()
    db.refresh(project)
    return project


def client_approve(db: Session, actor: Actor, project_id: str) -> Approval:
    project = _require_view(db, actor, project_id)
    if not perm.can_approve(actor, project_as_dict(project)) or actor.role != "CLIENT":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Client cannot approve in this state")
    doc = _document(db, project)
    approval = Approval(project_id=project.id, revision_id=doc.current_revision_id, actor_id=actor.id, kind="CLIENT_APPROVED")
    db.add(approval)
    log_event(db, event_type="CLIENT_APPROVED", actor_id=actor.id, project_id=project.id, revision_id=doc.current_revision_id)
    notify(db, project.architect_id, "CLIENT_APPROVED", f"Client approved {project.name}", project.id)
    db.commit()
    db.refresh(approval)
    return approval


def architect_approve(db: Session, actor: Actor, project_id: str) -> Project:
    project = _require_view(db, actor, project_id)
    if not perm.can_approve(actor, project_as_dict(project)) or actor.role != "ARCHITECT":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Architect cannot approve in this state")
    client_ok = (
        db.query(Approval)
        .filter(Approval.project_id == project.id, Approval.kind == "CLIENT_APPROVED")
        .first()
    )
    if client_ok is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Client approval is required before architect approval")
    doc = _document(db, project)
    db.add(Approval(project_id=project.id, revision_id=doc.current_revision_id, actor_id=actor.id, kind="ARCHITECT_APPROVED"))
    _set_status(db, project, "APPROVED", actor.id)
    log_event(db, event_type="ARCHITECT_APPROVED", actor_id=actor.id, project_id=project.id, revision_id=doc.current_revision_id)
    notify(db, project.client_id, "ARCHITECT_APPROVED", f"Architect approved {project.name}", project.id)
    db.commit()
    db.refresh(project)
    return project


def publish_project(db: Session, actor: Actor, project_id: str) -> Revision:
    project = _require_view(db, actor, project_id)
    if not perm.can_publish(actor, project_as_dict(project)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot publish")
    doc = _document(db, project)
    current = db.get(Revision, doc.current_revision_id) if doc.current_revision_id else None
    if current is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No current revision to publish")
    published = _add_revision(
        db,
        doc=doc,
        floor_plan=_loads(current.floor_plan),
        created_by=actor.id,
        source_type="PUBLISHED",
        source_revision_id=current.id,
    )
    doc.current_revision_id = published.id
    doc.stage = "FINAL_DESIGN"
    _set_status(db, project, "PUBLISHED", actor.id)
    log_event(db, event_type="PROJECT_PUBLISHED", actor_id=actor.id, project_id=project.id, revision_id=published.id)
    notify(db, project.client_id, "PROJECT_PUBLISHED", f"{project.name} was published", project.id)
    notify_it(db, "PROJECT_PUBLISHED", f"{project.name} was published", project.id)
    db.commit()
    db.refresh(published)
    return published


def list_notifications(db: Session, actor: Actor) -> list[dict]:
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == actor.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return [
        {
            "id": n.id,
            "kind": n.kind,
            "message": n.message,
            "project_id": n.project_id,
            "read": n.read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in rows
    ]


def mark_notification_read(db: Session, actor: Actor, notification_id: str) -> None:
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != actor.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    n.read = True
    db.commit()


def list_audit(db: Session, actor: Actor, project_id: str | None = None) -> list[dict]:
    if not perm.can_view_audit(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot view audit")
    q = db.query(AuditEvent)
    if project_id:
        project = _require_view(db, actor, project_id)
        q = q.filter(AuditEvent.project_id == project.id)
    elif actor.role == "ARCHITECT":
        ids = [p.id for p in db.query(Project).filter(Project.architect_id == actor.id).all()]
        q = q.filter(AuditEvent.project_id.in_(ids or ["__none__"]))
    rows = q.order_by(AuditEvent.created_at.desc()).limit(500).all()
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "actor_id": e.actor_id,
            "project_id": e.project_id,
            "revision_id": e.revision_id,
            "target": e.target,
            "metadata": _loads(e.metadata_json),
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in rows
    ]


def list_users(db: Session, actor: Actor) -> list[dict]:
    if not perm.can_manage_accounts(actor) and actor.role != "ARCHITECT":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot list accounts")
    if actor.role == "ARCHITECT":
        client_ids = {
            p.client_id
            for p in db.query(Project).filter(Project.architect_id == actor.id, Project.client_id.isnot(None)).all()
        }
        accepted_ids = {
            row.accepted_user_id
            for row in db.query(Invitation.accepted_user_id)
            .filter(Invitation.architect_id == actor.id, Invitation.accepted_user_id.isnot(None))
            .all()
        }
        ids = {uid for uid in client_ids.union(accepted_ids) if uid}
        if not ids:
            return []
        rows = db.query(User).filter(User.id.in_(ids), User.role == "CLIENT").order_by(User.email.asc()).all()
        return [serialize_user(u) for u in rows]
    rows = db.query(User).order_by(User.email.asc()).all()
    return [serialize_user(u) for u in rows]


def patch_account(db: Session, actor: Actor, user_id: str, approved: bool | None, role: str | None) -> User:
    if not perm.can_manage_accounts(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot manage accounts")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if approved is not None:
        user.approved = approved
    if role is not None:
        user.role = role
    log_event(db, event_type="ACCOUNT_MODIFIED", actor_id=actor.id, target=user.id, metadata={"approved": user.approved, "role": user.role})
    notify(db, user.id, "ACCOUNT_MODIFIED", "Your KIYUB account was updated")
    db.commit()
    db.refresh(user)
    return user


def serialize_user(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "role": u.role,
        "approved": u.approved,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def serialize_revision(r: Revision, current_id: str | None = None, include_payload: bool = False) -> dict:
    data = {
        "id": r.id,
        "version": r.version,
        "source_revision_id": r.source_revision_id,
        "created_by": r.created_by,
        "source_type": r.source_type,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "is_current": r.id == current_id,
    }
    if include_payload:
        data["floor_plan"] = _loads(r.floor_plan)
        data["scene_document"] = _loads(r.scene_document)
    return data


def serialize_candidate(db: Session, c: AICandidate) -> dict:
    rev = db.get(Revision, c.revision_id)
    return {
        "id": c.id,
        "project_id": c.project_id,
        "generation_job_id": c.generation_job_id,
        "revision_id": c.revision_id,
        "selected_by_client": c.selected_by_client,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "floor_plan": _loads(rev.floor_plan) if rev else {},
        "scene_document": _loads(rev.scene_document) if rev else {},
        "source_type": rev.source_type if rev else None,
    }


def serialize_job(job: GenerationJob) -> dict:
    return {
        "id": job.id,
        "project_id": job.project_id,
        "requested_by": job.requested_by,
        "source_revision_id": job.source_revision_id,
        "source_brief_id": job.source_brief_id,
        "status": job.status,
        "result_candidate_id": job.result_candidate_id,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


def serialize_comment(c: Comment, db: Session | None = None) -> dict:
    session = db or object_session(c)
    author = session.get(User, c.author_id) if session is not None else None
    return {
        "id": c.id,
        "project_id": c.project_id,
        "stage": c.stage,
        "revision_id": c.revision_id,
        "author_id": c.author_id,
        "author_email": author.email if author else None,
        "author_role": author.role if author else None,
        "object_id": c.object_id,
        "body": c.body,
        "x": c.x,
        "y": c.y,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def serialize_approval(a: Approval) -> dict:
    return {
        "id": a.id,
        "project_id": a.project_id,
        "revision_id": a.revision_id,
        "actor_id": a.actor_id,
        "kind": a.kind,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def project_detail(db: Session, actor: Actor, project_id: str) -> dict:
    project = _require_view(db, actor, project_id)
    doc = _document(db, project)
    current = db.get(Revision, doc.current_revision_id) if doc.current_revision_id else None
    payload = project_as_dict(project, db)
    invitation = (
        db.query(Invitation)
        .filter(Invitation.project_id == project.id)
        .order_by(Invitation.created_at.desc())
        .first()
    )
    if invitation:
        _refresh_invitation_status(db, invitation)
    document = {
        "id": doc.id,
        "stage": doc.stage,
        "current_revision_id": doc.current_revision_id,
    }
    if perm.can_edit_design(actor, payload):
        working = json.loads(doc.working_scene_document) if doc.working_scene_document else None
        document["working_scene_document"] = working
        document["working_updated_at"] = doc.working_updated_at.isoformat() if doc.working_updated_at else None
    return {
        "project": payload,
        "document": document,
        "current_revision": serialize_revision(current, doc.current_revision_id, include_payload=True) if current else None,
        "invitation": serialize_invitation(invitation) if invitation else None,
        "permissions": {
            "canViewProject": perm.can_view_project(actor, payload),
            "canEditDesign": perm.can_edit_design(actor, payload),
            "canGenerate": perm.can_generate(actor, payload),
            "canComment": perm.can_comment(actor, payload),
            "canSelectCandidate": perm.can_select_candidate(actor, payload),
            "canRequestRevision": perm.can_request_revision(actor, payload),
            "canApprove": perm.can_approve(actor, payload),
            "canPublish": perm.can_publish(actor, payload),
            "canOpenArchitectCanvas": perm.can_open_architect_canvas(actor, payload),
            "canSubmitReview": perm.can_submit_review(actor, payload),
        },
    }


def serialize_invitation(inv: Invitation, token: str | None = None) -> dict:
    data = {
        "id": inv.id,
        "project_id": inv.project_id,
        "architect_id": inv.architect_id,
        "email": inv.email,
        "status": inv.status,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "accepted_at": inv.accepted_at.isoformat() if inv.accepted_at else None,
        "accepted_user_id": inv.accepted_user_id,
    }
    if token:
        data["token"] = token
        data["invite_url"] = f"/invite/{token}"
    return data


def _refresh_invitation_status(db: Session, inv: Invitation) -> Invitation:
    if inv.status == "PENDING":
        expires = _aware(inv.expires_at)
        if expires and expires < _now():
            inv.status = "EXPIRED"
            db.flush()
    return inv


def _get_invitation_by_token(db: Session, token: str) -> Invitation:
    if not token:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    inv = db.query(Invitation).filter(Invitation.token_hash == _hash_invite_token(token)).one_or_none()
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    return _refresh_invitation_status(db, inv)


def _can_invite_to_project(actor: Actor, project: Project) -> bool:
    if actor.role == "ARCHITECT" and actor.approved and project.architect_id == actor.id:
        return True
    if actor.role == "MAIN_ADMIN":
        return True
    return False


def create_invitation(db: Session, actor: Actor, project_id: str, email: str, resend: bool = False) -> dict:
    project = _require_view(db, actor, project_id)
    if not _can_invite_to_project(actor, project):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot invite clients to this project")
    email = email.lower().strip()
    if not email or "@" not in email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A valid email is required")
    if project.client_id:
        existing = db.get(User, project.client_id)
        if existing and existing.email != email:
            raise HTTPException(status.HTTP_409_CONFLICT, "Project already has a different client")
    pending = (
        db.query(Invitation)
        .filter(
            Invitation.project_id == project.id,
            Invitation.email == email,
            Invitation.status == "PENDING",
        )
        .all()
    )
    for row in pending:
        _refresh_invitation_status(db, row)
    active = [row for row in pending if row.status == "PENDING"]
    if active and not resend:
        raise HTTPException(status.HTTP_409_CONFLICT, "A pending invitation already exists for this email")
    if active and resend:
        for row in active:
            row.status = "CANCELLED"
    token = secrets.token_urlsafe(32)
    inv = Invitation(
        architect_id=project.architect_id or actor.id,
        project_id=project.id,
        email=email,
        status="PENDING",
        token_hash=_hash_invite_token(token),
        expires_at=_now() + timedelta(days=INVITE_TTL_DAYS),
    )
    db.add(inv)
    db.flush()
    log_event(
        db,
        event_type="CLIENT_INVITED",
        actor_id=actor.id,
        project_id=project.id,
        target=email,
        metadata={"invitation_id": inv.id},
    )
    notify(db, actor.id, "CLIENT_INVITED", f"Invitation created for {email} on {project.name}", project.id)
    db.commit()
    db.refresh(inv)
    return serialize_invitation(inv, token=token)


def list_project_invitations(db: Session, actor: Actor, project_id: str) -> list[dict]:
    project = _require_view(db, actor, project_id)
    if not _can_invite_to_project(actor, project) and actor.role not in ("MAIN_ADMIN", "IT_PERSONNEL"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot list invitations")
    rows = db.query(Invitation).filter(Invitation.project_id == project.id).order_by(Invitation.created_at.desc()).all()
    return [serialize_invitation(_refresh_invitation_status(db, row)) for row in rows]


def cancel_invitation(db: Session, actor: Actor, invitation_id: str) -> dict:
    inv = db.get(Invitation, invitation_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    project = _require_view(db, actor, inv.project_id)
    if not _can_invite_to_project(actor, project):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot cancel this invitation")
    _refresh_invitation_status(db, inv)
    if inv.status != "PENDING":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot cancel a {inv.status.lower()} invitation")
    inv.status = "CANCELLED"
    log_event(db, event_type="CLIENT_INVITE_CANCELLED", actor_id=actor.id, project_id=project.id, target=inv.email)
    db.commit()
    db.refresh(inv)
    return serialize_invitation(inv)


def public_invitation(db: Session, token: str) -> dict:
    inv = _get_invitation_by_token(db, token)
    project = db.get(Project, inv.project_id)
    existing = db.query(User).filter(User.email == inv.email).one_or_none()
    db.commit()
    return {
        "email": inv.email,
        "project_name": project.name if project else None,
        "status": inv.status,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
        "needs_registration": existing is None,
    }


def accept_invitation_token(db: Session, actor: Actor, token: str) -> dict:
    inv = _get_invitation_by_token(db, token)
    if inv.status == "EXPIRED":
        raise HTTPException(status.HTTP_410_GONE, "This invitation has expired")
    if inv.status == "CANCELLED":
        raise HTTPException(status.HTTP_409_CONFLICT, "This invitation was cancelled")
    if inv.status == "ACCEPTED":
        if inv.accepted_user_id == actor.id:
            project = db.get(Project, inv.project_id)
            return {"invitation": serialize_invitation(inv), "project": project_as_dict(project, db) if project else None}
        raise HTTPException(status.HTTP_409_CONFLICT, "This invitation was already accepted")
    if inv.status != "PENDING":
        raise HTTPException(status.HTTP_409_CONFLICT, "Invitation is not pending")
    user = db.get(User, actor.id)
    if user is None or user.email.lower() != inv.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This invitation is for a different email")
    if user.role != "CLIENT":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a client account can accept this invitation")
    project = db.get(Project, inv.project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    if project.client_id and project.client_id != user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Project already has a different client")
    project.client_id = user.id
    project.updated_at = _now()
    inv.status = "ACCEPTED"
    inv.accepted_at = _now()
    inv.accepted_user_id = user.id
    log_event(db, event_type="CLIENT_INVITE_ACCEPTED", actor_id=actor.id, project_id=project.id, target=inv.email)
    notify(db, project.architect_id, "CLIENT_INVITE_ACCEPTED", f"{inv.email} joined {project.name}", project.id)
    notify(db, user.id, "PROJECT_ASSIGNED", f"You joined project {project.name}", project.id)
    db.commit()
    db.refresh(inv)
    db.refresh(project)
    return {"invitation": serialize_invitation(inv), "project": project_as_dict(project, db)}


def register_client_from_invite(db: Session, email: str, password: str, token: str, hash_password) -> User:
    inv = _get_invitation_by_token(db, token)
    if inv.status != "PENDING":
        if inv.status == "EXPIRED":
            raise HTTPException(status.HTTP_410_GONE, "This invitation has expired")
        raise HTTPException(status.HTTP_409_CONFLICT, "Invitation is not pending")
    email = email.lower().strip()
    if email != inv.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Email does not match this invitation")
    if db.query(User).filter(User.email == email).one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(email=email, password_hash=hash_password(password), role="CLIENT", approved=True)
    db.add(user)
    db.flush()
    log_event(db, event_type="ACCOUNT_MODIFIED", actor_id=user.id, target=user.id, metadata={"created": True, "role": "CLIENT", "via": "invitation"})
    actor = Actor(id=user.id, role="CLIENT", approved=True)
    accept_invitation_token(db, actor, token)
    db.refresh(user)
    return user


def list_architect_clients(db: Session, actor: Actor) -> list[dict]:
    if actor.role not in ("ARCHITECT", "MAIN_ADMIN"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot list clients")
    projects = list_projects(db, actor)
    rows: list[dict] = []
    for project in projects:
        invites = (
            db.query(Invitation)
            .filter(Invitation.project_id == project.id)
            .order_by(Invitation.created_at.desc())
            .all()
        )
        seen_emails: set[str] = set()
        for inv in invites:
            _refresh_invitation_status(db, inv)
            seen_emails.add(inv.email)
            user = db.get(User, inv.accepted_user_id) if inv.accepted_user_id else db.query(User).filter(User.email == inv.email).one_or_none()
            rows.append({
                "email": inv.email,
                "user_id": user.id if user else None,
                "project_id": project.id,
                "project_name": project.name,
                "invitation_status": inv.status,
                "project_status": project.status,
                "last_activity": project.updated_at.isoformat() if project.updated_at else None,
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
                "invitation_id": inv.id,
            })
        if project.client_id:
            client = db.get(User, project.client_id)
            if client and client.email not in seen_emails:
                rows.append({
                    "email": client.email,
                    "user_id": client.id,
                    "project_id": project.id,
                    "project_name": project.name,
                    "invitation_status": None,
                    "project_status": project.status,
                    "last_activity": project.updated_at.isoformat() if project.updated_at else None,
                    "created_at": client.created_at.isoformat() if client.created_at else None,
                    "invitation_id": None,
                })
    db.commit()
    return rows


def serialize_inquiry(item: Inquiry) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "email": item.email,
        "message": item.message,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def create_inquiry(db: Session, name: str, email: str, message: str) -> Inquiry:
    cleaned_name = (name or "").strip()
    cleaned_email = (email or "").strip().lower()
    cleaned_message = (message or "").strip()
    if not cleaned_name or not cleaned_email or not cleaned_message:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Name, email, and message are required")
    if "@" not in cleaned_email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A valid email is required")
    item = Inquiry(name=cleaned_name, email=cleaned_email, message=cleaned_message)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_inquiries(db: Session, actor: Actor) -> list[dict]:
    if not perm.can_view_inquiries(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot view inquiries")
    rows = db.query(Inquiry).order_by(Inquiry.created_at.desc()).all()
    return [serialize_inquiry(item) for item in rows]
