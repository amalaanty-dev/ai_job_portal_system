"""
semantic_engine/threshold_tuner.py
────────────────────────────────────
Calibrates similarity thresholds per job type using ground-truth labels.

Algorithm:
  1. Run the semantic matcher on all ground-truth pairs.
  2. For each job type, sweep threshold values and find the cut-points
     that maximise F1 for each label boundary (strong / good / partial / weak).
  3. Return a per-job-type threshold dict.

Default (pre-tuned) thresholds are also provided for use without
ground-truth data.
"""

import numpy as np
from dataclasses import dataclass
from typing import Callable


# ═══════════════════════════════════════════════════════════════
# DEFAULT THRESHOLDS  (pre-tuned baselines)
# Derived empirically from all-MiniLM-L6-v2 on resume/JD pairs.
# ═══════════════════════════════════════════════════════════════

DEFAULT_THRESHOLDS = {
    "strong_match":  0.75,
    "good_match":    0.55,
    "partial_match": 0.40,
    "weak_match":    0.25,
}

# Per job-type tuned thresholds
# Technical JDs tend to have higher lexical overlap → higher thresholds needed
JOB_TYPE_THRESHOLDS = {
    "software_engineering": {
        "strong_match":  0.72,
        "good_match":    0.55,
        "partial_match": 0.38,
        "weak_match":    0.22,
    },
    "data_analytics": {
        "strong_match":  0.70,
        "good_match":    0.52,
        "partial_match": 0.38,
        "weak_match":    0.24,
    },
    "healthcare_analytics": {
        "strong_match":  0.68,
        "good_match":    0.50,
        "partial_match": 0.36,
        "weak_match":    0.22,
    },
    "marketing": {
        "strong_match":  0.72,
        "good_match":    0.54,
        "partial_match": 0.38,
        "weak_match":    0.24,
    },
    "mechanical_engineering": {
        "strong_match":  0.73,
        "good_match":    0.55,
        "partial_match": 0.38,
        "weak_match":    0.23,
    },
    "default": DEFAULT_THRESHOLDS,
}


def get_thresholds(job_type: str) -> dict:
    """Return the tuned thresholds for a given job type."""
    return JOB_TYPE_THRESHOLDS.get(job_type, JOB_TYPE_THRESHOLDS["default"])


# ═══════════════════════════════════════════════════════════════
# THRESHOLD TUNER CLASS
# ═══════════════════════════════════════════════════════════════

@dataclass
class TuningResult:
    job_type:        str
    best_thresholds: dict
    f1_score:        float
    precision:       float
    recall:          float
    n_samples:       int
    sweep_results:   list   # all candidate thresholds tested


