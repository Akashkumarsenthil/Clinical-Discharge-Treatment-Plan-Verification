"""Classifier-style metrics for Z3 plan verifier (TA requirement).

Treats verifier as binary classifier: label=True means plan is valid,
prediction=True means verifier accepted (no blocking violations).
Reports precision, recall, F1, accuracy, and escape rate as percentages.
"""
from __future__ import annotations

from sklearn.metrics import precision_recall_fscore_support, accuracy_score


def compute_classifier_metrics(
    labels: list[bool], predictions: list[bool]
) -> dict:
    """Compute classifier metrics for verifier predictions vs ground-truth labels.

    Args:
        labels: ground-truth validity (True = valid plan).
        predictions: verifier acceptance (True = verifier accepted).

    Returns:
        dict with n, accuracy, precision, recall, f1, escape_rate,
        acceptance_rate — all as fractions (multiply by 100 for %).
    """
    n = len(labels)
    if n == 0:
        return {"n": 0, "accuracy": None, "precision": None,
                "recall": None, "f1": None, "escape_rate": None,
                "acceptance_rate": None}

    acc = accuracy_score(labels, predictions)
    p, r, f1, _ = precision_recall_fscore_support(
        labels, predictions, average="binary", zero_division=0
    )
    # escape rate: invalid plans the verifier let through (false positives)
    fp = sum(1 for lbl, pred in zip(labels, predictions) if not lbl and pred)
    tn = sum(1 for lbl, pred in zip(labels, predictions) if not lbl and not pred)
    escape = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    return {
        "n": n,
        "accuracy": round(acc, 3),
        "precision": round(float(p), 3),
        "recall": round(float(r), 3),
        "f1": round(float(f1), 3),
        "escape_rate": round(escape, 3),
        "acceptance_rate": round(sum(predictions) / n, 3),
    }


def format_metrics_table(metrics: dict, label: str = "Model") -> str:
    """Format metrics dict as a readable table row for comparison."""
    if metrics.get("n", 0) == 0:
        return f"{label}: no data"
    pct = {k: f"{v * 100:.1f}%" if v is not None else "N/A"
           for k, v in metrics.items() if isinstance(v, float)}
    return (
        f"{label} (n={metrics['n']}): "
        f"accuracy={pct.get('accuracy','N/A')}  "
        f"precision={pct.get('precision','N/A')}  "
        f"recall={pct.get('recall','N/A')}  "
        f"F1={pct.get('f1','N/A')}  "
        f"escape={pct.get('escape_rate','N/A')}"
    )
