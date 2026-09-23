"""Workflow API tests against in-memory SQLite. Generation is stubbed."""
from __future__ import annotations

import os

os.environ["KIYUB_WORKFLOW_STUB_GENERATE"] = "1"
os.environ["JWT_SECRET"] = "test-jwt-secret"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from workflow import db as wfdb
from workflow.seed import seed_users
from workflow.api import router
from workflow.models import DesignDocument
from workflow.state import apply_transition, IllegalTransition

BRIEF = {
    "site": {"lotShape": "rectangle", "lotWidth": 20, "lotDepth": 30},
    "house": {"floors": 1, "bedrooms": 3, "bathrooms": 2, "livingAreaSqft": 1800},
    "spaces": {"homeOffice": False, "laundry": "room", "garage": "2car", "outdoor": "patio"},
    "preferences": {
        "style": "modern",
        "openPlan": False,
        "primarySuite": True,
        "formalDining": False,
        "ceilingHeight": "standard",
    },
}


@pytest.fixture
def client():
    wfdb.configure("sqlite:///:memory:")
    wfdb.init_db()
    db = wfdb.SessionLocal()
    seed_users(db)
    db.close()
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def login(client: TestClient, email: str, password: str) -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def ids(client: TestClient):
    tokens = {
        "client": login(client, "client@kiyub.local", "clientpass"),
        "architect": login(client, "architect@kiyub.local", "architectpass"),
        "admin": login(client, "admin@kiyub.local", "adminpass"),
        "it": login(client, "it@kiyub.local", "itpass"),
    }
    return tokens


def provision(client: TestClient) -> dict:
    tok = ids(client)
    client_id = tok["client"]["user"]["id"]
    r = client.post(
        "/api/projects",
        json={"name": "Lot A", "client_id": client_id},
        headers=auth(tok["architect"]["token"]),
    )
    assert r.status_code == 200, r.text
    project = r.json()
    r = client.put(
        f"/api/projects/{project['id']}/brief",
        json={"questionnaire": BRIEF, "specification": {}},
        headers=auth(tok["client"]["token"]),
    )
    assert r.status_code == 200, r.text
    return {"tokens": tok, "project": project}


