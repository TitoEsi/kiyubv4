"""Project workflow services. Generation results become candidates; never overwrite architect revisions."""
from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

from fastapi import HTTPException, status

from generation_units import (
    METRIC,
    normalize_comment_coords,
    normalize_floor_plan,
    normalize_questionnaire,
    normalize_scene_document,
    normalize_specification,
)

from . import permissions as perm
from .audit import log_event, notify, notify_it, notify_project_roles
from .generate import brief_to_constraints, run_generation
from .models import (
    AICandidate,
    Approval,
    ArchitectApplication,
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
    SiteConstraint,
    User,
)
from . import mail
from .repositories.base import MemoryStore as Session
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


def _sync_site_constraints(db: Session, project_id: str, questionnaire: dict) -> None:
    """Companion row derived from questionnaire.site — not a second source of truth."""
    site = questionnaire.get("site") if isinstance(questionnaire, dict) else {}
    if not isinstance(site, dict):
        site = {}
    row = db.query(SiteConstraint).filter(SiteConstraint.project_id == project_id).one_or_none()
    if row is None:
        row = SiteConstraint(project_id=project_id)
        db.add(row)
    width = site.get("lotWidth")
    depth = site.get("lotDepth")
    try:
        row.lot_width = float(width) if width is not None else None
    except (TypeError, ValueError):
        row.lot_width = None
    try:
        row.lot_depth = float(depth) if depth is not None else None
    except (TypeError, ValueError):
        row.lot_depth = None
    row.lot_shape = site.get("lotShape")
    row.updated_at = _now()


def floor_plan_has_geometry(plan: Any) -> bool:
    if not isinstance(plan, dict):
        return False
    rooms = plan.get("rooms")
    return isinstance(rooms, list) and len(rooms) > 0


