"""
scripts/run_ats_testing.py
==========================
MAIN ORCHESTRATOR for Day 17 ATS testing.

Steps:
  1. Load all score JSONs from ats_results/ats_test_resumes_scores/
  2. Load HR ground truth from datasets/hr_manual_evaluations.json
  3. Join AI decisions with HR decisions
  4. Compute overall + per-category metrics
  5. Run mismatch analysis & build improvement backlog
  6. Persist:
        ats_results/day17_metrics.json
        ats_results/day17_backlog.json
  7. Print summary to console

Run:
    python scripts/run_ats_testing.py
    python scripts/run_ats_testing.py --scaffold-hr   # auto-create HR template entries

Day: 17
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make project root importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.score_loader import load_all_scores, get_resume_jd_pair_key, extract_decision
from utils.metrics_calculator import evaluate, evaluate_by_category
from utils.backlog_generator import generate_backlog, analyze_mismatches

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("day17")


def load_config():
    cfg_path = ROOT / "ats_engine" / "ats_test_config.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Missing config: {cfg_path}")
    with open(cfg_path) as f:
        return json.load(f)


def load_hr_evaluations(path: Path):
    if not path.exists():
        logger.warning(f"HR evaluations file not found: {path}")
        return {}
    with open(path) as f:
        data = json.load(f)
    return {
        k: v for k, v in data.get("evaluations", {}).items()
        if not k.startswith("EXAMPLE_")
    }


def scaffold_hr_template(scores, hr_path: Path):
    """If HR file is empty/example-only, scaffold PENDING entries based on existing scores."""
    if hr_path.exists():
        with open(hr_path) as f:
            data = json.load(f)
    else:
        data = {"version": "1.0", "evaluations": {}}

    evaluations = data.get("evaluations", {})
    added = 0
    for rec in scores:
        key = get_resume_jd_pair_key(rec)
        if key not in evaluations and not key.startswith("EXAMPLE_"):
            ids = rec.get("identifiers", {})
            evaluations[key] = {
                "candidate_id": ids.get("resume_id"),
                "category": "PENDING",  # tech | non_tech | fresher | senior
                "role": ids.get("job_role"),
                "hr_decision": "PENDING",  # Shortlisted | Manual Review | Rejected
                "hr_score": None,
                "hr_notes": "",
                "expected_role": ids.get("job_role"),
            }
            added += 1

    data["evaluations"] = evaluations
    hr_path.parent.mkdir(parents=True, exist_ok=True)
    with open(hr_path, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(f"Scaffolded {added} HR entries in {hr_path}")
    return added


def join_records(scores, hr_evals, threshold):
    joined = []
    skipped_no_hr = 0
    for rec in scores:
        key = get_resume_jd_pair_key(rec)
        hr = hr_evals.get(key)
        if hr is None or hr.get("hr_decision") in {"PENDING", None}:
            skipped_no_hr += 1
            continue
        joined.append({
            "key": key,
            "ai_decision": extract_decision(rec, threshold=threshold),
            "hr_decision": hr["hr_decision"],
            "category": hr.get("category", "uncategorized"),
            "final_score": rec.get("final_score"),
            "identifiers": rec.get("identifiers", {}),
            "matched_skills": rec.get("matched_skills", []),
            "missing_skills": rec.get("missing_skills", []),
            "experience": rec.get("experience", {}),
            "scoring_breakdown": rec.get("scoring_breakdown", {}),
            "hr_expected_role": hr.get("expected_role"),
        })
    return joined, skipped_no_hr


def main():
    parser = argparse.ArgumentParser(description="Day 17 ATS Testing Orchestrator")
    parser.add_argument(
        "--scaffold-hr",
        action="store_true",
        help="Auto-create PENDING HR entries for all score files",
    )
    args = parser.parse_args()

    config = load_config()
    scores_dir = ROOT / config["paths"]["scores_dir"]
    hr_path = ROOT / config["paths"]["hr_evaluations"]
    metrics_out = ROOT / config["paths"]["metrics_output"]
    backlog_out = ROOT / config["paths"]["backlog_output"]

    logger.info("=" * 70)
    logger.info("Day 17 — ATS System Testing")
    logger.info("=" * 70)

    # 1. Load scores
    scores = load_all_scores(scores_dir)
    logger.info(f"Loaded {len(scores)} score JSONs from {scores_dir}")

    if not scores:
        logger.error(
            f"No scores found in {scores_dir}. "
            "Populate this folder by running your scoring pipeline first."
        )
        return 1

    # 2. Optional HR scaffolding
    if args.scaffold_hr:
        scaffold_hr_template(scores, hr_path)
        logger.info("HR scaffold complete. Edit datasets/hr_manual_evaluations.json and re-run without --scaffold-hr.")
        return 0

    # 3. Load HR
    hr_evals = load_hr_evaluations(hr_path)
    logger.info(f"Loaded {len(hr_evals)} HR evaluations")

    if not hr_evals:
        logger.error(
            "No HR evaluations available. Run with --scaffold-hr to generate a template."
        )
        return 1

    # 4. Join
    threshold = config["decision_thresholds"]["shortlist"]
    joined, skipped = join_records(scores, hr_evals, threshold)
    logger.info(f"Joined {len(joined)} records (skipped {skipped} pending/missing HR)")

    if not joined:
        logger.error("No (AI, HR) pairs to evaluate. Fill in HR evaluations and rerun.")
        return 1

    # 5. Metrics
    ai_list = [r["ai_decision"] for r in joined]
    hr_list = [r["hr_decision"] for r in joined]
    overall = evaluate(ai_list, hr_list)
    per_cat = evaluate_by_category(joined, category_field="category")

    # 6. Backlog
    backlog = generate_backlog(joined, per_cat)
    mismatch_analysis = analyze_mismatches(joined)

    # 7. Persist
    metrics_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "day": 17,
        "total_records": len(joined),
        "overall": overall.as_dict(),
        "by_category": {cat: m.as_dict() for cat, m in per_cat.items()},
        "mismatch_analysis": mismatch_analysis,
        "config": {
            "shortlist_threshold": threshold,
            "target_metrics": config["target_metrics"],
            "category_targets": config["category_targets"],
        },
    }
    metrics_out.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_out, "w") as f:
        json.dump(metrics_payload, f, indent=2)
    logger.info(f"✓ Wrote metrics → {metrics_out}")

    backlog_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "day": 17,
        "total_items": sum(len(v) for v in backlog.values()),
        "items": backlog,
    }
    with open(backlog_out, "w") as f:
        json.dump(backlog_payload, f, indent=2)
    logger.info(f"✓ Wrote backlog → {backlog_out}")

    # 8. Console summary
    print()
    print("─" * 70)
    print(f"OVERALL METRICS  (n={len(joined)})")
    print("─" * 70)
    print(f"  Precision : {overall.precision * 100:6.2f}%")
    print(f"  Recall    : {overall.recall * 100:6.2f}%")
    print(f"  Accuracy  : {overall.accuracy * 100:6.2f}%")
    print(f"  F1 Score  : {overall.f1_score * 100:6.2f}%")
    cm = overall.confusion_matrix
    print(f"  Confusion : TP={cm.tp}  FP={cm.fp}  FN={cm.fn}  TN={cm.tn}")
    print()
    print("CATEGORY-WISE")
    print("─" * 70)
    for cat, m in per_cat.items():
        print(f"  {cat:12s}  acc={m.accuracy * 100:5.1f}%  prec={m.precision * 100:5.1f}%  rec={m.recall * 100:5.1f}%  (n={m.confusion_matrix.total})")
    print()
    print(f"BACKLOG  (high={len(backlog['high'])}  medium={len(backlog['medium'])}  low={len(backlog['low'])})")
    print("─" * 70)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
