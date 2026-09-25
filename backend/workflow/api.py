"""Workflow HTTP API. Does not replace POST /api/generate/moe."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from .audit import log_event
from .auth import account_block_reason, actor_from, get_current_user, issue_session_token, verify_password
from .db import get_db, supabase_enabled
from .models import User
from .repositories.base import MemoryStore as Session
from .schemas import (
    AccountPatch,
    ArchitectApplicationComplete,
    ArchitectApplicationCreate,
    ArchitectApplicationReject,
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
    SubmitReviewBody,
    WorkingDesignBody,
)
from . import services as svc
from .permissions import can_manage_accounts

router = APIRouter(prefix="/api", tags=["workflow"])


@router.post("/auth/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    if supabase_enabled():
        from supabase.auth import sign_in_password

        token, user_id = sign_in_password(email, body.password)
        user = db.get(User, user_id) or db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
        blocked = account_block_reason(user)
        if blocked:
            raise HTTPException(status.HTTP_403_FORBIDDEN, blocked)
        log_event(db, event_type="LOGIN", actor_id=user.id, target=user.email)
        db.commit()
        return {"token": token, "user": svc.serialize_user(user)}
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    blocked = account_block_reason(user)
    if blocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, blocked)
    log_event(db, event_type="LOGIN", actor_id=user.id, target=user.email)
    db.commit()
    return {"token": issue_session_token(user), "user": svc.serialize_user(user)}


@router.post("/auth/signup")
def signup(body: RegisterBody, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    if body.invitation_token:
        result = svc.complete_client_account(db, email, body.password, body.invitation_token, body.full_name)
        user = result["user"]
        return {
            "token": issue_session_token(user, body.password),
            "user": svc.serialize_user(user),
            "project": result.get("project"),
        }
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Accounts are created by invitation")


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
def submit_review(
    project_id: str,
    body: SubmitReviewBody | None = Body(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.submit_review(
        db,
        actor_from(user),
        project_id,
        scene_document=body.scene_document if body else None,
        floor_plan=body.floor_plan if body else None,
    )


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


@router.post("/notifications/read-all")
def read_all_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count = svc.mark_all_notifications_read(db, actor_from(user))
    return {"ok": True, "count": count}


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
    updated = svc.patch_account(db, actor_from(user), user_id, body.approved, body.role, body.suspended)
    return svc.serialize_user(updated)


@router.delete("/accounts/{user_id}")
def delete_account(user_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    updated = svc.soft_delete_account(db, actor_from(user), user_id)
    return svc.serialize_user(updated)


@router.post("/invitations")
def create_invitation(body: InvitationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.create_client_invitation(db, actor_from(user), body.email, body.project_name, body.resend)


@router.get("/invitations")
def list_my_invitations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_invitations(db, actor_from(user))


@router.post("/projects/{project_id}/invitations")
def create_project_invitation(project_id: str, body: InvitationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.create_invitation(db, actor_from(user), project_id, body.email, body.resend)


@router.get("/projects/{project_id}/invitations")
def list_invitations(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_project_invitations(db, actor_from(user), project_id)


@router.post("/invitations/{invitation_id}/cancel")
def cancel_invitation(invitation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.cancel_invitation(db, actor_from(user), invitation_id)


@router.post("/invitations/{invitation_id}/accept")
def accept_invitation_id(invitation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.accept_invitation_id(db, actor_from(user), invitation_id)


@router.post("/invitations/{invitation_id}/decline")
def decline_invitation_id(invitation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.decline_invitation_id(db, actor_from(user), invitation_id)


@router.get("/invitations/by-token/{token}")
def invitation_by_token(token: str, db: Session = Depends(get_db)):
    return svc.public_invitation(db, token)


@router.post("/invitations/by-token/{token}/accept")
def accept_invitation(token: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.accept_invitation_token(db, actor_from(user), token)


@router.post("/invitations/by-token/{token}/decline")
def decline_invitation(token: str, db: Session = Depends(get_db)):
    return svc.decline_invitation_by_token_public(db, token)


@router.get("/architect/clients")
def architect_clients(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_architect_clients(db, actor_from(user))


@router.post("/inquiries")
def post_inquiry(body: InquiryCreate, db: Session = Depends(get_db)):
    return svc.serialize_inquiry(svc.create_inquiry(db, body.name, body.email, body.message))


@router.get("/inquiries")
def get_inquiries(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_inquiries(db, actor_from(user))


@router.post("/architect-applications")
def create_architect_application(body: ArchitectApplicationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.create_architect_application(db, actor_from(user), body.email, body.full_name, body.information)


@router.get("/architect-applications")
def list_architect_applications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_architect_applications(db, actor_from(user))


@router.post("/architect-applications/{application_id}/approve")
def approve_architect_application(application_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.approve_architect_application(db, actor_from(user), application_id)


@router.post("/architect-applications/{application_id}/reject")
def reject_architect_application(application_id: str, body: ArchitectApplicationReject, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.reject_architect_application(db, actor_from(user), application_id, body.reason)


@router.get("/architect-applications/by-token/{token}")
def architect_application_by_token(token: str, db: Session = Depends(get_db)):
    return svc.public_architect_application(db, token)


@router.post("/architect-applications/by-token/{token}/complete")
def complete_architect_application(token: str, body: ArchitectApplicationComplete, db: Session = Depends(get_db)):
    result = svc.complete_architect_application(db, token, body.password)
    user = db.get(User, result["user"]["id"])
    return {
        "token": issue_session_token(user, body.password) if user else None,
        "user": result["user"],
    }
