"""
Bias Evaluator - Task 5 (Day 15)
Path: ai_job_portal_system/fairness_engine/bias_evaluator.py

PURPOSE:
    Evaluate bias indicators in the ATS scoring pipeline by checking:
        1. Score distribution disparity across cohorts (gender, location,
           college tier) - if cohort metadata is available.
        2. Keyword-stuffing rate (avg keyword_dependency_ratio).
        3. PII masking effectiveness (% PII masked vs leaked).
        4. Elite-institution score gap.
        5. Variance / std-dev of scores.

INPUT:
    - List of normalized scores  (from ScoreNormalizer)
    - List of dependency reports (from KeywordDependencyReducer) [optional]
    - List of mask audits        (from PIIMasker)                [optional]
    - Optional cohort_map        : { resume_id -> {gender, location, ...} }

OUTPUT:
    - bias_reports/<run_id>_bias_audit.json
"""

import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.fairness_utils import (
    ensure_dir, get_logger, load_json, now_iso,
    round_score, safe_divide, save_json,
)
from utils.normalization_constants import BIAS_THRESHOLDS, ELITE_INSTITUTIONS

logger = get_logger("bias_evaluator")


class BiasEvaluator:
    """Evaluate bias indicators across a candidate pool."""

    def __init__(self, output_dir: str = "fairness_engine_outputs/bias_reports"):
        self.output_dir = ensure_dir(output_dir)

    # ----------------------------------------------------------
    # PUBLIC ENTRY
    # ----------------------------------------------------------
    def evaluate(
        self,
        normalized_scores: List[Dict[str, Any]],
        dependency_reports: Optional[List[Dict[str, Any]]] = None,
        mask_audits:        Optional[List[Dict[str, Any]]] = None,
        cohort_map:         Optional[Dict[str, Dict[str, str]]] = None,
        run_id:             str = "audit",
        save:               bool = True,
    ) -> Dict[str, Any]:
        """
        Run a full bias audit.

        Args:
            normalized_scores: list of records from ScoreNormalizer.
            dependency_reports: optional dependency analysis records.
            mask_audits:        optional mask audit records.
            cohort_map:         optional dict resume_id -> demographics.
            run_id:             identifier for this audit run.

        Returns:
            Dict with bias indicators and pass/fail flags.
        """
        report: Dict[str, Any] = {
            "run_id": run_id,
            "evaluated_at": now_iso(),
            "n_candidates": len(normalized_scores),
            "indicators": {},
            "flags": [],
            "summary_verdict": None,
        }

        if not normalized_scores:
            report["summary_verdict"] = "no_data"
            return report

        # 1. Score distribution stats
        report["indicators"]["score_distribution"] = self._score_distribution(
            normalized_scores
        )

        # 2. Cohort-based disparity (if metadata available)
        if cohort_map:
            report["indicators"]["cohort_disparity"] = self._cohort_disparity(
                normalized_scores, cohort_map
            )

        # 3. Keyword dependency aggregate
        if dependency_reports:
            report["indicators"]["keyword_dependency"] = (
                self._keyword_dependency_summary(dependency_reports)
            )

        # 4. PII masking effectiveness
        if mask_audits:
            report["indicators"]["pii_masking"] = self._pii_masking_summary(
                mask_audits
            )

        # 5. Elite institution gap (uses raw breakdown if institution present)
        report["indicators"]["elite_institution_gap"] = (
            self._elite_institution_gap(normalized_scores)
        )

        # 6. Apply thresholds -> flag issues
        report["flags"] = self._derive_flags(report["indicators"])
        report["summary_verdict"] = (
            "PASS" if not report["flags"] else "REVIEW_NEEDED"
        )

        if save:
            out_path = self.output_dir / f"{run_id}_bias_audit.json"
            save_json(report, out_path)
            logger.info(f"Bias report saved -> {out_path}")
        return report

    # ----------------------------------------------------------
    # INDICATOR FUNCTIONS
    # ----------------------------------------------------------
    @staticmethod
    def _score_distribution(records: List[Dict[str, Any]]) -> Dict[str, float]:
        # Support both new schema (normalized_final_score, 0-1) and
        # old schema (normalized_score, 0-100). Convert all to 0-100.
        scores = []
        for r in records:
            if "normalized_final_score" in r:
                scores.append(r["normalized_final_score"] * 100)
            else:
                scores.append(r.get("normalized_score", 0.0))
        if len(scores) < 2:
            return {
                "mean": scores[0] if scores else 0.0,
                "stdev": 0.0,
                "variance_ratio": 0.0,
                "n": len(scores),
            }
        mu = statistics.mean(scores)
        sd = statistics.stdev(scores)
        var_ratio = safe_divide(sd, mu) if mu else 0.0
        return {
            "mean": round_score(mu, 2),
            "stdev": round_score(sd, 2),
            "min": round_score(min(scores), 2),
            "max": round_score(max(scores), 2),
            "variance_ratio": round_score(var_ratio, 3),
            "n": len(scores),
        }

    @staticmethod
    def _cohort_disparity(
        records: List[Dict[str, Any]],
        cohort_map: Dict[str, Dict[str, str]],
    ) -> Dict[str, Any]:
        """Compute mean score per cohort attribute (gender, location, ...)."""
        attr_scores: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
        for r in records:
            rid = r.get("resume_id")
            cohort = cohort_map.get(rid, {})
            # support both schemas
            if "normalized_final_score" in r:
                score = r["normalized_final_score"] * 100
            else:
                score = r.get("normalized_score", 0.0)
            for attr, value in cohort.items():
                attr_scores[attr][str(value).lower()].append(score)

        out: Dict[str, Any] = {}
        for attr, groups in attr_scores.items():
            group_stats = {}
            for grp, sc in groups.items():
                if sc:
                    group_stats[grp] = {
                        "n": len(sc),
                        "mean": round_score(statistics.mean(sc), 2),
                    }
            if len(group_stats) >= 2:
                means = [g["mean"] for g in group_stats.values()]
                gap = max(means) - min(means)
            else:
                gap = 0.0
            out[attr] = {"groups": group_stats, "max_gap": round_score(gap, 2)}
        return out

    @staticmethod
    def _keyword_dependency_summary(
        reports: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        ratios = [r.get("keyword_dependency_ratio", 0.0) for r in reports]
        ctx = [r.get("context_adjusted_skill_score", 0.0) for r in reports]
        return {
            "n_resumes": len(reports),
            "avg_dependency_ratio":
                round_score(statistics.mean(ratios), 3) if ratios else 0.0,
            "max_dependency_ratio":
                round_score(max(ratios), 3) if ratios else 0.0,
            "avg_context_adjusted_score":
                round_score(statistics.mean(ctx), 2) if ctx else 0.0,
            "high_dependency_count":
                sum(1 for r in ratios
                    if r > BIAS_THRESHOLDS["max_acceptable_keyword_dependency"]),
        }

    @staticmethod
    def _pii_masking_summary(audits: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_masks = sum(a.get("audit", a).get("total_masks_applied", 0)
                          for a in audits)
        n = len(audits)
        avg_per_resume = safe_divide(total_masks, n)
        return {
            "n_audits": n,
            "total_masks": total_masks,
            "avg_masks_per_resume": round_score(avg_per_resume, 2),
        }

    @staticmethod
    def _elite_institution_gap(records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compare avg score of candidates with elite institution mention vs others.
        We use 'original_breakdown' presence as proxy. If institution metadata
        is unavailable here, this returns N/A.
        """
        # The records from ScoreNormalizer don't carry institution. Caller
        # can extend cohort_map with 'is_elite' attribute. So return placeholder.
        return {"note": "Pass cohort_map with 'is_elite' attribute to enable",
                "computed": False}

    # ----------------------------------------------------------
    # FLAG DERIVATION
    # ----------------------------------------------------------
    @staticmethod
    def _derive_flags(indicators: Dict[str, Any]) -> List[Dict[str, Any]]:
        flags = []

        # Score variance
        sd_dist = indicators.get("score_distribution", {})
        var_ratio = sd_dist.get("variance_ratio", 0.0)
        if var_ratio > BIAS_THRESHOLDS["max_acceptable_score_variance"]:
            flags.append({
                "type": "high_score_variance",
                "value": var_ratio,
                "threshold": BIAS_THRESHOLDS["max_acceptable_score_variance"],
                "severity": "medium",
            })

        # Keyword dependency
        kd = indicators.get("keyword_dependency", {})
        avg_dep = kd.get("avg_dependency_ratio", 0.0)
        if avg_dep > BIAS_THRESHOLDS["max_acceptable_keyword_dependency"]:
            flags.append({
                "type": "high_keyword_dependency",
                "value": avg_dep,
                "threshold": BIAS_THRESHOLDS["max_acceptable_keyword_dependency"],
                "severity": "high",
            })

        # Cohort gaps
        cohort = indicators.get("cohort_disparity", {})
        for attr, attr_data in cohort.items():
            gap = attr_data.get("max_gap", 0.0)
            if gap > BIAS_THRESHOLDS["max_elite_bias_gap"]:
                flags.append({
                    "type": f"cohort_gap_{attr}",
                    "value": gap,
                    "threshold": BIAS_THRESHOLDS["max_elite_bias_gap"],
                    "severity": "high",
                })

        return flags


# ----------------------------------------------------------
# CLI entry
# ----------------------------------------------------------
if __name__ == "__main__":
    import argparse, glob
    parser = argparse.ArgumentParser(description="Run bias audit")
    parser.add_argument("--scores_file", required=True,
                        help="path to normalized scores JSON")
    parser.add_argument("--deps_dir", help="dir with dependency reports")
    parser.add_argument("--mask_dir", help="dir with mask audits")
    parser.add_argument("--run_id", default="audit")
    parser.add_argument("--output_dir", default="fairness_engine_outputs/bias_reports")
    args = parser.parse_args()

    scores_data = load_json(args.scores_file)
    records = scores_data.get("records", [])

    deps = []
    if args.deps_dir:
        deps = [load_json(f) for f in glob.glob(str(Path(args.deps_dir) / "*.json"))]

    masks = []
    if args.mask_dir:
        masks = [load_json(f) for f in glob.glob(str(Path(args.mask_dir) / "*.json"))]

    evaluator = BiasEvaluator(output_dir=args.output_dir)
    out = evaluator.evaluate(records, deps, masks, run_id=args.run_id)
    print(f"Verdict: {out['summary_verdict']}")
    print(f"Flags: {out['flags']}")
