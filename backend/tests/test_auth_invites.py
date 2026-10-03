"""Invitation email + architect approval tests. Auth send is mocked."""
from __future__ import annotations

import os

os.environ["KIYUB_WORKFLOW_STUB_GENERATE"] = "1"
os.environ["KIYUB_WORKFLOW_MEMORY"] = "1"
os.environ["JWT_SECRET"] = "test-jwt-secret"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workflow import db as wfdb
from workflow.auth import provision_user
from workflow.seed import seed_users
from workflow.api import router
from workflow.models import ArchitectApplication, User
from workflow.services import _hash_invite_token

ACCEPT = {"accept_terms": True, "accept_privacy": True}


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, email: str, password: str) -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def tokens(client: TestClient) -> dict:
    return {
        "client": login(client, "client@kiyub.local", "clientpass"),
        "architect": login(client, "architect@kiyub.local", "architectpass"),
        "admin": login(client, "admin@kiyub.local", "adminpass"),
        "it": login(client, "it@kiyub.local", "itpass"),
    }


def test_client_invite_sends_email_and_creates_no_project(client, monkeypatch):
    calls: list[tuple] = []

    def fake_send(email, redirect_to, metadata=None):
        calls.append((email, redirect_to, metadata))
        return None

    monkeypatch.setattr("workflow.mail.send_auth_invite", fake_send)
    tok = tokens(client)
    h_arch = auth(tok["architect"]["token"])
    before = {p["id"] for p in client.get("/api/projects", headers=h_arch).json()}
    invited = client.post(
        "/api/invitations",
        json={"email": "fresh@kiyub.local", "project_name": "Mail lot"},
        headers=h_arch,
    )
    assert invited.status_code == 200, invited.text
    assert invited.json()["status"] == "PENDING"
    assert invited.json()["project_id"] is None
    after = {p["id"] for p in client.get("/api/projects", headers=h_arch).json()}
    assert after == before


def test_complete_account_creates_one_draft_project(client):
    tok = tokens(client)
    h_arch = auth(tok["architect"]["token"])
    invited = client.post(
        "/api/invitations",
        json={"email": "complete@kiyub.local", "project_name": "Complete lot"},
        headers=h_arch,
    )
    token = invited.json()["token"]
    first = client.post(
        "/api/auth/signup",
        json={
            "email": "complete@kiyub.local",
            "password": "completepass",
            **ACCEPT,
            "invitation_token": token,
            "full_name": "Complete Client",
            "role": "MAIN_ADMIN",
        },
    )
    assert first.status_code == 200, first.text
    user = first.json()["user"]
    project = first.json()["project"]
    assert user["role"] == "CLIENT"
    assert user["full_name"] == "Complete Client"
    assert project["status"] == "DRAFT"
    assert project["architect_id"] == tok["architect"]["user"]["id"]
    assert project["client_id"] == user["id"]
    assert project["invitation_id"] == invited.json()["id"]
    docs = client.get(f"/api/projects/{project['id']}", headers=auth(first.json()["token"])).json()
    assert docs["document"]["stage"] == "CLIENT_BRIEF"
    second = client.post(
        "/api/auth/signup",
        json={
            "email": "complete@kiyub.local",
            "password": "completepass",
            **ACCEPT,
            "invitation_token": token,
            "full_name": "Complete Client",
        },
    )
    assert second.status_code == 200
    assert second.json()["project"]["id"] == project["id"]
    listed = client.get("/api/projects", headers=auth(first.json()["token"])).json()
    assert sum(1 for p in listed if p["id"] == project["id"]) == 1
    used = client.get(f"/api/invitations/by-token/{token}")
    assert used.json()["status"] == "ACCEPTED"
    assert used.json()["needs_registration"] is False


def test_pending_invite_needs_registration_when_profile_exists(client):
    tok = tokens(client)
    invited = client.post(
        "/api/invitations",
        json={"email": "preexist@kiyub.local", "project_name": "Ghost lot"},
        headers=auth(tok["architect"]["token"]),
    )
    assert invited.status_code == 200, invited.text
    token = invited.json()["token"]
    db = wfdb.SessionLocal()
    try:
        provision_user(db, "preexist@kiyub.local", "ghostpass", "CLIENT", True)
        db.commit()
        assert db.query(User).filter(User.email == "preexist@kiyub.local").one_or_none() is not None
    finally:
        db.close()
    public = client.get(f"/api/invitations/by-token/{token}")
    assert public.status_code == 200
    assert public.json()["status"] == "PENDING"
    assert public.json()["needs_registration"] is False
    assert "existing_client" not in public.json()


