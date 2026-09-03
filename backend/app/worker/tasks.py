"""Celery tasks: run a detection pipeline and persist the result."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from app.config import settings
from app.database import SessionLocal
from app.ml.base import DetectorUnavailableError
from app.models import Job, JobStatus
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="jobs.analyze", bind=True, max_retries=1, default_retry_delay=10)
def analyze_job(self, job_id: str) -> dict:
    """Run detection for ``job_id`` and write the verdict back to the database."""
    from app.ml.pipeline import analyze

    session = SessionLocal()
    started = time.perf_counter()
    try:
        job = session.get(Job, job_id)
        if job is None:
            logger.error("Job %s not found", job_id)
            return {"job_id": job_id, "status": "missing"}

        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now(UTC)
        session.commit()

        try:
            result = analyze(job.media_type, job.stored_path, settings.evidence_dir, job.id)
        except DetectorUnavailableError as exc:
            return _fail(session, job, f"Detection backend unavailable: {exc}")
        except FileNotFoundError:
            return _fail(session, job, "Stored media file is missing.")
        except ValueError as exc:
            # Unreadable/corrupt media — a user error, so do not retry.
            return _fail(session, job, f"Could not analyse the submitted file: {exc}")
        except Exception as exc:  # pragma: no cover - unexpected runtime failure
            logger.exception("Analysis crashed for job %s", job_id)
            return _fail(session, job, f"Analysis failed: {exc}")

        job.status = JobStatus.DONE
        job.fake_probability = result.fake_probability
        job.verdict = result.verdict
        job.confidence = result.confidence
        job.model_name = result.model_name
        job.model_version = result.model_version
        job.weights_status = result.weights_status
        job.evidence = result.evidence
        job.processing_ms = int((time.perf_counter() - started) * 1000)
        job.finished_at = datetime.now(UTC)
        job.error_message = None
        session.commit()

        logger.info(
            "Job %s complete: %s (p=%.4f) in %d ms",
            job_id,
            job.verdict.value,
            job.fake_probability,
            job.processing_ms,
        )
        return {
            "job_id": job_id,
            "status": job.status.value,
            "verdict": job.verdict.value,
            "fake_probability": job.fake_probability,
        }
    finally:
        session.close()


def _fail(session, job: Job, message: str) -> dict:
    """Mark a job failed with a user-facing message."""
    job.status = JobStatus.FAILED
    job.error_message = message
    job.finished_at = datetime.now(UTC)
    session.commit()
    logger.warning("Job %s failed: %s", job.id, message)
    return {"job_id": job.id, "status": job.status.value, "error": message}


def enqueue_analysis(job_id: str) -> str | None:
    """Queue a job; returns the Celery task id (``None`` in eager mode)."""
    async_result = analyze_job.delay(job_id)
    return getattr(async_result, "id", None)
