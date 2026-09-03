"""Dispatch to the correct detector for a media type."""

from __future__ import annotations

from pathlib import Path

from app.ml.base import AnalysisResult
from app.models import MediaType


def analyze(
    media_type: MediaType, path: str | Path, evidence_dir: str | Path, job_id: str
) -> AnalysisResult:
    """Run the pipeline matching ``media_type``."""
    if media_type is MediaType.IMAGE:
        from app.ml.image_pipeline import analyze_image
        return analyze_image(path, evidence_dir, job_id)

    if media_type is MediaType.AUDIO:
        from app.ml.audio_pipeline import analyze_audio
        return analyze_audio(path, evidence_dir, job_id)

    if media_type is MediaType.VIDEO:
        from app.ml.video_pipeline import analyze_video
        return analyze_video(path, evidence_dir, job_id)

    raise ValueError(f"Unsupported media type: {media_type}")
