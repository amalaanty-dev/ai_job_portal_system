"""
utils/metrics_calculator.py
===========================
Reusable accuracy metrics for ATS testing.

Computes:
- Confusion matrix (TP, FP, FN, TN)
- Precision, Recall, Accuracy, F1 Score
- Category-wise breakdowns

Day: 17
"""

from typing import List, Dict, Tuple, Any
from dataclasses import dataclass, asdict


@dataclass
class ConfusionMatrix:
    tp: int = 0  # AI Shortlist + HR Shortlist
    fp: int = 0  # AI Shortlist + HR Reject
    fn: int = 0  # AI Reject + HR Shortlist
    tn: int = 0  # AI Reject + HR Reject

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.fn + self.tn

    def as_dict(self) -> Dict[str, int]:
        return asdict(self)


@dataclass
class Metrics:
    precision: float
    recall: float
    accuracy: float
    f1_score: float
    confusion_matrix: ConfusionMatrix

    def as_dict(self) -> Dict[str, Any]:
        return {
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "accuracy": round(self.accuracy, 4),
            "f1_score": round(self.f1_score, 4),
            "precision_pct": f"{self.precision * 100:.1f}%",
            "recall_pct": f"{self.recall * 100:.1f}%",
            "accuracy_pct": f"{self.accuracy * 100:.1f}%",
            "f1_pct": f"{self.f1_score * 100:.1f}%",
            "confusion_matrix": self.confusion_matrix.as_dict(),
        }


def _normalize_decision(decision: str) -> str:
    """Normalize decision strings: 'Manual Review' -> 'Shortlisted' for binary classification."""
    if not decision:
        return "Rejected"
    decision = decision.strip().lower()
    if decision in {"shortlisted", "shortlist", "selected", "pass"}:
        return "Shortlisted"
    if decision in {"manual review", "review", "hold", "partial"}:
        return "Shortlisted"  # treated as positive class (recruiter follows up)
    return "Rejected"


def compute_confusion_matrix(
    ai_decisions: List[str],
    hr_decisions: List[str],
) -> ConfusionMatrix:
    """
    Build confusion matrix in single pass.

    Args:
        ai_decisions: list of AI-predicted decisions
        hr_decisions: list of HR ground-truth decisions (must be same length)

    Returns:
        ConfusionMatrix with TP/FP/FN/TN counts
    """
    if len(ai_decisions) != len(hr_decisions):
        raise ValueError(
            f"Length mismatch: ai_decisions={len(ai_decisions)} vs hr_decisions={len(hr_decisions)}"
        )

    cm = ConfusionMatrix()
    for ai, hr in zip(ai_decisions, hr_decisions):
        ai_n = _normalize_decision(ai)
        hr_n = _normalize_decision(hr)
        if ai_n == "Shortlisted" and hr_n == "Shortlisted":
            cm.tp += 1
        elif ai_n == "Shortlisted" and hr_n == "Rejected":
            cm.fp += 1
        elif ai_n == "Rejected" and hr_n == "Shortlisted":
            cm.fn += 1
        else:
            cm.tn += 1
    return cm


def compute_metrics(cm: ConfusionMatrix) -> Metrics:
    """Compute precision/recall/accuracy/F1 from a confusion matrix."""
    precision = cm.tp / (cm.tp + cm.fp) if (cm.tp + cm.fp) > 0 else 0.0
    recall = cm.tp / (cm.tp + cm.fn) if (cm.tp + cm.fn) > 0 else 0.0
    accuracy = (cm.tp + cm.tn) / cm.total if cm.total > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return Metrics(
        precision=precision,
        recall=recall,
        accuracy=accuracy,
        f1_score=f1,
        confusion_matrix=cm,
    )


def evaluate(
    ai_decisions: List[str],
    hr_decisions: List[str],
) -> Metrics:
    """One-shot helper: confusion matrix + metrics."""
    cm = compute_confusion_matrix(ai_decisions, hr_decisions)
    return compute_metrics(cm)


def evaluate_by_category(
    records: List[Dict[str, Any]],
    category_field: str = "category",
) -> Dict[str, Metrics]:
    """
    Compute per-category metrics.

    Args:
        records: list of dicts each with 'ai_decision', 'hr_decision', and category_field
        category_field: e.g. 'category' (tech/non_tech/fresher/senior)

    Returns:
        Dict {category_name: Metrics}
    """
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        cat = r.get(category_field, "uncategorized")
        grouped.setdefault(cat, []).append(r)

    results = {}
    for cat, items in grouped.items():
        ai = [i["ai_decision"] for i in items]
        hr = [i["hr_decision"] for i in items]
        results[cat] = evaluate(ai, hr)
    return results


# Backward-compat helper matching the PRD-mentioned signature
def evaluate_accuracy(ai_results: List[str], hr_results: List[str]) -> Tuple[float, float, float]:
    """Returns (precision, recall, accuracy) — matches PRD/outline reference signature."""
    m = evaluate(ai_results, hr_results)
    return m.precision, m.recall, m.accuracy


if __name__ == "__main__":
    # Smoke test using PRD sample numbers
    cm = ConfusionMatrix(tp=28, fp=3, fn=4, tn=5)
    m = compute_metrics(cm)
    print(m.as_dict())
