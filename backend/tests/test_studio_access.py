"""Studio generation endpoints are limited to Main Admin and IT server-side."""
from __future__ import annotations

import os
import re
from pathlib import Path

os.environ["KIYUB_WORKFLOW_STUB_GENERATE"] = "1"
os.environ["KIYUB_WORKFLOW_MEMORY"] = "1"
os.environ["JWT_SECRET"] = "test-jwt-secret"

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from workflow import db as wfdb
from workflow.api import router
from workflow.auth import STUDIO_API_ROLES, require_studio_user
from workflow.models import User
from workflow.seed import seed_users
from tests.test_workflow import auth, generate, ids, provision

CLIENT_DENIED = "Clients are not authorized to use Studio generation."
ARCHITECT_DENIED = "Studio generation is not available for this account."


def _client_and_counter():
    wfdb.reset_store()
    wfdb.init_db()
    db = wfdb.SessionLocal()
    seed_users(db)
    db.close()
    calls = {"n": 0}
    app = FastAPI()
    app.include_router(router)

    @app.post("/api/_studio_probe")
    def probe(_user: User = Depends(require_studio_user)):
        calls["n"] += 1
        return {"ok": True}

    return TestClient(app), calls


def test_client_is_denied_and_nothing_runs():
    client, calls = _client_and_counter()
    tok = ids(client)
    r = client.post("/api/_studio_probe", headers=auth(tok["client"]["token"]))
    assert r.status_code == 403
    assert r.json()["detail"] == CLIENT_DENIED
    assert calls["n"] == 0


def test_client_role_header_or_body_cannot_bypass():
    client, calls = _client_and_counter()
    tok = ids(client)
    r = client.post(
        "/api/_studio_probe",
        headers={**auth(tok["client"]["token"]), "X-Role": "ARCHITECT"},
        json={"role": "ARCHITECT"},
    )
    assert r.status_code == 403
    assert calls["n"] == 0


def test_architect_is_denied_and_nothing_runs():
    client, calls = _client_and_counter()
    tok = ids(client)
    r = client.post(
        "/api/_studio_probe",
        headers={**auth(tok["architect"]["token"]), "X-Role": "MAIN_ADMIN"},
        json={"role": "MAIN_ADMIN"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == ARCHITECT_DENIED
    assert calls["n"] == 0


def test_authorized_roles_still_work():
    client, calls = _client_and_counter()
    tok = ids(client)
    for role in ("admin", "it"):
        r = client.post("/api/_studio_probe", headers=auth(tok[role]["token"]))
        assert r.status_code == 200, (role, r.text)
    assert calls["n"] == 2


def test_architect_can_still_generate_on_own_project():
    client, _calls = _client_and_counter()
    ctx = provision(client)
    generate(client, ctx)
    r = client.post(
        f"/api/projects/{ctx['project']['id']}/generate",
        headers=auth(ctx["tokens"]["architect"]["token"]),
    )
    assert r.status_code == 200, r.text


def test_anonymous_is_unauthorized():
    client, calls = _client_and_counter()
    r = client.post("/api/_studio_probe")
    assert r.status_code == 401
    assert calls["n"] == 0


def test_main_studio_routes_use_studio_dependency():
    src = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    for name in ("generate", "generate_moe", "moe_experts"):
        m = re.search(rf"async def {name}\((.*?)\):\n", src)
        assert m, name
        assert "Depends(require_studio_user)" in m.group(1), name


def test_studio_api_roles_are_admin_and_it_only():
    assert STUDIO_API_ROLES == {"MAIN_ADMIN", "IT_PERSONNEL"}
