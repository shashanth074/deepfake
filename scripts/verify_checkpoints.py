#!/usr/bin/env python3
"""Check which checkpoints the backend will actually load, and what it will report.

Run this after training and after copying checkpoints onto a deployment. It
answers the only question that matters at handoff time: will this instance
produce evidential results, or is it still in demonstration mode?

  python scripts/verify_checkpoints.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

GREEN, RED, YELLOW, BOLD, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[1m", "\033[0m"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--checkpoint-dir", type=Path, default=None, help="Override CHECKPOINT_DIR for this check"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero unless every detector has trained weights "
        "(use this as a deployment gate)",
    )
    return parser.parse_args()


def output_varies(loaded, kind: str) -> bool | None:
    """Probe whether the model still discriminates in eval mode.

    A network can train to a high validation AUC and still emit a near-constant
    score once switched to eval mode, because BatchNorm's running statistics
    need many more updates to converge than the weights do. The symptom is
    every upload scoring the same value, which looks like a serving bug but is
    an undertrained model. Catching it here saves a long hunt in the wrong place.

    Returns None when the probe itself could not run.
    """
    import torch

    try:
        if kind == "image":
            size = loaded.input_size
            batch = torch.randn(6, 3, size, size)
        else:
            batch = torch.randn(6, 1, 64, 400)
        with torch.no_grad():
            outputs = torch.sigmoid(loaded.module(batch.to(loaded.device))).flatten()
        return float(outputs.max() - outputs.min()) > 1e-4
    except Exception:
        return None


def describe_checkpoint(path: Path) -> dict:
    """Load a checkpoint's metadata without building the network."""
    from app.ml.checkpoints import extract_metadata, load_checkpoint

    payload = load_checkpoint(path)
    if not isinstance(payload, dict):
        return {"note": "raw state_dict (no metadata)"}
    return extract_metadata(payload)


def main() -> int:
    args = parse_args()
    if args.checkpoint_dir:
        import os

        os.environ["CHECKPOINT_DIR"] = str(args.checkpoint_dir)
        from app.config import get_settings

        get_settings.cache_clear()

    try:
        import torch  # noqa: F401
    except ImportError:
        print(
            f"{RED}PyTorch is not installed.{RESET} Run: pip install -r backend/requirements-ml.txt"
        )
        return 2

    from app.config import settings
    from app.ml import registry

    print(f"{BOLD}Checkpoint directory:{RESET} {settings.checkpoint_dir}\n")

    loaders = {"image": registry.get_image_model, "audio": registry.get_audio_model}
    trained = 0

    for kind, loader in loaders.items():
        path = registry.checkpoint_path(kind)
        print(f"{BOLD}{kind.upper()} detector{RESET}")
        print(f"  expected file : {path.name}")

        if not path.exists():
            print(f"  status        : {RED}MISSING{RESET} — no file at {path}")
            print(
                f"  consequence   : results flagged {RED}untrained-backbone{RESET}; "
                "the UI shows a red 'not evidence' banner and the PDF carries a "
                "'MODEL NOT TRAINED' block."
            )
            print(
                f"  fix           : python ml/training/train_{kind}.py --data "
                f"data/processed/{'faces' if kind == 'image' else 'audio'}\n"
            )
            continue

        size_mb = path.stat().st_size / (1024 * 1024)
        try:
            metadata = describe_checkpoint(path)
        except Exception as exc:
            print(f"  status        : {RED}UNREADABLE{RESET} — {exc}\n")
            continue

        try:
            registry.reset_cache()
            loaded = loader()
        except Exception as exc:
            print(f"  status        : {RED}FAILED TO LOAD{RESET} — {exc}")
            print("  likely cause  : the checkpoint was trained with a different backbone.\n")
            continue

        ok = loaded.weights_status == registry.TRAINED
        colour = GREEN if ok else YELLOW
        print(
            f"  status        : {colour}{loaded.weights_status.upper()}{RESET} ({size_mb:.1f} MB)"
        )
        print(f"  serving as    : {loaded.name} {loaded.version} on {loaded.device}")
        if metadata:
            details = ", ".join(f"{k}={v}" for k, v in sorted(metadata.items()))
            print(f"  recorded      : {details}")
        if "val_auc" not in metadata and ok:
            print(
                f"  {YELLOW}note{RESET}          : no validation metrics recorded. Run "
                "ml/evaluation/evaluate.py before quoting accuracy anywhere."
            )

        varies = output_varies(loaded, kind)
        if varies is False:
            print(
                f"  {RED}WARNING{RESET}       : the model returns the same score for every "
                "input in eval mode."
            )
            print(
                "                  Its BatchNorm running statistics have not converged — "
                "typically too few"
            )
            print(
                "                  training steps. Validation AUC can look excellent while "
                "this is true."
            )
            print("                  Train for more epochs on more data before deploying it.")
            ok = False
        elif varies is None:
            print(f"  {YELLOW}note{RESET}          : could not probe the model's output range.")
        print()
        trained += int(ok)

    total = len(loaders)
    print(f"{BOLD}Summary:{RESET} {trained}/{total} detectors have trained weights.")
    if trained == total:
        print(f"{GREEN}This deployment will produce evidential results.{RESET}")
        print("Video reuses the image checkpoint, so it is covered too.")
        return 0

    print(
        f"{YELLOW}This deployment is in demonstration mode.{RESET} Scores carry no "
        "evidentiary value and every surface says so."
    )
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
