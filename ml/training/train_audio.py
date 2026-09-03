#!/usr/bin/env python3
"""Train the audio anti-spoofing detector (LCNN over log-Mel spectrograms).

Follows the ASVspoof baseline setup: bonafide=0, spoofed=1, BCE loss, Adam,
early stopping on validation loss. EER is reported every epoch because it is the
metric the anti-spoofing literature is scored on.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Running this file directly puts its own directory on sys.path, not the repo
# root, so `import ml...` would fail. Add the repo root before those imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.common import REPO_ROOT, set_seed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=REPO_ROOT / "data/processed/audio")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument(
        "--checkpoint", type=Path, default=REPO_ROOT / "checkpoints/audio_detector.pt"
    )
    parser.add_argument("--version", default="audio-lcnn-v1.0.0")
    parser.add_argument("--device", default=None)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    set_seed(args.seed)

    import torch
    from app.ml.models_arch import build_audio_model
    from torch.utils.data import DataLoader

    from ml.training.datasets import AudioWindowDataset, collate_spectrograms
    from ml.training.engine import TrainConfig, train_model

    manifest = args.data / "manifest.csv"
    if not manifest.exists():
        raise SystemExit(
            f"No manifest at {manifest}. Run ml/preprocessing/build_audio_dataset.py first."
        )

    train_set = AudioWindowDataset(manifest, "train", sample_rate=args.sample_rate)
    val_set = AudioWindowDataset(manifest, "val", sample_rate=args.sample_rate)
    print(f"train: {len(train_set)} windows | val: {len(val_set)} windows")

    train_loader = DataLoader(
        train_set,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.workers,
        collate_fn=collate_spectrograms,
        drop_last=True,
    )
    val_loader = DataLoader(
        val_set,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        collate_fn=collate_spectrograms,
    )

    model = build_audio_model()
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    labels = train_set.labels
    positives = sum(labels)
    pos_weight = (len(labels) - positives) / positives if 0 < positives < len(labels) else None

    config = TrainConfig(
        epochs=args.epochs,
        lr=args.lr,
        weight_decay=args.weight_decay,
        patience=args.patience,
        device=device,
        checkpoint_path=args.checkpoint,
        log_path=args.checkpoint.with_name("audio_training_log.csv"),
        model_version=args.version,
        extra_metadata={"architecture": "LCNN", "sample_rate": args.sample_rate},
    )

    print(f"Training LCNN on {device} for up to {args.epochs} epochs ...")
    summary = train_model(model, train_loader, val_loader, config, pos_weight=pos_weight)

    from ml.evaluation.metrics import format_report

    print("\nBest validation metrics:")
    print(format_report(summary["best_val_metrics"]))
    print(f"\nCheckpoint: {args.checkpoint}")


if __name__ == "__main__":
    main()
