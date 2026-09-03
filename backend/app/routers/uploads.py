"""Upload endpoint: validate, hash, store, enqueue."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import client_ip, enforce_upload_rate_limit, get_current_user_optional
from app.models import Job, JobStatus, User
from app.schemas import JobCreated
from app.storage import UploadValidationError, save_upload
from app.worker.tasks import enqueue_analysis

router = APIRouter(tags=["upload"])


@router.post("/upload", response_model=JobCreated, status_code=status.HTTP_202_ACCEPTED)
def upload_media(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Image, audio or video file to analyse"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> Job:
    """Accept a media file, store it with its SHA-256, and queue the analysis.

    Returns 202 with a job id: the caller then polls
    ``/api/jobs/{id}/status`` until the job leaves the queued/processing states.
    """
    enforce_upload_rate_limit(db, user, client_ip(request))

    job_id = uuid.uuid4().hex
    try:
        stored = save_upload(
            file.file,
            original_filename=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
            job_id=job_id,
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        file.file.close()

    job = Job(
        id=job_id,
        case_reference=_build_case_reference(),
        user_id=user.id if user else None,
        original_filename=stored.original_filename,
        stored_path=str(stored.path),
        media_type=stored.media_type,
        content_type=stored.content_type,
        file_size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        status=JobStatus.QUEUED,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if settings.queue_enabled:
        enqueue_analysis(job.id)
    else:
        background_tasks.add_task(enqueue_analysis, job.id)
        
    return job


def _build_case_reference() -> str:
    """Human-quotable case reference, e.g. ``DF-20260831-8A3C21``."""
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return f"DF-{stamp}-{uuid.uuid4().hex[:6].upper()}"


@router.get("/upload/limits", tags=["upload"])
def upload_limits() -> dict:
    """Advertise upload constraints so the UI can validate before sending bytes."""
    from app.storage import ALLOWED_EXTENSIONS

    return {
        "max_upload_mb": settings.max_upload_mb,
        "allowed_extensions": {
            media_type.value: sorted(extensions)
            for media_type, extensions in ALLOWED_EXTENSIONS.items()
        },
        "rate_limit_per_hour": {
            "registered": settings.upload_rate_limit_per_hour,
            "guest": settings.guest_rate_limit_per_hour,
        },
    }
