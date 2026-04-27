"""
Run Full Batch Fairness Pipeline (Day 15)
Path: ai_job_portal_system/scripts/run_full_batch.py

Processes MANY resumes against MANY JDs in one shot:
  - Pairs each resume in --resumes_dir with its <name>_sections.json
  - Iterates each (resume, jd) combination
  - Produces per-resume artifacts (normalized, masked, dependency)
  - Reads all ATS results from --ats_dir, groups by jd_id, and produces
    ONE <jd_id>_normalized_scores.json per JD
  - Final combined bias audit across the entire pool

USAGE:
    python -m scripts.run_full_batch ^
        --resumes_dir   data/parsed ^
        --sections_dir  data/parsed ^
        --jds_dir       data/parsed_jds ^
        --ats_dir       ats_results ^
        --method        min_max ^
        --run_id        full_batch_q1

Input folder structure expected:
    data/parsed/
        candidate1.json
        candidate1_sections.json
        candidate2.json
        candidate2_sections.json
        ...
    data/parsed_jds/
        ai_specialist_parsed_jd.json
        ui_ux_designer_parsed_jd.json
        sales_executive_parsed_jd.json
    ats_results/
        candidate1__ai_specialist_parsed_jd.json
        candidate1__ui_ux_designer_parsed_jd.json
        candidate2__ai_specialist_parsed_jd.json
        ...
"""

import argparse
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fairness_engine.fairness_pipeline import FairnessPipeline
from fairness_engine.resume_normalizer import ResumeNormalizer
from fairness_engine.keyword_dependency_reducer import KeywordDependencyReducer
from fairness_engine.pii_masker import PIIMasker
from utils.fairness_utils import get_logger, load_json

logger = get_logger("run_full_batch")


def discover_resumes(resumes_dir: str, sections_dir: str):
    """Yield (resume_path, sections_path|None) tuples."""
    resume_files = sorted(glob.glob(str(Path(resumes_dir) / "*.json")))
    # Exclude *_sections.json files - they are paired metadata
    resume_files = [f for f in resume_files if "_sections" not in f]

    for rf in resume_files:
        stem = Path(rf).stem
        sec_candidate = Path(sections_dir) / f"{stem}_sections.json"
        sec_path = str(sec_candidate) if sec_candidate.exists() else None
        yield rf, sec_path


def discover_jds(jds_dir: str):
    """Yield JD JSON paths."""
    return sorted(glob.glob(str(Path(jds_dir) / "*.json")))


def main():
    p = argparse.ArgumentParser(description="Bulk fairness pipeline (many resumes x many JDs)")
    p.add_argument("--resumes_dir",  required=True, help="dir with parsed resume JSONs")
    p.add_argument("--sections_dir", required=True, help="dir with section JSONs (often same as resumes_dir)")
    p.add_argument("--jds_dir",      required=True, help="dir with parsed JD JSONs")
    p.add_argument("--ats_dir",      required=True, help="dir with ATS scoring outputs")
    p.add_argument("--method", default="min_max",
                   choices=["min_max", "z_score", "percentile", "robust"])
    p.add_argument("--run_id", default="full_batch")
    p.add_argument("--data_root", default="fairness_engine_outputs")
    args = p.parse_args()

    # 1. Initialize pipeline (one instance reused)
    pipe = FairnessPipeline(
        normalization_method=args.method,
        data_root=args.data_root,
    )

    # 2. Discover input files
    resumes = list(discover_resumes(args.resumes_dir, args.sections_dir))
    jds = discover_jds(args.jds_dir)

    if not resumes:
        logger.error(f"No resumes found in {args.resumes_dir}")
        return
    if not jds:
        logger.error(f"No JDs found in {args.jds_dir}")
        return

    logger.info(f"Discovered {len(resumes)} resumes, {len(jds)} JDs")
    logger.info(f"Will process {len(resumes) * len(jds)} (resume, jd) pairs")

    # 3. Per-resume tasks for every (resume, JD) combination
    all_dependency_reports = []
    all_mask_audits = []
    success, failed = 0, 0

    for resume_path, sections_path in resumes:
        for jd_path in jds:
            try:
                logger.info(f"Processing: {Path(resume_path).stem} x {Path(jd_path).stem}")
                single = pipe.run_single(resume_path, sections_path, jd_path)
                all_dependency_reports.append(single["dependency_report"])
                all_mask_audits.append({"audit": single["masked_resume_audit"]})
                success += 1
            except Exception as e:
                logger.error(f"FAILED: {resume_path} x {jd_path}: {e}")
                failed += 1

    print(f"\n--- Per-Resume-Per-JD Results ---")
    print(f"Successful pairs: {success}")
    print(f"Failed pairs:     {failed}")

    # 4. Batch tasks (per-JD score normalization + bias audit)
    # Exclude ranked_jd summary files - only candidate score files have
    # an "identifiers" block with resume_id + jd_id.
    all_ats_files = glob.glob(str(Path(args.ats_dir) / "*.json"))
    ats_files = [
        f for f in all_ats_files
        if not Path(f).stem.lower().startswith("ranked_")
        and Path(f).stem.lower() != "summary"
    ]
    if not ats_files:
        logger.warning(f"No ATS files in {args.ats_dir}; skipping batch tasks.")
        return
    logger.info(
        f"ATS dir: {len(all_ats_files)} total files, "
        f"{len(all_ats_files) - len(ats_files)} ranked_jd excluded, "
        f"{len(ats_files)} candidate score files loaded."
    )

    ats_records = [load_json(f) for f in ats_files]
    summary = pipe.run_batch(
        ats_records,
        dependency_reports=all_dependency_reports,
        mask_audits=all_mask_audits,
        run_id=args.run_id,
    )

    # 5. Print human-readable summary
    print(f"\n--- Batch Results ---")
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
    print(f"\nOutputs saved under: {args.data_root}/")


if __name__ == "__main__":
    main()