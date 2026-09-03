"""Network architectures for the detectors.

Two backbones are provided for images/video frames:

* ``efficientnet_b0`` / ``efficientnet_b4`` — torchvision, ImageNet-pretrained.
* ``xception`` — a compact re-implementation of Chollet (2017), the backbone
  used by the FaceForensics++ baseline. Implemented here so the project has no
  dependency on the unmaintained ``pretrainedmodels`` package.

The audio detector is a Light CNN (LCNN) over log-Mel spectrograms, the
architecture used by the ASVspoof baselines.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


# --------------------------------------------------------------------------- Xception
class SeparableConv2d(nn.Module):
    """Depthwise separable convolution — the Xception building block."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int = 3,
        stride: int = 1,
        padding: int = 0,
    ) -> None:
        super().__init__()
        self.depthwise = nn.Conv2d(
            in_channels, in_channels, kernel_size, stride, padding, groups=in_channels, bias=False
        )
        self.pointwise = nn.Conv2d(in_channels, out_channels, 1, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.pointwise(self.depthwise(x))


class XceptionBlock(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        reps: int,
        stride: int = 1,
        start_with_relu: bool = True,
        grow_first: bool = True,
    ) -> None:
        super().__init__()
        self.skip: nn.Module | None = None
        if out_channels != in_channels or stride != 1:
            self.skip = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, 1, stride=stride, bias=False),
                nn.BatchNorm2d(out_channels),
            )

        layers: list[nn.Module] = []
        channels = in_channels
        if grow_first:
            layers += [
                nn.ReLU(inplace=False),
                SeparableConv2d(in_channels, out_channels, 3, 1, 1),
                nn.BatchNorm2d(out_channels),
            ]
            channels = out_channels
        for _ in range(reps - 1):
            layers += [
                nn.ReLU(inplace=True),
                SeparableConv2d(channels, channels, 3, 1, 1),
                nn.BatchNorm2d(channels),
            ]
        if not grow_first:
            layers += [
                nn.ReLU(inplace=True),
                SeparableConv2d(in_channels, out_channels, 3, 1, 1),
                nn.BatchNorm2d(out_channels),
            ]
        if not start_with_relu:
            layers = layers[1:]
        if stride != 1:
            layers.append(nn.MaxPool2d(3, stride, 1))
        self.body = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.body(x)
        residual = x if self.skip is None else self.skip(x)
        return out + residual


class Xception(nn.Module):
    """Xception backbone with a binary classification head (real=0, fake=1)."""

    def __init__(self, num_classes: int = 1) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(3, 32, 3, 2, 0, bias=False)
        self.bn1 = nn.BatchNorm2d(32)
        self.conv2 = nn.Conv2d(32, 64, 3, bias=False)
        self.bn2 = nn.BatchNorm2d(64)

        self.block1 = XceptionBlock(64, 128, 2, 2, start_with_relu=False, grow_first=True)
        self.block2 = XceptionBlock(128, 256, 2, 2, grow_first=True)
        self.block3 = XceptionBlock(256, 728, 2, 2, grow_first=True)
        self.middle = nn.Sequential(
            *[XceptionBlock(728, 728, 3, 1, grow_first=True) for _ in range(8)]
        )
        self.block12 = XceptionBlock(728, 1024, 2, 2, grow_first=False)

        self.conv3 = SeparableConv2d(1024, 1536, 3, 1, 1)
        self.bn3 = nn.BatchNorm2d(1536)
        self.conv4 = SeparableConv2d(1536, 2048, 3, 1, 1)
        self.bn4 = nn.BatchNorm2d(2048)
        self.dropout = nn.Dropout(0.3)
        self.fc = nn.Linear(2048, num_classes)

    def features(self, x: torch.Tensor) -> torch.Tensor:
        """Feature map before pooling — the Grad-CAM target layer."""
        x = F.relu(self.bn1(self.conv1(x)), inplace=True)
        x = F.relu(self.bn2(self.conv2(x)), inplace=True)
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        x = self.middle(x)
        x = self.block12(x)
        x = F.relu(self.bn3(self.conv3(x)), inplace=True)
        x = F.relu(self.bn4(self.conv4(x)), inplace=True)
        return x

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = F.adaptive_avg_pool2d(x, 1).flatten(1)
        return self.fc(self.dropout(x))