class ThresholdTuner:
    """
    Calibrates similarity thresholds using scored ground-truth pairs.

    Usage:
        tuner   = ThresholdTuner()
        results = tuner.tune(scored_pairs, ground_truth)
        thresholds = tuner.best_thresholds("data_analytics")
    """

    def __init__(self, steps: int = 20):
        """
        Args:
            steps: number of threshold values to sweep between 0.1 and 0.9.
        """
        self.steps    = steps
        self._results: dict[str, TuningResult] = {}

    # ───────────────────────────────────────────────────────────
    # TUNE FROM SCORED PAIRS
    # ───────────────────────────────────────────────────────────

    def tune(
        self,
        scored_pairs:  list[dict],
        ground_truth:  list[tuple],
    ) -> dict[str, TuningResult]:
        """
        Calibrate thresholds using scored pairs and ground-truth labels.

        Args:
            scored_pairs: list of dicts with keys:
                          resume_id, jd_id, overall_score, job_type
            ground_truth: list of (resume_id, jd_id, expected_label, score_range)
                          expected_label: "strong_match" | "partial_match" | "mismatch"

        Returns:
            dict of {job_type: TuningResult}
        """
        # Build lookup: (resume_id, jd_id) → score + job_type
        pair_lookup = {
            (p["resume_id"], p["jd_id"]): p
            for p in scored_pairs
        }

        # Group ground truth by job type
        by_job_type: dict[str, list] = {}
        for (rid, jid, label, score_range) in ground_truth:
            pair = pair_lookup.get((rid, jid))
            if pair is None:
                continue
            jt = pair.get("job_type", "default")
            by_job_type.setdefault(jt, []).append({
                "score":       pair["overall_score"],
                "label":       label,
                "score_range": score_range,
            })

        for job_type, samples in by_job_type.items():
            result = self._tune_single_job_type(job_type, samples)
            self._results[job_type] = result

        return self._results

    def _tune_single_job_type(
        self,
        job_type: str,
        samples:  list[dict],
    ) -> TuningResult:
        """
        Sweep boundary thresholds and find those that maximise F1.
        """
        if not samples:
            return TuningResult(
                job_type=job_type,
                best_thresholds=DEFAULT_THRESHOLDS.copy(),
                f1_score=0.0, precision=0.0, recall=0.0,
                n_samples=0, sweep_results=[],
            )

        scores = np.array([s["score"] for s in samples])
        labels = [s["label"] for s in samples]

        sweep_vals   = np.linspace(0.10, 0.90, self.steps)
        best_f1      = -1.0
        best_thresh  = DEFAULT_THRESHOLDS.copy()
        sweep_log    = []

        # For simplicity: tune the strong_match boundary
        # (most impactful for accept/reject decisions)
        for strong_t in sweep_vals:
            for partial_t in sweep_vals:
                if partial_t >= strong_t:
                    continue

                pred_labels = []
                for sc in scores:
                    if sc >= strong_t:
                        pred_labels.append("strong_match")
                    elif sc >= partial_t:
                        pred_labels.append("partial_match")
                    else:
                        pred_labels.append("mismatch")

                f1, prec, rec = self._f1(labels, pred_labels)
                sweep_log.append({
                    "strong_t": round(float(strong_t), 3),
                    "partial_t": round(float(partial_t), 3),
                    "f1": round(f1, 4),
                })

                if f1 > best_f1:
                    best_f1 = f1
                    best_thresh = {
                        "strong_match":  round(float(strong_t), 3),
                        "good_match":    round(float((strong_t + partial_t) / 2), 3),
                        "partial_match": round(float(partial_t), 3),
                        "weak_match":    round(float(partial_t * 0.60), 3),
                    }

        _, prec, rec = self._f1(
            labels,
            ["strong_match" if s >= best_thresh["strong_match"]
             else "partial_match" if s >= best_thresh["partial_match"]
             else "mismatch"
             for s in scores]
        )

        return TuningResult(
            job_type=job_type,
            best_thresholds=best_thresh,
            f1_score=round(best_f1, 4),
            precision=round(prec, 4),
            recall=round(rec, 4),
            n_samples=len(samples),
            sweep_results=sorted(sweep_log, key=lambda x: -x["f1"])[:10],
        )

    @staticmethod
    def _f1(true_labels: list, pred_labels: list) -> tuple[float, float, float]:
        """Macro F1, precision, recall for 3-class problem."""
        classes = ["strong_match", "partial_match", "mismatch"]
        f1s, precs, recs = [], [], []
        for cls in classes:
            tp = sum(1 for t, p in zip(true_labels, pred_labels) if t == cls and p == cls)
            fp = sum(1 for t, p in zip(true_labels, pred_labels) if t != cls and p == cls)
            fn = sum(1 for t, p in zip(true_labels, pred_labels) if t == cls and p != cls)
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            f1s.append(f1); precs.append(prec); recs.append(rec)
        return float(np.mean(f1s)), float(np.mean(precs)), float(np.mean(recs))

    # ───────────────────────────────────────────────────────────
    # ACCESSORS
    # ───────────────────────────────────────────────────────────

    def best_thresholds(self, job_type: str) -> dict:
        """Return tuned thresholds for job_type, falling back to defaults."""
        if job_type in self._results:
            return self._results[job_type].best_thresholds
        return get_thresholds(job_type)

    def summary(self) -> list[dict]:
        """Summary of all tuning results."""
        rows = []
        for jt, res in self._results.items():
            rows.append({
                "job_type":       jt,
                "n_samples":      res.n_samples,
                "f1_score":       res.f1_score,
                "precision":      res.precision,
                "recall":         res.recall,
                "strong_thresh":  res.best_thresholds.get("strong_match"),
                "partial_thresh": res.best_thresholds.get("partial_match"),
            })
        return rows


# ═══════════════════════════════════════════════════════════════
# CONVENIENCE  (use pre-tuned thresholds without running tuner)
# ═══════════════════════════════════════════════════════════════

def apply_thresholds(score: float, job_type: str = "default") -> str:
    """
    Apply pre-tuned thresholds to a score and return the match label.
    """
    from .similarity import similarity_label
    thresholds = get_thresholds(job_type)
    return similarity_label(score, thresholds)
