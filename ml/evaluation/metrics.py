"""Evaluation metrics, implemented with NumPy so scikit-learn is optional.

Covers exactly the metrics the project report and viva require: accuracy,
precision, recall, F1, AUC-ROC, EER and the confusion matrix.
"""

from __future__ import annotations

import numpy as np


def compute_metrics(labels, probabilities, threshold: float = 0.5) -> dict:
    """Full metric set for binary detection (positive class = manipulated)."""
    labels = np.asarray(labels).ravel().astype(int)
    probabilities = np.asarray(probabilities).ravel().astype(float)
    if labels.size == 0:
        return _empty_metrics()

    predictions = (probabilities >= threshold).astype(int)
    tp = int(np.sum((predictions == 1) & (labels == 1)))
    tn = int(np.sum((predictions == 0) & (labels == 0)))
    fp = int(np.sum((predictions == 1) & (labels == 0)))
    fn = int(np.sum((predictions == 0) & (labels == 1)))

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "threshold": threshold,
        "accuracy": (tp + tn) / labels.size,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "auc_roc": roc_auc(labels, probabilities),
        "eer": equal_error_rate(labels, probabilities)[0],
        "eer_threshold": equal_error_rate(labels, probabilities)[1],
        # Real uploads are overwhelmingly authentic, so the false-positive rate
        # matters more than headline accuracy: it is the rate at which innocent
        # media gets called manipulated.
        "false_positive_rate": fp / (fp + tn) if (fp + tn) else 0.0,
        "false_negative_rate": fn / (fn + tp) if (fn + tp) else 0.0,
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "support": {"real": int(np.sum(labels == 0)), "fake": int(np.sum(labels == 1))},
    }


def _empty_metrics() -> dict:
    return {
        "threshold": 0.5,
        "accuracy": 0.0,
        "precision": 0.0,
        "recall": 0.0,
        "specificity": 0.0,
        "f1": 0.0,
        "auc_roc": 0.5,
        "eer": 0.5,
        "eer_threshold": 0.5,
        "false_positive_rate": 0.0,
        "false_negative_rate": 0.0,
        "confusion_matrix": {"tn": 0, "fp": 0, "fn": 0, "tp": 0},
        "support": {"real": 0, "fake": 0},
    }


def roc_curve(labels, scores) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(fpr, tpr, thresholds)`` sorted by descending threshold."""
    labels = np.asarray(labels).ravel().astype(int)
    scores = np.asarray(scores).ravel().astype(float)

    order = np.argsort(-scores)
    scores, labels = scores[order], labels[order]

    positives = np.sum(labels == 1)
    negatives = np.sum(labels == 0)
    if positives == 0 or negatives == 0:
        return np.array([0.0, 1.0]), np.array([0.0, 1.0]), np.array([1.0, 0.0])

    tps = np.cumsum(labels == 1)
    fps = np.cumsum(labels == 0)
    # Keep only the last index of each run of equal scores.
    distinct = np.where(np.diff(scores))[0]
    indices = np.r_[distinct, labels.size - 1]

    tpr = np.r_[0.0, tps[indices] / positives]
    fpr = np.r_[0.0, fps[indices] / negatives]
    thresholds = np.r_[scores[0] + 1.0, scores[indices]]
    return fpr, tpr, thresholds


def roc_auc(labels, scores) -> float:
    """Area under the ROC curve (trapezoidal)."""
    fpr, tpr, _ = roc_curve(labels, scores)
    if fpr.size < 2:
        return 0.5
    return float(np.trapezoid(tpr, fpr)) if hasattr(np, "trapezoid") else float(np.trapz(tpr, fpr))


def equal_error_rate(labels, scores) -> tuple[float, float]:
    """EER and its threshold — the standard audio anti-spoofing metric.

    The EER is where the false-acceptance and false-rejection rates cross.
    """
    fpr, tpr, thresholds = roc_curve(labels, scores)
    fnr = 1.0 - tpr
    difference = fpr - fnr
    crossing = np.where(np.diff(np.sign(difference)) != 0)[0]

    if crossing.size == 0:
        index = int(np.argmin(np.abs(difference)))
        return float((fpr[index] + fnr[index]) / 2), float(thresholds[index])

    index = int(crossing[0])
    # Linear interpolation between the two points that bracket the crossing.
    x0, x1 = difference[index], difference[index + 1]
    weight = 0.0 if x1 == x0 else x0 / (x0 - x1)
    eer = fpr[index] + weight * (fpr[index + 1] - fpr[index])
    threshold = thresholds[index] + weight * (thresholds[index + 1] - thresholds[index])
    return float(eer), float(threshold)


def precision_recall_curve(labels, scores) -> tuple[np.ndarray, np.ndarray]:
    """Precision and recall across thresholds."""
    labels = np.asarray(labels).ravel().astype(int)
    scores = np.asarray(scores).ravel().astype(float)
    order = np.argsort(-scores)
    labels = labels[order]

    tps = np.cumsum(labels == 1)
    fps = np.cumsum(labels == 0)
    positives = max(int(np.sum(labels == 1)), 1)

    precision = tps / np.maximum(tps + fps, 1)
    recall = tps / positives
    return precision, recall


def format_report(metrics: dict) -> str:
    """Human-readable metric block for the console and the project report."""
    matrix = metrics["confusion_matrix"]
    return "\n".join(
        [
            f"  Accuracy            {metrics['accuracy'] * 100:6.2f}%",
            f"  Precision           {metrics['precision'] * 100:6.2f}%",
            f"  Recall (sensitivity){metrics['recall'] * 100:6.2f}%",
            f"  Specificity         {metrics['specificity'] * 100:6.2f}%",
            f"  F1-score            {metrics['f1'] * 100:6.2f}%",
            f"  AUC-ROC             {metrics['auc_roc']:6.4f}",
            f"  EER                 {metrics['eer'] * 100:6.2f}%  "
            f"(threshold {metrics['eer_threshold']:.4f})",
            f"  False positive rate {metrics['false_positive_rate'] * 100:6.2f}%",
            f"  False negative rate {metrics['false_negative_rate'] * 100:6.2f}%",
            "",
            "  Confusion matrix        predicted real   predicted fake",
            f"    actual real          {matrix['tn']:12d}   {matrix['fp']:14d}",
            f"    actual fake          {matrix['fn']:12d}   {matrix['tp']:14d}",
        ]
    )
