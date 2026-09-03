"""Matplotlib charts embedded in the forensic report."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from app.config import settings  # noqa: E402

ACCENT = "#1f4e79"
FLAG = "#c62828"


def confidence_timeline(
    points: list[dict],
    output_path: str | Path,
    *,
    x_key: str,
    x_label: str,
    title: str,
) -> Path:
    """Line chart of per-frame / per-segment fake probability over time."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    xs = [float(point[x_key]) for point in points]
    ys = [float(point["fake_probability"]) for point in points]

    figure, axes = plt.subplots(figsize=(7.2, 2.6), dpi=150)
    axes.plot(xs, ys, color=ACCENT, linewidth=1.6, marker="o", markersize=3)
    axes.axhline(
        settings.fake_threshold,
        color=FLAG,
        linestyle="--",
        linewidth=1.0,
        label=f"decision threshold ({settings.fake_threshold:.2f})",
    )
    flagged_x = [x for x, y in zip(xs, ys, strict=True) if y >= settings.fake_threshold]
    flagged_y = [y for y in ys if y >= settings.fake_threshold]
    if flagged_x:
        axes.scatter(flagged_x, flagged_y, color=FLAG, s=18, zorder=3, label="flagged")

    axes.set_ylim(0, 1)
    axes.set_xlabel(x_label)
    axes.set_ylabel("P(manipulated)")
    axes.set_title(title, fontsize=10)
    axes.grid(alpha=0.25, linewidth=0.5)
    axes.legend(fontsize=7, loc="upper right")
    figure.tight_layout()
    figure.savefig(output_path, format="png")
    plt.close(figure)
    return output_path


def confidence_gauge(fake_probability: float, output_path: str | Path) -> Path:
    """Horizontal bar placing the score on the authentic..manipulated scale."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    low = settings.fake_threshold - settings.uncertain_band
    high = settings.fake_threshold + settings.uncertain_band

    figure, axes = plt.subplots(figsize=(7.2, 1.15), dpi=150)
    axes.axvspan(0, low, color="#2e7d32", alpha=0.28)
    axes.axvspan(low, high, color="#f9a825", alpha=0.32)
    axes.axvspan(high, 1, color="#c62828", alpha=0.28)
    axes.axvline(fake_probability, color="#111111", linewidth=2.4)
    axes.text(
        fake_probability,
        0.62,
        f" {fake_probability * 100:.1f}% ",
        ha="center",
        va="bottom",
        fontsize=9,
        fontweight="bold",
        bbox={"facecolor": "white", "edgecolor": "#111111", "boxstyle": "round,pad=0.25"},
    )
    axes.text(low / 2, 0.16, "Likely authentic", ha="center", fontsize=7.5)
    axes.text((low + high) / 2, 0.16, "Inconclusive", ha="center", fontsize=7.5)
    axes.text((high + 1) / 2, 0.16, "Likely manipulated", ha="center", fontsize=7.5)

    axes.set_xlim(0, 1)
    axes.set_ylim(0, 1)
    axes.set_yticks([])
    axes.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    axes.tick_params(labelsize=7)
    figure.tight_layout()
    figure.savefig(output_path, format="png")
    plt.close(figure)
    return output_path
