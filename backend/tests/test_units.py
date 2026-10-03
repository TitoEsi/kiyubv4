"""Meters-canonical unit boundary: adapter, legacy compatibility, preference persistence."""
from __future__ import annotations

import json
import os

os.environ["KIYUB_WORKFLOW_STUB_GENERATE"] = "1"
os.environ["KIYUB_WORKFLOW_MEMORY"] = "1"
os.environ["JWT_SECRET"] = "test-jwt-secret"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from generation_units import (
    METRIC,
    floor_plan_to_feet,
    floor_plan_to_metric,
    format_area,
    format_dimensions,
    format_measurement,
    ft2_to_m2,
    m2_to_ft2,
    normalize_comment_coords,
    normalize_floor_plan,
    normalize_questionnaire,
    normalize_scene_document,
)
from workflow import db as wfdb
from workflow.api import router
from workflow.generate import _stub_plan, brief_to_constraints, run_generation, to_engine_constraints
from workflow.models import ClientBrief, Comment, Project, Revision
from workflow.seed import READY_PROJECT_NAME, seed_users

FT = 0.3048


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


# ── Adapter ──────────────────────────────────────────────────────────────────


def test_area_and_length_conversions():
    assert abs(m2_to_ft2(20) - 215.278) < 1e-3
    assert abs(ft2_to_m2(200) - 18.5806) < 1e-4
    assert format_measurement(3.5, "m") == "3.5 m"
    assert format_measurement(3.5, "ft") == "11.48 ft"
    assert format_measurement(3.5, "mm") == "3500 mm"
    assert format_dimensions(4, 3, "m") == "4 × 3 m"
    assert format_area(20, "ft") == "215.28 ft²"
    assert format_area(20, "m") == "20 m²"


def test_floor_plan_round_trip_is_lossless():
    feet = _stub_plan(0)
    metric = floor_plan_to_metric(feet)
    assert metric["units"] == METRIC
    assert abs(metric["rooms"][0]["width"] - feet["rooms"][0]["width"] * FT) < 1e-9
    assert abs(metric["envelope"]["width"] - feet["envelope"]["width"] * FT) < 1e-9
    back = floor_plan_to_feet(metric)
    assert "units" not in back
    for a, b in zip(back["rooms"], feet["rooms"]):
        for k in ("x", "y", "width", "height"):
            assert abs(a[k] - b[k]) < 1e-9


def test_normalize_is_idempotent():
    metric = floor_plan_to_metric(_stub_plan(0))
    assert normalize_floor_plan(metric) is metric
    assert floor_plan_to_metric(metric) is metric


def test_legacy_scene_document_converts_geometry_but_not_site():
    doc = {
        "schemaVersion": 1,
        "units": "ft",
        "site": {"width": 20, "depth": 30},
        "envelope": {"width": 40, "depth": 30},
        "rooms": [{"id": "r", "x": 10, "y": 0, "width": 20, "height": 10}],
        "walls": [{"x1": 0, "y1": 0, "x2": 10, "y2": 0}],
        "openings": {"doors": [{"x": 5, "y": 0, "width": 3}], "windows": []},
    }
    out = normalize_scene_document(doc)
    assert out["units"] == METRIC
    assert out["site"] == {"width": 20, "depth": 30}
    assert abs(out["rooms"][0]["width"] - 20 * FT) < 1e-9
    assert abs(out["walls"][0]["x2"] - 10 * FT) < 1e-9
    assert abs(out["openings"]["doors"][0]["width"] - 3 * FT) < 1e-9
    assert abs(out["envelope"]["width"] - 40 * FT) < 1e-9
    assert normalize_scene_document(out) is out


def test_comment_coords():
    assert normalize_comment_coords(9, 7, None) == (9 * FT, 7 * FT)
    assert normalize_comment_coords(2.5, 1.0, METRIC) == (2.5, 1.0)


def test_living_area_metric_and_legacy_give_same_engine_sqft():
    legacy = brief_to_constraints({"house": {"livingAreaSqft": 1800}}, {})
    metric = brief_to_constraints({"house": {"livingAreaM2": ft2_to_m2(1800)}}, {})
    assert abs(legacy["livingAreaM2"] - metric["livingAreaM2"]) < 1e-9
    assert to_engine_constraints(legacy)["sqft"] == 1800
    assert to_engine_constraints(metric)["sqft"] == 1800
    assert normalize_questionnaire({"house": {"livingAreaSqft": 1800}}) == {"house": {"livingAreaM2": ft2_to_m2(1800)}}


