"""Audio deepfake / anti-spoofing pipeline.

Flow: load → normalise → trim silence → segment into 4-second windows →
log-Mel spectrogram per window → LCNN score → aggregate → spectrogram
visualisation with flagged windows outlined.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from app.config import settings
from app.ml.base import AnalysisResult
from app.ml.preprocessing import (
    load_audio,
    log_mel_spectrogram,
    normalize_waveform,
    segment_waveform,
    trim_silence,
)
from app.ml.registry import UNTRAINED, get_audio_model

logger = logging.getLogger(__name__)

# LCNN input: (batch, 1, n_mels, frames_per_window)
N_MELS = 64
N_FFT = 512
HOP_LENGTH = 160


def analyze_audio(path: str | Path, evidence_dir: str | Path, job_id: str) -> AnalysisResult:
    """Score an audio file and write a spectrogram visualisation into ``evidence_dir``."""
    import torch

    loaded = get_audio_model()
    evidence_dir = Path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ load
    waveform, sample_rate = load_audio(path, settings.audio_sample_rate)
    waveform = normalize_waveform(trim_silence(waveform))
    duration_s = len(waveform) / sample_rate

    # ------------------------------------------------------------------ segment → score
    segments = segment_waveform(waveform, sample_rate, settings.audio_window_seconds)
    segment_scores: list[dict] = []
    window_spectrograms: list[np.ndarray] = []

    for start_s, window in segments:
        mel = log_mel_spectrogram(window, sample_rate, N_MELS, N_FFT, HOP_LENGTH)
        window_spectrograms.append(mel)

        # LCNN expects (1, 1, n_mels, frames)
        tensor = (
            torch.from_numpy(mel)
            .unsqueeze(0)  # frames dim becomes last
            .unsqueeze(0)  # batch
            .unsqueeze(0)  # channel
            .float()
            .to(loaded.device)
        )
        with torch.no_grad():
            prob = torch.sigmoid(loaded.module(tensor)).item()

        segment_scores.append({
            "start_s": round(start_s, 3),
            "end_s": round(start_s + settings.audio_window_seconds, 3),
            "fake_probability": round(prob, 4),
        })

    # Worst-window drives the overall verdict (one synthetic splice = manipulated).
    fake_probability = float(max(s["fake_probability"] for s in segment_scores))

    # ------------------------------------------------------------------ spectrogram image
    spectrogram_name = None
    try:
        spectrogram_path = evidence_dir / f"{job_id}_spectrogram.png"
        _save_spectrogram_figure(
            waveform=waveform,
            sample_rate=sample_rate,
            segment_scores=segment_scores,
            out_path=spectrogram_path,
        )
        spectrogram_name = spectrogram_path.name
    except Exception as exc:
        logger.warning("Spectrogram generation failed for job %s: %s", job_id, exc)

    # ------------------------------------------------------------------ notes
    notes: list[str] = []
    if loaded.weights_status == UNTRAINED:
        notes.append(
            "Model is running on an untrained backbone (no checkpoint found). "
            "Scores are NOT valid evidence — train the model or install checkpoints first."
        )
    if duration_s < settings.audio_window_seconds:
        notes.append(
            f"Clip is only {duration_s:.1f} s — shorter than the {settings.audio_window_seconds:.0f}-second "
            "analysis window. The score is less reliable on very short clips."
        )

    return AnalysisResult(
        fake_probability=fake_probability,
        model_name=loaded.name,
        model_version=loaded.version,
        weights_status=loaded.weights_status,
        evidence={
            "media": "audio",
            "duration_seconds": round(duration_s, 3),
            "sample_rate": sample_rate,
            "segments_analysed": len(segment_scores),
            "segment_scores": segment_scores,
            "spectrogram_file": spectrogram_name,
            "notes": notes,
        },
    )


# --------------------------------------------------------------------------- visualisation
def _save_spectrogram_figure(
    waveform: np.ndarray,
    sample_rate: int,
    segment_scores: list[dict],
    out_path: Path,
) -> None:
    """Write a log-Mel spectrogram PNG with red boxes over synthetic windows."""
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt

    threshold_high = settings.fake_threshold + settings.uncertain_band

    mel = log_mel_spectrogram(waveform, sample_rate, N_MELS, N_FFT, HOP_LENGTH)
    duration_s = len(waveform) / sample_rate

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.imshow(
        mel,
        aspect="auto",
        origin="lower",
        cmap="magma",
        extent=[0, duration_s, 0, sample_rate / 2 / 1000],
    )
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (kHz)")
    ax.set_title("Log-Mel Spectrogram — red boxes mark windows flagged as synthetic")

    # Draw bounding boxes over flagged windows
    for seg in segment_scores:
        if seg["fake_probability"] >= threshold_high:
            rect = mpatches.FancyBboxPatch(
                (seg["start_s"], 0),
                width=seg["end_s"] - seg["start_s"],
                height=sample_rate / 2 / 1000,
                boxstyle="square,pad=0",
                linewidth=2,
                edgecolor="red",
                facecolor="none",
                alpha=0.85,
            )
            ax.add_patch(rect)

    fig.tight_layout()
    fig.savefig(str(out_path), dpi=120, bbox_inches="tight")
    plt.close(fig)
