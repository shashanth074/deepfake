"""ORM models: users, analysis jobs and generated forensic reports."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid.uuid4().hex


class MediaType(enum.StrEnum):
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


class JobStatus(enum.StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Verdict(enum.StrEnum):
    AUTHENTIC = "likely_authentic"
    MANIPULATED = "likely_manipulated"
    INCONCLUSIVE = "inconclusive"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    jobs: Mapped[list[Job]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Job(Base):
    """One uploaded media file and the analysis performed on it."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    case_reference: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)

    # --- Submitted file details (Phase 8, report section 2) ---
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    media_type: Mapped[MediaType] = mapped_column(Enum(MediaType), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # --- Job lifecycle ---
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.QUEUED, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    # --- Results ---
    verdict: Mapped[Verdict | None] = mapped_column(Enum(Verdict))
    fake_probability: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    model_name: Mapped[str | None] = mapped_column(String(128))
    model_version: Mapped[str | None] = mapped_column(String(64))
    weights_status: Mapped[str | None] = mapped_column(String(32))
    processing_ms: Mapped[int | None] = mapped_column(Integer)
    # Evidence payload: per-frame scores, per-segment scores, heatmap paths, notes.
    evidence: Mapped[dict | None] = mapped_column(JSON)

    user: Mapped[User | None] = relationship(back_populates="jobs")
    reports: Mapped[list[Report]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="Report.generated_at"
    )


class Report(Base):
    """A generated PDF forensic report, hashed for chain of custody."""

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True, nullable=False)
    report_reference: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    job: Mapped[Job] = relationship(back_populates="reports")


class UploadEvent(Base):
    """Upload audit trail, also used for per-user/IP rate limiting."""

    __tablename__ = "upload_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(32), index=True)
    client_ip: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
