"""Grad-CAM explainability for the image / video-frame detector.

Selvaraju et al. (2017): weight the final convolutional feature maps by the
gradient of the target score with respect to those maps, so the heatmap shows
which regions pushed the model toward "manipulated".
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


def compute_gradcam(model, input_tensor, target_layer=None) -> np.ndarray:
    """Return a ``(H, W)`` heatmap in ``[0, 1]`` for a single-image batch.

    ``model`` must expose either ``features()`` or a ``target_layer`` to hook.
    """
    import torch

    activations: dict[str, torch.Tensor] = {}
    gradients: dict[str, torch.Tensor] = {}

    if target_layer is None:
        target_layer = _default_target_layer(model)

    def forward_hook(_module, _inputs, output):
        activations["value"] = output

    def backward_hook(_module, _grad_input, grad_output):
        gradients["value"] = grad_output[0]

    handles = [
        target_layer.register_forward_hook(forward_hook),
        target_layer.register_full_backward_hook(backward_hook),
    ]

    try:
        model.zero_grad(set_to_none=True)
        with torch.enable_grad():
            logit = model(input_tensor)
            score = logit.squeeze()
            score.backward()

        activation = activations["value"].detach()[0]  # (C, H, W)
        gradient = gradients["value"].detach()[0]  # (C, H, W)
        weights = gradient.mean(dim=(1, 2), keepdim=True)  # global-average-pooled gradients
        cam = torch.relu((weights * activation).sum(dim=0))

        cam_np = cam.cpu().numpy().astype(np.float32)
    finally:
        for handle in handles:
            handle.remove()

    peak = float(cam_np.max())
    if peak <= 0:
        return np.zeros_like(cam_np)
    return cam_np / peak


def _default_target_layer(model):
    """Last convolutional module — the standard Grad-CAM target."""
    import torch.nn as nn

    if hasattr(model, "backbone") and hasattr(model.backbone, "features"):
        return model.backbone.features[-1]
    conv_layers = [module for module in model.modules() if isinstance(module, nn.Conv2d)]
    if not conv_layers:
        raise ValueError("Model has no Conv2d layer to attach Grad-CAM to.")
    return conv_layers[-1]


def overlay_heatmap(image, cam: np.ndarray, output_path: str | Path, alpha: float = 0.45) -> Path:
    """Blend a Grad-CAM heatmap over a PIL image and save it as PNG."""
    from PIL import Image

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    base = image.convert("RGB")
    cam_image = Image.fromarray((np.clip(cam, 0, 1) * 255).astype(np.uint8), mode="L")
    cam_image = cam_image.resize(base.size, Image.BILINEAR)
    colored = Image.fromarray(_apply_colormap(np.asarray(cam_image) / 255.0), mode="RGB")

    blended = Image.blend(base, colored, alpha)
    blended.save(output_path, format="PNG")
    return output_path


def _apply_colormap(normalized: np.ndarray) -> np.ndarray:
    """Jet-like colormap: blue (low evidence) -> red (high evidence)."""
    value = np.clip(normalized, 0.0, 1.0)
    red = np.clip(1.5 - np.abs(4 * value - 3), 0, 1)
    green = np.clip(1.5 - np.abs(4 * value - 2), 0, 1)
    blue = np.clip(1.5 - np.abs(4 * value - 1), 0, 1)
    return (np.stack([red, green, blue], axis=-1) * 255).astype(np.uint8)
