"""Scan history and report register."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Job, Report, User
from app.schemas import HistoryItem, HistoryPage
from app.storage import delete_job_artifacts

router = APIRouter(tags=["history"])


@router.get("/history", response_model=HistoryPage)
def list_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HistoryPage:
    """Page through the signed-in user's past scans, newest first."""
    total = db.scalar(select(func.count()).select_from(Job).where(Job.user_id == user.id)) or 0
    jobs = db.scalars(
        select(Job)
        .where(Job.user_id == user.id)
        .order_by(Job.uploaded_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    items = [
        HistoryItem(
            id=job.id,
            case_reference=job.case_reference,
            original_filename=job.original_filename,
            media_type=job.media_type,
            status=job.status,
            verdict=job.verdict,
            fake_probability=job.fake_probability,
            uploaded_at=job.uploaded_at,
            has_report=bool(job.reports),
        )
        for job in jobs
    ]
    return HistoryPage(items=items, total=total, limit=limit, offset=offset)


@router.delete("/history/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scan(
    job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    """Delete a scan and every file it produced (data-retention right to erasure)."""
    job = db.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    evidence = job.evidence or {}
    from app.config import settings

    artifacts = [job.stored_path]
    for key in ("heatmap_file", "spectrogram_file"):
        if evidence.get(key):
            artifacts.append(Path(settings.evidence_dir) / evidence[key])
    artifacts += [report.file_path for report in job.reports]

    delete_job_artifacts(*artifacts)
    db.delete(job)
    db.commit()


@router.get("/reports/{report_reference}/verify")
def verify_report(report_reference: str, db: Session = Depends(get_db)) -> dict:
    """Publish the registered SHA-256 for a report so a recipient can check it.

    Deliberately public and unauthenticated: a police officer or forensic
    reviewer holding the PDF must be able to confirm its hash without an
    account. Only the reference and hashes are exposed — never the media, the
    verdict, or who submitted it.
    """
    report = db.scalar(select(Report).where(Report.report_reference == report_reference))
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No report is registered under this reference.",
        )

    exists = Path(report.file_path).exists()
    return {
        "report_reference": report.report_reference,
        "report_sha256": report.sha256,
        "analysed_file_sha256": report.job.sha256,
        "generated_at": report.generated_at,
        "stored_copy_intact": (
            None if not exists else _hash_matches(report.file_path, report.sha256)
        ),
        "how_to_verify": (
            "Run 'shasum -a 256 <report.pdf>' (Linux/macOS) or "
            "'certutil -hashfile <report.pdf> SHA256' (Windows) on the PDF you received. "
            "It must equal report_sha256 above."
        ),
    }


def _hash_matches(path: str, expected: str) -> bool:
    from app.report.generator import verify_report_hash

    return verify_report_hash(path, expected)
