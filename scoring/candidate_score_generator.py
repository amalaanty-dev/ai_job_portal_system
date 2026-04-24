"""
Candidate Score Generator — Day 13
Zecpath AI Job Portal

Orchestrates full batch ATS scoring:
  1. Loads ALL JDs from data/job_descriptions/parsed_jd/
  2. Discovers ALL candidates from data/extracted_skills/
  3. Scores every candidate x every JD (N x M matrix)
  4. Saves per-pair JSONs to ats_results/ats_scores/
  5. Saves ranked-per-JD JSONs, a summary JSON, and a flat CSV report
"""

import json
import os
import sys
import csv
import logging
from datetime import datetime

# -------------------------------------------------------------------
# Ensure project root is always on sys.path regardless of where the
# script is invoked from (project root, scripts/, anywhere).
# -------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))   # scoring/
_ROOT = os.path.dirname(_HERE)                        # project root
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ats_engine.scoring_engine import ATSScoringEngine      # noqa: E402
from ats_engine.score_interpreter import ScoreInterpreter   # noqa: E402
from scoring.jd_registry import JDRegistry                  # noqa: E402

logger = logging.getLogger(__name__)


class CandidateScoreGenerator:
    """
    High-level orchestrator for batch ATS scoring.

    Input folders (relative to project root):
      data/extracted_skills/           -> candidate skill JSONs
      data/experience_outputs/         -> candidate experience JSONs
      data/education_outputs/          -> candidate education JSONs
      data/semantic_outputs/           -> candidate semantic JSONs
      data/job_descriptions/parsed_jd/ -> JD JSONs

    Output folder:
      ats_results/ats_scores/
        <candidate>__<jd>.json         individual pair scores
        ranked_<jd_id>.json            candidates ranked per JD
        summary.json                   all scores condensed
        ats_scores_report.csv          flat spreadsheet
    """

    def __init__(
        self,
        skill_outputs_dir: str      = None,
        experience_outputs_dir: str = None,
        education_outputs_dir: str  = None,
        semantic_outputs_dir: str   = None,
        ats_results_dir: str        = None,
        jd_dir: str                 = None,
    ):
        # Default paths match actual project folder names
        _base = _ROOT  # always absolute regardless of cwd

        self.skill_outputs_dir      = skill_outputs_dir      or os.path.join(_base, "data", "extracted_skills")
        self.experience_outputs_dir = experience_outputs_dir or os.path.join(_base, "data", "experience_outputs")
        self.education_outputs_dir  = education_outputs_dir  or os.path.join(_base, "data", "education_outputs")
        self.semantic_outputs_dir   = semantic_outputs_dir   or os.path.join(_base, "data", "semantic_outputs")
        self.ats_results_dir        = ats_results_dir        or os.path.join(_base, "ats_results", "ats_scores")
        self.jd_dir                 = jd_dir                 or os.path.join(_base, "data", "job_descriptions", "parsed_jd")

        self.engine      = ATSScoringEngine(
            skill_outputs_dir      = self.skill_outputs_dir,
            experience_outputs_dir = self.experience_outputs_dir,
            education_outputs_dir  = self.education_outputs_dir,
            semantic_outputs_dir   = self.semantic_outputs_dir,
            ats_results_dir        = self.ats_results_dir,
        )
        self.interpreter = ScoreInterpreter()
        self.jd_registry = JDRegistry(self.jd_dir)

        os.makedirs(self.ats_results_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """
        Execute full N-candidates x M-JDs scoring batch.

        Returns summary dict:
          all_results     : list of all individual result dicts
          per_jd          : { jd_id: [ranked candidates] }
          per_candidate   : { resume_id: [all JD scores] }
          top_candidates  : { jd_id: top-3 candidates }
        """
        jd_registry = self.jd_registry.get_all()
        logger.info(
            "Starting batch scoring: %d JD(s) in registry", len(jd_registry)
        )

        all_results = self.engine.score_all(jd_registry)

        if not all_results:
            logger.warning(
                "No results generated.\n"
                "  Check that candidate JSONs exist in: %s",
                self.skill_outputs_dir,
            )
            self._save_summary_json([])
            self._save_csv_report([])
            return {
                "all_results": [],
                "per_jd": {},
                "per_candidate": {},
                "top_candidates": {},
            }

        # Global rank by final_score descending
        ranked_results = self.interpreter.bulk_rank(all_results)

        # Group by JD
        per_jd: dict = {}
        for r in ranked_results:
            jd_id = r["identifiers"]["jd_id"]
            per_jd.setdefault(jd_id, []).append(r)

        # Re-rank within each JD
        for jd_id in per_jd:
            per_jd[jd_id].sort(key=lambda x: x["final_score"], reverse=True)
            for idx, r in enumerate(per_jd[jd_id], 1):
                r["jd_rank"] = idx

        # Group by candidate
        per_candidate: dict = {}
        for r in ranked_results:
            cid = r["identifiers"]["resume_id"]
            per_candidate.setdefault(cid, []).append(r)

        # Top 3 per JD
        top_candidates = {jd: res[:3] for jd, res in per_jd.items()}

        # Persist reports
        self._save_summary_json(ranked_results)
        self._save_per_jd_reports(per_jd)
        self._save_csv_report(ranked_results)

        logger.info(
            "Batch scoring complete. %d result(s) across %d candidate(s) x %d JD(s).",
            len(all_results), len(per_candidate), len(per_jd),
        )
        self._print_summary(per_jd)

        return {
            "all_results":    ranked_results,
            "per_jd":         per_jd,
            "per_candidate":  per_candidate,
            "top_candidates": top_candidates,
        }

    # ------------------------------------------------------------------
    # Save helpers
    # ------------------------------------------------------------------

    def _save_summary_json(self, results: list):
        """Save condensed summary of all scores to summary.json."""
        table = self.interpreter.summary_table(results) if results else []
        path  = os.path.join(self.ats_results_dir, "summary.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "generated_at":  datetime.now().isoformat(timespec="seconds"),
                    "total_scores":  len(results),
                    "scores":        table,
                },
                f, indent=2, ensure_ascii=False,
            )
        logger.info("Summary JSON saved -> %s", path)

    def _save_per_jd_reports(self, per_jd: dict):
        """Save a ranked candidate list JSON for each JD."""
        for jd_id, results in per_jd.items():
            safe_jd  = jd_id.replace("/", "_").replace("\\", "_").replace(" ", "_")
            path     = os.path.join(self.ats_results_dir, f"ranked_{safe_jd}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "jd_id":              jd_id,
                        "job_role":           results[0]["identifiers"]["job_role"] if results else "",
                        "total_candidates":   len(results),
                        "generated_at":       datetime.now().isoformat(timespec="seconds"),
                        "ranked_candidates":  results,
                    },
                    f, indent=2, ensure_ascii=False,
                )
        logger.info("Per-JD ranked reports saved (%d files).", len(per_jd))

    def _save_csv_report(self, results: list):
        """Save a flat CSV of all scores for spreadsheet review."""
        path       = os.path.join(self.ats_results_dir, "ats_scores_report.csv")
        fieldnames = [
            "rank", "resume_id", "jd_id", "job_role", "final_score",
            "skill_match", "experience_relevance", "education_alignment",
            "semantic_similarity", "weight_strategy",
            "rating", "recommendation", "priority",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow({
                    "rank":                 r.get("rank", "-"),
                    "resume_id":            r["identifiers"]["resume_id"],
                    "jd_id":               r["identifiers"]["jd_id"],
                    "job_role":            r["identifiers"]["job_role"],
                    "final_score":         r["final_score"],
                    "skill_match":         r["scoring_breakdown"]["skill_match"],
                    "experience_relevance": r["scoring_breakdown"]["experience_relevance"],
                    "education_alignment":  r["scoring_breakdown"]["education_alignment"],
                    "semantic_similarity":  r["scoring_breakdown"]["semantic_similarity"],
                    "weight_strategy":     r["weights"]["weight_strategy"],
                    "rating":              r["score_interpretation"]["rating"],
                    "recommendation":      r["score_interpretation"]["recommendation"],
                    "priority":            r["score_interpretation"]["priority"],
                })
        logger.info("CSV report saved -> %s", path)

    def _print_summary(self, per_jd: dict):
        """Print human-readable batch summary to stdout."""
        print("\n" + "=" * 72)
        print("  ZECPATH ATS SCORING ENGINE — BATCH RESULTS SUMMARY")
        print("=" * 72)
        for jd_id, results in per_jd.items():
            role = results[0]["identifiers"]["job_role"] if results else ""
            print(f"\n  JD: {jd_id}  ({role})")
            print(f"  {'Rank':<5} {'Candidate':<35} {'Score':>7}  Rating")
            print(f"  {'-'*5} {'-'*35} {'-'*7}  {'-'*20}")
            for r in results:
                print(
                    f"  #{r.get('jd_rank', '-'):<4} "
                    f"{r['identifiers']['resume_id']:<35} "
                    f"{r['final_score']:>7.1f}  "
                    f"{r['score_interpretation']['rating']}"
                )
        print("\n" + "=" * 72)
