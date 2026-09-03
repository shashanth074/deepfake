"""Image deepfake detection pipeline.

Flow: load -> detect/crop face -> classify each face crop -> aggregate ->
Grad-CAM heatmap over the most suspicious crop.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings
from app.ml.base import AnalysisResult
from app.ml.faces import extract_faces
from app.ml.gradcam import compute_gradcam, overlay_heatmap
from app.ml.preprocessing import preprocess_image
from app.ml.registry import UNTRAINED, get_image_model

logger = logging.getLogger(__name__)

MAX_FACES = 5


def analyze_image(path: str | Path, evidence_dir: str | Path, job_id: str) -> AnalysisResult:
    """Score an image and write a Grad-CAM overlay into ``evidence_dir``."""
    import torch
    from PIL import Image

    loaded = get_image_model()
    evidence_dir = Path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(path) as opened:
        image = opened.convert("RGB")

    crops = extract_faces(image)[:MAX_FACES]
    face_detected = crops[0].box is not None

    notes: list[str] = []
    if not face_detected:
        notes.append(
            "No face was detected; the whole image was analysed. Scores for non-facial "
            "imagery are less reliable than for face-centred media."
        )

    face_scores: list[dict] = []
    tensors = []
    for index, crop in enumerate(crops):
        tensor = preprocess_image(crop.image, loaded.input_size).to(loaded.device)
        tensors.append(tensor)
        with torch.no_grad():
            probability = torch.sigmoid(loaded.module(tensor)).item()
        face_scores.append(
            {
                "index": index,
                "box": list(crop.box) if crop.box else None,
                "detection_confidence": round(crop.confidence, 4) if crop.confidence else None,
                "fake_probability": round(probability, 4),
            }
        )

    # The most suspicious region drives the verdict: one manipulated face in a
    # group photo still makes the image manipulated.
    worst = max(range(len(face_scores)), key=lambda i: face_scores[i]["fake_probability"])
    fake_probability = float(face_scores[worst]["fake_probability"])

    heatmap_name = None
    try:
        cam = compute_gradcam(loaded.module, tensors[worst])
        heatmap_path = evidence_dir / f"{job_id}_heatmap.png"
        overlay_heatmap(crops[worst].image, cam, heatmap_path)
        heatmap_name = heatmap_path.name
    except Exception as exc:  # heatmap is supporting evidence, not the verdict
        logger.warning("Grad-CAM failed for job %s: %s", job_id, exc)
        notes.append("Heatmap generation failed; the numeric score is unaffected.")

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
            "media": "image",
            "image_size": list(image.size),
            "faces_detected": len(face_scores) if face_detected else 0,
            "face_scores": face_scores,
            "analysed_region": face_scores[worst]["box"],
            "heatmap_file": heatmap_name,
            "backbone": settings.image_model_backbone,
            "input_size": loaded.input_size,
            "notes": notes,
        },
    )
