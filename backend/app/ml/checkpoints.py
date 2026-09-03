"""Safe checkpoint loading.

``torch.load`` defaults to pickle, which executes arbitrary code while
deserialising. Since the documented workflow is to train elsewhere (Colab, a lab
GPU) and copy a ``.pt`` file onto the server, a checkpoint is untrusted input
arriving on the machine that holds user media — the worst possible place for
remote code execution.

Loading therefore uses ``weights_only=True``, which restricts deserialisation to
tensors and simple built-ins. That is enough for the checkpoints this project
writes. Loading a checkpoint that needs full pickle requires an explicit opt-in.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

UNSAFE_OPT_IN = "ALLOW_UNSAFE_CHECKPOINTS"


class UnsafeCheckpointError(RuntimeError):
    """A checkpoint could not be loaded under the safe deserialiser."""


def unsafe_loading_allowed() -> bool:
    return os.environ.get(UNSAFE_OPT_IN, "").lower() in {"1", "true", "yes"}


def load_checkpoint(path: str | Path) -> Any:
    """Load a checkpoint, preferring the safe deserialiser.

    Falls back to full pickle only when ``ALLOW_UNSAFE_CHECKPOINTS`` is set, and
    says so loudly when it does.
    """
    import torch

    path = Path(path)
    try:
        return torch.load(path, map_location="cpu", weights_only=True)
    except Exception as exc:
        if not unsafe_loading_allowed():
            raise UnsafeCheckpointError(
                f"'{path.name}' could not be loaded safely: {exc}\n"
                "It likely contains pickled Python objects, which execute code on load.\n"
                "If you trust its origin, re-run with "
                f"{UNSAFE_OPT_IN}=true, or better, re-save it as a plain state_dict:\n"
                "    torch.save({'state_dict': model.state_dict()}, 'model.pt')"
            ) from exc

        logger.warning(
            "%s set: loading '%s' with full pickle. This executes code contained in the "
            "file — only do this for checkpoints you produced or fully trust.",
            UNSAFE_OPT_IN,
            path.name,
        )
        # Reached only when the operator explicitly opted in above, after the
        # safe loader failed and a warning was emitted.
        return torch.load(path, map_location="cpu", weights_only=False)  # nosec B614


def extract_state_dict(payload: Any) -> Any:
    """Return the tensor state dict from a checkpoint payload."""
    if isinstance(payload, dict) and "state_dict" in payload:
        return payload["state_dict"]
    return payload


def extract_metadata(payload: Any) -> dict[str, Any]:
    """Return the scalar metadata recorded alongside the weights."""
    if not isinstance(payload, dict):
        return {}
    return {
        key: value
        for key, value in payload.items()
        if key != "state_dict" and isinstance(value, (str, int, float, bool))
    }
