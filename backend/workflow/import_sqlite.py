"""One-shot CLI: import a legacy kiyub_workflow.db into Supabase.

Not imported by API startup. Does not copy password hashes. Does not dual-write.
Run: python -m workflow.import_sqlite [path] --password ...
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from supabase.auth import admin_create_user, admin_user_id_by_email
from supabase.client import supabase_configured
from workflow.db import SessionLocal, configure
from workflow.models import (
    AICandidate,
    Approval,
    AuditEvent,
    ClientBrief,
    Comment,
    DesignDocument,
    GenerationJob,
    HistoricalActor,
    Inquiry,
    Invitation,
    Notification,
    Project,
    Revision,
    User,
)
from workflow.services import _sync_site_constraints

LEGACY_ROLE_MAP = {"MAIN_ADMIN": "ADMIN"}
RETIRED_ROLES = {"IT_PERSONNEL"}

TABLE_MODELS = (
    ("projects", Project),
    ("client_briefs", ClientBrief),
    ("design_documents", DesignDocument),
    ("revisions", Revision),
    ("generation_jobs", GenerationJob),
    ("ai_candidates", AICandidate),
    ("comments", Comment),
    ("approvals", Approval),
    ("audit_events", AuditEvent),
    ("notifications", Notification),
    ("invitations", Invitation),
    ("inquiries", Inquiry),
)


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False


def _parse_dt(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def import_sqlite(db_path: Path, default_password: str, skip_existing_auth: bool = True) -> dict:
    if not supabase_configured():
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    configure()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    report = {"users": [], "skipped": [], "imported": {}, "site_constraints": 0}
    db = SessionLocal()
    try:
        user_map: dict[str, str] = {}
        historical_ids: set[str] = set()
        try:
            users = conn.execute("select * from users").fetchall()
        except sqlite3.Error:
            users = conn.execute("select * from profiles").fetchall()
        for raw in users:
            row = dict(raw)
            email = (row.get("email") or "").lower().strip()
            old_id = str(row.get("id"))
            role = LEGACY_ROLE_MAP.get(row.get("role") or "CLIENT", row.get("role") or "CLIENT")
            approved = bool(row.get("approved", True))
            if role in RETIRED_ROLES:
                # Retired roles are not recreated as accounts; keep only the identity for audit history.
                hist_id = old_id if _is_uuid(old_id) else str(uuid.uuid4())
                if db.get(HistoricalActor, hist_id) is None:
                    db.add(HistoricalActor(id=hist_id, email=email, full_name=row.get("full_name"), role=role))
                user_map[old_id] = hist_id
                historical_ids.add(hist_id)
                report["users"].append({"email": email, "old_id": old_id, "new_id": hist_id, "auth": "historical"})
                continue
            existing = admin_user_id_by_email(email)
            if existing:
                user_map[old_id] = existing
                report["users"].append({"email": email, "old_id": old_id, "new_id": existing, "auth": "exists"})
                if skip_existing_auth:
                    continue
            try:
                new_id = existing or admin_create_user(
                    email,
                    default_password,
                    role,
                    approved,
                    user_id=old_id if _is_uuid(old_id) else None,
                )
            except Exception as exc:
                report["skipped"].append({"email": email, "reason": str(exc)})
                continue
            user_map[old_id] = new_id
            profile = db.get(User, new_id)
            if profile is None:
                db.add(User(id=new_id, email=email, role=role, approved=approved, password_hash=""))
            else:
                profile.email = email
                profile.role = role
                profile.approved = approved
            report["users"].append({"email": email, "old_id": old_id, "new_id": new_id, "auth": "created" if not existing else "exists"})
        db.commit()

        def remap(uid):
            if uid is None:
                return None
            return user_map.get(str(uid), uid if _is_uuid(str(uid)) else None)

        for table, model in TABLE_MODELS:
            try:
                rows = conn.execute(f"select * from {table}").fetchall()
            except sqlite3.Error:
                report["imported"][table] = 0
                continue
            count = 0
            for raw in rows:
                data = dict(raw)
                ident = str(data.get("id"))
                if not _is_uuid(ident):
                    report["skipped"].append({"table": table, "id": ident, "reason": "non-uuid id"})
                    continue
                if db.get(model, ident):
                    continue
                if "client_id" in data:
                    data["client_id"] = remap(data.get("client_id"))
                if "architect_id" in data:
                    data["architect_id"] = remap(data.get("architect_id"))
                if "author_id" in data:
                    data["author_id"] = remap(data.get("author_id"))
                if "actor_id" in data:
                    data["actor_id"] = remap(data.get("actor_id"))
                if "created_by" in data:
                    data["created_by"] = remap(data.get("created_by"))
                if "requested_by" in data:
                    data["requested_by"] = remap(data.get("requested_by"))
                if "user_id" in data:
                    data["user_id"] = remap(data.get("user_id"))
                    if data["user_id"] in historical_ids:
                        continue
                if "accepted_user_id" in data:
                    data["accepted_user_id"] = remap(data.get("accepted_user_id"))
                data.pop("password_hash", None)
                for key in list(data):
                    if key.endswith("_at"):
                        data[key] = _parse_dt(data[key])
                obj = model(**{k: v for k, v in data.items() if k in model.__dataclass_fields__})
                db.add(obj)
                count += 1
            db.commit()
            report["imported"][table] = count

        briefs = db.query(ClientBrief).all()
        for brief in briefs:
            try:
                questionnaire = json.loads(brief.questionnaire or "{}")
            except json.JSONDecodeError:
                questionnaire = {}
            _sync_site_constraints(db, brief.project_id, questionnaire)
            report["site_constraints"] += 1
        db.commit()
    finally:
        db.close()
        conn.close()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import SQLite workflow data into Supabase")
    parser.add_argument("db_path", nargs="?", default=str(Path(__file__).resolve().parent.parent / "kiyub_workflow.db"))
    parser.add_argument("--password", default="ChangeMeNow!1", help="Password for newly created Auth users")
    args = parser.parse_args(argv)
    report = import_sqlite(Path(args.db_path), args.password)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
