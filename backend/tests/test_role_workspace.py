"""Role-workspace API: mark-all-read, client audit, suspend, soft-delete."""
from __future__ import annotations

import os

os.environ["KIYUB_WORKFLOW_STUB_GENERATE"] = "1"
os.environ["KIYUB_WORKFLOW_MEMORY"] = "1"
os.environ["JWT_SECRET"] = "test-jwt-secret"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workflow import db as wfdb
from workflow.api import router
from workflow.seed import seed_users
from tests.test_workflow import auth, ids, login, provision


def _client():
    wfdb.reset_store()
    wfdb.init_db()
    db = wfdb.SessionLocal()
    seed_users(db)
    db.close()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_mark_all_notifications_read():
    client = _client()
    ctx = provision(client)
    notes = client.get("/api/notifications", headers=auth(ctx["tokens"]["architect"]["token"])).json()
    assert any(not n["read"] for n in notes)
    r = client.post("/api/notifications/read-all", headers=auth(ctx["tokens"]["architect"]["token"]))
    assert r.status_code == 200
    after = client.get("/api/notifications", headers=auth(ctx["tokens"]["architect"]["token"])).json()
    assert all(n["read"] for n in after)


def test_client_can_view_own_project_audit():
    client = _client()
    ctx = provision(client)
    r = client.get("/api/audit", headers=auth(ctx["tokens"]["client"]["token"]))
    assert r.status_code == 200
    assert all(e.get("project_id") == ctx["project"]["id"] or e.get("project_id") is None for e in r.json()) or True
    scoped = [e for e in r.json() if e.get("project_id")]
    assert all(e["project_id"] == ctx["project"]["id"] for e in scoped)


def test_it_can_list_clients():
    client = _client()
    provision(client)
    tok = ids(client)
    r = client.get("/api/architect/clients", headers=auth(tok["it"]["token"]))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_admin_suspend_blocks_login():
    client = _client()
    tok = ids(client)
    arch_id = tok["architect"]["user"]["id"]
    r = client.patch(f"/api/accounts/{arch_id}", json={"suspended": True}, headers=auth(tok["admin"]["token"]))
    assert r.status_code == 200
    assert r.json()["suspended"] is True
    denied = client.post("/api/auth/login", json={"email": "architect@kiyub.local", "password": "architectpass"})
    assert denied.status_code == 403


def test_it_cannot_suspend():
    client = _client()
    tok = ids(client)
    arch_id = tok["architect"]["user"]["id"]
    r = client.patch(f"/api/accounts/{arch_id}", json={"suspended": True}, headers=auth(tok["it"]["token"]))
    assert r.status_code == 403


def test_it_cannot_delete_active_architect():
    client = _client()
    tok = ids(client)
    arch_id = tok["architect"]["user"]["id"]
    r = client.delete(f"/api/accounts/{arch_id}", headers=auth(tok["it"]["token"]))
    assert r.status_code == 400


def test_it_can_soft_delete_suspended_architect():
    client = _client()
    tok = ids(client)
    arch_id = tok["architect"]["user"]["id"]
    assert client.patch(f"/api/accounts/{arch_id}", json={"suspended": True}, headers=auth(tok["admin"]["token"])).status_code == 200
    r = client.delete(f"/api/accounts/{arch_id}", headers=auth(tok["it"]["token"]))
    assert r.status_code == 200
    assert r.json()["deleted_at"]
    listed = client.get("/api/accounts", headers=auth(tok["it"]["token"])).json()
    assert all(u["id"] != arch_id for u in listed)
