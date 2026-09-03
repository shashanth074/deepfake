"""SQLAlchemy engine, session factory and declarative base."""

from __future__ import annotations

import logging
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

logger = logging.getLogger(__name__)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Prepare the database for the running application.

    In development the schema is created directly, so a fresh clone runs with no
    extra step. In production this is deliberately a no-op: the schema is owned
    by Alembic (``alembic upgrade head``), because ``create_all`` only ever adds
    missing tables — it cannot alter a column, backfill data, or be rolled back,
    so relying on it silently diverges a live database from the models.
    """
    from app import models  # noqa: F401  (registers the mappers)

    settings.ensure_directories()

    if settings.environment.lower() == "production":
        logger.info("Production: skipping create_all; run 'alembic upgrade head' to migrate.")
        return

    Base.metadata.create_all(bind=engine)