def has_generated_floor_plan(db: Session, project: Project) -> bool:
    if db.query(AICandidate).filter(AICandidate.project_id == project.id).first():
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
        "invitation_id": p.invitation_id,
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
    floor_plan = normalize_floor_plan(floor_plan)
    scene_payload = (
        normalize_scene_document(scene_document)
        if scene_document is not None
        else floor_plan_to_scene_document(floor_plan)
    )
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
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only administrators can create projects directly")
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
    if actor.role not in ("MAIN_ADMIN", "IT_PERSONNEL"):
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
    questionnaire = normalize_questionnaire(questionnaire)
    brief.questionnaire = json.dumps(questionnaire)
    brief.specification = json.dumps(normalize_specification(specification or {}))
    brief.updated_at = _now()
    _sync_site_constraints(db, project.id, questionnaire)
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
        "questionnaire": normalize_questionnaire(_loads(brief.questionnaire)) if brief else {},
        "specification": normalize_specification(_loads(brief.specification)) if brief else {},
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
        plan = normalize_floor_plan(plan)
        scene = floor_plan_to_scene_document(plan)
        site = scene.setdefault("site", {})
        site["width"] = constraints.get("lotWidth")
        site["depth"] = constraints.get("lotDepth")
        rev = _add_revision(
            db,
            doc=doc,
            floor_plan=plan,
            created_by=actor.id,
            source_type="AI_GENERATED",
            source_revision_id=job.source_revision_id,
            scene_document=scene,
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
    scene = _loads(source.scene_document)
    if _is_scene_document(scene):
        doc.working_scene_document = json.dumps(scene)
        doc.working_updated_at = _now()
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
        coord_units=METRIC,
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
    if "x" in patch or "y" in patch:
        comment.x, comment.y = normalize_comment_coords(comment.x, comment.y, comment.coord_units)
        comment.coord_units = METRIC
        if "x" in patch:
            comment.x = patch["x"]
        if "y" in patch:
            comment.y = patch["y"]
    db.touch(comment)
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


def _is_scene_document(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return (
        value.get("version") == "2.0"
        and value.get("units") == "metric"
        and isinstance(value.get("walls"), list)
        and isinstance(value.get("rooms"), list)
    )


def _latest_review_revision(db: Session, doc: DesignDocument) -> Revision | None:
    return (
        db.query(Revision)
        .filter(Revision.design_document_id == doc.id, Revision.source_type == "REVIEW")
        .order_by(Revision.version.desc())
        .first()
    )


def _require_latest_review(db: Session, doc: DesignDocument) -> Revision:
    review = _latest_review_revision(db, doc)
    if review is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No submitted review is available for approval")
    return review


def _active_review_revision(db: Session, doc: DesignDocument, project: Project) -> Revision | None:
    if project.status not in ("FOR_CHECKING", "APPROVED"):
        return None
    submitted = _latest_review_revision(db, doc)
    if submitted is None:
        return None
    if project.status == "APPROVED":
        return submitted
    current = db.get(Revision, doc.current_revision_id) if doc.current_revision_id else None
    if current and current.version > submitted.version:
        return None
    return submitted


def submit_review(
    db: Session,
    actor: Actor,
    project_id: str,
    scene_document: dict | None = None,
    floor_plan: dict | None = None,
) -> dict:
    project = _require_view(db, actor, project_id)
    if actor.role == "CLIENT" and scene_document is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot submit this project for checking")
    if actor.role == "CLIENT" and project.status == "FOR_CHECKING":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already submitted for checking")
    payload = project_as_dict(project, db)
    if not perm.can_submit_review(actor, payload):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot submit this project for checking")
    review_rev: Revision | None = None
    if actor.role == "ARCHITECT":
        doc = _document(db, project)
        scene = scene_document
        if not _is_scene_document(scene) and doc.working_scene_document:
            try:
                scene = json.loads(doc.working_scene_document)
            except json.JSONDecodeError:
                scene = None
        if not _is_scene_document(scene):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "A current SceneDocument is required to submit for review")
        plan = floor_plan if isinstance(floor_plan, dict) else None
        if plan is None and doc.current_revision_id:
            current = db.get(Revision, doc.current_revision_id)
            plan = _loads(current.floor_plan) if current else {}
        review_rev = _add_revision(
            db,
            doc=doc,
            floor_plan=plan or {},
            created_by=actor.id,
            source_type="REVIEW",
            source_revision_id=doc.current_revision_id,
            scene_document=scene,
        )
    if project.status == "IN_PROGRESS":
        _set_status(db, project, "FOR_CHECKING", actor.id)
        if actor.role == "CLIENT":
            notify(db, project.architect_id, "STATUS_CHANGED", f"{project.name} was sent for review", project.id)
        else:
            notify(db, project.client_id, "STATUS_CHANGED", f"{project.name} is ready for your review", project.id)
    db.commit()
    db.refresh(project)
    data = project_as_dict(project, db)
    if review_rev is None:
        review_rev = _latest_review_revision(db, _document(db, project))
    if review_rev is not None:
        data["submitted_revision_id"] = review_rev.id
        data["version"] = review_rev.version
    return data


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
    review = _require_latest_review(db, doc)
    approval = Approval(project_id=project.id, revision_id=review.id, actor_id=actor.id, kind="CLIENT_APPROVED")
    db.add(approval)
    log_event(db, event_type="CLIENT_APPROVED", actor_id=actor.id, project_id=project.id, revision_id=review.id)
    notify(db, project.architect_id, "CLIENT_APPROVED", f"Client approved {project.name}", project.id)
    db.commit()
    db.refresh(approval)
    return approval


def architect_approve(db: Session, actor: Actor, project_id: str) -> Project:
    project = _require_view(db, actor, project_id)
    if not perm.can_approve(actor, project_as_dict(project)) or actor.role != "ARCHITECT":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Architect cannot approve in this state")
    doc = _document(db, project)
    review = _require_latest_review(db, doc)
    client_ok = (
        db.query(Approval)
        .filter(
            Approval.project_id == project.id,
            Approval.kind == "CLIENT_APPROVED",
            Approval.revision_id == review.id,
        )
        .first()
    )
    if client_ok is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Client approval is required before architect approval")
    db.add(Approval(project_id=project.id, revision_id=review.id, actor_id=actor.id, kind="ARCHITECT_APPROVED"))
    _set_status(db, project, "APPROVED", actor.id)
    log_event(db, event_type="ARCHITECT_APPROVED", actor_id=actor.id, project_id=project.id, revision_id=review.id)
    notify(db, project.client_id, "ARCHITECT_APPROVED", f"Architect approved {project.name}", project.id)
    db.commit()
    db.refresh(project)
    return project


def publish_project(
    db: Session,
    actor: Actor,
    project_id: str,
    scene_document: dict | None = None,
    floor_plan: dict | None = None,
) -> Revision:
    """Publish the approved REVIEW snapshot. Optional body is ignored so a stale canvas cannot override it."""
    project = _require_view(db, actor, project_id)
    if not perm.can_publish(actor, project_as_dict(project)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot publish")
    doc = _document(db, project)
    review = _latest_review_revision(db, doc)
    if review is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No submitted review is available to publish")
    published = _add_revision(
        db,
        doc=doc,
        floor_plan=_loads(review.floor_plan),
        created_by=actor.id,
        source_type="PUBLISHED",
        source_revision_id=review.id,
        scene_document=_loads(review.scene_document),
    )
    doc.current_revision_id = published.id
    doc.working_scene_document = None
    doc.working_updated_at = None
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


def mark_all_notifications_read(db: Session, actor: Actor) -> int:
    rows = db.query(Notification).filter(Notification.user_id == actor.id).all()
    count = 0
    for n in rows:
        if not n.read:
            n.read = True
            count += 1
    db.commit()
    return count


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
    elif actor.role == "CLIENT":
        ids = [p.id for p in db.query(Project).filter(Project.client_id == actor.id).all()]
        q = q.filter(AuditEvent.project_id.in_(ids or ["__none__"]))
    rows = q.order_by(AuditEvent.created_at.desc()).limit(500).all()
    actor_ids = {e.actor_id for e in rows if e.actor_id}
    emails = {}
    if actor_ids:
        for u in db.query(User).filter(User.id.in_(list(actor_ids))).all():
            emails[u.id] = u.email
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "actor_id": e.actor_id,
            "actor_email": emails.get(e.actor_id) if e.actor_id else None,
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
            for row in db.query(Invitation)
            .filter(Invitation.architect_id == actor.id, Invitation.accepted_user_id.isnot(None))
            .all()
        }
        ids = {uid for uid in client_ids.union(accepted_ids) if uid}
        if not ids:
            return []
        rows = db.query(User).filter(User.id.in_(ids), User.role == "CLIENT").order_by(User.email.asc()).all()
        return [serialize_user(u) for u in rows if getattr(u, "deleted_at", None) is None]
    rows = db.query(User).order_by(User.email.asc()).all()
    return [serialize_user(u) for u in rows if getattr(u, "deleted_at", None) is None]


def patch_account(
    db: Session,
    actor: Actor,
    user_id: str,
    approved: bool | None,
    role: str | None,
    suspended: bool | None = None,
) -> User:
    if not perm.can_manage_accounts(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot manage accounts")
    user = db.get(User, user_id)
    if user is None or getattr(user, "deleted_at", None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if approved is not None:
        user.approved = approved
    if role is not None:
        if role in ("MAIN_ADMIN", "IT_PERSONNEL") and actor.role != "MAIN_ADMIN":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot assign that role")
        user.role = role
    if suspended is not None:
        if actor.role != "MAIN_ADMIN":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admin can suspend an architect")
        if user.role != "ARCHITECT":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only architects can be suspended")
        user.suspended = suspended
        log_event(
            db,
            event_type="ACCOUNT_SUSPENDED" if suspended else "ACCOUNT_REINSTATED",
            actor_id=actor.id,
            target=user.id,
            metadata={"suspended": suspended},
        )
    log_event(db, event_type="ACCOUNT_MODIFIED", actor_id=actor.id, target=user.id, metadata={"approved": user.approved, "role": user.role, "suspended": getattr(user, "suspended", False)})
    notify(db, user.id, "ACCOUNT_MODIFIED", "Your KIYUB account was updated")
    db.commit()
    db.refresh(user)
    return user


def soft_delete_account(db: Session, actor: Actor, user_id: str) -> User:
    if actor.role != "IT_PERSONNEL":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only IT can delete a suspended architect")
    user = db.get(User, user_id)
    if user is None or getattr(user, "deleted_at", None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.role != "ARCHITECT":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only architect profiles can be deleted")
    if not getattr(user, "suspended", False):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only a suspended architect can be deleted")
    user.deleted_at = datetime.now(timezone.utc)
    log_event(db, event_type="ACCOUNT_DELETED", actor_id=actor.id, target=user.id, metadata={"soft": True})
    db.commit()
    db.refresh(user)
    return user


def serialize_user(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "role": u.role,
        "approved": u.approved,
        "suspended": bool(getattr(u, "suspended", False)),
        "deleted_at": u.deleted_at.isoformat() if getattr(u, "deleted_at", None) else None,
        "full_name": u.full_name,
        "measurement_unit": getattr(u, "measurement_unit", None) or "m",
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def update_preferences(db: Session, user: User, measurement_unit: str) -> dict:
    user.measurement_unit = measurement_unit
    db.touch(user)
    db.commit()
    db.refresh(user)
    return serialize_user(user)


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
        data["floor_plan"] = normalize_floor_plan(_loads(r.floor_plan))
        data["scene_document"] = normalize_scene_document(_loads(r.scene_document))
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
        "floor_plan": normalize_floor_plan(_loads(rev.floor_plan)) if rev else {},
        "scene_document": normalize_scene_document(_loads(rev.scene_document)) if rev else {},
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
    author = db.get(User, c.author_id) if db is not None else None
    x, y = normalize_comment_coords(c.x, c.y, getattr(c, "coord_units", None))
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
        "x": x,
        "y": y,
        "coord_units": METRIC,
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
    submitted = _active_review_revision(db, doc, project)
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
        "submitted_revision": serialize_revision(submitted, doc.current_revision_id, include_payload=True) if submitted else None,
        "invitation": serialize_invitation(invitation, db=db) if invitation else None,
        "permissions": {
            "canViewProject": perm.can_view_project(actor, payload),
            "canEditDesign": perm.can_edit_design(actor, payload),
            "canGenerate": perm.can_generate(actor, payload),
            "canComment": perm.can_comment(actor, payload),
            "canSelectCandidate": perm.can_select_candidate(actor, payload),
            "canApprove": perm.can_approve(actor, payload),
            "canPublish": perm.can_publish(actor, payload),
            "canOpenArchitectCanvas": perm.can_open_architect_canvas(actor, payload),
            "canSubmitReview": perm.can_submit_review(actor, payload),
        },
    }


def serialize_invitation(inv: Invitation, token: str | None = None, db: Session | None = None) -> dict:
    architect = db.get(User, inv.architect_id) if db is not None and inv.architect_id else None
    data = {
        "id": inv.id,
        "project_id": inv.project_id,
        "architect_id": inv.architect_id,
        "architect_email": architect.email if architect else None,
        "email": inv.email,
        "status": inv.status,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "accepted_at": inv.accepted_at.isoformat() if inv.accepted_at else None,
        "accepted_user_id": inv.accepted_user_id,
        "project_name": inv.project_name,
    }
    if token:
        data["token"] = token
        data["invite_url"] = f"/invite/{token}"
    if db is not None:
        data["existing_client"] = _client_profile_exists(db, inv.email)
    return data


def _refresh_invitation_status(db: Session, inv: Invitation) -> Invitation:
    if inv.status == "PENDING":
        expires = _aware(inv.expires_at)
        if expires and expires < _now():
            inv.status = "EXPIRED"
            db.touch(inv)
            db.flush()
    return inv


def _get_invitation_by_token(db: Session, token: str) -> Invitation:
    if not token:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    inv = db.query(Invitation).filter(Invitation.token_hash == _hash_invite_token(token)).one_or_none()
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    return _refresh_invitation_status(db, inv)


def _can_invite(actor: Actor) -> bool:
    if actor.role == "ARCHITECT" and actor.approved:
        return True
    if actor.role == "MAIN_ADMIN":
        return True
    return False


def _can_manage_invitation(actor: Actor, inv: Invitation) -> bool:
    if actor.role == "MAIN_ADMIN":
        return True
    return actor.role == "ARCHITECT" and actor.approved and inv.architect_id == actor.id


def _default_project_name(email: str, project_name: str | None) -> str:
    cleaned = (project_name or "").strip()
    if cleaned:
        return cleaned
    local = email.split("@", 1)[0].replace(".", " ").strip() or "Client"
    return f"Project with {local}"


def _user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).one_or_none()


def _client_profile_exists(db: Session, email: str) -> bool:
    user = _user_by_email(db, email)
    return bool(user and user.role == "CLIENT")


def _email_already_registered(db: Session, email: str) -> bool:
    if _user_by_email(db, email):
        return True
    try:
        from supabase.auth import auth_user_exists
        from .db import supabase_enabled

        if supabase_enabled() and auth_user_exists(email):
            return True
    except Exception:
        pass
    return False


def create_client_invitation(db: Session, actor: Actor, email: str, project_name: str | None = None, resend: bool = False) -> dict:
    if not _can_invite(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot invite clients")
    email = email.lower().strip()
    if not email or "@" not in email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A valid email is required")
    existing = _user_by_email(db, email)
    if existing and existing.role != "CLIENT":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This email belongs to an architect or staff account")
    pending = (
        db.query(Invitation)
        .filter(
            Invitation.architect_id == actor.id,
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
            db.touch(row)
    token = secrets.token_urlsafe(32)
    name = _default_project_name(email, project_name)
    inv = Invitation(
        architect_id=actor.id,
        project_id=None,
        project_name=name,
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
        target=email,
        metadata={"invitation_id": inv.id, "project_name": name, "existing_client": bool(existing and existing.role == "CLIENT")},
    )
    notify(db, actor.id, "CLIENT_INVITED", f"Invitation created for {email}", None)
    if existing and existing.role == "CLIENT":
        inv.auth_user_id = existing.id
        notify(db, existing.id, "CLIENT_INVITED", f"You were invited to a new project: {name}", None)
        db.touch(inv)
    elif not _email_already_registered(db, email):
        try:
            redirect = f"{mail.require_public_app_url()}/invite/{token}"
            auth_uid = mail.send_auth_invite(email, redirect, {"role": "CLIENT", "invitation_id": inv.id})
        except Exception as exc:
            if not resend:
                db.delete(inv)
                db.commit()
                raise mail.invite_failed(exc) from exc
            auth_uid = None
        if auth_uid:
            inv.auth_user_id = auth_uid
            db.touch(inv)
    db.commit()
    db.refresh(inv)
    return serialize_invitation(inv, token=token, db=db)


def create_invitation(db: Session, actor: Actor, project_id: str, email: str, resend: bool = False) -> dict:
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Invite a client with POST /api/invitations")


def list_project_invitations(db: Session, actor: Actor, project_id: str) -> list[dict]:
    project = _require_view(db, actor, project_id)
    if actor.role not in ("ARCHITECT", "MAIN_ADMIN", "IT_PERSONNEL"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot list invitations")
    if actor.role == "ARCHITECT" and project.architect_id != actor.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot list invitations")
    rows = db.query(Invitation).filter(Invitation.project_id == project.id).order_by(Invitation.created_at.desc()).all()
    return [serialize_invitation(_refresh_invitation_status(db, row), db=db) for row in rows]


def list_invitations(db: Session, actor: Actor) -> list[dict]:
    q = db.query(Invitation)
    if actor.role == "ARCHITECT":
        q = q.filter(Invitation.architect_id == actor.id)
    elif actor.role == "CLIENT":
        user = db.get(User, actor.id)
        email = (user.email if user else "").lower()
        q = q.filter(Invitation.email == email)
    elif actor.role not in ("MAIN_ADMIN", "IT_PERSONNEL"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot list invitations")
    rows = q.order_by(Invitation.created_at.desc()).all()
    payload = [serialize_invitation(_refresh_invitation_status(db, row), db=db) for row in rows]
    db.commit()
    return payload


def cancel_invitation(db: Session, actor: Actor, invitation_id: str) -> dict:
    inv = db.get(Invitation, invitation_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    if not _can_manage_invitation(actor, inv):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot cancel this invitation")
    _refresh_invitation_status(db, inv)
    if inv.status != "PENDING":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot cancel a {inv.status.lower()} invitation")
    inv.status = "CANCELLED"
    db.touch(inv)
    log_event(db, event_type="CLIENT_INVITE_CANCELLED", actor_id=actor.id, project_id=inv.project_id, target=inv.email)
    db.commit()
    db.refresh(inv)
    return serialize_invitation(inv)


def public_invitation(db: Session, token: str) -> dict:
    inv = _get_invitation_by_token(db, token)
    project = db.get(Project, inv.project_id) if inv.project_id else None
    architect = db.get(User, inv.architect_id) if inv.architect_id else None
    architect_name = None
    if architect:
        architect_name = architect.full_name or architect.email
    db.commit()
    return {
        "email": inv.email,
        "project_name": project.name if project else inv.project_name,
        "architect_name": architect_name,
        "status": inv.status,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
        "needs_registration": inv.status == "PENDING" and not _client_profile_exists(db, inv.email),
    }


def _project_for_accepted(db: Session, inv: Invitation) -> Project | None:
    if inv.project_id:
        return db.get(Project, inv.project_id)
    return db.query(Project).filter(Project.invitation_id == inv.id).one_or_none()


def accept_invitation_id(db: Session, actor: Actor, invitation_id: str) -> dict:
    inv = db.get(Invitation, invitation_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    return _accept_invitation(db, actor, _refresh_invitation_status(db, inv))


def accept_invitation_token(db: Session, actor: Actor, token: str) -> dict:
    inv = _get_invitation_by_token(db, token)
    return _accept_invitation(db, actor, inv)


def _accept_invitation(db: Session, actor: Actor, inv: Invitation) -> dict:
    if inv.status == "EXPIRED":
        raise HTTPException(status.HTTP_410_GONE, "This invitation has expired")
    if inv.status == "CANCELLED":
        raise HTTPException(status.HTTP_409_CONFLICT, "This invitation was cancelled")
    if inv.status == "DECLINED":
        raise HTTPException(status.HTTP_409_CONFLICT, "This invitation was declined")
    if inv.status == "ACCEPTED":
        if inv.accepted_user_id == actor.id:
            project = _project_for_accepted(db, inv)
            return {"invitation": serialize_invitation(inv), "project": project_as_dict(project, db) if project else None}
        raise HTTPException(status.HTTP_409_CONFLICT, "This invitation was already accepted")
    if inv.status != "PENDING":
        raise HTTPException(status.HTTP_409_CONFLICT, "Invitation is not pending")
    user = db.get(User, actor.id)
    if user is None or user.email.lower() != inv.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This invitation is for a different email")
    if user.role != "CLIENT":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a client account can accept this invitation")
    architect = db.get(User, inv.architect_id)
    if architect is None or architect.role != "ARCHITECT":
        raise HTTPException(status.HTTP_409_CONFLICT, "The inviting architect is no longer available")
    existing = _project_for_accepted(db, inv)
    if existing is not None:
        inv.status = "ACCEPTED"
        inv.accepted_at = inv.accepted_at or _now()
        inv.accepted_user_id = user.id
        inv.project_id = existing.id
        existing.client_id = existing.client_id or user.id
        existing.architect_id = existing.architect_id or architect.id
        existing.invitation_id = existing.invitation_id or inv.id
        db.touch(inv)
        db.touch(existing)
        db.commit()
        db.refresh(inv)
        db.refresh(existing)
        return {"invitation": serialize_invitation(inv), "project": project_as_dict(existing, db)}
    name = _default_project_name(inv.email, inv.project_name)
    project = Project(
        name=name,
        client_id=user.id,
        architect_id=architect.id,
        invitation_id=inv.id,
        status="DRAFT",
    )
    db.add(project)
    db.flush()
    _document(db, project)
    inv.status = "ACCEPTED"
    inv.accepted_at = _now()
    inv.accepted_user_id = user.id
    inv.project_id = project.id
    inv.project_name = name
    db.touch(inv)
    log_event(db, event_type="PROJECT_CREATED", actor_id=actor.id, project_id=project.id, target=name)
    log_event(db, event_type="CLIENT_INVITE_ACCEPTED", actor_id=actor.id, project_id=project.id, target=inv.email)
    notify(db, architect.id, "CLIENT_INVITE_ACCEPTED", f"{inv.email} joined {project.name}", project.id)
    notify(db, user.id, "PROJECT_ASSIGNED", f"You joined project {project.name}", project.id)
    db.commit()
    db.refresh(inv)
    db.refresh(project)
    return {"invitation": serialize_invitation(inv), "project": project_as_dict(project, db)}


def decline_invitation_id(db: Session, actor: Actor, invitation_id: str) -> dict:
    inv = db.get(Invitation, invitation_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    return _decline_invitation(db, actor, _refresh_invitation_status(db, inv))


def decline_invitation_token(db: Session, actor: Actor, token: str) -> dict:
    inv = _get_invitation_by_token(db, token)
    return _decline_invitation(db, actor, inv)


def decline_invitation_by_token_public(db: Session, token: str) -> dict:
    inv = _get_invitation_by_token(db, token)
    if inv.status == "EXPIRED":
        raise HTTPException(status.HTTP_410_GONE, "This invitation has expired")
    if inv.status == "ACCEPTED":
        raise HTTPException(status.HTTP_409_CONFLICT, "This invitation was already accepted")
    if inv.status != "PENDING":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot decline a {inv.status.lower()} invitation")
    inv.status = "DECLINED"
    db.touch(inv)
    log_event(db, event_type="CLIENT_INVITE_DECLINED", actor_id=None, target=inv.email)
    notify(db, inv.architect_id, "CLIENT_INVITE_DECLINED", f"{inv.email} declined an invitation", None)
    db.commit()
    db.refresh(inv)
    return serialize_invitation(inv)


def _decline_invitation(db: Session, actor: Actor, inv: Invitation) -> dict:
    if inv.status == "EXPIRED":
        raise HTTPException(status.HTTP_410_GONE, "This invitation has expired")
    if inv.status == "ACCEPTED":
        raise HTTPException(status.HTTP_409_CONFLICT, "This invitation was already accepted")
    if inv.status != "PENDING":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot decline a {inv.status.lower()} invitation")
    user = db.get(User, actor.id)
    if user is None or user.email.lower() != inv.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This invitation is for a different email")
    if user.role != "CLIENT":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a client account can decline this invitation")
    inv.status = "DECLINED"
    db.touch(inv)
    log_event(db, event_type="CLIENT_INVITE_DECLINED", actor_id=actor.id, target=inv.email)
    notify(db, inv.architect_id, "CLIENT_INVITE_DECLINED", f"{inv.email} declined an invitation", None)
    db.commit()
    db.refresh(inv)
    return serialize_invitation(inv)


def register_client_from_invite(db: Session, email: str, password: str, token: str, hash_password, full_name: str | None = None) -> dict:
    return complete_client_account(db, email, password, token, full_name)


def _require_legal_acceptance(accept_terms: bool, accept_privacy: bool) -> None:
    if not (accept_terms and accept_privacy):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "You must accept the Terms and Conditions and Privacy Policy to create an account.",
        )


def _stamp_legal_acceptance(user: User) -> None:
    now = _now()
    user.terms_accepted_at = now
    user.privacy_accepted_at = now


def complete_client_account(
    db: Session,
    email: str,
    password: str,
    token: str,
    full_name: str | None = None,
    *,
    accept_terms: bool = False,
    accept_privacy: bool = False,
) -> dict:
    inv = _get_invitation_by_token(db, token)
    if inv.status == "ACCEPTED":
        existing = db.query(User).filter(User.email == inv.email).one_or_none()
        if existing and existing.email == email.lower().strip():
            project = _project_for_accepted(db, inv)
            return {"user": existing, "project": project_as_dict(project, db) if project else None}
        raise HTTPException(status.HTTP_409_CONFLICT, "This invitation was already accepted")
    if inv.status == "EXPIRED":
        raise HTTPException(status.HTTP_410_GONE, "This invitation has expired")
    if inv.status != "PENDING":
        raise HTTPException(status.HTTP_409_CONFLICT, "Invitation is not pending")
    email = email.lower().strip()
    if email != inv.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Email does not match this invitation")
    name = (full_name or "").strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Full name is required")
    _require_legal_acceptance(accept_terms, accept_privacy)
    from .auth import provision_user
    from .db import supabase_enabled

    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None and inv.auth_user_id:
        user = db.get(User, inv.auth_user_id)
    if user is None:
        user = provision_user(db, email, password, "CLIENT", True)
    elif user.role != "CLIENT":
        raise HTTPException(status.HTTP_409_CONFLICT, "This email cannot be invited")
    else:
        if supabase_enabled():
            from supabase.auth import admin_update_password

            admin_update_password(user.id, password)
        else:
            from .auth import hash_password

            user.password_hash = hash_password(password)
        user.role = "CLIENT"
        user.approved = True
    user.full_name = name
    user.email = email
    _stamp_legal_acceptance(user)
    db.touch(user)
    db.flush()
    log_event(db, event_type="ACCOUNT_MODIFIED", actor_id=user.id, target=user.id, metadata={"created": True, "role": "CLIENT", "via": "invitation"})
    actor = Actor(id=user.id, role="CLIENT", approved=True)
    accepted = accept_invitation_token(db, actor, token)
    db.refresh(user)
    return {"user": user, "project": accepted.get("project")}


def list_architect_clients(db: Session, actor: Actor) -> list[dict]:
    if actor.role not in ("ARCHITECT", "MAIN_ADMIN", "IT_PERSONNEL"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot list clients")
    rows: list[dict] = []
    seen: set[tuple[str | None, str]] = set()
    invites = db.query(Invitation).filter(Invitation.architect_id == actor.id).order_by(Invitation.created_at.desc()).all()
    if actor.role in ("MAIN_ADMIN", "IT_PERSONNEL"):
        invites = db.query(Invitation).order_by(Invitation.created_at.desc()).all()
    for inv in invites:
        _refresh_invitation_status(db, inv)
        project = db.get(Project, inv.project_id) if inv.project_id else None
        user = db.get(User, inv.accepted_user_id) if inv.accepted_user_id else db.query(User).filter(User.email == inv.email).one_or_none()
        architect = db.get(User, inv.architect_id)
        key = (inv.project_id, inv.email)
        seen.add(key)
        rows.append({
            "email": inv.email,
            "full_name": user.full_name if user else None,
            "user_id": user.id if user else None,
            "architect_id": inv.architect_id,
            "architect_email": architect.email if architect else None,
            "project_id": inv.project_id,
            "project_name": project.name if project else inv.project_name,
            "invitation_status": inv.status,
            "project_status": project.status if project else None,
            "last_activity": (project.updated_at.isoformat() if project and project.updated_at else None),
            "created_at": (user.created_at.isoformat() if user and user.created_at else (inv.created_at.isoformat() if inv.created_at else None)),
            "invitation_id": inv.id,
        })
    for project in list_projects(db, actor):
        if not project.client_id:
            continue
        client = db.get(User, project.client_id)
        if client is None or (project.id, client.email) in seen:
            continue
        architect = db.get(User, project.architect_id) if project.architect_id else None
        rows.append({
            "email": client.email,
            "full_name": client.full_name,
            "user_id": client.id,
            "architect_id": project.architect_id,
            "architect_email": architect.email if architect else None,
            "project_id": project.id,
            "project_name": project.name,
            "invitation_status": None,
            "project_status": project.status,
            "last_activity": project.updated_at.isoformat() if project.updated_at else None,
            "created_at": client.created_at.isoformat() if client.created_at else None,
            "invitation_id": project.invitation_id,
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


def _can_review_applications(actor: Actor) -> bool:
    return actor.role in ("MAIN_ADMIN", "IT_PERSONNEL")


def serialize_architect_application(row: ArchitectApplication, token: str | None = None, email_sent: bool | None = None) -> dict:
    data = {
        "id": row.id,
        "email": row.email,
        "full_name": row.full_name,
        "information": row.information,
        "status": row.status,
        "invited_by": row.invited_by,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "rejection_reason": row.rejection_reason,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "accepted_user_id": row.accepted_user_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if email_sent is not None:
        data["email_sent"] = email_sent
    if token:
        data["token"] = token
        data["invite_url"] = f"/architect/complete/{token}"
    return data


def create_architect_application(db: Session, actor: Actor, email: str, full_name: str, information: str | None) -> dict:
    if actor.role != "MAIN_ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the main admin can invite architects")
    email = email.lower().strip()
    name = (full_name or "").strip()
    if not email or "@" not in email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A valid email is required")
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Name is required")
    if _email_already_registered(db, email):
        raise HTTPException(status.HTTP_409_CONFLICT, "This email cannot be invited")
    pending = (
        db.query(ArchitectApplication)
        .filter(ArchitectApplication.email == email, ArchitectApplication.status == "PENDING_APPROVAL")
        .one_or_none()
    )
    if pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "A pending architect request already exists for this email")
    row = ArchitectApplication(
        email=email,
        full_name=name,
        information=(information or "").strip() or None,
        status="PENDING_APPROVAL",
        invited_by=actor.id,
    )
    db.add(row)
    db.flush()
    log_event(db, event_type="ARCHITECT_APPLICATION_CREATED", actor_id=actor.id, target=email, metadata={"application_id": row.id})
    db.commit()
    db.refresh(row)
    return serialize_architect_application(row)


def list_architect_applications(db: Session, actor: Actor) -> list[dict]:
    if not _can_review_applications(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot list architect applications")
    rows = db.query(ArchitectApplication).order_by(ArchitectApplication.created_at.desc()).all()
    return [serialize_architect_application(row) for row in rows]


def approve_architect_application(db: Session, actor: Actor, application_id: str) -> dict:
    if actor.role not in ("IT_PERSONNEL", "MAIN_ADMIN"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot approve architect applications")
    row = db.get(ArchitectApplication, application_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if row.status != "PENDING_APPROVAL":
        raise HTTPException(status.HTTP_409_CONFLICT, "This request is not pending approval")
    if _email_already_registered(db, row.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "This email cannot be invited")
    token = secrets.token_urlsafe(32)
    row.status = "APPROVED"
    row.reviewed_by = actor.id
    row.reviewed_at = _now()
    row.token_hash = _hash_invite_token(token)
    row.expires_at = _now() + timedelta(days=INVITE_TTL_DAYS)
    db.touch(row)
    try:
        redirect = f"{mail.require_public_app_url()}/architect/complete/{token}"
        mail.send_auth_invite(row.email, redirect, {"role": "ARCHITECT", "application_id": row.id})
    except Exception as exc:
        row.status = "PENDING_APPROVAL"
        row.reviewed_by = None
        row.reviewed_at = None
        row.token_hash = None
        row.expires_at = None
        db.touch(row)
        db.commit()
        raise mail.invite_failed(exc) from exc
    log_event(db, event_type="ARCHITECT_APPLICATION_APPROVED", actor_id=actor.id, target=row.email)
    db.commit()
    db.refresh(row)
    return serialize_architect_application(row, token=token)


def reject_architect_application(db: Session, actor: Actor, application_id: str, reason: str | None) -> dict:
    if actor.role not in ("IT_PERSONNEL", "MAIN_ADMIN"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot reject architect applications")
    row = db.get(ArchitectApplication, application_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if row.status != "PENDING_APPROVAL":
        raise HTTPException(status.HTTP_409_CONFLICT, "This request is not pending approval")
    row.status = "REJECTED"
    row.reviewed_by = actor.id
    row.reviewed_at = _now()
    row.rejection_reason = (reason or "").strip() or None
    db.touch(row)
    log_event(db, event_type="ARCHITECT_APPLICATION_REJECTED", actor_id=actor.id, target=row.email)
    db.commit()
    db.refresh(row)
    email_sent = mail.send_application_rejection(row.email, row.full_name, row.rejection_reason)
    if not email_sent:
        logger.error("architect rejection email was not sent")
    return serialize_architect_application(row, email_sent=email_sent)


def _get_architect_application_by_token(db: Session, token: str) -> ArchitectApplication:
    if not token:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    row = db.query(ArchitectApplication).filter(ArchitectApplication.token_hash == _hash_invite_token(token)).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    if row.status == "APPROVED" and row.expires_at and _aware(row.expires_at) and _aware(row.expires_at) < _now():
        raise HTTPException(status.HTTP_410_GONE, "This invitation has expired")
    return row


def public_architect_application(db: Session, token: str) -> dict:
    row = _get_architect_application_by_token(db, token)
    return {
        "email": row.email,
        "full_name": row.full_name,
        "status": row.status,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }


def complete_architect_application(
    db: Session,
    token: str,
    password: str,
    *,
    accept_terms: bool = False,
    accept_privacy: bool = False,
) -> dict:
    row = _get_architect_application_by_token(db, token)
    if row.status == "COMPLETED":
        user = db.get(User, row.accepted_user_id) if row.accepted_user_id else db.query(User).filter(User.email == row.email).one_or_none()
        if user is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "This invitation was already used")
        return {"user": serialize_user(user)}
    if row.status != "APPROVED":
        raise HTTPException(status.HTTP_409_CONFLICT, "This invitation is not ready for account completion")
    _require_legal_acceptance(accept_terms, accept_privacy)
    from .auth import provision_user
    from .db import supabase_enabled

    user = db.query(User).filter(User.email == row.email).one_or_none()
    if user is None:
        user = provision_user(db, row.email, password, "ARCHITECT", True)
    else:
        if user.role != "ARCHITECT":
            raise HTTPException(status.HTTP_409_CONFLICT, "This email cannot be invited")
        if supabase_enabled():
            from supabase.auth import admin_update_password

            admin_update_password(user.id, password)
        else:
            from .auth import hash_password

            user.password_hash = hash_password(password)
        user.approved = True
        user.role = "ARCHITECT"
    user.full_name = row.full_name
    _stamp_legal_acceptance(user)
    db.touch(user)
    row.status = "COMPLETED"
    row.accepted_user_id = user.id
    db.touch(row)
    log_event(db, event_type="ARCHITECT_ACCOUNT_ACTIVATED", actor_id=user.id, target=user.email)
    db.commit()
    db.refresh(user)
    return {"user": serialize_user(user)}
