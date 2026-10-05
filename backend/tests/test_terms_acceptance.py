"""Terms/Privacy acceptance is required at account creation only, never at login."""
from __future__ import annotations

import os

os.environ["KIYUB_WORKFLOW_STUB_GENERATE"] = "1"
os.environ["KIYUB_WORKFLOW_MEMORY"] = "1"
os.environ["JWT_SECRET"] = "test-jwt-secret"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from workflow import db as wfdb
from workflow.api import router
from workflow.models import User
from workflow.seed import SEED_USERS, seed_users
from tests.test_workflow import auth, ids, login

DENIED = "You must accept the Terms and Conditions and Privacy Policy to create an account."


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("workflow.mail.send_auth_invite", lambda email, redirect_to, metadata=None: None)
    wfdb.reset_store()
    wfdb.init_db()
    db = wfdb.SessionLocal()
    seed_users(db)
    db.close()
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def _user(email: str) -> User | None:
    db = wfdb.SessionLocal()
    try:
        return db.query(User).filter(User.email == email).one_or_none()
    finally:
        db.close()


def _invite(client: TestClient, email: str) -> str:
    tok = ids(client)
    r = client.post(
        "/api/invitations",
        json={"email": email, "project_name": "Terms lot"},
        headers=auth(tok["architect"]["token"]),
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _approved_architect_token(client: TestClient, email: str) -> str:
    tok = ids(client)
    created = client.post(
        "/api/architect-applications",
        json={"email": email, "full_name": "Terms Architect"},
        headers=auth(tok["admin"]["token"]),
    )
    assert created.status_code == 200, created.text
    assert created.json()["status"] == "APPROVED"
    return created.json()["token"]


def _signup(client: TestClient, email: str, token: str, **flags):
    return client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "termspass",
            "invitation_token": token,
            "full_name": "Terms Client",
            **flags,
        },
    )


@pytest.mark.parametrize(
    "flags",
    [{}, {"accept_terms": True}, {"accept_privacy": True}, {"accept_terms": False, "accept_privacy": False}],
)
def test_client_signup_requires_both_acceptances(client, flags):
    email = "noterms@kiyub.local"
    token = _invite(client, email)
    r = _signup(client, email, token, **flags)
    assert r.status_code == 400
    assert r.json()["detail"] == DENIED
    assert client.get(f"/api/invitations/by-token/{token}").json()["status"] == "PENDING"
    assert client.post("/api/auth/login", json={"email": email, "password": "termspass"}).status_code == 401


def test_client_signup_with_acceptance_persists_timestamps(client):
    email = "terms@kiyub.local"
    token = _invite(client, email)
    r = _signup(client, email, token, accept_terms=True, accept_privacy=True)
    assert r.status_code == 200, r.text
    assert r.json()["project"] is not None
    user = _user(email)
    assert user.terms_accepted_at is not None
    assert user.privacy_accepted_at is not None


def test_architect_complete_requires_both_acceptances(client):
    email = "archnoterms@kiyub.local"
    token = _approved_architect_token(client, email)
    r = client.post(f"/api/architect-applications/by-token/{token}/complete", json={"password": "archpass"})
    assert r.status_code == 400
    assert r.json()["detail"] == DENIED
    assert client.get(f"/api/architect-applications/by-token/{token}").json()["status"] == "APPROVED"
    assert client.post("/api/auth/login", json={"email": email, "password": "archpass"}).status_code == 401


def test_architect_complete_with_acceptance_persists_timestamps(client):
    email = "archterms@kiyub.local"
    token = _approved_architect_token(client, email)
    r = client.post(
        f"/api/architect-applications/by-token/{token}/complete",
        json={"password": "archpass", "accept_terms": True, "accept_privacy": True},
    )
    assert r.status_code == 200, r.text
    user = _user(email)
    assert user.terms_accepted_at is not None
    assert user.privacy_accepted_at is not None
    assert login(client, email, "archpass")["user"]["role"] == "ARCHITECT"


def test_existing_accounts_log_in_repeatedly_without_acceptance(client):
    for email, password, _role, _approved in SEED_USERS:
        assert _user(email).terms_accepted_at is not None
        first = login(client, email, password)
        second = login(client, email, password)
        assert first["user"]["email"] == second["user"]["email"] == email


def test_login_ignores_missing_acceptance_values(client):
    db = wfdb.SessionLocal()
    user = db.query(User).filter(User.email == "client@kiyub.local").one()
    user.terms_accepted_at = None
    user.privacy_accepted_at = None
    db.touch(user)
    db.commit()
    db.close()
    assert login(client, "client@kiyub.local", "clientpass")["user"]["role"] == "CLIENT"
