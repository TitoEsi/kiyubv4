"""Workflow API tests against the in-memory repository. Generation is stubbed."""
from __future__ import annotations

import os
import uuid

os.environ["KIYUB_WORKFLOW_STUB_GENERATE"] = "1"
os.environ["KIYUB_WORKFLOW_MEMORY"] = "1"
os.environ["JWT_SECRET"] = "test-jwt-secret"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from workflow import db as wfdb
from workflow.seed import seed_users
from workflow.api import router
from workflow.models import DesignDocument, SiteConstraint, User
from workflow.state import apply_transition, IllegalTransition

ACCEPT = {"accept_terms": True, "accept_privacy": True}

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
    wfdb.reset_store()
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
    email = f"lot-{uuid.uuid4().hex[:8]}@kiyub.local"
    invited = client.post(
        "/api/invitations",
        json={"email": email, "project_name": "Lot A"},
        headers=auth(tok["architect"]["token"]),
    )
    assert invited.status_code == 200, invited.text
    signed = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "lotpass",
            **ACCEPT,
            "invitation_token": invited.json()["token"],
            "full_name": "Lot Client",
        },
    )
    assert signed.status_code == 200, signed.text
    project = signed.json()["project"]
    tok["client"] = {"token": signed.json()["token"], "user": signed.json()["user"]}
    r = client.put(
        f"/api/projects/{project['id']}/brief",
        json={"questionnaire": BRIEF, "specification": {}},
        headers=auth(tok["client"]["token"]),
    )
    assert r.status_code == 200, r.text
    return {"tokens": tok, "project": project}


def review_scene(label: str, x: float = 2.5) -> dict:
    return {
        "version": "2.0",
        "units": "metric",
        "walls": [{"id": f"w-{label}", "start": {"x": 0, "y": 0}, "end": {"x": x, "y": 0}, "thickness": 0.15}],
        "rooms": [{"id": f"r-{label}", "name": label, "position": {"x": 0, "y": 0}, "dimensions": {"width": x, "height": 3}}],
        "openings": [],
        "furniture": [],
        "site": {"width": 12, "depth": 10},
    }


