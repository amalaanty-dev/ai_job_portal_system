"""
Score Normalizer - Task 3 (Day 15)
Path: ai_job_portal_system/fairness_engine/score_normalizer.py

PURPOSE:
    Normalize ATS scores across a candidate pool so comparisons are fair and
    independent of absolute score scale.
    Produces per-JD normalized score files with rich audit metadata.

OUTPUT FORMAT (per JD, list of candidate records):
    [
      {
        "resume_id":              "R001",
        "candidate_name_masked":  "CAND_001",
        "scores": {
          "skill_score":      0.78,
          "experience_score": 0.64,
          "education_score":  0.82,
          "semantic_score":   0.74
        },
        "weighted_scores": { ... },
        "ats_score":              84,
        "normalized_final_score": 0.82,
        "confidence_score": { value, method },
        "ranking": { rank, percentile, total_candidates, method },
        "status":  "shortlisted" | "on_hold" | "rejected",
        "fairness_adjustments": { keyword_bias_reduction, ... },
        "flags": [...],
        "audit_trail": { raw_final_score, normalized_method,
                         weights_used, calculation_check }
      },
      ...
    ]

METHODS:
    - min_max    : (x - min) / (max - min)            -> 0..1
    - z_score    : (x - mean) / std  -> CDF           -> 0..1
    - percentile : rank / N                            -> 0..1
    - robust     : (x - median) / IQR -> sigmoid       -> 0..1

INPUTS:
    - List of ATS score JSONs (from ats_results/) each with:
        identifiers.{resume_id, jd_id, job_role}
        final_score, scoring_breakdown, weights, weighted_contributions

OUTPUT FILES (per JD):
    fairness_engine_outputs/normalized_scores/<jd_id>_normalized_scores.json
"""

import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.fairness_utils import (
    ensure_dir, get_logger, load_json, now_iso,
    round_score, save_json,
)
from utils.normalization_constants import (
    DEFAULT_NORMALIZATION_METHOD, NORMALIZATION_METHODS,
)

logger = get_logger("score_normalizer")


# Status thresholds based on normalized_final_score (0-1 scale)
STATUS_THRESHOLDS = {
    "shortlisted": 0.70,   # >= 0.70  -> shortlisted
    "on_hold":     0.50,   # 0.50 - 0.69 -> on_hold
    # below 0.50 -> rejected
}


