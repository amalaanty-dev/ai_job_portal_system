"""
scripts/populate_test_scores.py
================================
Populates `ats_results/ats_test_resumes_scores/` with one score JSON per
(test_resume, test_jd) pair.

Strategy:
  1. Discover test resumes from data/resumes/ats_test_resumes/
  2. Discover parsed test JDs from data/job_descriptions/ats_test_parsed_jds/
  3. For EACH resume, ensure these intermediates exist (smart-skip if present):
        - data/extracted_skills/<resume_id>_skills.json
        - data/education_outputs/<resume_id>_sections.json
        - data/semantic_outputs/<resume_id>_sections_semantic.json   (per JD)
        - data/experience_outputs/<resume_id>_vs_<jd_id>_experience.json
     If any are missing, the script invokes the relevant upstream pipeline
     via subprocess (exactly mirroring how main.py / Day 13 already do it).
  4. For each (resume, JD) pair, calls ATSScoringEngine.score_one(...)
     and writes the result to ats_results/ats_test_resumes_scores/

Smart-skip:
  - If a final score JSON already exists for a (resume, jd) pair, skip it.
  - Use --force to recompute.

Run:
    python scripts/populate_test_scores.py
    python scripts/populate_test_scores.py --force        # recompute all
    python scripts/populate_test_scores.py --skip-upstream    # don't run upstream pipelines
    python scripts/populate_test_scores.py --limit 20     # only first 20 pairs (dry-run)

Day: 17
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

# -------------------------------------------------------------------
# Resolve project root
# -------------------------------------------------------------------
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPTS_DIR)

if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s -- %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Paths (anchored to project root)
# -------------------------------------------------------------------
PATHS = {
    "test_resumes":        os.path.join(_ROOT, "data", "resumes", "ats_test_resumes"),
    "test_parsed_jds":     os.path.join(_ROOT, "data", "job_descriptions", "ats_test_parsed_jds"),

    # Upstream intermediate folders (your existing pipelines write here)
    "skill_outputs":       os.path.join(_ROOT, "data", "extracted_skills"),
    "experience_outputs":  os.path.join(_ROOT, "data", "experience_outputs"),
    "education_outputs":   os.path.join(_ROOT, "data", "education_outputs"),
    "semantic_outputs":    os.path.join(_ROOT, "data", "semantic_outputs"),

    # Final test-score destination
    "test_scores_out":     os.path.join(_ROOT, "ats_results", "ats_test_resumes_scores"),

    # Logs
    "logs":                os.path.join(_ROOT, "logs"),
}

for _p in PATHS.values():
    os.makedirs(_p, exist_ok=True)

# -------------------------------------------------------------------
# Upstream pipeline scripts (your existing ones)
# -------------------------------------------------------------------
UPSTREAM_SCRIPTS = {
    "skills":     os.path.join(_SCRIPTS_DIR, "run_skill_engine_pipeline.py"),
    "education":  os.path.join(_SCRIPTS_DIR, "run_education_pipeline.py"),
    "semantic":   os.path.join(_SCRIPTS_DIR, "run_semantic_pipeline.py"),
    "experience": os.path.join(_SCRIPTS_DIR, "run_experience_pipeline.py"),
}


# ===================================================================
#                      DISCOVERY
# ===================================================================
def discover_test_resumes() -> list[str]:
    """Return sorted list of resume IDs (filename stems) from test resumes folder."""
    folder = PATHS["test_resumes"]
    if not os.path.isdir(folder):
        return []
    extensions = (".pdf", ".docx", ".doc", ".txt")
    files = [f for f in os.listdir(folder) if f.lower().endswith(extensions)]
    # Resume ID = filename without extension
    return sorted(os.path.splitext(f)[0] for f in files)


def discover_test_jds() -> list[str]:
    """Return sorted list of JD IDs from test_parsed_jds folder.
    JD ID matches the filename stem (e.g. 'backend_developer_jd_parsed_jd')."""
    folder = PATHS["test_parsed_jds"]
    if not os.path.isdir(folder):
        return []
    return sorted(
        os.path.splitext(f)[0]
        for f in os.listdir(folder)
        if f.endswith(".json")
    )


# ===================================================================
#                INTERMEDIATE-FILE CHECK (smart-skip)
# ===================================================================
def _file_exists_with_stem(folder: str, stem_substring: str) -> bool:
    """Return True if any file in folder contains stem_substring."""
    if not os.path.isdir(folder):
        return False
    return any(stem_substring in f for f in os.listdir(folder))


def has_skills(resume_id: str) -> bool:
    return _file_exists_with_stem(PATHS["skill_outputs"], resume_id)


def has_education(resume_id: str) -> bool:
    return _file_exists_with_stem(PATHS["education_outputs"], resume_id)


def has_semantic(resume_id: str) -> bool:
    return _file_exists_with_stem(PATHS["semantic_outputs"], resume_id)


def has_experience(resume_id: str, jd_id: str) -> bool:
    """Experience outputs are per (resume, JD) pair."""
    folder = PATHS["experience_outputs"]
    if not os.path.isdir(folder):
        return False
    # Look for any file containing both resume_id and jd_id
    for f in os.listdir(folder):
        if resume_id in f and jd_id.replace("_parsed_jd", "") in f:
            return True
    return False


def has_final_score(resume_id: str, jd_id: str) -> bool:
    """Final score JSON already in test_scores_out folder."""
    folder = PATHS["test_scores_out"]
    if not os.path.isdir(folder):
        return False
    needle_resume = resume_id
    needle_jd = jd_id.replace("_parsed_jd", "")
    for f in os.listdir(folder):
        if needle_resume in f and needle_jd in f and f.endswith(".json"):
            return True
    return False


# ===================================================================
#                UPSTREAM PIPELINE INVOCATION
# ===================================================================
def run_upstream_script(script_path: str, label: str) -> bool:
    """
    Invoke an upstream pipeline script via subprocess.

    These scripts process whatever resumes are configured in their own
    code (typically data/resumes/raw_resumes by default). To handle the
    test_resumes folder, the cleanest approach is one of:
       (a) Temporarily symlink test_resumes -> raw_resumes
       (b) Have you run them once with the test folder
       (c) Modify the upstream scripts to accept a --resumes-dir arg

    This populator picks option (b) by simply running the existing script
    and trusting it has been pointed at the test folder.

    If the upstream scripts are NOT already configured for test resumes,
    you'll need to run them manually with appropriate arguments. The
    populator will detect missing intermediates and warn rather than
    silently fail.
    """
    if not os.path.exists(script_path):
        logger.warning(f"Upstream script missing: {script_path}")
        return False

    logger.info(f"  → Running {label} pipeline: {os.path.basename(script_path)}")
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min max
        )
        if result.returncode != 0:
            logger.warning(f"     [{label}] exited with code {result.returncode}")
            if result.stderr:
                logger.warning(f"     stderr: {result.stderr[:500]}")
            return False
        logger.info(f"     [{label}] OK")
        return True
    except subprocess.TimeoutExpired:
        logger.error(f"     [{label}] TIMED OUT after 10 minutes")
        return False
    except Exception as e:
        logger.error(f"     [{label}] error: {e}")
        return False


def ensure_upstream_intermediates(
    resume_ids: list[str],
    jd_ids: list[str],
    skip_upstream: bool = False,
) -> tuple[set, set]:
    """
    Walk through every required intermediate file. If any are missing
    (and skip_upstream is False), trigger the relevant upstream pipeline
    scripts. Returns sets of (resumes_with_all_intermediates, missing_resumes).
    """
    logger.info("Checking intermediate files...")
    missing = {
        "skills":     [r for r in resume_ids if not has_skills(r)],
        "education":  [r for r in resume_ids if not has_education(r)],
        "semantic":   [r for r in resume_ids if not has_semantic(r)],
    }

    # Experience is per (resume, jd) pair
    missing_exp_pairs = []
    for r in resume_ids:
        for j in jd_ids:
            if not has_experience(r, j):
                missing_exp_pairs.append((r, j))
    missing["experience_pairs"] = missing_exp_pairs

    # Report
    logger.info(f"  skills:           {len(missing['skills'])}/{len(resume_ids)} missing")
    logger.info(f"  education:        {len(missing['education'])}/{len(resume_ids)} missing")
    logger.info(f"  semantic:         {len(missing['semantic'])}/{len(resume_ids)} missing")
    logger.info(f"  experience pairs: {len(missing['experience_pairs'])}/{len(resume_ids) * len(jd_ids)} missing")

    if skip_upstream:
        logger.info("--skip-upstream flag set; not running upstream pipelines.")
        return set(resume_ids), set()

    # Decide which pipelines to run
    if missing["skills"]:
        run_upstream_script(UPSTREAM_SCRIPTS["skills"], "skills")
    if missing["education"]:
        run_upstream_script(UPSTREAM_SCRIPTS["education"], "education")
    if missing["semantic"]:
        run_upstream_script(UPSTREAM_SCRIPTS["semantic"], "semantic")
    if missing["experience_pairs"]:
        run_upstream_script(UPSTREAM_SCRIPTS["experience"], "experience")

    # Re-check after running
    fully_ready = set()
    not_ready = set()
    for r in resume_ids:
        if has_skills(r) and has_education(r) and has_semantic(r):
            fully_ready.add(r)
        else:
            not_ready.add(r)
    return fully_ready, not_ready


# ===================================================================
#                      SCORING (calls your engine)
# ===================================================================
def score_pair(engine, registry, resume_id: str, jd_id: str) -> dict | None:
    """Call ATSScoringEngine.score_one() and return the result dict."""
    jd_info = registry.get(jd_id)
    if not jd_info:
        logger.warning(f"  JD '{jd_id}' not found in registry")
        return None
    try:
        return engine.score_one(resume_id, jd_id, jd_info)
    except Exception as e:
        logger.error(f"  Scoring failed for {resume_id} vs {jd_id}: {e}")
        return None


def write_score_json(result: dict, resume_id: str, jd_id: str) -> str:
    """Persist the score dict using your existing naming convention."""
    jd_short = jd_id.replace("_parsed_jd", "")
    filename = f"{resume_id}__vs__{jd_short}_scoring.json"
    out_path = os.path.join(PATHS["test_scores_out"], filename)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return out_path


# ===================================================================
#                            MAIN
# ===================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Day 17 - Populate test score JSONs from test resumes x test JDs",
    )
    parser.add_argument("--force", action="store_true",
                        help="Recompute scores even if score JSON already exists")
    parser.add_argument("--skip-upstream", action="store_true",
                        help="Don't auto-run upstream pipelines (assumes intermediates exist)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Only process the first N (resume, jd) pairs (debug)")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("Day 17 - Populate ATS Test Scores")
    logger.info("=" * 70)

    # Step 1: discover
    resume_ids = discover_test_resumes()
    jd_ids = discover_test_jds()
    logger.info(f"Resumes: {len(resume_ids)} | JDs: {len(jd_ids)} | Total pairs: {len(resume_ids) * len(jd_ids)}")

    if not resume_ids:
        logger.error(f"No resumes in {PATHS['test_resumes']}")
        return 1
    if not jd_ids:
        logger.error(
            f"No parsed test JDs in {PATHS['test_parsed_jds']}. "
            "Run: python scripts/parse_test_jds.py first."
        )
        return 1

    # Step 2: ensure intermediates exist (smart-skip)
    ready, not_ready = ensure_upstream_intermediates(
        resume_ids, jd_ids, skip_upstream=args.skip_upstream,
    )
    if not_ready:
        logger.warning(
            f"{len(not_ready)} resumes are still missing intermediates after "
            f"upstream run. They will be skipped: {sorted(list(not_ready))[:5]}..."
        )

    # Step 3: import scoring engine (deferred so smart-skip can run first)
    try:
        from ats_engine.scoring_engine import ATSScoringEngine
        from scoring.jd_registry import JDRegistry
    except ImportError as e:
        logger.error(f"Failed to import scoring engine: {e}")
        return 1

    engine = ATSScoringEngine(
        skill_outputs_dir      = PATHS["skill_outputs"],
        experience_outputs_dir = PATHS["experience_outputs"],
        education_outputs_dir  = PATHS["education_outputs"],
        semantic_outputs_dir   = PATHS["semantic_outputs"],
        ats_results_dir        = PATHS["test_scores_out"],
    )
    registry = JDRegistry(PATHS["test_parsed_jds"])
    available_jd_ids = registry.list_ids()
    logger.info(f"Loaded {len(available_jd_ids)} JDs into registry")

    # Step 4: score every pair
    pairs = [(r, j) for r in resume_ids for j in available_jd_ids]
    if args.limit:
        pairs = pairs[: args.limit]
        logger.info(f"--limit set: only processing first {len(pairs)} pairs")

    total = len(pairs)
    success = 0
    skipped = 0
    failed = 0

    logger.info(f"Scoring {total} pairs...")
    for idx, (resume_id, jd_id) in enumerate(pairs, 1):
        # Smart-skip if final score already exists
        if not args.force and has_final_score(resume_id, jd_id):
            skipped += 1
            if idx % 25 == 0:
                logger.info(f"  [{idx}/{total}] (skip cached)")
            continue

        result = score_pair(engine, registry, resume_id, jd_id)
        if result is None:
            failed += 1
            logger.warning(f"  [{idx}/{total}] FAILED: {resume_id} vs {jd_id}")
            continue

        out_path = write_score_json(result, resume_id, jd_id)
        success += 1
        if idx % 10 == 0 or idx == total:
            logger.info(
                f"  [{idx}/{total}] OK: {resume_id} vs {jd_id} "
                f"(score={result.get('final_score')})"
            )

    # Step 5: summary
    logger.info("-" * 70)
    logger.info(f"DONE  total={total}  success={success}  skipped={skipped}  failed={failed}")
    logger.info(f"Output -> {PATHS['test_scores_out']}")
    logger.info("Next: python scripts/run_ats_testing.py --scaffold-hr")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
