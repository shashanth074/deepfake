"""Shared helpers for the offline training scripts.

Adds ``backend/`` to ``sys.path`` so training reuses the same preprocessing code
the API serves with — the transforms must be identical on both sides.
"""

from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def set_seed(seed: int = 42) -> None:
    """Seed every RNG so a training run can be reproduced for the report."""
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def write_manifest(path: Path, rows: list[dict]) -> None:
    """Write a dataset manifest as CSV (path,label,group,split)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "label", "group", "split"])
        writer.writeheader()
        writer.writerows(rows)


def read_manifest(path: Path, split: str | None = None) -> list[dict]:
    """Read a manifest, optionally filtered to one split."""
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["label"] = int(row["label"])
    return [row for row in rows if split is None or row["split"] == split]


def split_by_group(
    groups: list[str],
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
    seed: int = 42,
    labels: list[int] | None = None,
) -> dict[str, str]:
    """Assign whole groups (source video / speaker) to train/val/test.

    Splitting by group rather than by sample is what prevents identity leakage
    between train and test: frames of one face, or windows of one voice, never
    straddle the boundary.

    When ``labels`` is supplied the split is additionally stratified by class,
    so each split receives both real and fake groups in roughly the dataset's
    proportion. Without stratification a small or unlucky draw can hand the
    validation split a single class, which silently makes validation AUC
    meaningless (0.5) and turns best-checkpoint selection into a coin toss.
    """
    unique = sorted(set(groups))
    rng = random.Random(seed)

    if labels is None:
        strata = {0: unique}
    else:
        # A group belongs to whichever class most of its samples carry.
        counts: dict[str, dict[int, int]] = {}
        for group, label in zip(groups, labels, strict=True):
            counts.setdefault(group, {}).setdefault(label, 0)
            counts[group][label] += 1
        strata = {}
        for group in unique:
            majority = max(counts[group].items(), key=lambda kv: kv[1])[0]
            strata.setdefault(majority, []).append(group)

    assignment: dict[str, str] = {}
    for _label, members in sorted(strata.items()):
        members = list(members)
        rng.shuffle(members)
        total = len(members)
        # Guarantee at least one group per split once a stratum can afford it,
        # so no split silently loses a class.
        train_end = int(total * ratios[0])
        val_end = train_end + int(total * ratios[1])
        if total >= 3:
            train_end = min(max(train_end, 1), total - 2)
            val_end = min(max(val_end, train_end + 1), total - 1)
        for index, group in enumerate(members):
            if index < train_end:
                assignment[group] = "train"
            elif index < val_end:
                assignment[group] = "val"
            else:
                assignment[group] = "test"
    return assignment


def warn_on_single_class_splits(rows: list[dict]) -> list[str]:
    """Return a warning for any split that ended up with only one class."""
    warnings: list[str] = []
    for split in ("train", "val", "test"):
        labels = {row["label"] for row in rows if row["split"] == split}
        if len(labels) == 1:
            only = "real" if labels == {0} else "fake"
            warnings.append(
                f"WARNING: the '{split}' split contains only {only} samples. "
                "Metrics computed on it are meaningless (AUC will read 0.5). "
                "Use more source files or adjust the split ratios."
            )
        elif not labels:
            warnings.append(f"WARNING: the '{split}' split is empty.")
    return warnings


class CsvLogger:
    """Append-only CSV of per-epoch metrics — the source for training curves."""

    def __init__(self, path: Path, fieldnames: list[str]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fieldnames = fieldnames
        with open(self.path, "w", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=fieldnames).writeheader()

    def log(self, **row) -> None:
        with open(self.path, "a", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=self.fieldnames).writerow(row)


def save_json(path: Path, payload: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
