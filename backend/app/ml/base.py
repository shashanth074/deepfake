"""Shared types and helpers for the detection pipelines."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.models import Verdict


class DetectorUnavailableError(RuntimeError):
    """Raised when a pipeline's dependencies (torch, ffmpeg, ...) are missing."""


@dataclass
class AnalysisResult:
    """Normalised output of any detector, ready to persist on a Job."""

    fake_probability: float
    model_name: str
    model_version: str
    weights_status: str  # "trained" | "untrained-backbone"
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def verdict(self) -> Verdict:
        return classify(self.fake_probability)

    @property
    def confidence(self) -> float:
        """Distance from the undecided midpoint, expressed as 0..1.

        A probability of 0.5 carries no information (confidence 0.0); 0.0 or 1.0
        is maximally confident. This is what the UI shows, so a borderline score
        never renders as a confident verdict.
        """
        return round(abs(self.fake_probability - 0.5) * 2, 4)


def classify(fake_probability: float) -> Verdict:
    """Map a probability to a three-way verdict with an explicit uncertain band.

    Reporting 'inconclusive' near the threshold is deliberate: deepfake
    detectors are not certain, and a two-way label would overstate the result.
    """
    low = settings.fake_threshold - settings.uncertain_band
    high = settings.fake_threshold + settings.uncertain_band
    if fake_probability >= high:
        return Verdict.MANIPULATED
    if fake_probability <= low:
        return Verdict.AUTHENTIC
    return Verdict.INCONCLUSIVE


def torch_available() -> bool:
    """True when PyTorch can be imported in this process."""
    try:
        import torch  # noqa: F401
    except Exception:
        return False
    return True


def resolve_device(preferred: str | None = None) -> str:
    """Pick a torch device, strictly enforcing CUDA if requested."""
    preferred = preferred or settings.device
    if not preferred.startswith("cuda"):
        return preferred

    import torch
    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA was requested (DEVICE=cuda) but torch.cuda.is_available() is False. "
            "Refusing to silently fall back to the CPU."
        )
    return preferred
