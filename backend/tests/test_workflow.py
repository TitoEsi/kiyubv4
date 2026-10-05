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


def save_working(client: TestClient, pid: str, headers: dict, scene: dict) -> object:
    return client.put(f"/api/projects/{pid}/working-design", json={"scene_document": scene}, headers=headers)


def revision_count(client: TestClient, pid: str, headers: dict, source_type: str | None = None) -> int:
    rows = client.get(f"/api/projects/{pid}/revisions", headers=headers).json()
    return len([r for r in rows if source_type is None or r["source_type"] == source_type])


def test_client_cannot_edit_design(client):
    ctx = provision(client)
    generate(client, ctx)
    r = save_working(client, ctx["project"]["id"], auth(ctx["tokens"]["client"]["token"]), review_scene("C"))
    assert r.status_code == 403


def test_architect_can_edit_assigned(client):
    ctx = provision(client)
    generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    r = save_working(client, pid, h_arch, review_scene("Edited", 4.0))
    assert r.status_code == 200, r.text
    detail = client.get(f"/api/projects/{pid}", headers=h_arch).json()
    assert detail["document"]["working_scene_document"]["rooms"][0]["name"] == "Edited"
    assert detail["document"]["stage"] == "ARCHITECT_DESIGN"


def test_published_mutation_409(client):
    ctx = provision(client)
    generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    assert post_architect_review(client, pid, h_arch).status_code == 200
    assert client.post(f"/api/projects/{pid}/client-approve", headers=h_cli).status_code == 200
    assert client.post(f"/api/projects/{pid}/architect-approve", headers=h_arch).status_code == 200
    pub = client.post(f"/api/projects/{pid}/publish", headers=h_arch)
    assert pub.status_code == 200, pub.text
    r = save_working(client, pid, h_arch, review_scene("After publish"))
    assert r.status_code in (403, 409)


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
    submitted = post_architect_review(client, pid, h_arch)
    assert submitted.status_code == 200, submitted.text
    before = submitted.json()["submitted_revision_id"]

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


