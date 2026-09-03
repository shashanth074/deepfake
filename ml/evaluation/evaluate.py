#!/usr/bin/env python3
"""Evaluate a trained detector on its held-out test split.

Writes every figure the project report and viva need: the metric table, a
confusion matrix, ROC and precision-recall curves, and a score-distribution
histogram, plus a machine-readable metrics.json.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

# Running this file directly puts its own directory on sys.path, not the repo
# root, so `import ml...` would fail. Add the repo root before those imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.common import REPO_ROOT, save_json, set_seed
from ml.evaluation.metrics import (
    compute_metrics,
    equal_error_rate,
    format_report,
    precision_recall_curve,
    roc_curve,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["image", "audio"], required=True)
    parser.add_argument(
        "--data",
        type=Path,
        required=True,
        help="Processed dataset directory containing manifest.csv",
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument(
        "--backbone", default="efficientnet_b0", help="Image only: must match the trained backbone"
    )
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "reports/evaluation")
    parser.add_argument("--device", default=None)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def build_loader(args):
    from torch.utils.data import DataLoader

    manifest = args.data / "manifest.csv"
    if not manifest.exists():
        raise SystemExit(f"No manifest at {manifest}.")

    if args.model == "image":
        from ml.training.datasets import FaceCropDataset

        dataset = FaceCropDataset(manifest, args.split, augment=False)
        return DataLoader(
            dataset, batch_size=args.batch_size, shuffle=False, num_workers=args.workers
        )

    from ml.training.datasets import AudioWindowDataset, collate_spectrograms

    dataset = AudioWindowDataset(manifest, args.split, augment=False)
    return DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        collate_fn=collate_spectrograms,
    )


def build_model(args, device: str):
    from app.ml.checkpoints import extract_metadata, extract_state_dict, load_checkpoint
    from app.ml.models_arch import build_audio_model, build_image_model

    model = (
        build_image_model(args.backbone, pretrained=False)
        if args.model == "image"
        else build_audio_model()
    )

    payload = load_checkpoint(args.checkpoint)
    model.load_state_dict(extract_state_dict(payload), strict=False)
    model.eval().to(device)
    return model, extract_metadata(payload)


def main() -> None:
    args = parse_args()
    set_seed(args.seed)
    args.output.mkdir(parents=True, exist_ok=True)

    import torch

    from ml.training.engine import predict

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    loader = build_loader(args)
    model, metadata = build_model(args, device)

    print(f"Evaluating {args.model} model on the '{args.split}' split ({device}) ...")
    probabilities, labels = predict(model, loader, device)

    metrics = compute_metrics(labels, probabilities, threshold=args.threshold)
    print(f"\n=== {args.model.upper()} DETECTOR — {args.split} split ===")
    print(format_report(metrics))

    # The EER threshold is often a better operating point than a flat 0.5.
    eer, eer_threshold = equal_error_rate(labels, probabilities)
    at_eer = compute_metrics(labels, probabilities, threshold=eer_threshold)
    print(
        f"\n  At the EER threshold ({eer_threshold:.4f}): "
        f"accuracy {at_eer['accuracy'] * 100:.2f}%, F1 {at_eer['f1'] * 100:.2f}%"
    )

    plot_confusion_matrix(metrics, args.output / f"{args.model}_confusion_matrix.png")
    plot_roc(labels, probabilities, metrics, args.output / f"{args.model}_roc.png")
    plot_precision_recall(labels, probabilities, args.output / f"{args.model}_pr_curve.png")
    plot_score_distribution(
        labels, probabilities, args.output / f"{args.model}_score_distribution.png"
    )

    save_json(
        args.output / f"{args.model}_metrics.json",
        {
            "model": args.model,
            "checkpoint": str(args.checkpoint),
            "checkpoint_metadata": metadata,
            "split": args.split,
            "samples": int(np.asarray(labels).size),
            "metrics_at_threshold": metrics,
            "metrics_at_eer_threshold": at_eer,
        },
    )
    print(f"\nFigures and metrics written to {args.output}")


# --------------------------------------------------------------------------- plots
def _pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def plot_confusion_matrix(metrics: dict, path: Path) -> None:
    plt = _pyplot()
    matrix = metrics["confusion_matrix"]
    grid = np.array([[matrix["tn"], matrix["fp"]], [matrix["fn"], matrix["tp"]]])

    figure, axes = plt.subplots(figsize=(4.4, 4), dpi=150)
    axes.imshow(grid, cmap="Blues")
    for i in range(2):
        for j in range(2):
            share = grid[i, j] / max(grid.sum(), 1)
            axes.text(
                j,
                i,
                f"{grid[i, j]}\n{share * 100:.1f}%",
                ha="center",
                va="center",
                color="white" if share > 0.3 else "black",
                fontsize=11,
            )
    axes.set_xticks([0, 1], ["predicted real", "predicted fake"])
    axes.set_yticks([0, 1], ["actual real", "actual fake"])
    axes.set_title(f"Confusion matrix (acc {metrics['accuracy'] * 100:.1f}%)")
    figure.tight_layout()
    figure.savefig(path)
    plt.close(figure)


def plot_roc(labels, probabilities, metrics: dict, path: Path) -> None:
    plt = _pyplot()
    fpr, tpr, _ = roc_curve(labels, probabilities)

    figure, axes = plt.subplots(figsize=(4.6, 4.2), dpi=150)
    axes.plot(fpr, tpr, color="#1f4e79", linewidth=1.8, label=f"AUC = {metrics['auc_roc']:.4f}")
    axes.plot([0, 1], [0, 1], "--", color="#999999", linewidth=1, label="chance")
    axes.plot(
        [0, 1],
        [1, 0],
        ":",
        color="#c62828",
        linewidth=1,
        label=f"EER = {metrics['eer'] * 100:.2f}%",
    )
    axes.set_xlabel("False positive rate")
    axes.set_ylabel("True positive rate")
    axes.set_title("ROC curve")
    axes.legend(fontsize=8, loc="lower right")
    axes.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(path)
    plt.close(figure)


def plot_precision_recall(labels, probabilities, path: Path) -> None:
    plt = _pyplot()
    precision, recall = precision_recall_curve(labels, probabilities)

    figure, axes = plt.subplots(figsize=(4.6, 4.2), dpi=150)
    axes.plot(recall, precision, color="#2e7d32", linewidth=1.8)
    axes.set_xlabel("Recall")
    axes.set_ylabel("Precision")
    axes.set_title("Precision-recall curve")
    axes.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(path)
    plt.close(figure)


def plot_score_distribution(labels, probabilities, path: Path) -> None:
    """Overlaid score histograms — how separable the two classes actually are."""
    plt = _pyplot()
    labels = np.asarray(labels).ravel()
    probabilities = np.asarray(probabilities).ravel()

    figure, axes = plt.subplots(figsize=(6, 3.2), dpi=150)
    bins = np.linspace(0, 1, 41)
    axes.hist(probabilities[labels == 0], bins=bins, alpha=0.65, color="#2e7d32", label="real")
    axes.hist(probabilities[labels == 1], bins=bins, alpha=0.65, color="#c62828", label="fake")
    axes.set_xlabel("P(manipulated)")
    axes.set_ylabel("Samples")
    axes.set_title("Score distribution by true class")
    axes.legend(fontsize=8)
    axes.grid(alpha=0.2)
    figure.tight_layout()
    figure.savefig(path)
    plt.close(figure)


if __name__ == "__main__":
    main()
