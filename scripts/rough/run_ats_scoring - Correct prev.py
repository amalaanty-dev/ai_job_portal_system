"""
run_ats_scoring.py — Day 13 Entry Point
Zecpath AI Job Portal

Usage (run from project root):
    python scripts/run_ats_scoring.py
    python scripts/run_ats_scoring.py --candidate amala --jd JD_Data_Analyst_001
    python scripts/run_ats_scoring.py --list-jds
    python scripts/run_ats_scoring.py --list-candidates

Input folders (relative to project root):
    data/extracted_skills/             <- candidate skill JSONs       (PRIMARY)
    data/experience_outputs/           <- candidate experience JSONs
    data/education_outputs/            <- candidate education JSONs
    data/semantic_outputs/             <- candidate semantic JSONs
    data/job_descriptions/parsed_jd/   <- JD JSONs

Output folder:
    ats_results/ats_scores/
"""

import sys
import os
import json
import logging
import argparse

# -------------------------------------------------------------------
# Resolve project root from THIS file's location (scripts/ -> parent)
# Works correctly whether invoked as:
#   python scripts/run_ats_scoring.py          (from project root)
#   python run_ats_scoring.py                  (from scripts/)
# -------------------------------------------------------------------
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT        = os.path.dirname(_SCRIPTS_DIR)

if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# -------------------------------------------------------------------
# All paths are absolute, anchored to project root
# -------------------------------------------------------------------
PATHS = {
    "skill_outputs":      os.path.join(_ROOT, "data", "extracted_skills"),
    "experience_outputs": os.path.join(_ROOT, "data", "experience_outputs"),
    "education_outputs":  os.path.join(_ROOT, "data", "education_outputs"),
    "semantic_outputs":   os.path.join(_ROOT, "data", "semantic_outputs"),
    "ats_results":        os.path.join(_ROOT, "ats_results", "ats_scores"),
    "jd_dir":             os.path.join(_ROOT, "data", "job_descriptions", "parsed_jd"),
    "logs":               os.path.join(_ROOT, "logs"),
}

# Create required directories upfront
for _p in PATHS.values():
    os.makedirs(_p, exist_ok=True)

# -------------------------------------------------------------------
# Logging — file goes to logs/ats_scoring.log (absolute path)
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s -- %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(PATHS["logs"], "ats_scoring.log"), encoding="utf-8"
        ),
    ],
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Import engine AFTER sys.path is set up
# -------------------------------------------------------------------
from ats_engine.scoring_engine import ATSScoringEngine           # noqa: E402
from scoring.candidate_score_generator import CandidateScoreGenerator  # noqa: E402
from scoring.jd_registry import JDRegistry                      # noqa: E402


# -------------------------------------------------------------------
# Run modes
# -------------------------------------------------------------------

def run_batch():
    """Score ALL candidates against ALL JDs."""
    generator = CandidateScoreGenerator(
        skill_outputs_dir      = PATHS["skill_outputs"],
        experience_outputs_dir = PATHS["experience_outputs"],
        education_outputs_dir  = PATHS["education_outputs"],
        semantic_outputs_dir   = PATHS["semantic_outputs"],
        ats_results_dir        = PATHS["ats_results"],
        jd_dir                 = PATHS["jd_dir"],
    )
    summary = generator.run()
    total   = len(summary["all_results"])
    print(f"\nBatch scoring complete. {total} result(s) saved.")
    print(f"Results -> {PATHS['ats_results']}")
    return summary


def run_single(candidate_id: str, jd_id: str):
    """Score one candidate against one JD and print the JSON result."""
    engine   = ATSScoringEngine(
        skill_outputs_dir      = PATHS["skill_outputs"],
        experience_outputs_dir = PATHS["experience_outputs"],
        education_outputs_dir  = PATHS["education_outputs"],
        semantic_outputs_dir   = PATHS["semantic_outputs"],
        ats_results_dir        = PATHS["ats_results"],
    )
    registry = JDRegistry(PATHS["jd_dir"])
    jd_info  = registry.get(jd_id)

    if not jd_info:
        print(f"\nERROR: JD '{jd_id}' not found in registry.")
        print(f"Available JDs: {registry.list_ids()}")
        sys.exit(1)

    result = engine.score_one(candidate_id, jd_id, jd_info)
    if result:
        print("\n" + json.dumps(result, indent=2, ensure_ascii=False))
        print(f"\nScore: {result['final_score']} -- {result['score_interpretation']['rating']}")
    else:
        print(f"\nERROR: Scoring failed for {candidate_id} vs {jd_id}")


def list_jds():
    """List all available JD IDs."""
    registry = JDRegistry(PATHS["jd_dir"])
    print(f"\nRegistered Job Descriptions ({len(registry.list_ids())} total):")
    for jd_id in registry.list_ids():
        jd = registry.get(jd_id)
        role = jd.get("job_role", jd.get("title", "?"))
        print(f"  {jd_id:<45} ({role})")


def list_candidates():
    """List all candidate IDs discovered in extracted_skills/."""
    path       = PATHS["skill_outputs"]
    candidates = sorted(
        f[:-5] for f in os.listdir(path) if f.endswith(".json")
    ) if os.path.isdir(path) else []
    print(f"\nCandidates found in {path} ({len(candidates)} total):")
    for c in candidates:
        print(f"  {c}")


# -------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Zecpath ATS Scoring Engine — Day 13",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_ats_scoring.py
  python scripts/run_ats_scoring.py --candidate amala --jd JD_Data_Analyst_001
  python scripts/run_ats_scoring.py --list-jds
  python scripts/run_ats_scoring.py --list-candidates
        """,
    )
    parser.add_argument("--candidate", "-c",
                        help="Candidate ID (stem of JSON file in extracted_skills/)")
    parser.add_argument("--jd", "-j",
                        help="JD ID (stem of JSON file in parsed_jd/)")
    parser.add_argument("--list-jds", action="store_true",
                        help="List all available JD IDs")
    parser.add_argument("--list-candidates", action="store_true",
                        help="List all candidate IDs discovered")

    args = parser.parse_args()

    if args.list_jds:
        list_jds()
    elif args.list_candidates:
        list_candidates()
    elif args.candidate and args.jd:
        run_single(args.candidate, args.jd)
    else:
        run_batch()


if __name__ == "__main__":
    main()
