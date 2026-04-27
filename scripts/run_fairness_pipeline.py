"""
Run Fairness Pipeline (Day 15)
Path: ai_job_portal_system/scripts/run_fairness_pipeline.py

USAGE:
    python -m scripts.run_fairness_pipeline \
        --resume   data/parsed/Amala_Resume_DS_DA_2026_.json \
        --sections data/parsed/Amala_Resume_DS_DA_2026__sections.json \
        --jd       data/parsed_jds/ai_specialist_in_healthcare_analytics_parsed_jd.json \
        --ats_dir  ats_results

Run pre-existing single-resume fairness tasks AND batch tasks if multiple
ATS results are available.
"""

import argparse
import glob
import sys
from pathlib import Path

# allow `python scripts/...` from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fairness_engine.fairness_pipeline import FairnessPipeline
from utils.fairness_utils import get_logger, load_json

logger = get_logger("run_fairness_pipeline")


def main():
    p = argparse.ArgumentParser(description="Run Day-15 fairness pipeline")
    p.add_argument("--resume",   required=True, help="parsed resume JSON")
    p.add_argument("--sections", required=True, help="sections JSON")
    p.add_argument("--jd",       required=True, help="parsed JD JSON")
    p.add_argument("--ats_dir",  required=False,
                   help="dir with ATS scoring outputs for batch normalization")
    p.add_argument("--method", default="min_max",
                   choices=["min_max", "z_score", "percentile", "robust"])
    p.add_argument("--data_root", default="fairness_engine_outputs")
    p.add_argument("--run_id", default="fairness_run")
    args = p.parse_args()

    pipe = FairnessPipeline(
        normalization_method=args.method,
        data_root=args.data_root,
    )

    # 1. Per-resume tasks
    single = pipe.run_single(args.resume, args.sections, args.jd)
    print("\n--- Per-Resume Results ---")
    print(f"Candidate: {single['candidate_id']}")
    print(f"Keyword Dependency Ratio:  "
          f"{single['dependency_report']['keyword_dependency_ratio']}")
    print(f"Context-Adjusted Skill Score: "
          f"{single['dependency_report']['context_adjusted_skill_score']}")
    print(f"PII masks applied: "
          f"{single['masked_resume_audit']['total_masks_applied']}")

    # 2. Batch tasks (if ATS dir provided)
    if args.ats_dir:
        ats_files = glob.glob(str(Path(args.ats_dir) / "*.json"))
        if ats_files:
            ats_records = [load_json(f) for f in ats_files]
            summary = pipe.run_batch(
                ats_records,
                dependency_reports=[single["dependency_report"]],
                mask_audits=[{"audit": single["masked_resume_audit"]}],
                run_id=args.run_id,
            )
            print("\n--- Batch Results ---")
            print(f"Method: {summary['normalization_method']}")
            print(f"Total candidates: {summary['n_total_candidates']} "
                  f"across {summary['n_jds']} JD(s)")
            for jd_id, jd_sum in summary["per_jd_summaries"].items():
                print(f"\n  JD: {jd_id}")
                print(f"    Candidates: {jd_sum['n_candidates']}")
                print(f"    Shortlisted: {jd_sum['shortlisted']} | "
                      f"On hold: {jd_sum['on_hold']} | "
                      f"Rejected: {jd_sum['rejected']}")
                print(f"    Top candidate: {jd_sum['top_candidate']} "
                      f"(score={jd_sum['top_score']})")
            print(f"\nBias verdict: {summary['bias_verdict']}")
            print(f"Flags: {summary['flags']}")
        else:
            logger.warning(f"No ATS JSONs found in {args.ats_dir}")
    else:
        logger.info("Skipping batch step (no --ats_dir given).")


if __name__ == "__main__":
    main()
