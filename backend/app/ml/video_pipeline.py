"""Video deepfake detection pipeline.

Flow: sample frames at target FPS → detect/crop face per frame →
classify each frame with the image model (Grad-CAM on worst frame) →
aggregate per-frame scores → temporal confidence curve chart.

Video reuses the image model: face-swap deepfakes in video are the same
artefacts as in stills, just per frame. The temporal curve is what makes
video results richer than a single image score.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from app.config import settings
from app.ml.base import AnalysisResult
from app.ml.faces import extract_faces
from app.ml.gradcam import compute_gradcam, overlay_heatmap
from app.ml.preprocessing import preprocess_image, sample_video_frames
from app.ml.registry import UNTRAINED, get_image_model

logger = logging.getLogger(__name__)

MAX_FACES_PER_FRAME = 1   # speed: one face crop per frame is enough for video


def analyze_video(path: str | Path, evidence_dir: str | Path, job_id: str) -> AnalysisResult:
    """Score a video and write evidence (heatmap + timeline chart) into ``evidence_dir``."""
    import torch
    from PIL import Image as PILImage

    loaded = get_image_model()
    evidence_dir = Path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ sample frames
    frames, video_meta = sample_video_frames(
        path,
        target_fps=settings.video_sample_fps,
        max_frames=settings.video_max_frames,
    )
    logger.info("Video job %s: sampled %d frames from %.1fs clip", job_id, len(frames), video_meta["duration_seconds"])

    # ------------------------------------------------------------------ score each frame
    frame_scores: list[dict] = []
    frame_tensors: list[tuple] = []   # (timestamp, tensor, pil_image)

    for timestamp_s, pil_frame in frames:
        crops = extract_faces(pil_frame)[:MAX_FACES_PER_FRAME]
        crop = crops[0]                  # always at least one (whole frame fallback)

        tensor = preprocess_image(crop.image, loaded.input_size).to(loaded.device)
        with torch.no_grad():
            prob = torch.sigmoid(loaded.module(tensor)).item()

        frame_scores.append({
            "frame_index": len(frame_scores),
            "timestamp_s": round(timestamp_s, 3),
            "fake_probability": round(prob, 4),
            "face_detected": crop.box is not None,
        })
        frame_tensors.append((timestamp_s, tensor, crop.image))

    # Worst frame drives verdict — one manipulated face makes the video manipulated.
    worst_idx = int(np.argmax([s["fake_probability"] for s in frame_scores]))
    fake_probability = float(frame_scores[worst_idx]["fake_probability"])

    # ------------------------------------------------------------------ Grad-CAM on worst frame
    heatmap_name = None
    try:
        _, worst_tensor, worst_crop = frame_tensors[worst_idx]
        cam = compute_gradcam(loaded.module, worst_tensor)
        heatmap_path = evidence_dir / f"{job_id}_heatmap.png"
        overlay_heatmap(worst_crop, cam, heatmap_path)
        heatmap_name = heatmap_path.name
    except Exception as exc:
        logger.warning("Grad-CAM failed for video job %s: %s", job_id, exc)

    # ------------------------------------------------------------------ temporal chart
    chart_name = None
    try:
        chart_path = evidence_dir / f"{job_id}_timeline.png"
        _save_timeline_chart(frame_scores, chart_path)
        chart_name = chart_path.name
    except Exception as exc:
        logger.warning("Timeline chart failed for video job %s: %s", job_id, exc)

    # ------------------------------------------------------------------ notes
    notes: list[str] = []
    faces_detected = sum(1 for s in frame_scores if s["face_detected"])
    if faces_detected == 0:
        notes.append(
            "No face was detected in any sampled frame; entire frames were analysed. "
            "Scores for non-facial content are less reliable."
        )
    if loaded.weights_status == UNTRAINED:
        notes.append(
            "Model is running on an untrained backbone (no checkpoint found). "
            "Scores are NOT valid evidence — train the model or install checkpoints first."
        )

    return AnalysisResult(
        fake_probability=fake_probability,
        model_name=loaded.name,
        model_version=loaded.version,
        weights_status=loaded.weights_status,
        evidence={
            "media": "video",
            **video_meta,
            "frames_analysed": len(frame_scores),
            "faces_detected_in_frames": faces_detected,
            "worst_frame_index": worst_idx,
            "worst_frame_timestamp_s": frame_scores[worst_idx]["timestamp_s"],
            "frame_scores": frame_scores,
            "heatmap_file": heatmap_name,
            "timeline_file": chart_name,
            "backbone": settings.image_model_backbone,
            "input_size": loaded.input_size,
            "notes": notes,
        },
    )


# --------------------------------------------------------------------------- chart
def _save_timeline_chart(frame_scores: list[dict], out_path: Path) -> None:
    """Save a per-frame confidence curve as a PNG."""
    import matplotlib.pyplot as plt

    timestamps = [s["timestamp_s"] for s in frame_scores]
    probs = [s["fake_probability"] for s in frame_scores]
    threshold_high = settings.fake_threshold + settings.uncertain_band
    threshold_low = settings.fake_threshold - settings.uncertain_band

    fig, ax = plt.subplots(figsize=(12, 3))
    ax.fill_between(timestamps, probs, alpha=0.25, color="#ef4444")
    ax.plot(timestamps, probs, color="#ef4444", linewidth=2, label="Fake probability")
    ax.axhline(threshold_high, color="#ef4444", linestyle="--", linewidth=1, alpha=0.7, label="Manipulated threshold")
    ax.axhline(threshold_low, color="#22c55e", linestyle="--", linewidth=1, alpha=0.7, label="Authentic threshold")
    ax.axhspan(threshold_low, threshold_high, alpha=0.07, color="#f59e0b", label="Inconclusive band")

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Fake probability")
    ax.set_ylim(0, 1)
    ax.set_title("Per-frame manipulation probability over time")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(str(out_path), dpi=120, bbox_inches="tight")
    plt.close(fig)
