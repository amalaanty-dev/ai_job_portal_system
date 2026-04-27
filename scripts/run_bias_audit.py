"""
Run Bias Audit Standalone (Day 15)
Path: ai_job_portal_system/scripts/run_bias_audit.py

USAGE:
    python -m scripts.run_bias_audit \
        --scores_dir   ats_results \
        --deps_dir     data/normalized_scores \
        --masks_dir    data/masked_resumes \
        --cohort_file  data/cohort_map.json   (optional)
"""

import argparse
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fairness_engine.bias_evaluator import BiasEvaluator
from fairness_engine.score_normalizer import ScoreNormalizer
from utils.fairness_utils import get_logger, load_json

logger = get_logger("run_bias_audit")


def main():
    p = argparse.ArgumentParser(description="Standalone bias audit")
    p.add_argument("--scores_dir", required=True,
                   help="dir with raw ATS scoring JSONs")
    p.add_argument("--deps_dir", help="dir with dependency reports")
    p.add_argument("--masks_dir", help="dir with mask audits")
    p.add_argument("--cohort_file",
                   help="optional JSON: { resume_id: {gender, location, ...} }")
    p.add_argument("--method", default="min_max")
    p.add_argument("--run_id", default="bias_audit")
    p.add_argument("--output_dir", default="fairness_engine_outputs/bias_reports")
    args = p.parse_args()

    # 1. Load + normalize scores per JD
    score_files = glob.glob(str(Path(args.scores_dir) / "*.json"))
    if not score_files:
        logger.error(f"No score files found in {args.scores_dir}")
        return
    score_records = [load_json(f) for f in score_files]

    # 2. Load deps
    deps = []
    if args.deps_dir:
        deps = [load_json(f)
                for f in glob.glob(str(Path(args.deps_dir) / "*_dependency.json"))]

    # 3. Normalize per JD
    per_jd = ScoreNormalizer(method=args.method).normalize_per_jd(
        score_records, dependency_reports=deps
    )
    # flatten for combined audit
    all_candidates = []
    for jd_records in per_jd.values():
        all_candidates.extend(jd_records)

    # 4. Load mask audits
    masks = []
    if args.masks_dir:
        masks = [load_json(f)
                 for f in glob.glob(str(Path(args.masks_dir) / "*_masked.json"))]

    # 5. Load cohort map
    cohort = None
    if args.cohort_file and Path(args.cohort_file).exists():
        cohort = load_json(args.cohort_file)

    # 6. Evaluate
    evaluator = BiasEvaluator(output_dir=args.output_dir)
    report = evaluator.evaluate(
        normalized_scores=all_candidates,
        dependency_reports=deps,
        mask_audits=masks,
        cohort_map=cohort,
        run_id=args.run_id,
    )
    print(f"\nProcessed {len(all_candidates)} candidates "
          f"across {len(per_jd)} JD(s)")
    print(f"Verdict: {report['summary_verdict']}")
    print(f"Indicators: {list(report['indicators'].keys())}")
    print(f"Flags ({len(report['flags'])}): {report['flags']}")


if __name__ == "__main__":
    main()