class ScoreNormalizer:
    """Normalize a batch of candidate scores with configurable methods."""

    def __init__(
        self,
        method: str = DEFAULT_NORMALIZATION_METHOD,
        output_dir: str = "fairness_engine_outputs/normalized_scores",
    ):
        if method not in NORMALIZATION_METHODS:
            raise ValueError(
                f"Unknown method '{method}'. "
                f"Choose from {NORMALIZATION_METHODS}"
            )
        self.method = method
        self.output_dir = ensure_dir(output_dir)

    # ----------------------------------------------------------
    # PUBLIC ENTRY 1 - Normalize all records grouped by JD
    # ----------------------------------------------------------
    def normalize_per_jd(
        self,
        score_records: List[Dict[str, Any]],
        dependency_reports: Optional[List[Dict[str, Any]]] = None,
        save: bool = True,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group ATS records by jd_id and normalize each pool independently.
        Produces ONE output file per JD.
        """
        if not score_records:
            return {}

        # dep lookup keyed by resume_id
        dep_lookup = {}
        if dependency_reports:
            for d in dependency_reports:
                rid = d.get("resume_id")
                if rid:
                    dep_lookup[rid] = d

        # group by jd_id (canonicalized: spaces -> underscores, lowercased)
        jd_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for rec in score_records:
            raw_jd_id = (rec.get("identifiers", {}).get("jd_id")
                         or rec.get("jd_id") or "unknown_jd")
            jd_id = self._canonicalize_jd_id(raw_jd_id)
            jd_groups[jd_id].append(rec)

        results: Dict[str, List[Dict[str, Any]]] = {}
        for jd_id, group_recs in jd_groups.items():
            normalized = self.normalize_batch(
                group_recs,
                dep_lookup=dep_lookup,
                jd_id=jd_id,
                save=save,
            )
            results[jd_id] = normalized
            logger.info(
                f"JD '{jd_id}': normalized {len(normalized)} candidates "
                f"({self.method})"
            )
        return results

    # ----------------------------------------------------------
    # PUBLIC ENTRY 2 - Normalize a single batch (one JD)
    # ----------------------------------------------------------
    def normalize_batch(
        self,
        score_records: List[Dict[str, Any]],
        dep_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
        jd_id: str = "batch",
        save: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Normalize a single batch of candidate scores (one JD).

        Returns:
            List of records matching target output schema.
        """
        if not score_records:
            return []

        dep_lookup = dep_lookup or {}

        # extract raw final scores
        raw_scores = [self._safe_float(r.get("final_score"))
                      for r in score_records]

        # compute normalized scores (0-100 internally)
        if self.method == "min_max":
            norm_100 = self._min_max(raw_scores)
        elif self.method == "z_score":
            norm_100 = self._z_score(raw_scores)
        elif self.method == "percentile":
            norm_100 = self._percentile(raw_scores)
        elif self.method == "robust":
            norm_100 = self._robust(raw_scores)
        else:
            norm_100 = list(raw_scores)

        # rank map (1 = highest)
        sorted_pairs = sorted(
            enumerate(raw_scores), key=lambda p: p[1], reverse=True
        )
        rank_map = {idx: i + 1 for i, (idx, _) in enumerate(sorted_pairs)}
        total = len(raw_scores)

        # build target-schema records
        out_records: List[Dict[str, Any]] = []
        for i, (rec, raw_score, norm_score) in enumerate(
            zip(score_records, raw_scores, norm_100)
        ):
            normalized_final = round_score(norm_score / 100.0, 2)
            rank = rank_map[i]
            percentile = self._compute_percentile(raw_score, raw_scores)

            record = self._build_record(
                rec=rec,
                raw_score=raw_score,
                normalized_final=normalized_final,
                rank=rank,
                percentile=percentile,
                total=total,
                candidate_index=i,
                dep_lookup=dep_lookup,
            )
            out_records.append(record)

        # sort by rank ascending (best first)
        out_records.sort(key=lambda r: r["ranking"]["rank"])

        if save:
            safe_jd = self._safe_filename(jd_id)
            out_path = self.output_dir / f"{safe_jd}_normalized_scores.json"
            save_json(out_records, out_path)
            logger.info(f"Saved per-JD scores -> {out_path}")
        return out_records

    # ----------------------------------------------------------
    # RECORD BUILDER
    # ----------------------------------------------------------
    def _build_record(
        self,
        rec: Dict[str, Any],
        raw_score: float,
        normalized_final: float,
        rank: int,
        percentile: float,
        total: int,
        candidate_index: int,
        dep_lookup: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build one record matching the target schema."""
        idents = rec.get("identifiers", {})
        resume_id = idents.get("resume_id", f"R{candidate_index + 1:03d}")
        breakdown = rec.get("scoring_breakdown", {}) or {}
        weighted_contrib = rec.get("weighted_contributions", {}) or {}
        weights_raw = rec.get("weights", {}) or {}

        # 0-100 -> 0-1 component scores
        scores_01 = {
            "skill_score":      round_score(
                breakdown.get("skill_match", 0) / 100.0, 2),
            "experience_score": round_score(
                breakdown.get("experience_relevance", 0) / 100.0, 2),
            "education_score":  round_score(
                breakdown.get("education_alignment", 0) / 100.0, 2),
            "semantic_score":   round_score(
                breakdown.get("semantic_similarity", 0) / 100.0, 2),
        }

        # weighted contributions (assume input is 0-100) -> 0-1
        weighted_01 = {
            "skill_contribution":      round_score(
                weighted_contrib.get("skills", 0) / 100.0, 3),
            "experience_contribution": round_score(
                weighted_contrib.get("experience", 0) / 100.0, 3),
            "education_contribution":  round_score(
                weighted_contrib.get("education", 0) / 100.0, 3),
            "semantic_contribution":   round_score(
                weighted_contrib.get("semantic", 0) / 100.0, 3),
        }

        # weights from percent (e.g. 35) to fraction (0.35)
        weights_01 = {
            "skill":      round_score(weights_raw.get("skills", 0) / 100.0, 2),
            "experience": round_score(weights_raw.get("experience", 0) / 100.0, 2),
            "education":  round_score(weights_raw.get("education", 0) / 100.0, 2),
            "semantic":   round_score(weights_raw.get("semantic", 0) / 100.0, 2),
        }
        weighted_sum = round_score(sum(weighted_01.values()), 3)

        confidence = self._compute_confidence(scores_01)
        status = self._derive_status(normalized_final)
        flags = self._derive_flags(scores_01, normalized_final, percentile)
        dep_report = dep_lookup.get(resume_id, {})
        fairness_adj = self._compute_fairness_adjustments(scores_01, dep_report)

        return {
            "resume_id": resume_id,
            "candidate_name_masked": f"CAND_{candidate_index + 1:03d}",
            "scores": scores_01,
            "weighted_scores": weighted_01,
            "ats_score": int(round(raw_score)),
            "normalized_final_score": normalized_final,
            "confidence_score": confidence,
            "ranking": {
                "rank":             rank,
                "percentile":       int(round(percentile)),
                "total_candidates": total,
                "method":           "score_descending",
            },
            "status": status,
            "fairness_adjustments": fairness_adj,
            "flags": flags,
            "audit_trail": {
                "raw_final_score":   round_score(raw_score, 2),
                "normalized_method": self.method,
                "weights_used":      weights_01,
                "calculation_check": {
                    "weighted_sum":     weighted_sum,
                    "rounding_applied": True,
                },
                "normalized_at":     now_iso(),
            },
        }

    # ----------------------------------------------------------
    # CONFIDENCE / STATUS / FLAGS / FAIRNESS
    # ----------------------------------------------------------
    @staticmethod
    def _compute_confidence(scores: Dict[str, float]) -> Dict[str, Any]:
        """
        Confidence = average of (completeness, semantic strength, consistency).
        """
        components = list(scores.values())
        if not components:
            return {"value": 0.0, "method": "no_data"}

        completeness = sum(1 for c in components if c > 0) / len(components)
        semantic_strength = scores.get("semantic_score", 0.0)
        if len(components) > 1:
            consistency = max(0.0, 1.0 - statistics.stdev(components))
        else:
            consistency = 1.0

        value = (completeness + semantic_strength + consistency) / 3.0
        return {
            "value":  round_score(value, 2),
            "method": "completeness + semantic_strength + consistency",
        }

    @staticmethod
    def _derive_status(normalized_score: float) -> str:
        """Map normalized score to status bucket."""
        if normalized_score >= STATUS_THRESHOLDS["shortlisted"]:
            return "shortlisted"
        if normalized_score >= STATUS_THRESHOLDS["on_hold"]:
            return "on_hold"
        return "rejected"

    @staticmethod
    def _derive_flags(
        scores: Dict[str, float],
        normalized_final: float,
        percentile: float,
    ) -> List[str]:
        """Derive descriptive flags."""
        flags = []
        if scores.get("semantic_score", 0) >= 0.70:
            flags.append("high_semantic_match")
        elif scores.get("semantic_score", 0) < 0.30:
            flags.append("low_semantic_match")

        comps = list(scores.values())
        if len(comps) > 1 and statistics.stdev(comps) < 0.15:
            flags.append("balanced_profile")

        if scores.get("skill_score", 0) >= 0.85:
            flags.append("strong_skill_match")
        if scores.get("experience_score", 0) < 0.40:
            flags.append("experience_gap")
        if scores.get("education_score", 0) < 0.40:
            flags.append("education_mismatch")

        if percentile >= 95:
            flags.append("top_percentile")
        if normalized_final >= 0.85:
            flags.append("high_potential")
        return flags

    @staticmethod
    def _compute_fairness_adjustments(
        scores: Dict[str, float],
        dep_report: Dict[str, Any],
    ) -> Dict[str, float]:
        """Derive fairness-adjustment deltas."""
        adj: Dict[str, float] = {
            "keyword_bias_reduction":      0.0,
            "experience_bias_correction":  0.0,
            "education_standardization":   0.0,
        }
        # keyword bias reduction
        dep_ratio = dep_report.get("keyword_dependency_ratio", 0.0)
        if dep_ratio > 0.6:
            adj["keyword_bias_reduction"] = round_score(-dep_ratio * 0.05, 3)
        elif dep_ratio < 0.2 and dep_report:
            adj["keyword_bias_reduction"] = -0.03

        # experience bias correction
        if scores.get("experience_score", 0) < 0.50 and \
                scores.get("skill_score", 0) >= 0.70:
            adj["experience_bias_correction"] = 0.02

        # education standardization
        if scores.get("education_score", 0) < 0.50 and \
                scores.get("semantic_score", 0) >= 0.50:
            adj["education_standardization"] = 0.01
        return adj

    # ----------------------------------------------------------
    # NORMALIZATION ALGORITHMS (return 0-100)
    # ----------------------------------------------------------
    @staticmethod
    def _min_max(scores: List[float]) -> List[float]:
        if not scores:
            return []
        lo, hi = min(scores), max(scores)
        if hi == lo:
            return [50.0] * len(scores)
        return [(s - lo) / (hi - lo) * 100 for s in scores]

    @staticmethod
    def _z_score(scores: List[float]) -> List[float]:
        if len(scores) < 2:
            return [50.0] * len(scores)
        mu = statistics.mean(scores)
        sigma = statistics.stdev(scores)
        if sigma == 0:
            return [50.0] * len(scores)
        return [
            ScoreNormalizer._normal_cdf((s - mu) / sigma) * 100
            for s in scores
        ]

    @staticmethod
    def _percentile(scores: List[float]) -> List[float]:
        if not scores:
            return []
        n = len(scores)
        ranks = []
        for s in scores:
            below = sum(1 for x in scores if x < s)
            equal = sum(1 for x in scores if x == s)
            pct = (below + 0.5 * equal) / n * 100
            ranks.append(pct)
        return ranks

    @staticmethod
    def _robust(scores: List[float]) -> List[float]:
        if not scores:
            return []
        if len(scores) == 1:
            return [50.0]
        med = statistics.median(scores)
        sorted_s = sorted(scores)
        q1 = sorted_s[len(sorted_s) // 4]
        q3 = sorted_s[(3 * len(sorted_s)) // 4]
        iqr = q3 - q1
        if iqr == 0:
            return [50.0] * len(scores)
        return [
            100 / (1 + math.exp(-(s - med) / iqr))
            for s in scores
        ]

    # ----------------------------------------------------------
    # HELPERS
    # ----------------------------------------------------------
    @staticmethod
    def _normal_cdf(x: float) -> float:
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _compute_percentile(score: float, all_scores: List[float]) -> float:
        n = len(all_scores)
        if n == 0:
            return 0.0
        below = sum(1 for x in all_scores if x < score)
        equal = sum(1 for x in all_scores if x == score)
        return (below + 0.5 * equal) / n * 100

    @staticmethod
    def _safe_filename(name: str) -> str:
        return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)

    @staticmethod
    def _canonicalize_jd_id(raw_jd_id: str) -> str:
        """
        Canonicalize jd_id so the same JD with spaces vs underscores
        vs different casing maps to a single bucket.

        Examples:
            'ai specialist in healthcare analytics_parsed_jd'
            'ai_specialist_in_healthcare_analytics_parsed_jd'
            'AI Specialist in Healthcare Analytics_parsed_jd'
              -> all map to: 'ai_specialist_in_healthcare_analytics_parsed_jd'
        """
        if not raw_jd_id:
            return "unknown_jd"
        # lowercase, replace spaces and dashes with underscore, collapse
        s = raw_jd_id.strip().lower()
        s = s.replace("-", "_").replace(" ", "_")
        # collapse repeated underscores
        while "__" in s:
            s = s.replace("__", "_")
        return s


# ----------------------------------------------------------
# CLI entry
# ----------------------------------------------------------
if __name__ == "__main__":
    import argparse, glob
    parser = argparse.ArgumentParser(description="Normalize ATS scores per JD")
    parser.add_argument("--input_dir", required=True,
                        help="dir containing ATS scoring JSONs")
    parser.add_argument("--method", default="min_max",
                        choices=NORMALIZATION_METHODS)
    parser.add_argument("--deps_dir",
                        help="optional dir with dependency reports")
    parser.add_argument(
        "--output_dir",
        default="fairness_engine_outputs/normalized_scores")
    args = parser.parse_args()

    files = glob.glob(str(Path(args.input_dir) / "*.json"))
    records = [load_json(f) for f in files]
    deps = []
    if args.deps_dir:
        deps = [load_json(f)
                for f in glob.glob(str(Path(args.deps_dir) / "*_dependency.json"))]

    normalizer = ScoreNormalizer(method=args.method, output_dir=args.output_dir)
    out = normalizer.normalize_per_jd(records, dependency_reports=deps)
    print(f"Normalized {sum(len(v) for v in out.values())} candidates "
          f"across {len(out)} JDs using '{args.method}'")
    for jd_id, recs in out.items():
        print(f"  - {jd_id}: {len(recs)} candidates")
