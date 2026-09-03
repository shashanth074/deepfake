#!/usr/bin/env python3
"""Build a face-crop dataset from real/fake videos or images.

Videos are decoded at a fixed sampling rate, faces are detected and cropped with
a margin, and crops are written as JPEGs. Every crop records the source file as
its *group* so the train/val/test split can keep an identity entirely on one
side of the split.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Running this file directly puts its own directory on sys.path, not the repo
# root, so `import ml...` would fail. Add the repo root before those imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.common import (
    REPO_ROOT,
    save_json,
    set_seed,
    split_by_group,
    warn_on_single_class_splits,
    write_manifest,
)  # noqa: E402

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--real-dir", type=Path, required=True, help="Directory of authentic videos/images"
    )
    parser.add_argument(
        "--fake-dir", type=Path, required=True, help="Directory of manipulated videos/images"
    )
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "data/processed/faces")
    parser.add_argument("--fps", type=float, default=1.0, help="Frames sampled per second")
    parser.add_argument("--max-frames", type=int, default=32, help="Max frames per video")
    parser.add_argument("--size", type=int, default=224, help="Output crop size")
    parser.add_argument(
        "--face-detection",
        choices=["auto", "required", "off"],
        default="auto",
        help="auto: crop faces when a detector is installed, else use whole images; "
        "required: fail if no detector is available; "
        "off: use whole images (right for datasets that are already face crops, "
        "such as 140k Real and Fake Faces)",
    )
    parser.add_argument(
        "--balance",
        action="store_true",
        default=True,
        help="Trim the larger class so real/fake counts match",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def iter_sources(directory: Path):
    """Yield every media file under ``directory``."""
    for path in sorted(directory.rglob("*")):
        if path.suffix.lower() in VIDEO_EXTENSIONS | IMAGE_EXTENSIONS:
            yield path


def detection_enabled(mode: str) -> bool:
    """Decide whether to run face detection, failing loudly when it is required."""
    if mode == "off":
        return False

    from app.ml.faces import get_detector

    if get_detector() is not None:
        return True
    if mode == "required":
        raise SystemExit(
            "--face-detection required, but no face detector is installed.\n"
            "Install it with: pip install facenet-pytorch\n"
            "Or pass --face-detection off if your images are already face crops."
        )
    print(
        "note: no face detector installed (pip install facenet-pytorch); using whole\n"
        "      images. That is correct for datasets which are already face crops, and\n"
        "      wrong for full scenes or video frames, where the face must be isolated.\n"
    )
    return False


def crops_from_source(
    path: Path, fps: float, max_frames: int, size: int, detect_faces: bool = True
):
    """Yield ``(index, PIL image)`` training crops from one video or image."""
    from app.ml.faces import extract_faces
    from app.ml.preprocessing import sample_video_frames
    from PIL import Image

    if path.suffix.lower() in IMAGE_EXTENSIONS:
        with Image.open(path) as opened:
            frames = [(0.0, opened.convert("RGB"))]
    else:
        frames, _ = sample_video_frames(path, target_fps=fps, max_frames=max_frames)

    for index, (_timestamp, frame) in enumerate(frames):
        if not detect_faces:
            yield index, frame.convert("RGB").resize((size, size), Image.BILINEAR)
            continue
        faces = extract_faces(frame)
        if not faces or faces[0].box is None:
            continue  # no face found: nothing useful for a face-centred detector
        yield index, faces[0].image.convert("RGB").resize((size, size), Image.BILINEAR)


def build_split(
    directory: Path, label: int, output: Path, args, detect_faces: bool = True
) -> list[dict]:
    rows: list[dict] = []
    class_name = "fake" if label else "real"
    class_dir = output / class_name
    class_dir.mkdir(parents=True, exist_ok=True)

    for source in iter_sources(directory):
        group = source.stem
        written = 0
        for index, crop in crops_from_source(
            source, args.fps, args.max_frames, args.size, detect_faces
        ):
            target = class_dir / f"{group}_{index:04d}.jpg"
            crop.save(target, format="JPEG", quality=95)
            rows.append({"path": str(target), "label": label, "group": group, "split": ""})
            written += 1
        print(f"  {source.name}: {written} crops")
    return rows


def main() -> None:
    args = parse_args()
    set_seed(args.seed)
    args.output.mkdir(parents=True, exist_ok=True)

    detect_faces = detection_enabled(args.face_detection)

    print(f"Extracting authentic samples from {args.real_dir} ...")
    real_rows = build_split(args.real_dir, 0, args.output, args, detect_faces)
    print(f"Extracting manipulated samples from {args.fake_dir} ...")
    fake_rows = build_split(args.fake_dir, 1, args.output, args, detect_faces)

    if args.balance and real_rows and fake_rows:
        # An unbalanced set teaches the model the prior, not the artefacts.
        import random

        limit = min(len(real_rows), len(fake_rows))
        rng = random.Random(args.seed)
        real_rows = rng.sample(real_rows, limit)
        fake_rows = rng.sample(fake_rows, limit)

    rows = real_rows + fake_rows
    if not rows:
        sources = sum(1 for _ in iter_sources(args.real_dir)) + sum(
            1 for _ in iter_sources(args.fake_dir)
        )
        if sources == 0:
            raise SystemExit(
                f"No media files found under {args.real_dir} or {args.fake_dir}. "
                f"Supported: {sorted(VIDEO_EXTENSIONS | IMAGE_EXTENSIONS)}"
            )
        raise SystemExit(
            f"Read {sources} source files but produced no crops: no face was detected in "
            "any of them.\nIf these images are already cropped faces, re-run with "
            "--face-detection off."
        )

    assignment = split_by_group(
        [row["group"] for row in rows],
        seed=args.seed,
        labels=[row["label"] for row in rows],
    )
    for row in rows:
        row["split"] = assignment[row["group"]]

    for warning in warn_on_single_class_splits(rows):
        print(warning)

    manifest = args.output / "manifest.csv"
    write_manifest(manifest, rows)

    summary = {
        "face_detection": "enabled" if detect_faces else "disabled (whole images used)",
        "total_crops": len(rows),
        "real": sum(1 for row in rows if row["label"] == 0),
        "fake": sum(1 for row in rows if row["label"] == 1),
        "groups": len(assignment),
        "split_counts": {
            split: sum(1 for row in rows if row["split"] == split)
            for split in ("train", "val", "test")
        },
        "split_policy": "by source file (identity-disjoint)",
    }
    save_json(args.output / "dataset_summary.json", summary)
    print(f"\nManifest: {manifest}")
    print(summary)


if __name__ == "__main__":
    main()