def test_production_missing_public_app_url_rejects_invite(client, monkeypatch):
    monkeypatch.setattr("workflow.mail.supabase_enabled", lambda: True)
    monkeypatch.delenv("PUBLIC_APP_URL", raising=False)
    sent: list = []
    monkeypatch.setattr("workflow.mail.send_auth_invite", lambda *a, **k: sent.append(a))
    tok = tokens(client)
    r = client.post(
        "/api/invitations",
        json={"email": "prod-missing@kiyub.local", "project_name": "Prod missing"},
        headers=auth(tok["architect"]["token"]),
    )
    assert r.status_code == 503
    assert sent == []
    listed = client.get("/api/invitations", headers=auth(tok["architect"]["token"])).json()
    assert not any(i["email"] == "prod-missing@kiyub.local" for i in listed)


def test_production_localhost_public_app_url_rejects_invite(client, monkeypatch):
    monkeypatch.setattr("workflow.mail.supabase_enabled", lambda: True)
    monkeypatch.setenv("PUBLIC_APP_URL", "http://localhost:5173")
    sent: list = []
    monkeypatch.setattr("workflow.mail.send_auth_invite", lambda *a, **k: sent.append(a))
    tok = tokens(client)
    r = client.post(
        "/api/invitations",
        json={"email": "prod-local@kiyub.local", "project_name": "Prod local"},
        headers=auth(tok["architect"]["token"]),
    )
    assert r.status_code == 503
    assert sent == []


def test_memory_default_allows_localhost_invite(client, monkeypatch):
    monkeypatch.delenv("PUBLIC_APP_URL", raising=False)
    from workflow.mail import require_public_app_url

    assert require_public_app_url() == "http://localhost:5173"
    tok = tokens(client)
    invited = client.post(
        "/api/invitations",
        json={"email": "memory-local@kiyub.local", "project_name": "Memory lot"},
        headers=auth(tok["architect"]["token"]),
    )
    assert invited.status_code == 200, invited.text
    assert invited.json()["status"] == "PENDING"


def test_production_missing_public_app_url_rejects_architect_approve(client, monkeypatch):
    monkeypatch.setattr("workflow.mail.supabase_enabled", lambda: True)
    monkeypatch.delenv("PUBLIC_APP_URL", raising=False)
    sent: list = []
    monkeypatch.setattr("workflow.mail.send_auth_invite", lambda *a, **k: sent.append(a))
    tok = tokens(client)
    created = client.post(
        "/api/architect-applications",
        json={"email": "prod-arch@kiyub.local", "full_name": "Prod Arch", "information": "N/A"},
        headers=auth(tok["admin"]["token"]),
    )
    assert created.status_code == 200
    approved = client.post(
        f"/api/architect-applications/{created.json()['id']}/approve",
        headers=auth(tok["it"]["token"]),
    )
    assert approved.status_code == 503
    assert sent == []
    listed = client.get("/api/architect-applications", headers=auth(tok["it"]["token"])).json()
    row = next(item for item in listed if item["id"] == created.json()["id"])
    assert row["status"] == "PENDING_APPROVAL"


