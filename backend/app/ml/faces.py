"""Face detection and cropping.

MTCNN (via facenet-pytorch) is used when available — deepfake artifacts live in
the face region, so cropping before classification is what the FF++-style
models expect. When MTCNN is unavailable the frame is used whole, and the
pipeline records that in the evidence notes rather than failing.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_detector = None
_detector_lock = threading.Lock()
_detector_failed = False


@dataclass
class FaceCrop:
    image: object  # PIL.Image.Image
    box: tuple[int, int, int, int] | None  # (x1, y1, x2, y2) in source coordinates
    confidence: float | None


def get_detector():
    """Cached MTCNN detector, or ``None`` when facenet-pytorch is unavailable."""
    global _detector, _detector_failed
    if _detector is not None or _detector_failed:
        return _detector
    with _detector_lock:
        if _detector is None and not _detector_failed:
            try:
                from facenet_pytorch import MTCNN

                from app.ml.base import resolve_device

                _detector = MTCNN(keep_all=True, device=resolve_device(), post_process=False)
            except Exception as exc:
                logger.warning("Face detector unavailable (%s); using full frames.", exc)
                _detector_failed = True
    return _detector


def extract_faces(image, margin: float = 0.25, min_size: int = 48) -> list[FaceCrop]:
    """Detect faces and return aligned crops with a margin around each box.

    Returns a single whole-image ``FaceCrop`` (``box=None``) when no face is
    found or no detector is installed.
    """
    detector = get_detector()
    width, height = image.size
    if detector is None:
        return [FaceCrop(image=image, box=None, confidence=None)]

    try:
        boxes, probs = detector.detect(image)
    except Exception as exc:  # pragma: no cover - detector runtime failure
        logger.warning("Face detection failed (%s); using the full frame.", exc)
        return [FaceCrop(image=image, box=None, confidence=None)]

    if boxes is None or len(boxes) == 0:
        return [FaceCrop(image=image, box=None, confidence=None)]

    crops: list[FaceCrop] = []
    probs = probs if probs is not None else [None] * len(boxes)
    for box, prob in zip(boxes, probs, strict=True):
        x1, y1, x2, y2 = (float(v) for v in box)
        box_width, box_height = x2 - x1, y2 - y1
        if box_width < min_size or box_height < min_size:
            continue
        pad_x, pad_y = box_width * margin, box_height * margin
        crop_box = (
            max(0, int(x1 - pad_x)),
            max(0, int(y1 - pad_y)),
            min(width, int(x2 + pad_x)),
            min(height, int(y2 + pad_y)),
        )
        crops.append(
            FaceCrop(
                image=image.crop(crop_box),
                box=crop_box,
                confidence=float(prob) if prob is not None else None,
            )
        )

    if not crops:
        return [FaceCrop(image=image, box=None, confidence=None)]
    # Largest face first — the subject of the media is normally the biggest face.
    crops.sort(key=lambda crop: crop.image.size[0] * crop.image.size[1], reverse=True)
    return crops
