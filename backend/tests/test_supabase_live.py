"""Optional live Supabase checks. Skipped unless SUPABASE_URL is set."""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
    reason="SUPABASE_URL not set",
)


def test_profile_project_brief_round_trip():
    os.environ.pop("KIYUB_WORKFLOW_MEMORY", None)
    from supabase.client import get_service_client, reset_clients
    from workflow.auth import provision_user
    from workflow.db import SessionLocal, configure
    from workflow.models import ClientBrief, DesignDocument, Project, Revision, SiteConstraint, User
    from workflow.services import _sync_site_constraints

    reset_clients()
    configure()
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    try:
        user = provision_user(db, f"live-{suffix}@kiyub.local", "LivePass!1", "ARCHITECT", True)
        db.flush()
        project = Project(name=f"Live {suffix}", architect_id=user.id, status="DRAFT")
        db.add(project)
        db.flush()
        db.add(ClientBrief(
            project_id=project.id,
            questionnaire='{"site":{"lotShape":"rectangle","lotWidth":18,"lotDepth":27}}',
            specification="{}",
        ))
        _sync_site_constraints(db, project.id, {"site": {"lotShape": "rectangle", "lotWidth": 18, "lotDepth": 27}})
        doc = DesignDocument(project_id=project.id, stage="CLIENT_BRIEF")
        db.add(doc)
        db.flush()
        rev = Revision(
            design_document_id=doc.id,
            version=1,
            scene_document='{"schemaVersion":"2.0","site":{"width":18,"depth":27}}',
            floor_plan="{}",
            created_by=user.id,
            source_type="AI_GENERATED",
        )
        db.add(rev)
        db.commit()

        other = SessionLocal()
        try:
            assert other.get(Project, project.id) is not None
            site = other.query(SiteConstraint).filter(SiteConstraint.project_id == project.id).one()
            assert site.lot_width == 18
            assert site.lot_depth == 27
            stored = other.get(Revision, rev.id)
            assert stored is not None
            assert "18" in stored.scene_document
            assert other.get(User, user.id).role == "ARCHITECT"
        finally:
            other.close()

        with pytest.raises(Exception):
            get_service_client().table("revisions").insert({
                "design_document_id": doc.id,
                "version": 1,
                "scene_document": {},
                "floor_plan": {},
                "created_by": user.id,
                "source_type": "AI_GENERATED",
            }).execute()
    finally:
        db.close()
