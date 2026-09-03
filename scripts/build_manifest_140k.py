#!/usr/bin/env python3
"""Build manifest.csv directly from the 140k Real and Fake Faces folder layout.

The dataset is already split into train/valid/test and already face-cropped,
so we skip face detection entirely and just enumerate files into a manifest.

Usage (from the repo root):
    python scripts/build_manifest_140k.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))

RAW_ROOT = REPO_ROOT / "data" / "raw" / "faces-140k" / "real_vs_fake" / "real-vs-fake"
OUT_DIR  = REPO_ROOT / "data" / "processed" / "faces"
MANIFEST = OUT_DIR / "manifest.csv"

SPLIT_MAP = {"train": "train", "valid": "val", "test": "test"}
LABEL_MAP = {"real": 0, "fake": 1}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for raw_split, csv_split in SPLIT_MAP.items():
        split_dir = RAW_ROOT / raw_split
        if not split_dir.exists():
            print(f"  WARNING: expected directory not found: {split_dir}")
            continue
        for class_name, label in LABEL_MAP.items():
            class_dir = split_dir / class_name
            if not class_dir.exists():
                print(f"  WARNING: {class_dir} missing, skipping")
                continue
            files = [p for p in class_dir.iterdir() if p.suffix.lower() in IMAGE_EXT]
            print(f"  {raw_split}/{class_name}: {len(files):,} images")
            for p in files:
                rows.append({
                    "path":  str(p),
                    "label": label,
                    "group": p.stem,      # unique per image — each is its own group
                    "split": csv_split,
                })

    if not rows:
        raise SystemExit(f"No images found under {RAW_ROOT}. Check the dataset path.")

    with open(MANIFEST, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "label", "group", "split"])
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    train_n  = sum(1 for r in rows if r["split"] == "train")
    val_n    = sum(1 for r in rows if r["split"] == "val")
    test_n   = sum(1 for r in rows if r["split"] == "test")
    real_n   = sum(1 for r in rows if r["label"] == 0)
    fake_n   = sum(1 for r in rows if r["label"] == 1)

    print(f"\nManifest written: {MANIFEST}")
    print(f"  Total : {total:,}  (real={real_n:,}  fake={fake_n:,})")
    print(f"  Train : {train_n:,}")
    print(f"  Val   : {val_n:,}")
    print(f"  Test  : {test_n:,}")
    print("\nNext step:")
    print(f"  python ml/training/train_image.py --data {OUT_DIR} --device cuda --epochs 20 --batch-size 64")


if __name__ == "__main__":
    main()
