"""Workflow database session. SQLite by default; DATABASE_URL may point at Postgres."""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

DB_PATH = Path(__file__).resolve().parent.parent / "kiyub_workflow.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")

engine = None
SessionLocal = None


class Base(DeclarativeBase):
    pass


def _attach_sqlite_fk(eng) -> None:
    if not str(eng.url).startswith("sqlite"):
        return

    @event.listens_for(eng, "connect")
    def _fk_pragma(dbapi_conn, _rec):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def configure(url: str | None = None) -> None:
    global engine, SessionLocal, DATABASE_URL
    DATABASE_URL = url or os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")
    kwargs: dict = {"future": True}
    if DATABASE_URL.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in DATABASE_URL:
            kwargs["poolclass"] = StaticPool
    engine = create_engine(DATABASE_URL, **kwargs)
    _attach_sqlite_fk(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


configure()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _ensure_comment_xy()
    _ensure_working_scene()


def _ensure_comment_xy() -> None:
    from sqlalchemy import inspect, text
    if engine is None:
        return
    insp = inspect(engine)
    if "comments" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("comments")}
    with engine.begin() as conn:
        if "x" not in cols:
            conn.execute(text("ALTER TABLE comments ADD COLUMN x FLOAT"))
        if "y" not in cols:
            conn.execute(text("ALTER TABLE comments ADD COLUMN y FLOAT"))


def _ensure_working_scene() -> None:
    from sqlalchemy import inspect, text
    if engine is None:
        return
    insp = inspect(engine)
    if "design_documents" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("design_documents")}
    with engine.begin() as conn:
        if "working_scene_document" not in cols:
            conn.execute(text("ALTER TABLE design_documents ADD COLUMN working_scene_document TEXT"))
        if "working_updated_at" not in cols:
            conn.execute(text("ALTER TABLE design_documents ADD COLUMN working_updated_at DATETIME"))
