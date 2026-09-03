#!/usr/bin/env python3
"""Download the openly available datasets and arrange them for preprocessing.

Only datasets that download without an approval process are handled here:

* ``faces-140k``  — 140k Real and Fake Faces (StyleGAN vs real), image pipeline
* ``for-audio``   — Fake-or-Real, TTS vs human speech, audio pipeline

FaceForensics++, Celeb-DF, DFDC, WildDeepfake and ASVspoof are deliberately
absent: each requires an academic-use agreement signed by a named researcher at
a named institution. No script can accept those terms on your behalf — request
them yourself (see docs/datasets.md) and drop the extracted media into the same
directory layout this script produces.

Requires a Kaggle API token:
  1. kaggle.com -> Account -> "Create New API Token" -> kaggle.json
  2. mkdir -p ~/.kaggle && mv ~/Downloads/kaggle.json ~/.kaggle/
  3. chmod 600 ~/.kaggle/kaggle.json
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DATASETS = {
    "faces-140k": {
        "slug": "xhlulu/140k-real-and-fake-faces",
        "size": "~4 GB",
        "modality": "image",
        "description": "StyleGAN-generated vs real faces (Flickr-Faces-HQ)",
        # Source subdirectory -> destination class directory.
        "layout": {"real": "real", "fake": "fake"},
    },
    "for-audio": {
        "slug": "mohammedabdeldayem/the-fake-or-real-dataset",
        "size": "~5 GB",
        "modality": "audio",
        "description": "Fake-or-Real: TTS-generated vs human speech",
        "layout": {"real": "bonafide", "fake": "spoof"},
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("dataset", nargs="?", choices=sorted(DATASETS), help="Dataset to fetch")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "data" / "raw")
    parser.add_argument("--list", action="store_true", help="List available datasets and exit")
    parser.add_argument(
        "--keep-archive", action="store_true", help="Keep the downloaded zip after extracting"
    )
    return parser.parse_args()


def check_kaggle_credentials() -> None:
    pass


def ensure_kaggle_cli() -> None:
    if shutil.which("kaggle") is None:
        raise SystemExit("The kaggle CLI is not installed. Run: pip install kaggle")


def download(slug: str, destination: Path, keep_archive: bool) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {slug} into {destination} (this takes a while) ...")
    command = ["kaggle", "datasets", "download", "-d", slug, "-p", str(destination), "--unzip"]
    if keep_archive:
        command.remove("--unzip")
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(
            f"kaggle download failed (exit {result.returncode}).\n"
            "A 403 usually means you have not accepted the dataset's terms — open\n"
            f"  https://www.kaggle.com/datasets/{slug}\n"
            "in a browser, click through the rules once, then re-run this script."
        )


def find_class_directories(root: Path, layout: dict[str, str]) -> dict[str, Path]:
    """Locate each class directory inside an archive whose depth varies by dataset."""
    found: dict[str, Path] = {}
    for source_name in layout:
        matches = [
            path for path in root.rglob(source_name) if path.is_dir() and any(path.iterdir())
        ]
        if matches:
            # Prefer the largest: these archives repeat class names across splits.
            found[source_name] = max(matches, key=lambda p: sum(1 for _ in p.rglob("*")))
    return found


def main() -> None:
    args = parse_args()

    if args.list or not args.dataset:
        print("Openly downloadable datasets:\n")
        for name, meta in DATASETS.items():
            print(f"  {name:<12} {meta['size']:<8} {meta['modality']:<6} {meta['description']}")
        print("\nDatasets requiring a signed academic-use agreement (request them yourself,")
        print("see docs/datasets.md): FaceForensics++, Celeb-DF, DFDC, WildDeepfake, ASVspoof.")
        return

    meta = DATASETS[args.dataset]
    ensure_kaggle_cli()
    check_kaggle_credentials()

    staging = args.output / args.dataset
    download(meta["slug"], staging, args.keep_archive)

    directories = find_class_directories(staging, meta["layout"])
    if not directories:
        print(
            f"\nDownloaded to {staging}, but the expected class folders "
            f"({', '.join(meta['layout'])}) were not found.\n"
            "Archive layouts change; point the preprocessing script at the correct\n"
            "directories manually with --real-dir/--fake-dir.",
            file=sys.stderr,
        )
        return

    print("\nReady. Next step:\n")
    if meta["modality"] == "image":
        real = directories.get("real", staging)
        fake = directories.get("fake", staging)
        print(
            f"  python ml/preprocessing/build_face_dataset.py \\\n"
            f"      --real-dir {real} \\\n"
            f"      --fake-dir {fake} \\\n"
            f"      --output data/processed/faces"
        )
    else:
        bonafide = directories.get("real", staging)
        spoof = directories.get("fake", staging)
        print(
            f"  python ml/preprocessing/build_audio_dataset.py \\\n"
            f"      --bonafide-dir {bonafide} \\\n"
            f"      --spoof-dir {spoof} \\\n"
            f"      --output data/processed/audio"
        )


if __name__ == "__main__":
    main()
