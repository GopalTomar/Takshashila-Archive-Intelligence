"""SQLAlchemy engine / session / declarative base.

Dialect-aware: on PostgreSQL we enable pgvector; on SQLite we use a JSON
fallback for embeddings (see ``types.Vector``). The application reports
semantic search as available only when a real vector index + embeddings exist
— never faked.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

_connect_args = {}
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    connect_args=_connect_args,
)


@event.listens_for(engine, "connect")
def _on_connect(dbapi_conn, _record):  # pragma: no cover - trivial
    # Enforce foreign keys on SQLite (off by default).
    if settings.database_url.startswith("sqlite"):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def dialect_name() -> str:
    return engine.dialect.name