def generate(client: TestClient, ctx: dict) -> dict:
    r = client.post(
        f"/api/projects/{ctx['project']['id']}/generate",
        headers=auth(ctx["tokens"]["client"]["token"]),
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_client_cannot_edit_design(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    rev_id = gen["candidates"][0]["revision_id"]
    r = client.put(
        f"/api/revisions/{rev_id}/design",
        json={"floor_plan": gen["candidates"][0]["floor_plan"]},
        headers=auth(ctx["tokens"]["client"]["token"]),
    )
    assert r.status_code == 403


def test_architect_can_edit_assigned(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    cand_id = gen["candidates"][0]["id"]
    r = client.post(
        f"/api/projects/{ctx['project']['id']}/candidates/{cand_id}/accept",
        headers=auth(ctx["tokens"]["architect"]["token"]),
    )
    assert r.status_code == 200, r.text
    rev = r.json()
    plan = rev["floor_plan"]
    plan["rooms"][0]["width"] = 22
    r = client.put(
        f"/api/revisions/{rev['id']}/design",
        json={"floor_plan": plan, "expected_revision_id": rev["id"]},
        headers=auth(ctx["tokens"]["architect"]["token"]),
    )
    assert r.status_code == 200, r.text
    assert r.json()["source_type"] == "REVISION"
    assert r.json()["id"] != rev["id"]


def test_published_mutation_409(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    pid = ctx["project"]["id"]
    cand = gen["candidates"][0]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    rev = client.post(f"/api/projects/{pid}/candidates/{cand}/accept", headers=h_arch).json()
    assert client.post(f"/api/projects/{pid}/submit-review", headers=h_arch).status_code == 200
    assert client.post(f"/api/projects/{pid}/client-approve", headers=h_cli).status_code == 200
    assert client.post(f"/api/projects/{pid}/architect-approve", headers=h_arch).status_code == 200
    pub = client.post(f"/api/projects/{pid}/publish", headers=h_arch)
    assert pub.status_code == 200, pub.text
    r = client.put(
        f"/api/revisions/{pub.json()['id']}/design",
        json={"floor_plan": rev["floor_plan"]},
        headers=h_arch,
    )
    assert r.status_code == 409


def test_illegal_status_transition_rejected(client):
    with pytest.raises(IllegalTransition):
        apply_transition("DRAFT", "PUBLISHED")
    ctx = provision(client)
    r = client.post(
        f"/api/projects/{ctx['project']['id']}/publish",
        headers=auth(ctx["tokens"]["architect"]["token"]),
    )
    assert r.status_code in (403, 409)


def test_generate_writes_candidates(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    assert len(gen["candidates"]) >= 1
    assert gen["candidates"][0]["source_type"] == "AI_GENERATED"
    detail = client.get(
        f"/api/projects/{ctx['project']['id']}",
        headers=auth(ctx["tokens"]["architect"]["token"]),
    ).json()
    assert detail["document"]["current_revision_id"] is None


def test_stale_job_does_not_overwrite_architect_revision(client, monkeypatch):
    ctx = provision(client)
    gen = generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    accepted = client.post(
        f"/api/projects/{pid}/candidates/{gen['candidates'][0]['id']}/accept",
        headers=h_arch,
    ).json()
    before = accepted["id"]

    import workflow.services as services

    original = services.run_generation

    def hijack(constraints, num_variants=3):
        db = wfdb.SessionLocal()
        doc = db.query(DesignDocument).filter(DesignDocument.project_id == pid).one()
        doc.current_revision_id = "human-newer-than-job"
        db.commit()
        db.close()
        return original(constraints, num_variants)

    monkeypatch.setattr(services, "run_generation", hijack)
    again = generate(client, ctx)
    assert again["stale_source"] is True
    detail = client.get(f"/api/projects/{pid}", headers=h_arch).json()
    assert detail["document"]["current_revision_id"] == "human-newer-than-job"
    assert detail["document"]["current_revision_id"] != again["candidates"][0]["revision_id"]
    assert before != again["candidates"][0]["revision_id"]


def test_client_selects_candidate(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    cand = gen["candidates"][1]["id"] if len(gen["candidates"]) > 1 else gen["candidates"][0]["id"]
    r = client.post(
        f"/api/projects/{ctx['project']['id']}/candidates/{cand}/select",
        headers=auth(ctx["tokens"]["client"]["token"]),
    )
    assert r.status_code == 200
    listed = client.get(
        f"/api/projects/{ctx['project']['id']}/candidates",
        headers=auth(ctx["tokens"]["client"]["token"]),
    ).json()
    selected = [c for c in listed if c["selected_by_client"]]
    assert len(selected) == 1
    assert selected[0]["id"] == cand


def test_architect_accept_copies_revision(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    source_id = gen["candidates"][0]["revision_id"]
    r = client.post(
        f"/api/projects/{ctx['project']['id']}/candidates/{gen['candidates'][0]['id']}/accept",
        headers=auth(ctx["tokens"]["architect"]["token"]),
    )
    assert r.status_code == 200
    copy = r.json()
    assert copy["id"] != source_id
    assert copy["source_type"] == "ARCHITECT_EDIT"
    assert copy["source_revision_id"] == source_id
    original = client.get(
        f"/api/revisions/{source_id}",
        headers=auth(ctx["tokens"]["architect"]["token"]),
    ).json()
    assert original["source_type"] == "AI_GENERATED"


def test_unassigned_client_cannot_generate(client):
    ctx = provision(client)
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    extra_project = client.post(
        "/api/projects",
        json={"name": "Other lot"},
        headers=h_arch,
    ).json()
    invited = client.post(
        f"/api/projects/{extra_project['id']}/invitations",
        json={"email": "other@kiyub.local"},
        headers=h_arch,
    )
    assert invited.status_code == 200, invited.text
    extra = client.post(
        "/api/auth/signup",
        json={
            "email": "other@kiyub.local",
            "password": "otherpass",
            "role": "CLIENT",
            "invitation_token": invited.json()["token"],
        },
    )
    assert extra.status_code == 200, extra.text
    token = extra.json()["token"]
    r = client.post(
        f"/api/projects/{ctx['project']['id']}/generate",
        headers=auth(token),
    )
    assert r.status_code == 403


def test_comments_client_architect(client):
    ctx = provision(client)
    pid = ctx["project"]["id"]
    r = client.post(
        f"/api/projects/{pid}/comments",
        json={"body": "Please enlarge the kitchen"},
        headers=auth(ctx["tokens"]["client"]["token"]),
    )
    assert r.status_code == 200
    r = client.post(
        f"/api/projects/{pid}/comments",
        json={"body": "Will do"},
        headers=auth(ctx["tokens"]["architect"]["token"]),
    )
    assert r.status_code == 200
    listed = client.get(f"/api/projects/{pid}/comments", headers=auth(ctx["tokens"]["client"]["token"])).json()
    assert len(listed) == 2

    pin = client.post(
        f"/api/projects/{pid}/comments",
        json={"body": "Move this wall", "x": 12.5, "y": 8.0, "object_id": "living"},
        headers=auth(ctx["tokens"]["client"]["token"]),
    )
    assert pin.status_code == 200
    assert pin.json()["x"] == 12.5
    assert pin.json()["author_role"] == "CLIENT"
    assert pin.json()["object_id"] == "living"
    cid = pin.json()["id"]
    listed_arch = client.get(
        f"/api/projects/{pid}/comments",
        headers=auth(ctx["tokens"]["architect"]["token"]),
    ).json()
    client_pin = next(c for c in listed_arch if c["id"] == cid)
    assert client_pin["author_role"] == "CLIENT"
    assert client_pin["x"] == 12.5
    assert client_pin["y"] == 8.0
    assert client_pin["object_id"] == "living"
    projects = client.get("/api/projects", headers=auth(ctx["tokens"]["architect"]["token"])).json()
    row = next(p for p in projects if p["id"] == pid)
    assert row["client_comment_count"] >= 2
    patched = client.patch(
        f"/api/projects/{pid}/comments/{cid}",
        json={"body": "Move this door", "x": 13.0},
        headers=auth(ctx["tokens"]["client"]["token"]),
    )
    assert patched.status_code == 200
    assert patched.json()["body"] == "Move this door"
    assert patched.json()["x"] == 13.0
    gone = client.delete(
        f"/api/projects/{pid}/comments/{cid}",
        headers=auth(ctx["tokens"]["client"]["token"]),
    )
    assert gone.status_code == 200
    listed2 = client.get(f"/api/projects/{pid}/comments", headers=auth(ctx["tokens"]["client"]["token"])).json()
    assert len(listed2) == 2


def test_request_revision_transition(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    client.post(f"/api/projects/{pid}/candidates/{gen['candidates'][0]['id']}/accept", headers=h_arch)
    assert client.post(f"/api/projects/{pid}/submit-review", headers=h_arch).status_code == 200
    r = client.post(f"/api/projects/{pid}/request-revision", headers=h_cli)
    assert r.status_code == 200
    assert r.json()["status"] == "FOR_REVISION"


def test_approve_and_publish(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    client.post(f"/api/projects/{pid}/candidates/{gen['candidates'][0]['id']}/accept", headers=h_arch)
    client.post(f"/api/projects/{pid}/submit-review", headers=h_arch)
    assert client.post(f"/api/projects/{pid}/client-approve", headers=h_cli).status_code == 200
    r = client.post(f"/api/projects/{pid}/architect-approve", headers=h_arch)
    assert r.status_code == 200
    assert r.json()["status"] == "APPROVED"
    pub = client.post(f"/api/projects/{pid}/publish", headers=h_arch)
    assert pub.status_code == 200
    assert pub.json()["source_type"] == "PUBLISHED"
    detail = client.get(f"/api/projects/{pid}", headers=h_cli).json()
    assert detail["project"]["status"] == "PUBLISHED"
    assert detail["document"]["stage"] == "FINAL_DESIGN"


def test_admin_it_cannot_edit(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    rev_id = gen["candidates"][0]["revision_id"]
    plan = gen["candidates"][0]["floor_plan"]
    for role in ("admin", "it"):
        r = client.put(
            f"/api/revisions/{rev_id}/design",
            json={"floor_plan": plan},
            headers=auth(ctx["tokens"][role]["token"]),
        )
        assert r.status_code == 403


def test_unapproved_architect_login_blocked(client):
    r = client.post(
        "/api/auth/signup",
        json={"email": "pending@kiyub.local", "password": "pendingpass", "role": "ARCHITECT"},
    )
    assert r.status_code == 200
    assert "token" not in r.json() or r.json().get("token") in (None, "")
    denied = client.post("/api/auth/login", json={"email": "pending@kiyub.local", "password": "pendingpass"})
    assert denied.status_code == 403
    users = client.get("/api/accounts", headers=auth(ids(client)["it"]["token"])).json()
    pending = next(u for u in users if u["email"] == "pending@kiyub.local")
    ok = client.patch(
        f"/api/accounts/{pending['id']}",
        json={"approved": True},
        headers=auth(ids(client)["it"]["token"]),
    )
    assert ok.status_code == 200
    assert login(client, "pending@kiyub.local", "pendingpass")["user"]["approved"] is True


def test_audit_events_recorded(client):
    ctx = provision(client)
    generate(client, ctx)
    r = client.get("/api/audit", headers=auth(ctx["tokens"]["it"]["token"]))
    assert r.status_code == 200
    types = {e["event_type"] for e in r.json()}
    assert "LOGIN" in types
    assert "PROJECT_CREATED" in types
    assert "AI_GENERATION_COMPLETED" in types
    blocked = client.get("/api/audit", headers=auth(ctx["tokens"]["client"]["token"]))
    assert blocked.status_code == 403


def test_revision_stores_scene_document(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    scene = gen["candidates"][0]["scene_document"]
    plan = gen["candidates"][0]["floor_plan"]
    assert scene.get("schemaVersion") == "2.0"
    assert scene.get("rooms")
    assert plan.get("rooms")
    notes = client.get("/api/notifications", headers=auth(ctx["tokens"]["architect"]["token"]))
    assert notes.status_code == 200
    assert any("candidates" in n["message"] for n in notes.json())


def test_client_signup_requires_invitation(client):
    r = client.post(
        "/api/auth/signup",
        json={"email": "solo@kiyub.local", "password": "solopass", "role": "CLIENT"},
    )
    assert r.status_code == 403


def test_invitation_accepts_and_locks_architect_canvas(client):
    tok = ids(client)
    h_arch = auth(tok["architect"]["token"])
    project = client.post("/api/projects", json={"name": "Invite lot"}, headers=h_arch).json()
    pid = project["id"]
    before = client.get(f"/api/projects/{pid}", headers=h_arch).json()
    assert before["project"]["has_floor_plan"] is False
    assert before["permissions"]["canOpenArchitectCanvas"] is False
    blocked = client.post(f"/api/projects/{pid}/generate", headers=h_arch)
    assert blocked.status_code == 403

    invited = client.post(
        f"/api/projects/{pid}/invitations",
        json={"email": "invited@kiyub.local"},
        headers=h_arch,
    )
    assert invited.status_code == 200, invited.text
    token = invited.json()["token"]
    dup = client.post(
        f"/api/projects/{pid}/invitations",
        json={"email": "invited@kiyub.local"},
        headers=h_arch,
    )
    assert dup.status_code == 409
    public = client.get(f"/api/invitations/by-token/{token}")
    assert public.status_code == 200
    assert public.json()["email"] == "invited@kiyub.local"
    assert public.json()["needs_registration"] is True
    wrong = client.post(
        "/api/auth/signup",
        json={
            "email": "other@kiyub.local",
            "password": "otherpass",
            "role": "CLIENT",
            "invitation_token": token,
        },
    )
    assert wrong.status_code == 403
    signed = client.post(
        "/api/auth/signup",
        json={
            "email": "invited@kiyub.local",
            "password": "invitepass",
            "role": "CLIENT",
            "invitation_token": token,
        },
    )
    assert signed.status_code == 200, signed.text
    h_cli = auth(signed.json()["token"])
    brief = client.put(
        f"/api/projects/{pid}/brief",
        json={"questionnaire": BRIEF, "specification": {}},
        headers=h_cli,
    )
    assert brief.status_code == 200, brief.text
    gen = client.post(f"/api/projects/{pid}/generate", headers=h_cli)
    assert gen.status_code == 200, gen.text
    after = client.get(f"/api/projects/{pid}", headers=h_arch).json()
    assert after["project"]["has_floor_plan"] is True
    assert after["permissions"]["canOpenArchitectCanvas"] is True
    listed = client.get("/api/architect/clients", headers=h_arch)
    assert listed.status_code == 200
    assert any(row["email"] == "invited@kiyub.local" for row in listed.json())

    pending = client.post(
        "/api/auth/signup",
        json={"email": "otherarch@kiyub.local", "password": "archpass", "role": "ARCHITECT"},
    )
    assert pending.status_code == 200
    users = client.get("/api/accounts", headers=auth(tok["it"]["token"])).json()
    other = next(u for u in users if u["email"] == "otherarch@kiyub.local")
    client.patch(f"/api/accounts/{other['id']}", json={"approved": True}, headers=auth(tok["it"]["token"]))
    other_login = login(client, "otherarch@kiyub.local", "archpass")
    denied = client.get(f"/api/projects/{pid}", headers=auth(other_login["token"]))
    assert denied.status_code == 403


def test_cancel_invitation(client):
    tok = ids(client)
    h_arch = auth(tok["architect"]["token"])
    project = client.post("/api/projects", json={"name": "Cancel lot"}, headers=h_arch).json()
    invited = client.post(
        f"/api/projects/{project['id']}/invitations",
        json={"email": "cancelme@kiyub.local"},
        headers=h_arch,
    ).json()
    cancelled = client.post(f"/api/invitations/{invited['id']}/cancel", headers=h_arch)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    public = client.get(f"/api/invitations/by-token/{invited['token']}")
    assert public.json()["status"] == "CANCELLED"


def test_seed_collaboration_uses_existing_users(client):
    users = client.get("/api/accounts", headers=auth(ids(client)["it"]["token"])).json()
    emails = sorted(u["email"] for u in users)
    assert emails == [
        "admin@kiyub.local",
        "architect@kiyub.local",
        "client@kiyub.local",
        "it@kiyub.local",
    ]
    h_arch = auth(ids(client)["architect"]["token"])
    projects = {p["name"]: p for p in client.get("/api/projects", headers=h_arch).json()}
    assert "Seed Residence" in projects
    assert "Awaiting Plan" in projects
    ready = projects["Seed Residence"]
    waiting = projects["Awaiting Plan"]
    assert ready["client_email"] == "client@kiyub.local"
    assert ready["has_floor_plan"] is True
    assert waiting["has_floor_plan"] is False
    assert waiting["client_email"] == "client@kiyub.local"

    ready_detail = client.get(f"/api/projects/{ready['id']}", headers=h_arch).json()
    assert ready_detail["permissions"]["canOpenArchitectCanvas"] is True
    comments = client.get(f"/api/projects/{ready['id']}/comments", headers=h_arch).json()
    assert any(
        c["author_role"] == "CLIENT" and c["object_id"] == "living-0" and c["x"] == 9.0
        for c in comments
    )
    invites = client.get(f"/api/projects/{ready['id']}/invitations", headers=h_arch).json()
    assert any(i["status"] == "ACCEPTED" and i["email"] == "client@kiyub.local" for i in invites)

    waiting_detail = client.get(f"/api/projects/{waiting['id']}", headers=h_arch).json()
    assert waiting_detail["permissions"]["canOpenArchitectCanvas"] is False
    blocked = client.post(f"/api/projects/{waiting['id']}/generate", headers=h_arch)
    assert blocked.status_code == 403


def test_seed_collaboration_is_idempotent(client):
    from workflow import db as wfdb
    from workflow.models import Project, User
    from workflow.seed import seed_users

    db = wfdb.SessionLocal()
    seed_users(db)
    seed_users(db)
    assert db.query(User).count() == 4
    arch = db.query(User).filter(User.email == "architect@kiyub.local").one()
    names = [p.name for p in db.query(Project).filter(Project.architect_id == arch.id).all()]
    assert names.count("Seed Residence") == 1
    assert names.count("Awaiting Plan") == 1
    db.close()


def test_client_submit_review_notifies_architect(client):
    ctx = provision(client)
    generate(client, ctx)
    pid = ctx["project"]["id"]
    h_cli = auth(ctx["tokens"]["client"]["token"])
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    r = client.post(f"/api/projects/{pid}/submit-review", headers=h_cli)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "FOR_CHECKING"
    notes = client.get("/api/notifications", headers=h_arch).json()
    assert any(
        n.get("kind") == "STATUS_CHANGED" and n.get("project_id") == pid
        for n in notes
    )
    again = client.post(f"/api/projects/{pid}/submit-review", headers=h_cli)
    assert again.status_code == 409


def test_client_cannot_submit_review_without_plan(client):
    ctx = provision(client)
    r = client.post(
        f"/api/projects/{ctx['project']['id']}/submit-review",
        headers=auth(ctx["tokens"]["client"]["token"]),
    )
    assert r.status_code == 403


def test_inquiry_public_post_staff_get(client):
    created = client.post(
        "/api/inquiries",
        json={"name": "Ada", "email": "ada@example.com", "message": "Requesting studio access"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["email"] == "ada@example.com"
    tok = ids(client)
    listed = client.get("/api/inquiries", headers=auth(tok["it"]["token"]))
    assert listed.status_code == 200
    assert any(row["email"] == "ada@example.com" for row in listed.json())
    admin_listed = client.get("/api/inquiries", headers=auth(tok["admin"]["token"]))
    assert admin_listed.status_code == 200
    denied = client.get("/api/inquiries", headers=auth(tok["client"]["token"]))
    assert denied.status_code == 403
    architect_denied = client.get("/api/inquiries", headers=auth(tok["architect"]["token"]))
    assert architect_denied.status_code == 403


def _accepted_revision(client, ctx):
    gen = generate(client, ctx)
    cand_id = gen["candidates"][0]["id"]
    r = client.post(
        f"/api/projects/{ctx['project']['id']}/candidates/{cand_id}/accept",
        headers=auth(ctx["tokens"]["architect"]["token"]),
    )
    assert r.status_code == 200, r.text
    return r.json(), gen


def test_client_cannot_patch_working_design(client):
    ctx = provision(client)
    generate(client, ctx)
    r = client.put(
        f"/api/projects/{ctx['project']['id']}/working-design",
        json={"scene_document": {"version": "2.0", "units": "metric", "walls": [], "rooms": []}},
        headers=auth(ctx["tokens"]["client"]["token"]),
    )
    assert r.status_code == 403


def test_working_autosave_does_not_create_revision(client):
    ctx = provision(client)
    rev, _gen = _accepted_revision(client, ctx)
    pid = ctx["project"]["id"]
    before = client.get(f"/api/projects/{pid}/revisions", headers=auth(ctx["tokens"]["architect"]["token"]))
    assert before.status_code == 200
    count = len(before.json())
    scene = {
        "version": "2.0",
        "units": "metric",
        "walls": [{"id": "w1", "start": {"x": 0, "y": 0}, "end": {"x": 3, "y": 0}}],
        "rooms": [],
        "openings": [],
    }
    r = client.put(
        f"/api/projects/{pid}/working-design",
        json={"scene_document": scene},
        headers=auth(ctx["tokens"]["architect"]["token"]),
    )
    assert r.status_code == 200, r.text
    after = client.get(f"/api/projects/{pid}/revisions", headers=auth(ctx["tokens"]["architect"]["token"]))
    assert len(after.json()) == count
    architect_detail = client.get(f"/api/projects/{pid}", headers=auth(ctx["tokens"]["architect"]["token"]))
    assert architect_detail.json()["document"]["working_scene_document"]["version"] == "2.0"
    client_detail = client.get(f"/api/projects/{pid}", headers=auth(ctx["tokens"]["client"]["token"]))
    assert "working_scene_document" not in client_detail.json()["document"]
    assert client_detail.json()["current_revision"]["id"] == rev["id"]
    assert client_detail.json()["current_revision"]["floor_plan"]["rooms"] == rev["floor_plan"]["rooms"]


def test_save_revision_stores_scene_and_increments(client):
    ctx = provision(client)
    rev, _gen = _accepted_revision(client, ctx)
    pid = ctx["project"]["id"]
    plan = rev["floor_plan"]
    plan["rooms"][0]["width"] = 21
    scene = {
        "version": "2.0",
        "units": "metric",
        "walls": [],
        "rooms": [],
        "openings": [],
        "site": {"width": 20, "depth": 20},
    }
    r = client.put(
        f"/api/revisions/{rev['id']}/design",
        json={"floor_plan": plan, "expected_revision_id": rev["id"], "scene_document": scene},
        headers=auth(ctx["tokens"]["architect"]["token"]),
    )
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["source_type"] == "REVISION"
    assert saved["id"] != rev["id"]
    assert saved["scene_document"]["version"] == "2.0"
    assert saved["scene_document"]["units"] == "metric"
    stale = client.put(
        f"/api/revisions/{rev['id']}/design",
        json={"floor_plan": plan, "expected_revision_id": rev["id"]},
        headers=auth(ctx["tokens"]["architect"]["token"]),
    )
    assert stale.status_code == 409
    client_detail = client.get(f"/api/projects/{pid}", headers=auth(ctx["tokens"]["client"]["token"]))
    assert client_detail.json()["current_revision"]["id"] == saved["id"]
    assert client_detail.json()["current_revision"]["floor_plan"]["rooms"][0]["width"] == 21
