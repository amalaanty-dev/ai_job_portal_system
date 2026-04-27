"""
Fairness Pipeline - Orchestrator (Day 15)
Path: ai_job_portal_system/fairness_engine/fairness_pipeline.py

PURPOSE:
    Chain all 5 Day-15 tasks for a single resume + JD pair OR a batch.

PIPELINE:
    [parsed_resume + sections + parsed_jd + ats_score]
        |
        v
    1. ResumeNormalizer        -> normalized_resume
    2. KeywordDependencyReducer-> dependency_report  (uses normalized resume)
    3. PIIMasker               -> masked_resume + audit
    4. ScoreNormalizer         -> normalized_score   (batch)
    5. BiasEvaluator           -> bias_report         (batch)

OUTPUT:
    - Each stage saves its own artifacts to data/<subdir>/
    - Pipeline returns a unified dict.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.fairness_utils import get_logger, load_json, now_iso, save_json, ensure_dir

from .bias_evaluator import BiasEvaluator
from .keyword_dependency_reducer import KeywordDependencyReducer
from .pii_masker import PIIMasker
from .resume_normalizer import ResumeNormalizer
from .score_normalizer import ScoreNormalizer

logger = get_logger("fairness_pipeline")


class FairnessPipeline:
    """End-to-end fairness pipeline orchestrating all Day-15 tasks."""

    def __init__(
        self,
        normalization_method: str = "min_max",
        mask_profile: Optional[Dict[str, bool]] = None,
        data_root: str = "fairness_engine_outputs",
    ):
        self.data_root = Path(data_root)
        ensure_dir(self.data_root)

        self.resume_normalizer = ResumeNormalizer(
            output_dir=str(self.data_root / "normalized_resumes"))
        self.dep_reducer = KeywordDependencyReducer(
            output_dir=str(self.data_root / "normalized_scores"))
        self.pii_masker = PIIMasker(
            mask_profile=mask_profile,
            output_dir=str(self.data_root / "masked_resumes"))
        self.score_normalizer = ScoreNormalizer(
            method=normalization_method,
            output_dir=str(self.data_root / "normalized_scores"))
        self.bias_evaluator = BiasEvaluator(
            output_dir=str(self.data_root / "bias_reports"))

    # ----------------------------------------------------------
    # SINGLE RESUME RUN (Tasks 1, 2, 4)
    # ----------------------------------------------------------
    def run_single(
        self,
        parsed_resume_path: str,
        sections_path: str,
        parsed_jd_path: str,
    ) -> Dict[str, Any]:
        """
        Run per-resume tasks (normalize, keyword-reduce, mask) for one candidate.

        Score normalization & bias eval need a batch, so they run separately.
        """
        logger.info(f"=== Single-resume fairness run: {parsed_resume_path} ===")
        # 1. Normalize
        normalized = self.resume_normalizer.normalize(
            parsed_resume_path, sections_path, save=True
        )
        # 2. Keyword dependency
        jd = load_json(parsed_jd_path)
        dep = self.dep_reducer.analyze(normalized, jd, save=True)
        # 3. Mask PII
        masked = self.pii_masker.mask(normalized, save=True)

        return {
            "candidate_id": normalized["candidate_id"],
            "normalized_resume_path":
                str(self.data_root / "normalized_resumes" /
                    f"{normalized['candidate_id']}_normalized.json"),
            "dependency_report": dep,
            "masked_resume_audit": masked["audit"],
            "ran_at": now_iso(),
        }

    # ----------------------------------------------------------
    # BATCH RUN (Tasks 3 + 5)
    # ----------------------------------------------------------
    def run_batch(
        self,
        ats_score_records: List[Dict[str, Any]],
        dependency_reports: Optional[List[Dict[str, Any]]] = None,
        mask_audits:        Optional[List[Dict[str, Any]]] = None,
        cohort_map:         Optional[Dict[str, Dict[str, str]]] = None,
        run_id:             str = "fairness_run",
    ) -> Dict[str, Any]:
        """
        Run pool-level tasks (per-JD score normalization + bias evaluation).

        Produces:
          - One <jd_id>_normalized_scores.json per JD (target schema)
          - One <run_id>_bias_audit.json (combined audit across all JDs)
        """
        logger.info(f"=== Batch fairness run: {run_id} "
                    f"(n={len(ats_score_records)}) ===")

        # 4. Score normalization PER JD (each JD gets its own file)
        per_jd = self.score_normalizer.normalize_per_jd(
            ats_score_records,
            dependency_reports=dependency_reports,
            save=True,
        )

        # Flatten all candidate records for combined bias audit
        all_candidates: List[Dict[str, Any]] = []
        for jd_records in per_jd.values():
            all_candidates.extend(jd_records)

        # 5. Bias evaluation (uses combined pool)
        bias = self.bias_evaluator.evaluate(
            normalized_scores=all_candidates,
            dependency_reports=dependency_reports,
            mask_audits=mask_audits,
            cohort_map=cohort_map,
            run_id=run_id,
            save=True,
        )

        # build summary stats per JD
        jd_summaries = {}
        for jd_id, recs in per_jd.items():
            shortlisted = sum(1 for r in recs if r["status"] == "shortlisted")
            on_hold     = sum(1 for r in recs if r["status"] == "on_hold")
            rejected    = sum(1 for r in recs if r["status"] == "rejected")
            jd_summaries[jd_id] = {
                "n_candidates":       len(recs),
                "shortlisted":        shortlisted,
                "on_hold":            on_hold,
                "rejected":           rejected,
                "top_candidate":      recs[0]["resume_id"] if recs else None,
                "top_score":          recs[0]["normalized_final_score"] if recs else None,
            }

        summary = {
            "run_id": run_id,
            "n_total_candidates": len(ats_score_records),
            "n_jds": len(per_jd),
            "normalization_method": self.score_normalizer.method,
            "per_jd_summaries": jd_summaries,
            "bias_verdict": bias["summary_verdict"],
            "flags": bias["flags"],
            "ran_at": now_iso(),
        }
        save_json(summary,
                  self.data_root / "bias_reports" / f"{run_id}_summary.json")
        logger.info("Pipeline summary saved.")
        return summary
