#!/usr/bin/env python3
"""Build a windowed audio dataset from bonafide/spoofed speech.

Clips are resampled to 16 kHz mono, silence-trimmed, peak-normalised, and split
into fixed-length windows saved as .npy arrays. Each window records its source
clip's speaker as its group, so the split stays speaker-disjoint and the test
set measures generalisation to unheard voices.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

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

AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".m4a", ".ogg"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bonafide-dir", type=Path, required=True, help="Directory of genuine human speech"
    )
    parser.add_argument(
        "--spoof-dir",
        type=Path,
        required=True,
        help="Directory of TTS / voice-converted / cloned speech",
    )
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "data/processed/audio")
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--window", type=float, default=4.0, help="Window length in seconds")
    parser.add_argument(
        "--speaker-from",
        choices=["prefix", "parent", "stem"],
        default="prefix",
        help="How to derive the speaker id used for grouping",
    )
    parser.add_argument("--balance", action="store_true", default=True)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def speaker_id(path: Path, mode: str) -> str:
    """Derive a speaker/group id from the file path.

    ASVspoof-style corpora encode the speaker in a filename prefix
    (``LA_0079_...``); other layouts use one directory per speaker.
    """
    if mode == "parent":
        return path.parent.name
    if mode == "stem":
        return path.stem
    parts = path.stem.split("_")
    return "_".join(parts[:2]) if len(parts) >= 2 else path.stem


def build_split(directory: Path, label: int, output: Path, args) -> list[dict]:
    from app.ml.preprocessing import (
        load_audio,
        normalize_waveform,
        segment_waveform,
        trim_silence,
    )

    rows: list[dict] = []
    class_name = "spoof" if label else "bonafide"
    class_dir = output / class_name
    class_dir.mkdir(parents=True, exist_ok=True)

    sources = [p for p in sorted(directory.rglob("*")) if p.suffix.lower() in AUDIO_EXTENSIONS]
    for source in sources:
        try:
            waveform, rate = load_audio(source, args.sample_rate)
        except Exception as exc:
            print(f"  skipped {source.name}: {exc}")
            continue

        waveform = normalize_waveform(trim_silence(waveform))
        if waveform.size == 0:
            continue

        group = speaker_id(source, args.speaker_from)
        for index, (_start, samples) in enumerate(segment_waveform(waveform, rate, args.window)):
            target = class_dir / f"{source.stem}_{index:03d}.npy"
            np.save(target, samples.astype(np.float32))
            rows.append({"path": str(target), "label": label, "group": group, "split": ""})
        print(f"  {source.name}: {index + 1} windows (speaker {group})")
    return rows


def main() -> None:
    args = parse_args()
    set_seed(args.seed)
    args.output.mkdir(parents=True, exist_ok=True)

    print(f"Windowing bonafide speech from {args.bonafide_dir} ...")
    bonafide_rows = build_split(args.bonafide_dir, 0, args.output, args)
    print(f"Windowing spoofed speech from {args.spoof_dir} ...")
    spoof_rows = build_split(args.spoof_dir, 1, args.output, args)

    if args.balance and bonafide_rows and spoof_rows:
        import random

        limit = min(len(bonafide_rows), len(spoof_rows))
        rng = random.Random(args.seed)
        bonafide_rows = rng.sample(bonafide_rows, limit)
        spoof_rows = rng.sample(spoof_rows, limit)

    rows = bonafide_rows + spoof_rows
    if not rows:
        raise SystemExit("No audio windows were produced — check the input directories.")

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
        "total_windows": len(rows),
        "bonafide": sum(1 for row in rows if row["label"] == 0),
        "spoof": sum(1 for row in rows if row["label"] == 1),
        "speakers": len(assignment),
        "window_seconds": args.window,
        "sample_rate": args.sample_rate,
        "split_counts": {
            split: sum(1 for row in rows if row["split"] == split)
            for split in ("train", "val", "test")
        },
        "split_policy": "by speaker (speaker-disjoint)",
    }
    save_json(args.output / "dataset_summary.json", summary)
    print(f"\nManifest: {manifest}")
    print(summary)


if __name__ == "__main__":
    main()
