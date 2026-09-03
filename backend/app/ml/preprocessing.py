"""Preprocessing shared by training and inference.

Keeping these transforms in one module is what stops train/serve skew: the
training scripts in ``ml/`` import exactly the same functions the API uses.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from app.config import settings

IMAGE_SIZE = 224
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


# --------------------------------------------------------------------------- image
def preprocess_image(image, size: int = IMAGE_SIZE):
    """PIL image -> normalised ``(1, 3, size, size)`` float tensor."""
    import torch
    from PIL import Image

    resized = image.convert("RGB").resize((size, size), Image.BILINEAR)
    array = np.asarray(resized, dtype=np.float32) / 255.0
    array = (array - IMAGENET_MEAN) / IMAGENET_STD
    tensor = torch.from_numpy(array.transpose(2, 0, 1)).unsqueeze(0)
    return tensor.contiguous()


# --------------------------------------------------------------------------- video
def sample_video_frames(
    path: str | Path,
    target_fps: float | None = None,
    max_frames: int | None = None,
) -> tuple[list[tuple[float, object]], dict]:
    """Sample frames at ``target_fps``, returning ``[(timestamp_s, PIL image)]``.

    Sampling rather than decoding every frame keeps long videos tractable —
    processing every frame of a 5-minute clip is the classic way to make this
    pipeline unusably slow.
    """
    import cv2
    from PIL import Image

    target_fps = target_fps or settings.video_sample_fps
    max_frames = max_frames or settings.video_max_frames

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"Could not open video file: {path}")

    try:
        source_fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = total_frames / source_fps if source_fps > 0 and total_frames > 0 else 0.0

        step = max(1, int(round(source_fps / max(target_fps, 0.01))))
        indices = list(range(0, total_frames, step)) if total_frames > 0 else []
        if not indices:
            # Frame count unavailable (some containers) — read sequentially instead.
            indices = []
        if len(indices) > max_frames:
            # Spread the budget across the whole clip instead of only the opening.
            picks = np.linspace(0, len(indices) - 1, max_frames).round().astype(int)
            indices = [indices[i] for i in dict.fromkeys(picks.tolist())]

        frames: list[tuple[float, object]] = []
        if indices:
            for index in indices:
                capture.set(cv2.CAP_PROP_POS_FRAMES, index)
                ok, frame = capture.read()
                if not ok:
                    continue
                frames.append((index / source_fps, Image.fromarray(frame[:, :, ::-1])))
        else:
            position = 0
            while len(frames) < max_frames:
                ok, frame = capture.read()
                if not ok:
                    break
                if position % step == 0:
                    frames.append((position / source_fps, Image.fromarray(frame[:, :, ::-1])))
                position += 1
            duration = duration or position / source_fps
    finally:
        capture.release()

    if not frames:
        raise ValueError(f"No decodable frames found in video: {path}")

    metadata = {
        "source_fps": round(float(source_fps), 3),
        "total_frames": int(total_frames),
        "duration_seconds": round(float(duration), 3),
        "sampled_frames": len(frames),
        "sampling_fps": target_fps,
    }
    return frames, metadata


# --------------------------------------------------------------------------- audio
def load_audio(path: str | Path, sample_rate: int | None = None) -> tuple[np.ndarray, int]:
    """Load audio as mono float32 at ``sample_rate``.

    Tries librosa (handles every format), then soundfile, then the standard
    library's ``wave`` module. The last fallback only reads PCM WAV, but it means
    a plain WAV upload still works on an install with no audio libraries at all.
    """
    sample_rate = sample_rate or settings.audio_sample_rate
    try:
        import librosa

        waveform, rate = librosa.load(str(path), sr=sample_rate, mono=True)
        return waveform.astype(np.float32), int(rate)
    except ImportError:
        pass

    try:
        import soundfile as sf

        waveform, rate = sf.read(str(path), dtype="float32", always_2d=True)
        waveform = waveform.mean(axis=1)
    except ImportError:
        waveform, rate = _read_wav_stdlib(path)

    if rate != sample_rate:
        waveform = _resample_linear(waveform, rate, sample_rate)
        rate = sample_rate
    return waveform.astype(np.float32), int(rate)


def _read_wav_stdlib(path: str | Path) -> tuple[np.ndarray, int]:
    """Read a PCM WAV into mono float32 using only the standard library."""
    import wave

    try:
        with wave.open(str(path), "rb") as handle:
            channels = handle.getnchannels()
            width = handle.getsampwidth()
            rate = handle.getframerate()
            frames = handle.readframes(handle.getnframes())
    except wave.Error as exc:
        raise RuntimeError(
            f"Cannot decode '{Path(path).name}': install librosa or soundfile to support "
            "compressed audio formats."
        ) from exc

    dtypes = {1: np.uint8, 2: np.int16, 4: np.int32}
    if width not in dtypes:
        raise RuntimeError(f"Unsupported WAV sample width: {width * 8} bit")

    samples = np.frombuffer(frames, dtype=dtypes[width]).astype(np.float32)
    if width == 1:  # 8-bit WAV is unsigned, centred on 128
        samples = (samples - 128.0) / 128.0
    else:
        samples = samples / float(2 ** (width * 8 - 1))
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples.astype(np.float32), int(rate)


def _resample_linear(waveform: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    """Linear resampling fallback when librosa is not installed."""
    if source_rate == target_rate:
        return waveform
    duration = len(waveform) / source_rate
    target_length = int(round(duration * target_rate))
    source_positions = np.linspace(0, len(waveform) - 1, num=len(waveform))
    target_positions = np.linspace(0, len(waveform) - 1, num=target_length)
    return np.interp(target_positions, source_positions, waveform).astype(np.float32)


def normalize_waveform(waveform: np.ndarray) -> np.ndarray:
    """Peak-normalise, guarding against silent clips."""
    peak = float(np.max(np.abs(waveform))) if waveform.size else 0.0
    if peak < 1e-8:
        return waveform
    return (waveform / peak).astype(np.float32)


def trim_silence(waveform: np.ndarray, top_db: float = 35.0) -> np.ndarray:
    """Trim leading/trailing silence; returns the input when librosa is absent."""
    try:
        import librosa

        trimmed, _ = librosa.effects.trim(waveform, top_db=top_db)
        return trimmed if trimmed.size else waveform
    except ImportError:
        return waveform


def log_mel_spectrogram(
    waveform: np.ndarray,
    sample_rate: int | None = None,
    n_mels: int = 64,
    n_fft: int = 512,
    hop_length: int = 160,
) -> np.ndarray:
    """Log-Mel spectrogram ``(n_mels, frames)`` — the LCNN input feature."""
    sample_rate = sample_rate or settings.audio_sample_rate
    try:
        import librosa

        mel = librosa.feature.melspectrogram(
            y=waveform, sr=sample_rate, n_mels=n_mels, n_fft=n_fft, hop_length=hop_length
        )
        return librosa.power_to_db(mel, ref=np.max).astype(np.float32)
    except ImportError:
        return _log_mel_numpy(waveform, sample_rate, n_mels, n_fft, hop_length)


def _log_mel_numpy(waveform, sample_rate, n_mels, n_fft, hop_length) -> np.ndarray:
    """Pure-NumPy log-Mel so the audio path works without librosa installed."""
    if waveform.size < n_fft:
        waveform = np.pad(waveform, (0, n_fft - waveform.size))
    window = np.hanning(n_fft).astype(np.float32)
    frame_count = 1 + (len(waveform) - n_fft) // hop_length
    frames = np.stack(
        [waveform[i * hop_length : i * hop_length + n_fft] * window for i in range(frame_count)]
    )
    power = np.abs(np.fft.rfft(frames, axis=1)) ** 2
    filters = _mel_filterbank(sample_rate, n_fft, n_mels)
    mel = power @ filters.T
    log_mel = 10.0 * np.log10(np.maximum(mel, 1e-10))
    return (log_mel - log_mel.max()).T.astype(np.float32)


def _mel_filterbank(sample_rate: int, n_fft: int, n_mels: int) -> np.ndarray:
    def hz_to_mel(hz: float) -> float:
        return 2595.0 * math.log10(1.0 + hz / 700.0)

    def mel_to_hz(mel: np.ndarray) -> np.ndarray:
        return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)

    low_mel, high_mel = hz_to_mel(0.0), hz_to_mel(sample_rate / 2)
    mel_points = np.linspace(low_mel, high_mel, n_mels + 2)
    bin_points = np.floor((n_fft + 1) * mel_to_hz(mel_points) / sample_rate).astype(int)

    filters = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
    for m in range(1, n_mels + 1):
        left, center, right = bin_points[m - 1], bin_points[m], bin_points[m + 1]
        for k in range(left, min(center, filters.shape[1])):
            if center > left:
                filters[m - 1, k] = (k - left) / (center - left)
        for k in range(center, min(right, filters.shape[1])):
            if right > center:
                filters[m - 1, k] = (right - k) / (right - center)
    return filters


def segment_waveform(
    waveform: np.ndarray,
    sample_rate: int | None = None,
    window_seconds: float | None = None,
) -> list[tuple[float, np.ndarray]]:
    """Split audio into fixed windows, returning ``[(start_seconds, samples)]``.

    Per-window scoring is what lets the report point at *which seconds* of a
    clip look synthetic, instead of only giving one number for the whole file.
    """
    sample_rate = sample_rate or settings.audio_sample_rate
    window_seconds = window_seconds or settings.audio_window_seconds
    window = int(sample_rate * window_seconds)
    if window <= 0:
        raise ValueError("window_seconds must be positive")

    if waveform.size <= window:
        padded = np.pad(waveform, (0, window - waveform.size))
        return [(0.0, padded.astype(np.float32))]

    segments: list[tuple[float, np.ndarray]] = []
    for start in range(0, waveform.size - window + 1, window):
        segments.append((start / sample_rate, waveform[start : start + window].astype(np.float32)))

    remainder = waveform.size % window
    if remainder > window * 0.5:  # keep a substantial tail, zero-padded
        tail = waveform[-remainder:]
        segments.append(
            (
                (waveform.size - remainder) / sample_rate,
                np.pad(tail, (0, window - remainder)).astype(np.float32),
            )
        )
    return segments
