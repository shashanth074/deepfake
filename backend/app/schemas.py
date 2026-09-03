"""Pydantic request/response schemas for the public API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import JobStatus, MediaType, Verdict

RESULT_DISCLAIMER = (
    "This is an automated technical assessment, not a certified forensic opinion. "
    "For legal proceedings, verification by a certified forensic expert is recommended."
)


# --------------------------------------------------------------------------- auth
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=200)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    full_name: str | None
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


# --------------------------------------------------------------------------- jobs
class JobCreated(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_reference: str
    media_type: MediaType
    status: JobStatus
    original_filename: str
    sha256: str
    file_size_bytes: int
    uploaded_at: datetime


class JobStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_reference: str
    status: JobStatus
    media_type: MediaType
    uploaded_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class EvidenceOut(BaseModel):
    """Model evidence: shape varies by media type, hence the permissive typing."""

    heatmap_url: str | None = None
    spectrogram_url: str | None = None
    frame_scores: list[dict] | None = None
    segment_scores: list[dict] | None = None
    faces_detected: int | None = None
    notes: list[str] = Field(default_factory=list)


class JobResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_reference: str
    status: JobStatus
    media_type: MediaType
    original_filename: str
    sha256: str
    file_size_bytes: int
    uploaded_at: datetime
    finished_at: datetime | None = None

    verdict: Verdict | None = None
    fake_probability: float | None = None
    confidence: float | None = None
    model_name: str | None = None
    model_version: str | None = None
    weights_status: str | None = None
    processing_ms: int | None = None
    evidence: dict | None = None
    disclaimer: str = RESULT_DISCLAIMER


class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_reference: str
    original_filename: str
    media_type: MediaType
    status: JobStatus
    verdict: Verdict | None = None
    fake_probability: float | None = None
    uploaded_at: datetime
    has_report: bool = False


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    total: int
    limit: int
    offset: int


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    report_reference: str
    sha256: str
    generated_at: datetime
    download_url: str


class HealthOut(BaseModel):
    status: str
    version: str
    queue_enabled: bool
    models: dict[str, str]