def test_run_generation_returns_metric_plans():
    result = run_generation(brief_to_constraints({}, {}), num_variants=2)
    assert len(result["plans"]) == 2
    assert all(p["units"] == METRIC for p in result["plans"])
    feet = _stub_plan(0)
    assert abs(result["plans"][0]["rooms"][0]["width"] - feet["rooms"][0]["width"] * FT) < 1e-9
    assert "livingAreaM2" in result["applied_constraints"]


# ── Legacy persisted data served as meters ───────────────────────────────────


def _seed_project(db) -> Project:
    return db.query(Project).filter(Project.name == READY_PROJECT_NAME).one()


def test_legacy_feet_revision_is_served_in_meters(client):
    db = wfdb.SessionLocal()
    project = _seed_project(db)
    feet = _stub_plan(0)
    rev = db.query(Revision).first()
    rev.floor_plan = json.dumps(feet)
    rev.scene_document = json.dumps({"schemaVersion": 1, "units": "ft", "rooms": [{"x": 0, "y": 0, "width": 10, "height": 10}]})
    db.commit()
    rid = rev.id
    assert project.id
    db.close()

    tok = login(client, "architect@kiyub.local", "architectpass")["token"]
    r = client.get(f"/api/revisions/{rid}", headers=auth(tok))
    assert r.status_code == 200, r.text
    current = r.json()
    plan = current["floor_plan"]
    assert plan["units"] == METRIC
    assert abs(plan["rooms"][0]["width"] - feet["rooms"][0]["width"] * FT) < 1e-9
    scene = current["scene_document"]
    assert scene["units"] == METRIC
    assert abs(scene["rooms"][0]["width"] - 10 * FT) < 1e-9


def test_legacy_comment_is_served_in_meters_and_new_comment_is_metric(client):
    db = wfdb.SessionLocal()
    project = _seed_project(db)
    for c in db.query(Comment).filter(Comment.project_id == project.id).all():
        c.x, c.y, c.coord_units = 9.0, 7.0, None
    db.commit()
    pid = project.id
    db.close()

    tok = login(client, "client@kiyub.local", "clientpass")["token"]
    listed = client.get(f"/api/projects/{pid}/comments", headers=auth(tok)).json()
    legacy = next(c for c in listed if c["object_id"] == "living-0")
    assert abs(legacy["x"] - 9 * FT) < 1e-9 and abs(legacy["y"] - 7 * FT) < 1e-9
    assert legacy["coord_units"] == METRIC

    created = client.post(f"/api/projects/{pid}/comments", json={"body": "pin", "x": 2.5, "y": 1.25}, headers=auth(tok))
    assert created.status_code == 200, created.text
    assert created.json()["x"] == 2.5
    db = wfdb.SessionLocal()
    row = db.query(Comment).filter(Comment.id == created.json()["id"]).one()
    assert row.coord_units == METRIC and row.x == 2.5
    db.close()


def test_legacy_living_area_in_brief_is_served_as_m2(client):
    db = wfdb.SessionLocal()
    pid = _seed_project(db).id
    db.add(ClientBrief(
        project_id=pid,
        questionnaire=json.dumps({"house": {"livingAreaSqft": 1800}}),
        specification=json.dumps({"building": {"livingAreaSqft": 1800}}),
    ))
    db.commit()
    db.close()
    tok = login(client, "architect@kiyub.local", "architectpass")["token"]
    brief = client.get(f"/api/projects/{pid}/brief", headers=auth(tok)).json()
    assert brief["questionnaire"]["house"] == {"livingAreaM2": ft2_to_m2(1800)}
    assert brief["specification"]["building"] == {"livingAreaM2": ft2_to_m2(1800)}


# ── Preference persistence ───────────────────────────────────────────────────


def test_unit_preference_persists_per_user(client):
    arch = login(client, "architect@kiyub.local", "architectpass")
    assert arch["user"]["measurement_unit"] == "m"
    r = client.patch("/api/auth/me/preferences", json={"measurement_unit": "ft"}, headers=auth(arch["token"]))
    assert r.status_code == 200, r.text
    assert r.json()["measurement_unit"] == "ft"

    again = login(client, "architect@kiyub.local", "architectpass")
    assert again["user"]["measurement_unit"] == "ft"
    other = login(client, "client@kiyub.local", "clientpass")
    assert other["user"]["measurement_unit"] == "m"


def test_invalid_unit_rejected(client):
    tok = login(client, "architect@kiyub.local", "architectpass")["token"]
    r = client.patch("/api/auth/me/preferences", json={"measurement_unit": "yd"}, headers=auth(tok))
    assert r.status_code == 422


def test_preferences_requires_auth(client):
    r = client.patch("/api/auth/me/preferences", json={"measurement_unit": "ft"})
    assert r.status_code == 401