# --------------------------------------------------------------------------- EfficientNet
class EfficientNetDetector(nn.Module):
    """torchvision EfficientNet with the classifier swapped for a binary head."""

    def __init__(
        self, variant: str = "efficientnet_b0", pretrained: bool = True, num_classes: int = 1
    ) -> None:
        super().__init__()
        from torchvision import models as tv_models

        builder = getattr(tv_models, variant, None)
        if builder is None:
            raise ValueError(f"Unknown torchvision backbone: {variant}")
        weights = "DEFAULT" if pretrained else None
        try:
            backbone = builder(weights=weights)
        except Exception:
            # No network access for the ImageNet weights — start from scratch.
            backbone = builder(weights=None)
        in_features = backbone.classifier[-1].in_features
        backbone.classifier[-1] = nn.Linear(in_features, num_classes)
        self.backbone = backbone

    def features(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone.features(x)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x)


def build_image_model(backbone: str = "efficientnet_b0", pretrained: bool = True) -> nn.Module:
    """Factory for the image/video-frame detector."""
    if backbone == "xception":
        return Xception(num_classes=1)
    return EfficientNetDetector(variant=backbone, pretrained=pretrained, num_classes=1)


# --------------------------------------------------------------------------- LCNN (audio)
class MaxFeatureMap2d(nn.Module):
    """Max-Feature-Map activation: split channels in half and take the max."""

    def __init__(self) -> None:
        super().__init__()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        first, second = torch.chunk(x, 2, dim=1)
        return torch.max(first, second)


class LCNN(nn.Module):
    """Light CNN over log-Mel spectrograms (ASVspoof anti-spoofing baseline).

    Input: ``(batch, 1, n_mels, frames)``. Output: one logit, spoof=1.
    """

    def __init__(self, num_classes: int = 1) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, 5, 1, 2),
            MaxFeatureMap2d(),
            nn.MaxPool2d(2, 2),
            nn.Conv2d(16, 32, 1, 1, 0),
            MaxFeatureMap2d(),
            nn.BatchNorm2d(16),
            nn.Conv2d(16, 96, 3, 1, 1),
            MaxFeatureMap2d(),
            nn.MaxPool2d(2, 2),
            nn.BatchNorm2d(48),
            nn.Conv2d(48, 96, 1, 1, 0),
            MaxFeatureMap2d(),
            nn.BatchNorm2d(48),
            nn.Conv2d(48, 128, 3, 1, 1),
            MaxFeatureMap2d(),
            nn.MaxPool2d(2, 2),
            nn.Conv2d(64, 128, 1, 1, 0),
            MaxFeatureMap2d(),
            nn.BatchNorm2d(64),
            nn.Conv2d(64, 64, 3, 1, 1),
            MaxFeatureMap2d(),
            nn.BatchNorm2d(32),
            nn.Conv2d(32, 64, 1, 1, 0),
            MaxFeatureMap2d(),
            nn.BatchNorm2d(32),
            nn.Conv2d(32, 64, 3, 1, 1),
            MaxFeatureMap2d(),
            nn.MaxPool2d(2, 2),
        )
        self.head = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(32, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
            nn.Linear(64, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = F.adaptive_avg_pool2d(x, 1).flatten(1)
        return self.head(x)


def build_audio_model() -> nn.Module:
    return LCNN(num_classes=1)


# --------------------------------------------------------------------------- temporal head
class FrameSequenceLSTM(nn.Module):
    """Optional sequence model over per-frame CNN embeddings (Phase 4.2)."""

    def __init__(self, feature_dim: int = 1280, hidden_dim: int = 256, num_layers: int = 1) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            feature_dim, hidden_dim, num_layers, batch_first=True, bidirectional=True
        )
        self.head = nn.Linear(hidden_dim * 2, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, feature_dim)
        output, _ = self.lstm(x)
        return self.head(output.mean(dim=1))
