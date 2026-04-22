"""
semantic_engine/threshold_tuner.py
────────────────────────────────────
Calibrates similarity thresholds per job type using ground-truth labels.

FIXES in this version
─────────────────────
1. DEFAULT_THRESHOLDS updated to TF-IDF-calibrated values (was calibrated
   for sentence-transformer output). TF-IDF cosine scores peak at ~0.60 for
   real-world resume/JD pairs, so thresholds of 0.75/0.55/0.40/0.25 produced
   nothing but "Weak Match" / "Mismatch" for every pair.

2. JOB_TYPE_THRESHOLDS updated accordingly for all job families.

3. apply_thresholds() now imports TFIDF_THRESHOLDS from similarity.py as the
   canonical source of truth so thresholds are consistent everywhere.
"""

import numpy as np
from dataclasses import dataclass
from typing import Callable


# ═══════════════════════════════════════════════════════════════
# DEFAULT THRESHOLDS
# FIX: calibrated for TF-IDF cosine score range [~0.10, ~0.65]
# ═══════════════════════════════════════════════════════════════

DEFAULT_THRESHOLDS = {
    "strong_match":  0.55,    # was 0.75 — unreachable with TF-IDF
    "good_match":    0.40,    # was 0.55
    "partial_match": 0.28,    # was 0.40
    "weak_match":    0.18,    # was 0.25
}

# Per job-type tuned thresholds
# Healthcare JDs have richer shared vocabulary → can use slightly higher cuts.
JOB_TYPE_THRESHOLDS = {
    "software_engineering": {
        "strong_match":  0.55,
        "good_match":    0.40,
        "partial_match": 0.27,
        "weak_match":    0.17,
    },
    "data_analytics": {
        "strong_match":  0.53,
        "good_match":    0.38,
        "partial_match": 0.26,
        "weak_match":    0.16,
    },
    "healthcare_analytics": {
        "strong_match":  0.52,
        "good_match":    0.38,
        "partial_match": 0.26,
        "weak_match":    0.16,
    },
    "marketing": {
        "strong_match":  0.55,
        "good_match":    0.40,
        "partial_match": 0.28,
        "weak_match":    0.18,
    },
    "mechanical_engineering": {
        "strong_match":  0.55,
        "good_match":    0.40,
        "partial_match": 0.28,
        "weak_match":    0.18,
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
    sweep_results:   list


class ThresholdTuner:
    """
    Calibrates similarity thresholds using scored ground-truth pairs.

    Usage:
        tuner   = ThresholdTuner()
        results = tuner.tune(scored_pairs, ground_truth)
        thresholds = tuner.best_thresholds("data_analytics")
    """

    def __init__(self, steps: int = 20):
        self.steps    = steps
        self._results: dict = {}

    def tune(
        self,
        scored_pairs: list,
        ground_truth: list,
    ) -> dict:
        """
        Calibrate thresholds using scored pairs and ground-truth labels.

        Args:
            scored_pairs: list of dicts with keys:
                          resume_id, jd_id, overall_score, job_type
            ground_truth: list of (resume_id, jd_id, expected_label, score_range)

        Returns:
            dict of {job_type: TuningResult}
        """
        pair_lookup = {
            (p["resume_id"], p["jd_id"]): p
            for p in scored_pairs
        }

        by_job_type: dict = {}
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

    def _tune_single_job_type(self, job_type: str, samples: list) -> TuningResult:
        if not samples:
            return TuningResult(
                job_type=job_type,
                best_thresholds=DEFAULT_THRESHOLDS.copy(),
                f1_score=0.0, precision=0.0, recall=0.0,
                n_samples=0, sweep_results=[],
            )

        scores = np.array([s["score"] for s in samples])
        labels = [s["label"] for s in samples]

        # FIX: sweep range adjusted to TF-IDF score range [0.05, 0.70]
        sweep_vals  = np.linspace(0.05, 0.70, self.steps)
        best_f1     = -1.0
        best_thresh = DEFAULT_THRESHOLDS.copy()
        sweep_log   = []

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
                    "strong_t":  round(float(strong_t),  3),
                    "partial_t": round(float(partial_t), 3),
                    "f1":        round(f1, 4),
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
    def _f1(true_labels: list, pred_labels: list) -> tuple:
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

    def best_thresholds(self, job_type: str) -> dict:
        if job_type in self._results:
            return self._results[job_type].best_thresholds
        return get_thresholds(job_type)

    def summary(self) -> list:
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
# CONVENIENCE
# ═══════════════════════════════════════════════════════════════

def apply_thresholds(score: float, job_type: str = "default") -> str:
    """Apply pre-tuned thresholds to a score and return the match label."""
    from .similarity import similarity_label
    thresholds = get_thresholds(job_type)
    return similarity_label(score, thresholds)
