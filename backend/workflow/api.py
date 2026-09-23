"""Workflow HTTP API. Does not replace POST /api/generate/moe."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .audit import log_event
from .auth import actor_from, create_token, get_current_user, hash_password, verify_password
from .db import get_db
from .models import User
from .schemas import (
    AccountPatch,
    BriefBody,
    CommentBody,
    CommentPatch,
    DesignBody,
    InquiryCreate,
    InvitationCreate,
    LoginBody,
    ProjectAssign,
    ProjectCreate,
    RegisterBody,
    WorkingDesignBody,
)
from . import services as svc
from .permissions import can_manage_accounts
from .state import ROLES

router = APIRouter(prefix="/api", tags=["workflow"])


@router.post("/auth/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if user.role == "ARCHITECT" and not user.approved:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Architect account pending IT approval")
    log_event(db, event_type="LOGIN", actor_id=user.id, target=user.email)
    db.commit()
    return {"token": create_token(user), "user": svc.serialize_user(user)}


@router.post("/auth/signup")
def signup(body: RegisterBody, db: Session = Depends(get_db)):
    role = body.role.upper()
    if role not in ROLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid role")
    if role in ("MAIN_ADMIN", "IT_PERSONNEL"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin and IT accounts cannot self-register")
    email = body.email.lower().strip()
    if role == "CLIENT":
        if not body.invitation_token:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "A valid architect invitation is required")
        user = svc.register_client_from_invite(db, email, body.password, body.invitation_token, hash_password)
        return {"token": create_token(user), "user": svc.serialize_user(user)}
    if db.query(User).filter(User.email == email).one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    approved = False
    user = User(email=email, password_hash=hash_password(body.password), role=role, approved=approved)
    db.add(user)
    db.flush()
    log_event(db, event_type="ACCOUNT_MODIFIED", actor_id=user.id, target=user.id, metadata={"created": True, "role": role})
    db.commit()
    db.refresh(user)
    return {"user": svc.serialize_user(user), "message": "Architect account created. Wait for IT approval before logging in."}


@router.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return svc.serialize_user(user)


@router.get("/projects")
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [svc.project_as_dict(p, db) for p in svc.list_projects(db, actor_from(user))]


@router.post("/projects")
def create_project(body: ProjectCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = svc.create_project(db, actor_from(user), body.name, body.client_id, body.architect_id)
    return svc.project_as_dict(project, db)


@router.get("/projects/{project_id}")
def get_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.project_detail(db, actor_from(user), project_id)


@router.put("/projects/{project_id}/assign")
def assign(project_id: str, body: ProjectAssign, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = svc.assign_project(db, actor_from(user), project_id, body.client_id, body.architect_id)
    return svc.project_as_dict(project, db)


@router.put("/projects/{project_id}/brief")
def put_brief(project_id: str, body: BriefBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    brief = svc.save_brief(db, actor_from(user), project_id, body.questionnaire, body.specification)
    return {"id": brief.id, "project_id": brief.project_id}


@router.get("/projects/{project_id}/brief")
def get_brief(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.get_brief(db, actor_from(user), project_id)


@router.post("/projects/{project_id}/generate")
def generate(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.generate_candidates(db, actor_from(user), project_id)


@router.get("/projects/{project_id}/candidates")
def candidates(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_candidates(db, actor_from(user), project_id)


@router.post("/projects/{project_id}/candidates/{candidate_id}/select")
def select_candidate(project_id: str, candidate_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cand = svc.select_candidate(db, actor_from(user), project_id, candidate_id)
    return {"id": cand.id, "selected_by_client": cand.selected_by_client}


@router.post("/projects/{project_id}/candidates/{candidate_id}/accept")
def accept_candidate(project_id: str, candidate_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rev = svc.accept_candidate(db, actor_from(user), project_id, candidate_id)
    return svc.serialize_revision(rev, current_id=rev.id, include_payload=True)


@router.get("/projects/{project_id}/revisions")
def revisions(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_revisions(db, actor_from(user), project_id)


@router.get("/revisions/{revision_id}")
def get_revision(revision_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.get_revision(db, actor_from(user), revision_id)


@router.put("/revisions/{revision_id}/design")
def put_design(revision_id: str, body: DesignBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rev = svc.update_design(
        db, actor_from(user), revision_id, body.floor_plan, body.expected_revision_id, body.scene_document,
    )
    return svc.serialize_revision(rev, current_id=rev.id, include_payload=True)


@router.put("/projects/{project_id}/working-design")
def put_working_design(project_id: str, body: WorkingDesignBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.update_working_design(db, actor_from(user), project_id, body.scene_document)


@router.post("/projects/{project_id}/comments")
def post_comment(project_id: str, body: CommentBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = svc.add_comment(
        db, actor_from(user), project_id, body.body, body.revision_id, body.object_id, body.stage, body.x, body.y,
    )
    return svc.serialize_comment(c, db)


@router.get("/projects/{project_id}/comments")
def comments(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_comments(db, actor_from(user), project_id)


@router.patch("/projects/{project_id}/comments/{comment_id}")
def patch_comment(project_id: str, comment_id: str, body: CommentPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = svc.update_comment(db, actor_from(user), project_id, comment_id, body.model_dump(exclude_unset=True))
    return svc.serialize_comment(c, db)


@router.delete("/projects/{project_id}/comments/{comment_id}")
def remove_comment(project_id: str, comment_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.delete_comment(db, actor_from(user), project_id, comment_id)
    return {"ok": True}


@router.post("/projects/{project_id}/submit-review")
def submit_review(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.project_as_dict(svc.submit_review(db, actor_from(user), project_id))


@router.post("/projects/{project_id}/request-revision")
def request_revision(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.project_as_dict(svc.request_revision(db, actor_from(user), project_id))


@router.post("/projects/{project_id}/resume")
def resume(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.project_as_dict(svc.resume_after_revision(db, actor_from(user), project_id))


@router.post("/projects/{project_id}/client-approve")
def client_approve(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.serialize_approval(svc.client_approve(db, actor_from(user), project_id))


@router.post("/projects/{project_id}/architect-approve")
def architect_approve(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.project_as_dict(svc.architect_approve(db, actor_from(user), project_id))


@router.post("/projects/{project_id}/publish")
def publish(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rev = svc.publish_project(db, actor_from(user), project_id)
    return svc.serialize_revision(rev, current_id=rev.id, include_payload=True)


@router.get("/notifications")
def notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_notifications(db, actor_from(user))


@router.post("/notifications/{notification_id}/read")
def read_notification(notification_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.mark_notification_read(db, actor_from(user), notification_id)
    return {"ok": True}


@router.get("/audit")
def audit(
    project_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.list_audit(db, actor_from(user), project_id)


@router.get("/accounts")
def accounts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_users(db, actor_from(user))


@router.patch("/accounts/{user_id}")
def patch_account(user_id: str, body: AccountPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not can_manage_accounts(actor_from(user)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot manage accounts")
    updated = svc.patch_account(db, actor_from(user), user_id, body.approved, body.role)
    return svc.serialize_user(updated)


@router.post("/projects/{project_id}/invitations")
def create_invitation(project_id: str, body: InvitationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.create_invitation(db, actor_from(user), project_id, body.email, body.resend)


@router.get("/projects/{project_id}/invitations")
def list_invitations(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_project_invitations(db, actor_from(user), project_id)


@router.post("/invitations/{invitation_id}/cancel")
def cancel_invitation(invitation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.cancel_invitation(db, actor_from(user), invitation_id)


@router.get("/invitations/by-token/{token}")
def invitation_by_token(token: str, db: Session = Depends(get_db)):
    return svc.public_invitation(db, token)


@router.post("/invitations/by-token/{token}/accept")
def accept_invitation(token: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.accept_invitation_token(db, actor_from(user), token)


@router.get("/architect/clients")
def architect_clients(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_architect_clients(db, actor_from(user))


@router.post("/inquiries")
def post_inquiry(body: InquiryCreate, db: Session = Depends(get_db)):
    return svc.serialize_inquiry(svc.create_inquiry(db, body.name, body.email, body.message))


@router.get("/inquiries")
def get_inquiries(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_inquiries(db, actor_from(user))