def test_existing_client_can_be_invited(client, monkeypatch):
    sent: list = []
    monkeypatch.setattr("workflow.mail.send_auth_invite", lambda *a, **k: sent.append(a) or None)
    tok = tokens(client)
    r = client.post(
        "/api/invitations",
        json={"email": "client@kiyub.local", "project_name": "Taken"},
        headers=auth(tok["architect"]["token"]),
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["existing_client"] is True
    assert payload["status"] == "PENDING"
    assert payload["project_id"] is None
    assert sent == []
    db = wfdb.SessionLocal()
    try:
        assert db.query(User).filter(User.email == "client@kiyub.local").count() == 1
    finally:
        db.close()
    public = client.get(f"/api/invitations/by-token/{payload['token']}")
    assert public.status_code == 200
    assert public.json()["needs_registration"] is False
    assert public.json()["project_name"] == "Taken"
    assert public.json()["architect_name"]
    assert "existing_client" not in public.json()
    listed = client.get("/api/invitations", headers=auth(tok["architect"]["token"])).json()
    assert any(i["email"] == "client@kiyub.local" and i["status"] == "PENDING" and i["project_name"] == "Taken" for i in listed)


def test_staff_email_cannot_be_invited_as_client(client):
    tok = tokens(client)
    r = client.post(
        "/api/invitations",
        json={"email": "architect@kiyub.local", "project_name": "Staff lot"},
        headers=auth(tok["architect"]["token"]),
    )
    assert r.status_code == 400


def test_wrong_email_cannot_complete_invite(client):
    tok = tokens(client)
    invited = client.post(
        "/api/invitations",
        json={"email": "target2@kiyub.local", "project_name": "Private"},
        headers=auth(tok["architect"]["token"]),
    )
    stolen = client.post(
        "/api/auth/signup",
        json={
            "email": "client@kiyub.local",
            "password": "clientpass",
            **ACCEPT,
            "invitation_token": invited.json()["token"],
            "full_name": "Wrong Person",
        },
    )
    assert stolen.status_code == 403
    public = client.get(f"/api/invitations/by-token/{invited.json()['token']}")
    assert public.json()["status"] == "PENDING"


def test_expired_invite_cannot_complete(client, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from workflow.models import Invitation

    tok = tokens(client)
    invited = client.post(
        "/api/invitations",
        json={"email": "expired@kiyub.local", "project_name": "Old"},
        headers=auth(tok["architect"]["token"]),
    )
    db = wfdb.SessionLocal()
    try:
        row = db.query(Invitation).filter(Invitation.email == "expired@kiyub.local").one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.touch(row)
        db.commit()
    finally:
        db.close()
    done = client.post(
        "/api/auth/signup",
        json={
            "email": "expired@kiyub.local",
            "password": "expiredpass",
            **ACCEPT,
            "invitation_token": invited.json()["token"],
            "full_name": "Expired",
        },
    )
    assert done.status_code == 410


def test_architect_application_approval_and_login(client, monkeypatch):
    sent: list[str] = []
    monkeypatch.setattr("workflow.mail.send_auth_invite", lambda email, redirect_to, metadata=None: sent.append(email) or None)
    tok = tokens(client)
    created = client.post(
        "/api/architect-applications",
        json={"email": "newarch@kiyub.local", "full_name": "New Architect", "information": "License 1"},
        headers=auth(tok["admin"]["token"]),
    )
    assert created.status_code == 200
    assert created.json()["status"] == "PENDING_APPROVAL"
    denied = client.post("/api/auth/login", json={"email": "newarch@kiyub.local", "password": "archpass"})
    assert denied.status_code == 401
    forbidden = client.post(
        f"/api/architect-applications/{created.json()['id']}/approve",
        headers=auth(tok["architect"]["token"]),
    )
    assert forbidden.status_code == 403
    client_forbidden = client.post(
        f"/api/architect-applications/{created.json()['id']}/approve",
        headers=auth(tok["client"]["token"]),
    )
    assert client_forbidden.status_code == 403
    approved = client.post(
        f"/api/architect-applications/{created.json()['id']}/approve",
        headers=auth(tok["it"]["token"]),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    assert sent == ["newarch@kiyub.local"]
    done = client.post(
        f"/api/architect-applications/by-token/{approved.json()['token']}/complete",
        json={"password": "archpass", "role": "IT_PERSONNEL", **ACCEPT},
    )
    assert done.status_code == 200
    assert done.json()["user"]["role"] == "ARCHITECT"
    session = login(client, "newarch@kiyub.local", "archpass")
    assert session["user"]["approved"] is True
    db = wfdb.SessionLocal()
    try:
        user = db.query(User).filter(User.email == "newarch@kiyub.local").one()
        assert user.role == "ARCHITECT"
        assert user.full_name == "New Architect"
    finally:
        db.close()


def test_architect_application_rejection(client, monkeypatch):
    notices: list[tuple] = []

    def fake_send(email, full_name=None, reason=None):
        notices.append((email, full_name, reason))
        return True

    monkeypatch.setattr("workflow.mail.send_application_rejection", fake_send)
    tok = tokens(client)
    created = client.post(
        "/api/architect-applications",
        json={"email": "rejectme@kiyub.local", "full_name": "Reject Me", "information": "N/A"},
        headers=auth(tok["admin"]["token"]),
    )
    client_forbidden = client.post(
        f"/api/architect-applications/{created.json()['id']}/reject",
        json={"reason": "no"},
        headers=auth(tok["client"]["token"]),
    )
    assert client_forbidden.status_code == 403
    architect_forbidden = client.post(
        f"/api/architect-applications/{created.json()['id']}/reject",
        json={"reason": "no"},
        headers=auth(tok["architect"]["token"]),
    )
    assert architect_forbidden.status_code == 403
    rejected = client.post(
        f"/api/architect-applications/{created.json()['id']}/reject",
        json={"reason": "Incomplete credentials"},
        headers=auth(tok["it"]["token"]),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["rejection_reason"] == "Incomplete credentials"
    assert rejected.json()["email_sent"] is True
    assert notices == [("rejectme@kiyub.local", "Reject Me", "Incomplete credentials")]
    leaked = "rejected-complete-token"
    db = wfdb.SessionLocal()
    try:
        assert db.query(User).filter(User.email == "rejectme@kiyub.local").one_or_none() is None
        row = db.get(ArchitectApplication, created.json()["id"])
        assert row.status == "REJECTED"
        row.token_hash = _hash_invite_token(leaked)
        db.touch(row)
        db.commit()
    finally:
        db.close()
    done = client.post(
        f"/api/architect-applications/by-token/{leaked}/complete",
        json={"password": "shouldfail", **ACCEPT},
    )
    assert done.status_code == 409


def test_architect_rejection_persists_when_email_fails(client, monkeypatch):
    monkeypatch.setattr("workflow.mail.send_application_rejection", lambda *a, **k: False)
    tok = tokens(client)
    created = client.post(
        "/api/architect-applications",
        json={"email": "noreply@kiyub.local", "full_name": "No Mail", "information": "N/A"},
        headers=auth(tok["admin"]["token"]),
    )
    rejected = client.post(
        f"/api/architect-applications/{created.json()['id']}/reject",
        json={"reason": "Missing documents"},
        headers=auth(tok["it"]["token"]),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["rejection_reason"] == "Missing documents"
    assert rejected.json()["email_sent"] is False


def test_rejection_mail_invokes_edge_function(monkeypatch):
    monkeypatch.setattr("workflow.mail.supabase_enabled", lambda: True)
    monkeypatch.setenv("REJECTION_MAIL_SECRET", "shared-secret")
    calls: list[tuple] = []

    class _Result:
        error = None

    class _Functions:
        def invoke(self, name, invoke_options=None):
            calls.append((name, invoke_options))
            return _Result()

    class _Client:
        functions = _Functions()

    monkeypatch.setattr("supabase.client.get_service_client", lambda: _Client())
    from workflow.mail import send_application_rejection

    assert send_application_rejection("a@b.com", "Ada", "Incomplete") is True
    assert calls[0][0] == "architect-rejection"
    assert calls[0][1]["body"] == {
        "email": "a@b.com",
        "full_name": "Ada",
        "rejection_reason": "Incomplete",
        "status": "REJECTED",
    }
    assert calls[0][1]["headers"]["x-rejection-secret"] == "shared-secret"


def test_admin_cannot_invite_existing_architect(client):
    tok = tokens(client)
    r = client.post(
        "/api/architect-applications",
        json={"email": "architect@kiyub.local", "full_name": "Taken", "information": ""},
        headers=auth(tok["admin"]["token"]),
    )
    assert r.status_code == 409


def test_client_cannot_create_architect_application(client):
    tok = tokens(client)
    r = client.post(
        "/api/architect-applications",
        json={"email": "nope@kiyub.local", "full_name": "Nope", "information": ""},
        headers=auth(tok["client"]["token"]),
    )
    assert r.status_code == 403


def test_signup_without_invitation_is_forbidden(client):
    r = client.post("/api/auth/signup", json={"email": "free@kiyub.local", "password": "freepass", "role": "ARCHITECT"})
    assert r.status_code == 403


import pytest


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
