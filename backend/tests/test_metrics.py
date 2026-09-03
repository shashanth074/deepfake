"""Evaluation metrics — verified against cases with known answers."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.evaluation.metrics import (  # noqa: E402
    compute_metrics,
    equal_error_rate,
    roc_auc,
    roc_curve,
)


class TestRocAuc:
    def test_perfect_separation_scores_one(self):
        labels = np.r_[np.zeros(50), np.ones(50)]
        scores = np.r_[np.full(50, 0.1), np.full(50, 0.9)]
        assert roc_auc(labels, scores) == pytest.approx(1.0)

    def test_inverted_ranking_scores_zero(self):
        labels = np.r_[np.zeros(50), np.ones(50)]
        scores = np.r_[np.full(50, 0.9), np.full(50, 0.1)]
        assert roc_auc(labels, scores) == pytest.approx(0.0)

    def test_random_scores_near_half(self):
        rng = np.random.default_rng(7)
        labels = np.r_[np.zeros(2000), np.ones(2000)]
        assert roc_auc(labels, rng.random(4000)) == pytest.approx(0.5, abs=0.05)

    def test_single_class_returns_chance(self):
        assert roc_auc(np.ones(10), np.random.rand(10)) == 0.5

    def test_curve_is_monotonic(self):
        rng = np.random.default_rng(3)
        labels = np.r_[np.zeros(100), np.ones(100)]
        scores = np.r_[rng.beta(2, 5, 100), rng.beta(5, 2, 100)]
        fpr, tpr, _ = roc_curve(labels, scores)
        assert np.all(np.diff(fpr) >= 0) and np.all(np.diff(tpr) >= 0)


class TestEqualErrorRate:
    def test_perfect_classifier_has_zero_eer(self):
        labels = np.r_[np.zeros(50), np.ones(50)]
        scores = np.r_[np.full(50, 0.05), np.full(50, 0.95)]
        eer, _ = equal_error_rate(labels, scores)
        assert eer == pytest.approx(0.0, abs=1e-6)

    def test_random_classifier_has_eer_near_half(self):
        rng = np.random.default_rng(11)
        labels = np.r_[np.zeros(1000), np.ones(1000)]
        eer, _ = equal_error_rate(labels, rng.random(2000))
        assert eer == pytest.approx(0.5, abs=0.06)

    def test_known_overlap_gives_expected_eer(self):
        """10% of each class sits on the wrong side => EER ≈ 0.10."""
        labels = np.r_[np.zeros(100), np.ones(100)]
        scores = np.r_[np.full(90, 0.2), np.full(10, 0.8), np.full(10, 0.2), np.full(90, 0.8)]
        eer, _ = equal_error_rate(labels, scores)
        assert eer == pytest.approx(0.10, abs=0.02)


class TestComputeMetrics:
    def test_confusion_matrix_counts(self):
        labels = [0, 0, 0, 0, 1, 1, 1, 1]
        scores = [0.1, 0.2, 0.9, 0.4, 0.8, 0.9, 0.3, 0.7]  # 1 FP, 1 FN
        metrics = compute_metrics(labels, scores)
        assert metrics["confusion_matrix"] == {"tn": 3, "fp": 1, "fn": 1, "tp": 3}
        assert metrics["accuracy"] == pytest.approx(0.75)
        assert metrics["precision"] == pytest.approx(0.75)
        assert metrics["recall"] == pytest.approx(0.75)
        assert metrics["f1"] == pytest.approx(0.75)

    def test_reports_false_positive_rate(self):
        """FPR matters more than accuracy: real uploads are mostly authentic."""
        labels = [0] * 100 + [1] * 4
        scores = [0.9] * 10 + [0.1] * 90 + [0.9] * 4
        metrics = compute_metrics(labels, scores)
        assert metrics["false_positive_rate"] == pytest.approx(0.10)
        assert metrics["accuracy"] > 0.9, "accuracy alone hides the 10% false-positive rate"

    def test_threshold_shifts_predictions(self):
        labels = [0, 1]
        scores = [0.4, 0.6]
        assert compute_metrics(labels, scores, threshold=0.5)["accuracy"] == 1.0
        assert compute_metrics(labels, scores, threshold=0.7)["accuracy"] == 0.5

    def test_empty_input_is_handled(self):
        metrics = compute_metrics([], [])
        assert metrics["accuracy"] == 0.0 and metrics["auc_roc"] == 0.5


class TestGroupSplitting:
    """Dataset splitting — the guard against identity leakage."""

    def test_keeps_a_group_entirely_within_one_split(self):
        from ml.common import split_by_group

        groups = [f"video{i}" for i in range(30) for _ in range(5)]
        assignment = split_by_group(groups, seed=1)
        for group in set(groups):
            assert group in assignment
        # Every sample of a group resolves to the same split by construction.
        assert len({assignment[g] for g in ["video0"]}) == 1

    def test_stratifies_so_no_split_loses_a_class(self):
        """An unstratified split can hand validation a single class, which
        silently makes its AUC meaningless."""
        from ml.common import split_by_group

        groups, labels = [], []
        for i in range(12):
            groups += [f"spk{i}"] * 3
            labels += [i % 2] * 3

        assignment = split_by_group(groups, seed=3, labels=labels)
        for split in ("train", "val", "test"):
            classes = {
                label
                for group, label in zip(groups, labels, strict=True)
                if assignment[group] == split
            }
            assert classes == {0, 1}, f"split '{split}' lost a class: {classes}"

    def test_reports_a_single_class_split(self):
        from ml.common import warn_on_single_class_splits

        rows = [
            {"split": "train", "label": 0},
            {"split": "train", "label": 1},
            {"split": "val", "label": 0},
            {"split": "test", "label": 1},
        ]
        warnings = warn_on_single_class_splits(rows)
        assert any("'val'" in w for w in warnings)
        assert not any("'train'" in w for w in warnings)
