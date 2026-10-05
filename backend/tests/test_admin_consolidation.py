"""Admin owns every former IT Personnel capability, views canvases read-only, and the retired role stays dead."""
from __future__ import annotations

import os

os.environ["KIYUB_WORKFLOW_STUB_GENERATE"] = "1"
os.environ["KIYUB_WORKFLOW_MEMORY"] = "1"
os.environ["JWT_SECRET"] = "test-jwt-secret"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from workflow import db as wfdb
from workflow import permissions as perm
from workflow.api import router
from workflow.auth import STUDIO_API_ROLES, hash_password
from workflow.models import ArchitectApplication, AuditEvent, HistoricalActor, User
from workflow.seed import seed_users
from workflow.state import HISTORICAL_ROLES, ROLES
from tests.test_workflow import (
    ACCEPT,
    auth,
    generate,
    ids,
    login,
    post_architect_review,
    provision,
    review_scene,
    save_working,
)


@pytest.fixture
def client():
    wfdb.reset_store()
    wfdb.init_db()
    db = wfdb.SessionLocal()
    seed_users(db)
    db.close()
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def _set_role(email: str, role: str) -> None:
    db = wfdb.SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.role = role
        db.add(user)
        db.commit()
    finally:
        db.close()


def _drafted_project(client: TestClient) -> dict:
    """Assigned project with AI candidates, a submitted revision, and a newer unsubmitted working draft."""
    ctx = provision(client)
    gen = generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    submitted = post_architect_review(client, pid, h_arch, review_scene("Submitted"))
    assert submitted.status_code == 200, submitted.text
    assert save_working(client, pid, h_arch, review_scene("Draft", 4.0)).status_code == 200
    comment = client.post(f"/api/projects/{pid}/comments", json={"body": "Check the stair"}, headers=h_arch)
    assert comment.status_code == 200, comment.text
    ctx.update(
        pid=pid,
        candidate_id=gen["candidates"][0]["id"],
        revision_id=submitted.json()["submitted_revision_id"],
        comment_id=comment.json()["id"],
    )
    return ctx


def test_role_model_is_exactly_three_roles():
    assert ROLES == ("CLIENT", "ARCHITECT", "ADMIN")
    assert "IT_PERSONNEL" in HISTORICAL_ROLES
    assert STUDIO_API_ROLES == {"ADMIN"}
    assert not hasattr(perm, "IT_PERSONNEL")
    assert not hasattr(perm, "MAIN_ADMIN")


def test_seed_has_no_it_account(client):
    r = client.post("/api/auth/login", json={"email": "it@kiyub.local", "password": "itpass"})
    assert r.status_code == 401
    admin = login(client, "admin@kiyub.local", "adminpass")
    assert admin["user"]["role"] == "ADMIN"


def test_admin_onboards_architect_in_one_step(client):
    tok = ids(client)
    created = client.post(
        "/api/architect-applications",
        json={"email": "newarch@kiyub.local", "full_name": "New Architect", "information": ""},
        headers=auth(tok["admin"]["token"]),
    )
    assert created.status_code == 200, created.text
    assert created.json()["status"] == "APPROVED"
    done = client.post(
        f"/api/architect-applications/by-token/{created.json()['token']}/complete",
        json={"password": "newarchpass", **ACCEPT},
    )
    assert done.status_code == 200, done.text
    assert login(client, "newarch@kiyub.local", "newarchpass")["user"]["role"] == "ARCHITECT"
    types = {e["event_type"] for e in client.get("/api/audit", headers=auth(tok["admin"]["token"])).json()}
    assert {"ARCHITECT_APPLICATION_CREATED", "ARCHITECT_APPLICATION_APPROVED"} <= types


def test_admin_reviews_legacy_pending_requests(client):
    tok = ids(client)
    db = wfdb.SessionLocal()
    try:
        approve_row = ArchitectApplication(email="a1@kiyub.local", full_name="A1", information="", invited_by=tok["admin"]["user"]["id"])
        reject_row = ArchitectApplication(email="a2@kiyub.local", full_name="A2", information="", invited_by=tok["admin"]["user"]["id"])
        db.add(approve_row)
        db.add(reject_row)
        db.commit()
        approve_id, reject_id = approve_row.id, reject_row.id
    finally:
        db.close()
    h_admin = auth(tok["admin"]["token"])
    listed = client.get("/api/architect-applications", headers=h_admin)
    assert listed.status_code == 200
    assert {approve_id, reject_id} <= {row["id"] for row in listed.json()}
    assert client.post(f"/api/architect-applications/{approve_id}/approve", headers=h_admin).status_code == 200
    rejected = client.post(f"/api/architect-applications/{reject_id}/reject", json={"reason": "Incomplete"}, headers=h_admin)
    assert rejected.status_code == 200, rejected.text


