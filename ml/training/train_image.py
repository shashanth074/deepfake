#!/usr/bin/env python3
"""Fine-tune the image / video-frame deepfake detector.

Starts from an ImageNet-pretrained backbone and trains a binary head
(real=0, fake=1) on face crops, with BCE loss, Adam, and early stopping on
validation loss.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Running this file directly puts its own directory on sys.path, not the repo
# root, so `import ml...` would fail. Add the repo root and backend/ before
# those imports so that both `ml.*` and `app.*` (which lives in backend/) resolve.
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from ml.common import REPO_ROOT, set_seed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=REPO_ROOT / "data/processed/faces",
        help="Directory containing manifest.csv",
    )
    parser.add_argument(
        "--backbone",
        default="efficientnet_b0",
        choices=["efficientnet_b0", "efficientnet_b4", "xception"],
    )
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--size", type=int, default=224)
    parser.add_argument(
        "--no-amp", dest="use_amp", action="store_false", default=True,
        help="Disable automatic mixed precision (use for debugging)",
    )
    parser.add_argument(
        "--freeze-backbone",
        action="store_true",
        help="Train only the classification head (fast, weaker)",
    )
    parser.add_argument(
        "--checkpoint", type=Path, default=REPO_ROOT / "checkpoints/image_detector.pt"
    )
    parser.add_argument("--version", default="image-detector-v1.0.0")
    parser.add_argument("--device", default=None, help="cuda / cpu (auto-detected by default)")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    set_seed(args.seed)

    import torch
    from app.ml.models_arch import build_image_model
    from torch.utils.data import DataLoader

    from ml.training.datasets import FaceCropDataset
    from ml.training.engine import TrainConfig, train_model

    manifest = args.data / "manifest.csv"
    if not manifest.exists():
        raise SystemExit(
            f"No manifest at {manifest}. Run ml/preprocessing/build_face_dataset.py first."
        )

    train_set = FaceCropDataset(manifest, "train", size=args.size)
    val_set = FaceCropDataset(manifest, "val", size=args.size)
    print(f"train: {len(train_set)} crops | val: {len(val_set)} crops")

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    if device == "cuda":
        print(f"CUDA device: {torch.cuda.get_device_name(0)}")
        print(f"CUDA version: {torch.version.cuda}")

    # Use multiprocessing to keep the GPU fed with images
    safe_workers = args.workers
    pin = device == "cuda"

    train_loader = DataLoader(
        train_set,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=safe_workers,
        pin_memory=pin,
        drop_last=True,
    )
    val_loader = DataLoader(
        val_set,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=safe_workers,
        pin_memory=pin,
    )

    model = build_image_model(args.backbone, pretrained=True)
    if args.freeze_backbone:
        for name, parameter in model.named_parameters():
            parameter.requires_grad = "classifier" in name or "fc" in name

    labels = train_set.labels
    positives = sum(labels)
    # Re-weight the positive class if preprocessing could not fully balance it.
    pos_weight = (len(labels) - positives) / positives if 0 < positives < len(labels) else None

    config = TrainConfig(
        epochs=args.epochs,
        lr=args.lr,
        weight_decay=args.weight_decay,
        patience=args.patience,
        device=device,
        use_amp=args.use_amp,
        checkpoint_path=args.checkpoint,
        log_path=args.checkpoint.with_name("image_training_log.csv"),
        model_version=args.version,
        extra_metadata={"backbone": args.backbone, "input_size": args.size},
    )

    print(f"Training {args.backbone} on {device} for up to {args.epochs} epochs ...")
    summary = train_model(model, train_loader, val_loader, config, pos_weight=pos_weight)
    print("\nBest validation metrics:")
    from ml.evaluation.metrics import format_report

    print(format_report(summary["best_val_metrics"]))
    print(f"\nCheckpoint: {args.checkpoint}")
    print(
        "Evaluate on the held-out test split with ml/evaluation/evaluate.py before "
        "quoting any number in your report."
    )


if __name__ == "__main__":
    main()
