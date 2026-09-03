"""Model registry — loads each network once per process.

Loading happens lazily on first use and is then cached, so a Celery worker pays
the model-construction cost at startup rather than on every request.

If no checkpoint is present the model is still returned, but flagged
``weights_status="untrained-backbone"``. Every downstream consumer (API, PDF
report, UI) surfaces that flag, so an untrained demo build can never be mistaken
for a validated forensic result.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import settings
from app.ml.base import DetectorUnavailableError, resolve_device
from app.ml.checkpoints import extract_metadata, extract_state_dict, load_checkpoint
from app.ml.preprocessing import IMAGE_SIZE

logger = logging.getLogger(__name__)

TRAINED = "trained"
UNTRAINED = "untrained-backbone"

CHECKPOINT_FILENAMES = {
    "image": "image_detector.pt",
    "audio": "audio_detector.pt",
}


@dataclass
class LoadedModel:
    module: Any  # torch.nn.Module
    device: str
    weights_status: str
    version: str
    name: str
    metadata: dict[str, Any]

    @property
    def input_size(self) -> int:
        """Resolution this checkpoint was trained at.

        Serving at a different resolution than training silently degrades a
        model — the artefacts it learned to spot are resampled away — so the
        size is recorded in the checkpoint and honoured here rather than
        assumed.
        """
        recorded = self.metadata.get("input_size")
        try:
            return int(recorded) if recorded else IMAGE_SIZE
        except (TypeError, ValueError):
            return IMAGE_SIZE


_cache: dict[str, LoadedModel] = {}
_lock = threading.Lock()


def _require_torch():
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise DetectorUnavailableError(
            "PyTorch is not installed. Install backend/requirements-ml.txt to enable inference."
        ) from exc
    return torch


def checkpoint_path(kind: str) -> Path:
    return Path(settings.checkpoint_dir) / CHECKPOINT_FILENAMES[kind]


def _load_checkpoint(module: Any, path: Path) -> tuple[str, dict[str, Any]]:
    """Load weights if the checkpoint exists; report which state we ended in."""
    _require_torch()
    if not path.exists():
        logger.warning("No checkpoint at %s — running with untrained weights.", path)
        return UNTRAINED, {}

    payload = load_checkpoint(path)
    state_dict = extract_state_dict(payload)
    missing, unexpected = module.load_state_dict(state_dict, strict=False)
    if missing:
        logger.warning("Checkpoint %s is missing %d keys.", path.name, len(missing))
    return TRAINED, extract_metadata(payload)


def get_image_model() -> LoadedModel:
    """Image / video-frame detector (Xception or EfficientNet)."""
    return _get_or_load("image", _build_image_model)


def get_audio_model() -> LoadedModel:
    """Audio anti-spoofing detector (LCNN over log-Mel spectrograms)."""
    return _get_or_load("audio", _build_audio_model)


def _get_or_load(kind: str, builder) -> LoadedModel:
    cached = _cache.get(kind)
    if cached is not None:
        return cached
    with _lock:
        cached = _cache.get(kind)
        if cached is None:
            cached = builder()
            _cache[kind] = cached
    return cached


def _build_image_model() -> LoadedModel:
    _require_torch()
    from app.ml.models_arch import build_image_model

    device = resolve_device()
    module = build_image_model(settings.image_model_backbone, pretrained=True)
    status, metadata = _load_checkpoint(module, checkpoint_path("image"))
    module.eval().to(device)
    return LoadedModel(
        module=module,
        device=device,
        weights_status=status,
        version=str(metadata.get("version", settings.image_model_version)),
        name=f"{settings.image_model_backbone}-binary-head",
        metadata=metadata,
    )


def _build_audio_model() -> LoadedModel:
    _require_torch()
    from app.ml.models_arch import build_audio_model

    device = resolve_device()
    module = build_audio_model()
    status, metadata = _load_checkpoint(module, checkpoint_path("audio"))
    module.eval().to(device)
    return LoadedModel(
        module=module,
        device=device,
        weights_status=status,
        version=str(metadata.get("version", settings.audio_model_version)),
        name="lcnn-logmel",
        metadata=metadata,
    )


def warm_up() -> dict[str, str]:
    """Preload every model — called at Celery worker startup."""
    statuses: dict[str, str] = {}
    for kind, loader in (("image", get_image_model), ("audio", get_audio_model)):
        try:
            statuses[kind] = loader().weights_status
        except DetectorUnavailableError as exc:
            statuses[kind] = f"unavailable: {exc}"
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to load %s model", kind)
            statuses[kind] = f"error: {exc}"
    return statuses


def describe() -> dict[str, str]:
    """Lightweight status for /api/health — never constructs or loads a model.

    Because nothing is loaded here, the version shown is the configured default,
    not the version recorded inside a checkpoint. The authoritative version for
    any given analysis is the one stored on that job and printed in its report.
    """
    return {
        "image": f"{settings.image_model_backbone}, checkpoint "
        f"{TRAINED if checkpoint_path('image').exists() else UNTRAINED}, "
        f"configured {settings.image_model_version}",
        "audio": f"lcnn, checkpoint "
        f"{TRAINED if checkpoint_path('audio').exists() else UNTRAINED}, "
        f"configured {settings.audio_model_version}",
        "video": f"frame-aggregation over the image model, configured "
        f"{settings.video_model_version}",
    }


def reset_cache() -> None:
    """Drop cached models (used by tests)."""
    with _lock:
        _cache.clear()