def test_admin_account_management(client):
    tok = ids(client)
    h_admin = auth(tok["admin"]["token"])
    arch_id = tok["architect"]["user"]["id"]
    assert client.get("/api/accounts", headers=h_admin).status_code == 200
    assert client.patch(f"/api/accounts/{arch_id}", json={"suspended": True}, headers=h_admin).status_code == 200
    assert client.patch(f"/api/accounts/{arch_id}", json={"suspended": False}, headers=h_admin).status_code == 200
    assert client.patch(f"/api/accounts/{arch_id}", json={"suspended": True}, headers=h_admin).status_code == 200
    deleted = client.delete(f"/api/accounts/{arch_id}", headers=h_admin)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted_at"]


@pytest.mark.parametrize("role", ["IT_PERSONNEL", "MAIN_ADMIN", "SUPERUSER"])
def test_admin_cannot_assign_retired_or_unknown_role(client, role):
    tok = ids(client)
    arch_id = tok["architect"]["user"]["id"]
    r = client.patch(f"/api/accounts/{arch_id}", json={"role": role}, headers=auth(tok["admin"]["token"]))
    assert r.status_code == 400


def test_admin_sees_inquiries_clients_and_full_audit(client):
    ctx = provision(client)
    h_admin = auth(ctx["tokens"]["admin"]["token"])
    assert client.post("/api/inquiries", json={"name": "Ada", "email": "ada@example.com", "message": "Hi"}).status_code == 200
    assert client.get("/api/inquiries", headers=h_admin).status_code == 200
    assert client.get("/api/architect/clients", headers=h_admin).status_code == 200
    invites = client.get("/api/invitations", headers=h_admin)
    assert invites.status_code == 200
    assert invites.json()
    audit = client.get("/api/audit", headers=h_admin)
    assert audit.status_code == 200
    assert {"LOGIN", "PROJECT_CREATED"} <= {e["event_type"] for e in audit.json()}


def test_admin_assigns_projects(client):
    ctx = provision(client)
    pid = ctx["project"]["id"]
    arch_id = ctx["tokens"]["architect"]["user"]["id"]
    r = client.put(f"/api/projects/{pid}/assign", json={"architect_id": arch_id}, headers=auth(ctx["tokens"]["admin"]["token"]))
    assert r.status_code == 200, r.text
    denied = client.put(f"/api/projects/{pid}/assign", json={"architect_id": arch_id}, headers=auth(ctx["tokens"]["client"]["token"]))
    assert denied.status_code == 403


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/inquiries"),
        ("get", "/api/architect-applications"),
        ("post", "/api/architect-applications"),
    ],
)
def test_architect_and_client_denied_admin_endpoints(client, method, path):
    tok = ids(client)
    body = {"email": "x@kiyub.local", "full_name": "X", "information": ""}
    for role in ("architect", "client"):
        kwargs = {"headers": auth(tok[role]["token"])}
        if method == "post":
            kwargs["json"] = body
        r = getattr(client, method)(path, **kwargs)
        assert r.status_code == 403, (role, path, r.text)


def test_only_admin_sees_every_account(client):
    tok = ids(client)
    assert client.get("/api/accounts", headers=auth(tok["client"]["token"])).status_code == 403
    scoped = client.get("/api/accounts", headers=auth(tok["architect"]["token"]))
    assert scoped.status_code == 200
    assert all(u["role"] == "CLIENT" for u in scoped.json())
    everyone = client.get("/api/accounts", headers=auth(tok["admin"]["token"])).json()
    assert {u["role"] for u in everyone} == {"ADMIN", "ARCHITECT", "CLIENT"}