def test_architect_cannot_accept_candidate(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    before = revision_count(client, pid, h_arch)
    r = client.post(f"/api/projects/{pid}/candidates/{gen['candidates'][0]['id']}/accept", headers=h_arch)
    assert r.status_code in (404, 405)
    assert revision_count(client, pid, h_arch) == before
    detail = client.get(f"/api/projects/{pid}", headers=h_arch).json()
    assert detail["document"]["current_revision_id"] is None


def test_revision_design_save_endpoint_removed(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    before = revision_count(client, pid, h_arch)
    r = client.put(
        f"/api/revisions/{gen['candidates'][0]['revision_id']}/design",
        json={"floor_plan": gen["candidates"][0]["floor_plan"]},
        headers=h_arch,
    )
    assert r.status_code in (404, 405)
    assert revision_count(client, pid, h_arch) == before


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
    assert gone.status_code in (404, 405)
    listed2 = client.get(f"/api/projects/{pid}/comments", headers=auth(ctx["tokens"]["client"]["token"])).json()
    assert len(listed2) == 3


def test_request_revision_endpoint_removed(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    assert post_architect_review(client, pid, h_arch).status_code == 200
    r = client.post(f"/api/projects/{pid}/request-revision", headers=h_cli)
    assert r.status_code == 404


def test_approve_and_publish(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
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


def test_admin_cannot_edit(client):
    ctx = provision(client)
    generate(client, ctx)
    r = save_working(client, ctx["project"]["id"], auth(ctx["tokens"]["admin"]["token"]), review_scene("Admin"))
    assert r.status_code == 403


def test_unapproved_architect_login_blocked(client):
    tok = ids(client)
    created = client.post(
        "/api/architect-applications",
        json={"email": "pending@kiyub.local", "full_name": "Pending Architect", "information": "Studio"},
        headers=auth(tok["admin"]["token"]),
    )
    assert created.status_code == 200, created.text
    assert created.json()["status"] == "APPROVED"
    denied = client.post("/api/auth/login", json={"email": "pending@kiyub.local", "password": "pendingpass"})
    assert denied.status_code == 401
    token = created.json()["token"]
    done = client.post(
        f"/api/architect-applications/by-token/{token}/complete",
        json={"password": "pendingpass", "role": "ADMIN", **ACCEPT},
    )
    assert done.status_code == 200, done.text
    assert done.json()["user"]["role"] == "ARCHITECT"
    assert login(client, "pending@kiyub.local", "pendingpass")["user"]["approved"] is True


def test_audit_events_recorded(client):
    ctx = provision(client)
    generate(client, ctx)
    r = client.get("/api/audit", headers=auth(ctx["tokens"]["admin"]["token"]))
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
    client.post(
        f"/api/architect-applications/by-token/{pending.json()['token']}/complete",
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
    users = client.get("/api/accounts", headers=auth(ids(client)["admin"]["token"])).json()
    emails = sorted(u["email"] for u in users)
    assert emails == [
        "admin@kiyub.local",
        "architect@kiyub.local",
        "client@kiyub.local",
    ]
    assert sorted(u["role"] for u in users) == ["ADMIN", "ARCHITECT", "CLIENT"]
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
    assert db.query(User).count() == 3
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
    listed = client.get("/api/inquiries", headers=auth(tok["admin"]["token"]))
    assert listed.status_code == 200
    assert any(row["email"] == "ada@example.com" for row in listed.json())
    denied = client.get("/api/inquiries", headers=auth(tok["client"]["token"]))
    assert denied.status_code == 403
    architect_denied = client.get("/api/inquiries", headers=auth(tok["architect"]["token"]))
    assert architect_denied.status_code == 403


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
    generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    submitted = post_architect_review(client, pid, h_arch, review_scene("Reviewed"))
    assert submitted.status_code == 200, submitted.text
    count = revision_count(client, pid, h_arch)
    for i in range(4):
        r = save_working(client, pid, h_arch, review_scene(f"Draft {i}", 3.0 + i))
        assert r.status_code == 200, r.text
    assert revision_count(client, pid, h_arch) == count
    architect_detail = client.get(f"/api/projects/{pid}", headers=h_arch).json()
    assert architect_detail["document"]["working_scene_document"]["rooms"][0]["name"] == "Draft 3"
    client_detail = client.get(f"/api/projects/{pid}", headers=auth(ctx["tokens"]["client"]["token"])).json()
    assert "working_scene_document" not in client_detail["document"]
    assert client_detail["current_revision"]["id"] == submitted.json()["submitted_revision_id"]
    assert client_detail["submitted_revision"]["scene_document"]["rooms"][0]["name"] == "Reviewed"


def full_scene(label: str = "Full") -> dict:
    scene = review_scene(label, 5.0)
    scene["walls"].append({"id": "w-2", "start": {"x": 5, "y": 0}, "end": {"x": 5, "y": 4}, "thickness": 0.2, "height": 2.7})
    scene["openings"] = [
        {"id": "d-1", "type": "door", "wallId": f"w-{label}", "position": 1.2, "width": 0.9, "height": 2.1, "hinge": "left", "swing": "in"},
        {"id": "win-1", "type": "window", "wallId": "w-2", "position": 2.0, "width": 1.2, "height": 1.2, "sillHeight": 0.9},
    ]
    scene["furniture"] = [{"id": "f-1", "kind": "bed", "roomId": f"r-{label}", "position": {"x": 1, "y": 1}, "rotation": 90}]
    scene["floorData"] = {"ceilingHeight": 2.7, "floors": 1}
    scene["site"] = {"width": 12, "depth": 10, "north": 15}
    scene["measurements"] = [{"id": "m-1", "from": {"x": 0, "y": 0}, "to": {"x": 5, "y": 0}}]
    scene["metadata"] = {"createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z", "generator": "kiyub", "style": "modern"}
    return scene


def test_send_to_review_versions_only_on_persisted_change(client):
    ctx = provision(client)
    generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    base = revision_count(client, pid, h_arch)
    scene = full_scene()

    first = post_architect_review(client, pid, h_arch, scene)
    assert first.status_code == 200, first.text
    assert first.json()["created"] is True
    assert first.json()["status"] == "FOR_CHECKING"
    assert revision_count(client, pid, h_arch) == base + 1
    review_id = first.json()["submitted_revision_id"]
    detail = client.get(f"/api/projects/{pid}", headers=h_cli).json()
    assert detail["project"]["status"] == "FOR_CHECKING"
    assert detail["document"]["current_revision_id"] == review_id
    assert detail["current_revision"]["id"] == review_id
    assert detail["submitted_revision"]["id"] == review_id
    assert detail["submitted_revision"]["scene_document"] == scene

    repeat = post_architect_review(client, pid, h_arch, scene)
    assert repeat.json()["created"] is False
    assert repeat.json()["submitted_revision_id"] == review_id
    assert revision_count(client, pid, h_arch) == base + 1

    touched = {**scene, "metadata": {**scene["metadata"], "updatedAt": "2026-02-02T00:00:00Z", "createdAt": "2026-02-02T00:00:00Z"}}
    assert post_architect_review(client, pid, h_arch, touched).json()["created"] is False

    edited = full_scene()
    edited["walls"][1]["end"]["y"] = 6
    assert save_working(client, pid, h_arch, edited).status_code == 200
    assert save_working(client, pid, h_arch, scene).status_code == 200
    reverted = client.post(f"/api/projects/{pid}/submit-review", json={}, headers=h_arch)
    assert reverted.status_code == 200, reverted.text
    assert reverted.json()["created"] is False
    assert revision_count(client, pid, h_arch) == base + 1

    assert save_working(client, pid, h_arch, edited).status_code == 200
    from_persisted = client.post(f"/api/projects/{pid}/submit-review", json={}, headers=h_arch)
    assert from_persisted.json()["created"] is True
    assert from_persisted.json()["version"] > first.json()["version"]
    assert revision_count(client, pid, h_arch) == base + 2
    seen = client.get(f"/api/projects/{pid}", headers=h_cli).json()
    assert seen["project"]["status"] == "FOR_CHECKING"
    assert seen["submitted_revision"]["id"] == from_persisted.json()["submitted_revision_id"]
    assert seen["submitted_revision"]["scene_document"]["walls"][1]["end"]["y"] == 6
    assert seen["submitted_revision"]["scene_document"]["furniture"] == scene["furniture"]

    assert post_architect_review(client, pid, h_arch, edited).json()["created"] is False
    assert revision_count(client, pid, h_arch, "REVIEW") == 2
    notes = client.get("/api/notifications", headers=h_cli).json()
    assert any("is ready for your review" in n["message"] for n in notes)


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
    generate(client, ctx)
    submitted_a = post_architect_review(client, pid_a, h_arch, review_scene("A"))
    assert submitted_a.status_code == 200, submitted_a.text
    rev_a = submitted_a.json()["submitted_revision_id"]
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
    submitted_b = post_architect_review(client, pid_b, h_arch, review_scene("B"))
    assert submitted_b.status_code == 200, submitted_b.text
    after_a = client.get(f"/api/projects/{pid_a}", headers=h_cli).json()
    after_b = client.get(f"/api/projects/{pid_b}", headers=h_cli).json()
    assert after_a["document"]["current_revision_id"] == rev_a
    assert after_b["document"]["current_revision_id"] == submitted_b.json()["submitted_revision_id"]
    assert after_b["document"]["current_revision_id"] != rev_a

    db = wfdb.SessionLocal()
    try:
        assert db.query(User).filter(User.email == email).count() == 1
        docs = db.query(DesignDocument).filter(DesignDocument.project_id.in_([pid_a, pid_b])).all()
        assert {d.project_id for d in docs} == {pid_a, pid_b}
    finally:
        db.close()


def test_client_selection_and_generation_still_work_after_review(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    submitted = post_architect_review(client, pid, h_arch, review_scene("OLD", 2.0))
    assert submitted.status_code == 200, submitted.text
    later = gen["candidates"][-1]
    selected = client.post(f"/api/projects/{pid}/candidates/{later['id']}/select", headers=h_cli)
    assert selected.status_code == 200, selected.text
    again = client.post(f"/api/projects/{pid}/generate", headers=h_cli)
    assert again.status_code == 200, again.text
    after = client.get(f"/api/projects/{pid}", headers=h_cli).json()
    assert after["submitted_revision"]["id"] == submitted.json()["submitted_revision_id"]
    assert after["current_revision"]["id"] == submitted.json()["submitted_revision_id"]


def test_publish_uses_reviewed_scene_not_older_current(client):
    ctx = provision(client)
    gen = generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    older = post_architect_review(client, pid, h_arch, review_scene("OLDER", 2.0))
    assert older.status_code == 200, older.text
    older_id = older.json()["submitted_revision_id"]
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


@pytest.mark.parametrize("style", ["farmhouse", "craftsman"])
def test_retired_style_brief_stays_readable_but_cannot_generate(client, style):
    from workflow.models import GenerationJob

    ctx = provision(client)
    pid = ctx["project"]["id"]
    h_cli = auth(ctx["tokens"]["client"]["token"])
    legacy = {**BRIEF, "preferences": {**BRIEF["preferences"], "style": style}}
    saved = client.put(
        f"/api/projects/{pid}/brief",
        json={"questionnaire": legacy, "specification": {"style": style}},
        headers=h_cli,
    )
    assert saved.status_code == 200, saved.text
    read = client.get(f"/api/projects/{pid}/brief", headers=h_cli)
    assert read.status_code == 200, read.text
    assert read.json()["questionnaire"]["preferences"]["style"] == style

    r = client.post(f"/api/projects/{pid}/generate", headers=h_cli)
    assert r.status_code == 422
    assert "no longer offered" in r.json()["detail"]
    db = wfdb.SessionLocal()
    assert db.query(GenerationJob).filter(GenerationJob.project_id == pid).count() == 0
    db.close()
    assert client.get(f"/api/projects/{pid}/brief", headers=h_cli).json()["questionnaire"]["preferences"]["style"] == style

    fixed = {**BRIEF, "preferences": {**BRIEF["preferences"], "style": "japandi"}}
    client.put(f"/api/projects/{pid}/brief", json={"questionnaire": fixed, "specification": {"style": "japandi"}}, headers=h_cli)
    assert client.post(f"/api/projects/{pid}/generate", headers=h_cli).status_code == 200


def _activity(client: TestClient, pid: str, headers: dict) -> list[dict]:
    r = client.get(f"/api/projects/{pid}/activity", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _notes(client: TestClient, headers: dict) -> list[str]:
    return [n["kind"] for n in client.get("/api/notifications", headers=headers).json()]


def test_comment_threads_edits_and_architect_only_resolution(client):
    ctx = provision(client)
    generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    first = post_architect_review(client, pid, h_arch, review_scene("V1", 3.0))
    v1_id = first.json()["submitted_revision_id"]

    created = client.post(f"/api/projects/{pid}/comments", json={"body": "Move Bedroom 2 door away from the hallway.", "x": 1.0, "y": 2.0}, headers=h_cli)
    assert created.status_code == 200, created.text
    cid = created.json()["id"]
    assert created.json()["revision_id"] == v1_id
    assert created.json()["resolved"] is False
    reply = client.post(f"/api/projects/{pid}/comments", json={"body": "Done. I moved it 600mm.", "parent_id": cid, "x": 9, "y": 9}, headers=h_arch)
    assert reply.status_code == 200, reply.text
    assert reply.json()["parent_id"] == cid
    assert reply.json()["x"] is None
    nested = client.post(f"/api/projects/{pid}/comments", json={"body": "Looks good.", "parent_id": reply.json()["id"]}, headers=h_cli)
    assert nested.json()["parent_id"] == cid

    edited = client.patch(f"/api/projects/{pid}/comments/{cid}", json={"body": "Move Bedroom 2 door 600mm away from the hallway."}, headers=h_cli)
    assert edited.status_code == 200, edited.text
    assert edited.json()["updated_at"]
    history = edited.json()["edit_history"]
    assert len(history) == 1
    assert history[0]["previous"] == "Move Bedroom 2 door away from the hallway."
    assert history[0]["body"] == "Move Bedroom 2 door 600mm away from the hallway."
    assert history[0]["edited_by_role"] == "CLIENT"

    assert client.post(f"/api/projects/{pid}/comments/{cid}/resolve", json={"resolved": True}, headers=h_cli).status_code == 403
    assert client.post(f"/api/projects/{pid}/comments/{reply.json()['id']}/resolve", json={"resolved": True}, headers=h_arch).status_code == 400
    resolved = client.post(f"/api/projects/{pid}/comments/{cid}/resolve", json={"resolved": True, "note": "Bedroom 2 door moved 600mm."}, headers=h_arch)
    assert resolved.status_code == 200, resolved.text
    body = resolved.json()
    assert body["resolved"] is True and body["resolved_at"] and body["resolved_by_role"] == "ARCHITECT"
    assert body["resolution_note"] == "Bedroom 2 door moved 600mm."
    assert body["resolution_version"] is None

    listed = client.get(f"/api/projects/{pid}/comments", headers=h_cli).json()
    assert len(listed) == 3
    assert next(c for c in listed if c["id"] == cid)["resolved"] is True
    assert client.delete(f"/api/projects/{pid}/comments/{cid}", headers=h_arch).status_code in (404, 405)

    second = post_architect_review(client, pid, h_arch, review_scene("V2", 4.0))
    assert second.json()["created"] is True
    after = next(c for c in client.get(f"/api/projects/{pid}/comments", headers=h_cli).json() if c["id"] == cid)
    assert after["resolution_revision_id"] == second.json()["submitted_revision_id"]
    assert after["resolution_version"] == second.json()["version"]

    activity = _activity(client, pid, h_cli)
    types = [a["event_type"] for a in activity]
    for t in ("COMMENT_CREATED", "COMMENT_REPLIED", "COMMENT_EDITED", "COMMENT_RESOLVED", "VERSION_SUBMITTED", "STATUS_CHANGED"):
        assert t in types, t
    resolved_entry = next(a for a in activity if a["event_type"] == "COMMENT_RESOLVED")
    assert resolved_entry["actor_role"] == "ARCHITECT"
    assert resolved_entry["metadata"]["body"] == "Move Bedroom 2 door 600mm away from the hallway."
    assert resolved_entry["metadata"]["note"] == "Bedroom 2 door moved 600mm."
    assert resolved_entry["comment"]["resolution_version"] == second.json()["version"]
    edit_entry = next(a for a in activity if a["event_type"] == "COMMENT_EDITED")
    assert edit_entry["metadata"]["previous"] == "Move Bedroom 2 door away from the hallway."
    submitted_entry = next(a for a in activity if a["event_type"] == "VERSION_SUBMITTED" and a["version"] == second.json()["version"])
    assert submitted_entry["metadata"]["resolved_comment_ids"] == [cid]
    assert submitted_entry["metadata"]["changes"]
    assert _activity(client, pid, h_arch)[0]["id"] == activity[0]["id"]

    cli_kinds = _notes(client, h_cli)
    arch_kinds = _notes(client, h_arch)
    assert "COMMENT_CREATED" in arch_kinds and "COMMENT_EDITED" in arch_kinds and "COMMENT_REPLIED" in arch_kinds
    assert "COMMENT_REPLIED" in cli_kinds and "COMMENT_RESOLVED" in cli_kinds and "VERSION_SUBMITTED" in cli_kinds

    reopened = client.post(f"/api/projects/{pid}/comments/{cid}/resolve", json={"resolved": False}, headers=h_arch)
    assert reopened.json()["resolved"] is False
    assert "COMMENT_REOPENED" in [a["event_type"] for a in _activity(client, pid, h_arch)]


def test_activity_is_append_only(client):
    ctx = provision(client)
    generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    post_architect_review(client, pid, h_arch)
    entry = _activity(client, pid, h_arch)[0]
    for method in ("put", "patch", "delete"):
        r = getattr(client, method)(f"/api/projects/{pid}/activity", headers=h_arch)
        assert r.status_code == 405
        r = getattr(client, method)(f"/api/projects/{pid}/activity/{entry['id']}", headers=h_arch)
        assert r.status_code in (404, 405)
    assert _activity(client, pid, h_arch)[0] == entry


def test_restore_creates_new_version_and_keeps_original(client):
    ctx = provision(client)
    generate(client, ctx)
    pid = ctx["project"]["id"]
    h_arch = auth(ctx["tokens"]["architect"]["token"])
    h_cli = auth(ctx["tokens"]["client"]["token"])
    v_a = post_architect_review(client, pid, h_arch, full_scene("A")).json()
    v_b = post_architect_review(client, pid, h_arch, review_scene("B", 6.0)).json()
    original = client.get(f"/api/revisions/{v_a['submitted_revision_id']}", headers=h_arch).json()

    assert client.post(f"/api/revisions/{v_a['submitted_revision_id']}/restore", headers=h_cli).status_code == 403
    restored = client.post(f"/api/revisions/{v_a['submitted_revision_id']}/restore", headers=h_arch)
    assert restored.status_code == 200, restored.text
    r = restored.json()
    assert r["source_type"] == "RESTORED"
    assert r["version"] == v_b["version"] + 1
    assert r["source_revision_id"] == v_a["submitted_revision_id"]
    assert r["scene_document"] == original["scene_document"]
    assert client.get(f"/api/revisions/{v_a['submitted_revision_id']}", headers=h_arch).json() == original

    arch_detail = client.get(f"/api/projects/{pid}", headers=h_arch).json()
    assert arch_detail["document"]["current_revision_id"] == r["id"]
    assert arch_detail["document"]["working_scene_document"] == original["scene_document"]
    cli_detail = client.get(f"/api/projects/{pid}", headers=h_cli).json()
    assert cli_detail["submitted_revision"]["id"] == v_b["submitted_revision_id"]
    assert cli_detail["current_revision"]["id"] == v_b["submitted_revision_id"]
    assert r["id"] not in [x["id"] for x in client.get(f"/api/projects/{pid}/revisions", headers=h_cli).json()]
    assert client.get(f"/api/revisions/{r['id']}", headers=h_cli).status_code == 404

    during_draft = client.post(f"/api/projects/{pid}/comments", json={"body": "Seen while drafting"}, headers=h_cli).json()
    assert during_draft["revision_id"] == v_b["submitted_revision_id"]

    restore_entry = next(a for a in _activity(client, pid, h_cli) if a["event_type"] == "VERSION_RESTORED")
    assert restore_entry["metadata"]["from_version"] == v_a["version"]
    assert restore_entry["metadata"]["to_version"] == r["version"]
    assert "VERSION_RESTORED" in _notes(client, h_cli)

    count = revision_count(client, pid, h_arch)
    sent = client.post(f"/api/projects/{pid}/submit-review", json={}, headers=h_arch).json()
    assert sent["created"] is False
    assert sent["submitted_revision_id"] == r["id"]
    assert sent["version"] == r["version"]
    assert revision_count(client, pid, h_arch) == count
    seen = client.get(f"/api/projects/{pid}", headers=h_cli).json()
    assert seen["submitted_revision"]["id"] == r["id"]
    assert r["submitted_at"] is None
    listed = {x["id"]: x for x in client.get(f"/api/projects/{pid}/revisions", headers=h_cli).json()}
    assert listed[r["id"]]["submitted_at"]
    submitted_entry = next(a for a in _activity(client, pid, h_cli) if a["event_type"] == "VERSION_SUBMITTED" and a["version"] == r["version"])
    assert submitted_entry["metadata"]["restored_from_version"] == v_a["version"]
    again = client.post(f"/api/projects/{pid}/submit-review", json={}, headers=h_arch).json()
    assert again["created"] is False
    assert len([a for a in _activity(client, pid, h_arch) if a["event_type"] == "VERSION_SUBMITTED" and a["version"] == r["version"]]) == 1
