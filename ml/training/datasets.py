"""Torch datasets backed by the manifests the preprocessing scripts write."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

from ml.common import read_manifest


class FaceCropDataset(Dataset):
    """Face crops for the image/video detector, with training augmentation.

    Augmentation deliberately includes JPEG recompression and blur: uploads from
    a real user arrive after messaging-app recompression, and a model trained
    only on pristine crops collapses on them.
    """

    def __init__(
        self, manifest: str | Path, split: str, size: int = 224, augment: bool | None = None
    ) -> None:
        self.rows = read_manifest(Path(manifest), split)
        self.size = size
        self.augment = (split == "train") if augment is None else augment
        if not self.rows:
            raise ValueError(f"Manifest {manifest} has no rows for split '{split}'")

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        from app.ml.preprocessing import preprocess_image
        from PIL import Image

        row = self.rows[index]
        with Image.open(row["path"]) as opened:
            image = opened.convert("RGB")
        if self.augment:
            image = _augment(image)
        tensor = preprocess_image(image, self.size).squeeze(0)
        return tensor, torch.tensor([float(row["label"])])

    @property
    def labels(self) -> list[int]:
        return [row["label"] for row in self.rows]


def _augment(image):
    """Random flip, crop, brightness/contrast jitter, blur and JPEG artefacts."""
    import io

    from PIL import Image, ImageEnhance, ImageFilter

    if random.random() < 0.5:
        image = image.transpose(Image.FLIP_LEFT_RIGHT)

    if random.random() < 0.4:  # random crop back up to full size
        width, height = image.size
        scale = random.uniform(0.85, 1.0)
        new_width, new_height = int(width * scale), int(height * scale)
        left = random.randint(0, width - new_width)
        top = random.randint(0, height - new_height)
        image = image.crop((left, top, left + new_width, top + new_height))
        image = image.resize((width, height), Image.BILINEAR)

    if random.random() < 0.4:
        image = ImageEnhance.Brightness(image).enhance(random.uniform(0.75, 1.25))
    if random.random() < 0.4:
        image = ImageEnhance.Contrast(image).enhance(random.uniform(0.75, 1.25))
    if random.random() < 0.2:
        image = image.filter(ImageFilter.GaussianBlur(random.uniform(0.3, 1.2)))

    if random.random() < 0.5:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=random.randint(35, 95))
        buffer.seek(0)
        with Image.open(buffer) as reopened:
            image = reopened.convert("RGB")
    return image


class AudioWindowDataset(Dataset):
    """Log-Mel spectrograms of pre-windowed audio for the LCNN."""

    def __init__(
        self,
        manifest: str | Path,
        split: str,
        sample_rate: int = 16000,
        augment: bool | None = None,
    ) -> None:
        self.rows = read_manifest(Path(manifest), split)
        self.sample_rate = sample_rate
        self.augment = (split == "train") if augment is None else augment
        if not self.rows:
            raise ValueError(f"Manifest {manifest} has no rows for split '{split}'")

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        from app.ml.preprocessing import log_mel_spectrogram

        row = self.rows[index]
        waveform = np.load(row["path"]).astype(np.float32)
        if self.augment:
            waveform = _augment_audio(waveform)

        features = log_mel_spectrogram(waveform, self.sample_rate)
        tensor = torch.from_numpy(features).unsqueeze(0)
        if self.augment:
            tensor = _spec_augment(tensor)
        return tensor, torch.tensor([float(row["label"])])

    @property
    def labels(self) -> list[int]:
        return [row["label"] for row in self.rows]


def _augment_audio(waveform: np.ndarray) -> np.ndarray:
    """Gain jitter plus light noise — cheap robustness to recording conditions."""
    if random.random() < 0.5:
        waveform = waveform * random.uniform(0.7, 1.3)
    if random.random() < 0.3:
        waveform = waveform + np.random.normal(0, 0.003, size=waveform.shape).astype(np.float32)
    return np.clip(waveform, -1.0, 1.0).astype(np.float32)


def _spec_augment(
    spectrogram: torch.Tensor, max_freq_mask: int = 8, max_time_mask: int = 16
) -> torch.Tensor:
    """SpecAugment-style frequency/time masking on the spectrogram."""
    spectrogram = spectrogram.clone()
    _, mels, frames = spectrogram.shape

    if random.random() < 0.5 and mels > max_freq_mask:
        width = random.randint(1, max_freq_mask)
        start = random.randint(0, mels - width)
        spectrogram[:, start : start + width, :] = spectrogram.min()

    if random.random() < 0.5 and frames > max_time_mask:
        width = random.randint(1, max_time_mask)
        start = random.randint(0, frames - width)
        spectrogram[:, :, start : start + width] = spectrogram.min()

    return spectrogram


def collate_spectrograms(batch):
    """Pad spectrograms in a batch to the widest frame count."""
    features = [item[0] for item in batch]
    labels = torch.stack([item[1] for item in batch])
    width = max(feature.shape[-1] for feature in features)
    padded = [
        torch.nn.functional.pad(feature, (0, width - feature.shape[-1]), value=float(feature.min()))
        for feature in features
    ]
    return torch.stack(padded), labels