def test_admin_views_working_draft_and_revisions(client):
    ctx = _drafted_project(client)
    pid = ctx["pid"]
    h_admin = auth(ctx["tokens"]["admin"]["token"])
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    detail = client.get(f"/api/projects/{pid}", headers=h_admin)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["document"]["working_scene_document"]["rooms"][0]["name"] == "Draft"
    assert body["permissions"]["canViewDrafts"] is True
    assert body["permissions"]["canEditDesign"] is False
    admin_revs = client.get(f"/api/projects/{pid}/revisions", headers=h_admin)
    arch_revs = client.get(f"/api/projects/{pid}/revisions", headers=h_arch)
    assert admin_revs.status_code == 200
    assert {r["id"] for r in admin_revs.json()} == {r["id"] for r in arch_revs.json()}
    assert client.get(f"/api/revisions/{ctx['revision_id']}", headers=h_admin).status_code == 200
    assert client.get(f"/api/projects/{pid}/comments", headers=h_admin).status_code == 200
    assert client.get(f"/api/projects/{pid}/activity", headers=h_admin).status_code == 200


def test_admin_cannot_mutate_canvas_or_workflow(client):
    ctx = _drafted_project(client)
    pid = ctx["pid"]
    h_admin = auth(ctx["tokens"]["admin"]["token"])
    attempts = [
        save_working(client, pid, h_admin, review_scene("Admin edit")),
        client.post(f"/api/projects/{pid}/generate", headers=h_admin),
        client.post(f"/api/projects/{pid}/candidates/{ctx['candidate_id']}/select", headers=h_admin),
        client.post(f"/api/projects/{pid}/comments", json={"body": "Admin note"}, headers=h_admin),
        client.post(f"/api/projects/{pid}/comments/{ctx['comment_id']}/resolve", json={}, headers=h_admin),
        post_architect_review(client, pid, h_admin, review_scene("Admin submit")),
        client.post(f"/api/projects/{pid}/client-approve", headers=h_admin),
        client.post(f"/api/projects/{pid}/architect-approve", headers=h_admin),
        client.post(f"/api/projects/{pid}/publish", headers=h_admin),
        client.post(f"/api/revisions/{ctx['revision_id']}/restore", headers=h_admin),
        client.put(f"/api/projects/{pid}/brief", json={"questionnaire": {}, "specification": {}}, headers=h_admin),
    ]
    for r in attempts:
        assert r.status_code == 403, (r.request.method, r.request.url.path, r.status_code, r.text)
    after = client.get(f"/api/projects/{pid}", headers=h_admin).json()
    assert after["document"]["working_scene_document"]["rooms"][0]["name"] == "Draft"


def test_architect_and_client_keep_their_capabilities(client):
    ctx = _drafted_project(client)
    pid = ctx["pid"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    assert save_working(client, pid, h_arch, review_scene("Arch again")).status_code == 200
    assert client.post(f"/api/projects/{pid}/comments", json={"body": "Client note"}, headers=h_cli).status_code == 200
    assert save_working(client, pid, h_cli, review_scene("Client edit")).status_code == 403


def test_retired_role_cannot_log_in(client):
    db = wfdb.SessionLocal()
    try:
        db.add(User(email="legacy-it@kiyub.local", password_hash=hash_password("itpass"), role="IT_PERSONNEL"))
        db.commit()
    finally:
        db.close()
    r = client.post("/api/auth/login", json={"email": "legacy-it@kiyub.local", "password": "itpass"})
    assert r.status_code == 403
    assert "no longer supported" in r.json()["detail"]


def test_retired_role_session_is_rejected(client):
    tok = ids(client)
    _set_role("architect@kiyub.local", "IT_PERSONNEL")
    h = auth(tok["architect"]["token"])
    assert client.get("/api/auth/me", headers=h).status_code == 403
    assert client.get("/api/accounts", headers=h).status_code == 403
    assert client.get("/api/projects", headers=h).status_code == 403


def test_audit_keeps_deleted_it_actor_identity(client):
    tok = ids(client)
    db = wfdb.SessionLocal()
    try:
        ghost = HistoricalActor(email="it@kiyub.local", full_name="IT Desk", role="IT_PERSONNEL")
        db.add(ghost)
        db.add(AuditEvent(actor_id=ghost.id, event_type="ARCHITECT_APPLICATION_APPROVED", target="old@kiyub.local"))
        db.commit()
        ghost_id = ghost.id
    finally:
        db.close()
    rows = client.get("/api/audit", headers=auth(tok["admin"]["token"])).json()
    event = next(e for e in rows if e["actor_id"] == ghost_id)
    assert event["actor_email"] == "it@kiyub.local"
    assert event["actor_role"] == "IT_PERSONNEL"
    assert event["actor_deleted"] is True
    live = next(e for e in rows if e["actor_id"] == tok["admin"]["user"]["id"])
    assert live["actor_role"] == "ADMIN"
    assert live["actor_deleted"] is False