def post_architect_review(client: TestClient, pid: str, headers: dict, scene: dict | None = None) -> object:
    body = {"scene_document": scene or review_scene("B"), "floor_plan": {"name": (scene or {}).get("rooms", [{}])[0].get("name", "B")}}
    return client.post(f"/api/projects/{pid}/submit-review", json=body, headers=headers)


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
    assert post_architect_review(client, pid, h_arch).status_code == 200
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
    invited = client.post(
        "/api/invitations",
        json={"email": "other@kiyub.local", "project_name": "Other lot"},
        headers=h_arch,
    )
    assert invited.status_code == 200, invited.text
    extra = client.post(
        "/api/auth/signup",
        json={
            "email": "other@kiyub.local",
            "password": "otherpass",
            **ACCEPT,
            "invitation_token": invited.json()["token"],
            "full_name": "Other Client",
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


def test_request_revision_endpoint_removed(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    client.post(f"/api/projects/{pid}/candidates/{gen['candidates'][0]['id']}/accept", headers=h_arch)
    assert post_architect_review(client, pid, h_arch).status_code == 200
    r = client.post(f"/api/projects/{pid}/request-revision", headers=h_cli)
    assert r.status_code == 404


def test_approve_and_publish(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    client.post(f"/api/projects/{pid}/candidates/{gen['candidates'][0]['id']}/accept", headers=h_arch)
    post_architect_review(client, pid, h_arch)
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
    tok = ids(client)
    created = client.post(
        "/api/architect-applications",
        json={"email": "pending@kiyub.local", "full_name": "Pending Architect", "information": "Studio"},
        headers=auth(tok["admin"]["token"]),
    )
    assert created.status_code == 200, created.text
    assert created.json()["status"] == "PENDING_APPROVAL"
    denied = client.post("/api/auth/login", json={"email": "pending@kiyub.local", "password": "pendingpass"})
    assert denied.status_code == 401
    approved = client.post(
        f"/api/architect-applications/{created.json()['id']}/approve",
        headers=auth(tok["it"]["token"]),
    )
    assert approved.status_code == 200, approved.text
    token = approved.json()["token"]
    done = client.post(
        f"/api/architect-applications/by-token/{token}/complete",
        json={"password": "pendingpass", "role": "MAIN_ADMIN", **ACCEPT},
    )
    assert done.status_code == 200, done.text
    assert done.json()["user"]["role"] == "ARCHITECT"
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
    scoped = client.get("/api/audit", headers=auth(ctx["tokens"]["client"]["token"]))
    assert scoped.status_code == 200
    assert all(e.get("project_id") == ctx["project"]["id"] for e in scoped.json() if e.get("project_id"))


def test_revision_stores_scene_document(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    scene = gen["candidates"][0]["scene_document"]
    plan = gen["candidates"][0]["floor_plan"]
    assert scene.get("schemaVersion") == "2.0"
    assert scene.get("rooms")
    assert plan.get("rooms")
    site = scene.get("site") or {}
    assert site.get("width") == 20
    assert site.get("depth") == 30
    notes = client.get("/api/notifications", headers=auth(ctx["tokens"]["architect"]["token"]))
    assert notes.status_code == 200
    assert any("candidates" in n["message"] for n in notes.json())


def test_client_signup_requires_invitation(client):
    r = client.post(
        "/api/auth/signup",
        json={"email": "solo@kiyub.local", "password": "solopass", "role": "CLIENT"},
    )
    assert r.status_code == 403


def test_architect_cannot_create_standalone_project(client):
    tok = ids(client)
    r = client.post("/api/projects", json={"name": "Standalone"}, headers=auth(tok["architect"]["token"]))
    assert r.status_code == 403
    ctx = provision(client)
    assigned = client.put(
        f"/api/projects/{ctx['project']['id']}/assign",
        json={"client_id": tok["client"]["user"]["id"]},
        headers=auth(tok["architect"]["token"]),
    )
    assert assigned.status_code == 403
    legacy = client.post(
        f"/api/projects/{ctx['project']['id']}/invitations",
        json={"email": "another@kiyub.local"},
        headers=auth(tok["architect"]["token"]),
    )
    assert legacy.status_code == 403


def test_invitation_does_not_create_project_until_accept(client):
    tok = ids(client)
    h_arch = auth(tok["architect"]["token"])
    before = {p["id"] for p in client.get("/api/projects", headers=h_arch).json()}
    invited = client.post(
        "/api/invitations",
        json={"email": "newclient@kiyub.local", "project_name": "Invite lot"},
        headers=h_arch,
    )
    assert invited.status_code == 200, invited.text
    assert invited.json()["status"] == "PENDING"
    assert invited.json()["project_id"] is None
    after = {p["id"] for p in client.get("/api/projects", headers=h_arch).json()}
    assert after == before
    dup = client.post(
        "/api/invitations",
        json={"email": "newclient@kiyub.local", "project_name": "Invite lot"},
        headers=h_arch,
    )
    assert dup.status_code == 409


def test_invitation_accepts_and_creates_project(client):
    tok = ids(client)
    h_arch = auth(tok["architect"]["token"])
    invited = client.post(
        "/api/invitations",
        json={"email": "invited@kiyub.local", "project_name": "Invite lot"},
        headers=h_arch,
    )
    assert invited.status_code == 200, invited.text
    token = invited.json()["token"]
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
            **ACCEPT,
            "invitation_token": token,
        },
    )
    assert wrong.status_code == 403
    signed = client.post(
        "/api/auth/signup",
        json={
            "email": "invited@kiyub.local",
            "password": "invitepass",
            **ACCEPT,
            "invitation_token": token,
            "full_name": "Invited Client",
        },
    )
    assert signed.status_code == 200, signed.text
    h_cli = auth(signed.json()["token"])
    accepted = client.post(f"/api/invitations/by-token/{token}/accept", headers=h_cli)
    assert accepted.status_code == 200, accepted.text
    payload = accepted.json()
    pid = payload["project"]["id"]
    assert payload["invitation"]["status"] == "ACCEPTED"
    assert payload["project"]["architect_id"] == tok["architect"]["user"]["id"]
    assert payload["project"]["client_id"] == signed.json()["user"]["id"]
    assert payload["project"]["invitation_id"] == invited.json()["id"]
    assert payload["project"]["status"] == "DRAFT"
    again = client.post(f"/api/invitations/by-token/{token}/accept", headers=h_cli)
    assert again.status_code == 200
    assert again.json()["project"]["id"] == pid
    listed = client.get("/api/projects", headers=h_cli).json()
    assert sum(1 for p in listed if p["id"] == pid) == 1
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
        "/api/architect-applications",
        json={"email": "otherarch@kiyub.local", "full_name": "Other Architect", "information": ""},
        headers=auth(tok["admin"]["token"]),
    )
    assert pending.status_code == 200
    approved = client.post(
        f"/api/architect-applications/{pending.json()['id']}/approve",
        headers=auth(tok["it"]["token"]),
    )
    assert approved.status_code == 200
    client.post(
        f"/api/architect-applications/by-token/{approved.json()['token']}/complete",
        json={"password": "archpass", **ACCEPT},
    )
    other_login = login(client, "otherarch@kiyub.local", "archpass")
    denied = client.get(f"/api/projects/{pid}", headers=auth(other_login["token"]))
    assert denied.status_code == 403


def test_decline_invitation_creates_no_project(client):
    tok = ids(client)
    h_arch = auth(tok["architect"]["token"])
    invited = client.post(
        "/api/invitations",
        json={"email": "decliner@kiyub.local", "project_name": "Declined lot"},
        headers=h_arch,
    )
    assert invited.status_code == 200, invited.text
    before = {p["id"] for p in client.get("/api/projects", headers=h_arch).json()}
    declined = client.post(
        f"/api/invitations/by-token/{invited.json()['token']}/decline",
        headers=auth(tok["client"]["token"]),
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "DECLINED"
    after = {p["id"] for p in client.get("/api/projects", headers=h_arch).json()}
    assert after == before


def test_other_client_cannot_accept_invitation(client):
    tok = ids(client)
    h_arch = auth(tok["architect"]["token"])
    invited = client.post(
        "/api/invitations",
        json={"email": "target@kiyub.local", "project_name": "Private lot"},
        headers=h_arch,
    )
    assert invited.status_code == 200
    stolen = client.post(
        f"/api/invitations/by-token/{invited.json()['token']}/accept",
        headers=auth(tok["client"]["token"]),
    )
    assert stolen.status_code == 403
    public = client.get(f"/api/invitations/by-token/{invited.json()['token']}")
    assert public.json()["status"] == "PENDING"


def test_cancel_invitation(client):
    tok = ids(client)
    h_arch = auth(tok["architect"]["token"])
    invited = client.post(
        "/api/invitations",
        json={"email": "cancelme@kiyub.local", "project_name": "Cancel lot"},
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
    assert ready["invitation_id"]
    assert waiting["has_floor_plan"] is False
    assert waiting["client_email"] == "client@kiyub.local"
    assert waiting["invitation_id"]

    ready_detail = client.get(f"/api/projects/{ready['id']}", headers=h_arch).json()
    assert ready_detail["permissions"]["canOpenArchitectCanvas"] is True
    comments = client.get(f"/api/projects/{ready['id']}/comments", headers=h_arch).json()
    assert any(
        c["author_role"] == "CLIENT" and c["object_id"] == "living-0" and abs(c["x"] - 9.0 * 0.3048) < 1e-9
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


def test_brief_derives_site_constraints(client):
    ctx = provision(client)
    db = wfdb.SessionLocal()
    row = db.query(SiteConstraint).filter(SiteConstraint.project_id == ctx["project"]["id"]).one()
    assert row.lot_shape == "rectangle"
    assert row.lot_width == 20
    assert row.lot_depth == 30
    db.close()
    gen = generate(client, ctx)
    rev_id = gen["candidates"][0]["revision_id"]
    rev = client.get(
        f"/api/revisions/{rev_id}",
        headers=auth(ctx["tokens"]["client"]["token"]),
    )
    assert rev.status_code == 200, rev.text
    site = (rev.json().get("scene_document") or {}).get("site") or {}
    assert site.get("width") == 20
    assert site.get("depth") == 30


def test_architect_review_snapshot_is_client_visible(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    client.post(f"/api/projects/{pid}/candidates/{gen['candidates'][0]['id']}/accept", headers=h_arch)
    scene_a = review_scene("A", 2.0)
    scene_b = review_scene("B", 4.0)
    scene_c = review_scene("C", 6.0)
    client.put(f"/api/projects/{pid}/working-design", json={"scene_document": scene_a}, headers=h_arch)
    submitted = post_architect_review(client, pid, h_arch, scene_b)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "FOR_CHECKING"
    assert submitted.json()["submitted_revision_id"]
    detail = client.get(f"/api/projects/{pid}", headers=h_cli).json()
    assert detail["submitted_revision"]["source_type"] == "REVIEW"
    assert detail["submitted_revision"]["scene_document"]["rooms"][0]["name"] == "B"
    assert detail["submitted_revision"]["id"] == submitted.json()["submitted_revision_id"]
    assert "working_scene_document" not in detail["document"]
    client.put(f"/api/projects/{pid}/working-design", json={"scene_document": scene_c}, headers=h_arch)
    still_b = client.get(f"/api/projects/{pid}", headers=h_cli).json()
    assert still_b["submitted_revision"]["scene_document"]["rooms"][0]["name"] == "B"
    again = post_architect_review(client, pid, h_arch, scene_c)
    assert again.status_code == 200, again.text
    latest = client.get(f"/api/projects/{pid}", headers=h_cli).json()
    assert latest["submitted_revision"]["scene_document"]["rooms"][0]["name"] == "C"
    assert latest["submitted_revision"]["id"] == again.json()["submitted_revision_id"]
    assert latest["submitted_revision"]["id"] != submitted.json()["submitted_revision_id"]
    refreshed = client.get(f"/api/projects/{pid}", headers=h_cli).json()
    assert refreshed["submitted_revision"]["scene_document"] == latest["submitted_revision"]["scene_document"]
    stolen = client.put(
        f"/api/projects/{pid}/working-design",
        json={"scene_document": scene_a},
        headers=h_cli,
    )
    assert stolen.status_code == 403
    client_scene_submit = client.post(
        f"/api/projects/{pid}/submit-review",
        json={"scene_document": scene_a, "floor_plan": {"name": "nope"}},
        headers=h_cli,
    )
    assert client_scene_submit.status_code == 403
    client_again = client.post(f"/api/projects/{pid}/submit-review", headers=h_cli)
    assert client_again.status_code == 409


def test_returning_client_accepts_isolated_project(client):
    ctx = provision(client)
    email = ctx["tokens"]["client"]["user"]["email"]
    user_id = ctx["tokens"]["client"]["user"]["id"]
    pid_a = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    gen_a = generate(client, ctx)
    accepted_a = client.post(
        f"/api/projects/{pid_a}/candidates/{gen_a['candidates'][0]['id']}/accept",
        headers=h_arch,
    )
    assert accepted_a.status_code == 200, accepted_a.text
    rev_a = accepted_a.json()["id"]
    detail_a = client.get(f"/api/projects/{pid_a}", headers=h_cli).json()
    assert detail_a["document"]["current_revision_id"] == rev_a

    invited = client.post(
        "/api/invitations",
        json={"email": email, "project_name": "Lot B"},
        headers=h_arch,
    )
    assert invited.status_code == 200, invited.text
    assert invited.json()["existing_client"] is True
    token = invited.json()["token"]
    public = client.get(f"/api/invitations/by-token/{token}")
    assert public.json()["needs_registration"] is False
    assert public.json()["project_name"] == "Lot B"

    seed_client = ids(client)["client"]
    wrong = client.post(f"/api/invitations/by-token/{token}/accept", headers=auth(seed_client["token"]))
    assert wrong.status_code == 403
    still_pending = client.get(f"/api/invitations/by-token/{token}").json()
    assert still_pending["status"] == "PENDING"

    accepted = client.post(f"/api/invitations/by-token/{token}/accept", headers=h_cli)
    assert accepted.status_code == 200, accepted.text
    pid_b = accepted.json()["project"]["id"]
    assert pid_b != pid_a
    assert accepted.json()["project"]["client_id"] == user_id
    assert accepted.json()["project"]["status"] == "DRAFT"

    detail_b = client.get(f"/api/projects/{pid_b}", headers=h_cli).json()
    assert detail_b["document"]["current_revision_id"] is None
    assert detail_b["current_revision"] is None
    architect_b = client.get(f"/api/projects/{pid_b}", headers=h_arch).json()
    assert architect_b["document"].get("working_scene_document") in (None, {})

    still_a = client.get(f"/api/projects/{pid_a}", headers=h_cli).json()
    assert still_a["document"]["current_revision_id"] == rev_a

    brief = client.put(
        f"/api/projects/{pid_b}/brief",
        json={"questionnaire": BRIEF, "specification": {}},
        headers=h_cli,
    )
    assert brief.status_code == 200, brief.text
    gen_b = client.post(f"/api/projects/{pid_b}/generate", headers=h_cli)
    assert gen_b.status_code == 200, gen_b.text
    accepted_b = client.post(
        f"/api/projects/{pid_b}/candidates/{gen_b.json()['candidates'][0]['id']}/accept",
        headers=h_arch,
    )
    assert accepted_b.status_code == 200, accepted_b.text
    after_a = client.get(f"/api/projects/{pid_a}", headers=h_cli).json()
    after_b = client.get(f"/api/projects/{pid_b}", headers=h_cli).json()
    assert after_a["document"]["current_revision_id"] == rev_a
    assert after_b["document"]["current_revision_id"] == accepted_b.json()["id"]
    assert after_b["document"]["current_revision_id"] != rev_a

    db = wfdb.SessionLocal()
    try:
        assert db.query(User).filter(User.email == email).count() == 1
        docs = db.query(DesignDocument).filter(DesignDocument.project_id.in_([pid_a, pid_b])).all()
        assert {d.project_id for d in docs} == {pid_a, pid_b}
    finally:
        db.close()


def test_client_floor_plan_follows_accepted_candidate_after_review(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    first = client.post(f"/api/projects/{pid}/candidates/{gen['candidates'][0]['id']}/accept", headers=h_arch)
    assert first.status_code == 200, first.text
    submitted = post_architect_review(client, pid, h_arch, review_scene("OLD", 2.0))
    assert submitted.status_code == 200, submitted.text
    checking = client.get(f"/api/projects/{pid}", headers=h_cli).json()
    assert checking["project"]["status"] == "FOR_CHECKING"
    assert checking["submitted_revision"]["scene_document"]["rooms"][0]["name"] == "OLD"

    later = gen["candidates"][1] if len(gen["candidates"]) > 1 else generate(client, ctx)["candidates"][0]
    accepted = client.post(f"/api/projects/{pid}/candidates/{later['id']}/accept", headers=h_arch)
    assert accepted.status_code == 200, accepted.text
    after = client.get(f"/api/projects/{pid}", headers=h_cli).json()
    assert after["submitted_revision"] is None
    assert after["current_revision"]["id"] == accepted.json()["id"]
    assert after["current_revision"]["id"] != checking["submitted_revision"]["id"]
    if after["current_revision"].get("scene_document"):
        assert after["current_revision"]["scene_document"]["rooms"][0]["name"] != "OLD"


def test_publish_uses_reviewed_scene_not_older_current(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    accepted = client.post(f"/api/projects/{pid}/candidates/{gen['candidates'][0]['id']}/accept", headers=h_arch)
    assert accepted.status_code == 200, accepted.text
    older_id = accepted.json()["id"]
    reviewed_scene = review_scene("PUBLISHED-CURRENT", 4.5)
    reviewed_plan = {"name": "PUBLISHED-CURRENT", "units": "metric", "rooms": [{"id": "r-PUBLISHED-CURRENT", "name": "PUBLISHED-CURRENT", "width": 4.5}]}
    submitted = client.post(
        f"/api/projects/{pid}/submit-review",
        json={"scene_document": reviewed_scene, "floor_plan": reviewed_plan},
        headers=h_arch,
    )
    assert submitted.status_code == 200, submitted.text
    review_id = submitted.json()["submitted_revision_id"]
    assert review_id
    approved = client.post(f"/api/projects/{pid}/client-approve", headers=h_cli)
    assert approved.status_code == 200, approved.text
    assert approved.json()["revision_id"] == review_id
    assert approved.json()["revision_id"] != older_id
    arch = client.post(f"/api/projects/{pid}/architect-approve", headers=h_arch)
    assert arch.status_code == 200, arch.text
    published = client.post(
        f"/api/projects/{pid}/publish",
        json={"scene_document": review_scene("STALE-OVERRIDE", 1.0), "floor_plan": {"name": "STALE-OVERRIDE"}},
        headers=h_arch,
    )
    assert published.status_code == 200, published.text
    payload = published.json()
    assert payload["source_type"] == "PUBLISHED"
    assert payload["source_revision_id"] == review_id
    assert payload["source_revision_id"] != older_id
    assert payload["scene_document"] == reviewed_scene
    assert payload["floor_plan"] == reviewed_plan
    detail = client.get(f"/api/projects/{pid}", headers=h_cli).json()
    assert detail["project"]["status"] == "PUBLISHED"
    assert detail["document"]["stage"] == "FINAL_DESIGN"
    assert detail["current_revision"]["id"] == payload["id"]
    assert detail["current_revision"]["scene_document"] == reviewed_scene
    assert detail["current_revision"]["floor_plan"] == reviewed_plan
    assert detail["submitted_revision"] is None
    architect_detail = client.get(f"/api/projects/{pid}", headers=h_arch).json()
    assert architect_detail["current_revision"]["scene_document"] == reviewed_scene
    assert "working_scene_document" not in architect_detail["document"]


def test_architect_approve_requires_client_approval_on_latest_review(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    client.post(f"/api/projects/{pid}/candidates/{gen['candidates'][0]['id']}/accept", headers=h_arch)
    first = post_architect_review(client, pid, h_arch, review_scene("FIRST", 2.0))
    assert first.status_code == 200, first.text
    assert client.post(f"/api/projects/{pid}/client-approve", headers=h_cli).status_code == 200
    second = post_architect_review(client, pid, h_arch, review_scene("SECOND", 4.5))
    assert second.status_code == 200, second.text
    blocked = client.post(f"/api/projects/{pid}/architect-approve", headers=h_arch)
    assert blocked.status_code == 409
    assert client.post(f"/api/projects/{pid}/client-approve", headers=h_cli).status_code == 200
    allowed = client.post(f"/api/projects/{pid}/architect-approve", headers=h_arch)
    assert allowed.status_code == 200, allowed.text
    published = client.post(f"/api/projects/{pid}/publish", headers=h_arch)
    assert published.status_code == 200, published.text
    assert published.json()["source_revision_id"] == second.json()["submitted_revision_id"]
    assert published.json()["scene_document"]["rooms"][0]["name"] == "SECOND"
