"""
scripts/run_ats_scoring.py
──────────────────────────
ATS Day 13 – Main scoring pipeline.

Reads from:
  data/extracted_skills/     → *__skills.json
  data/education_outputs/    → *__sections.json
  data/experience_outputs/   → *__vs_*_experience.json
  data/semantic_outputs/     → *__sections_semantic.json

Writes to:
  ats_results/ats_scores/{resume_id}__vs_{jd_slug}__ats_score.json
  ats_results/ats_scores/{resume_id}__vs_{jd_slug}__ats_report.md
  ats_results/ats_scores/batch_leaderboard.json
  ats_results/ats_scores/batch_leaderboard.md

Usage
─────
# from project root (ai_job_portal_system/)
python scripts/run_ats_scoring.py
python scripts/run_ats_scoring.py --resume Amala_Resume_DS_DA_2026
python scripts/run_ats_scoring.py --verbose
python scripts/run_ats_scoring.py --audit          # show file discovery only
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# ── Allow imports from project root ──────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ats_engine.data_loader  import ATSDataLoader
from ats_engine.ats_scorer   import ATSScorer, WEIGHT_PROFILES
from ats_engine.result_writer import (
    write_json, write_markdown, write_batch_leaderboard,
    print_score_report, print_leaderboard,
)
from ats_engine.weight_config import detect_role_type, build_jd_config

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("run_ats_scoring")

# ── Output directory ──────────────────────────────────────────────────────────
OUT_DIR = ROOT / "ats_results" / "ats_scores"


# ════════════════════════════════════════════════════════════════
#  JD CONFIGURATION REGISTRY
# ════════════════════════════════════════════════════════════════
# Maps jd_slug → scoring parameters.
# Add new JDs here to support additional job descriptions.

JD_CONFIGS: dict[str, dict] = {
    "ai_specialist_in_healthcare_analytics_parsed_jd": build_jd_config(
        job_title            = "AI Specialist in Healthcare Analytics",
        jd_id                = "ai_specialist_in_healthcare_analytics_parsed_jd",
        required_skills      = ["python", "machine learning", "sql", "data analysis", "nlp"],
        preferred_skills     = ["deep learning", "tensorflow", "healthcare", "llm",
                                "feature engineering", "scikit-learn"],
        target_years         = 3.0,
        role_keywords        = ["data", "analyst", "scientist", "engineer", "ai"],
        preferred_degrees    = ["msc", "mtech", "phd", "mba"],
        preferred_fields     = ["computer science", "data science", "statistics",
                                "healthcare", "finance"],
        min_cert_count       = 1,
        weight_profile       = "healthcare_analytics",
    ),
    "healthcare_machine_learning_engineer_parsed_jd": build_jd_config(
        job_title            = "Healthcare Machine Learning Engineer",
        jd_id                = "healthcare_machine_learning_engineer_parsed_jd",
        required_skills      = ["python", "machine learning", "tensorflow", "deep learning",
                                "scikit-learn", "sql"],
        preferred_skills     = ["mlops", "docker", "kubernetes", "aws", "data pipeline"],
        target_years         = 4.0,
        role_keywords        = ["machine learning", "engineer", "ml", "data"],
        preferred_degrees    = ["mtech", "msc", "phd"],
        preferred_fields     = ["computer science", "data science", "engineering"],
        min_cert_count       = 1,
        weight_profile       = "ml_engineering",
    ),
    # Fallback / default
    "default": build_jd_config(
        job_title            = "Data Science / Analytics Role",
        jd_id                = "default",
        required_skills      = ["python", "sql", "data analysis"],
        preferred_skills     = ["machine learning", "statistics"],
        target_years         = 3.0,
        role_keywords        = ["data", "analyst", "scientist"],
        preferred_degrees    = ["msc", "mba", "btech"],
        preferred_fields     = ["computer science", "statistics", "data science"],
        min_cert_count       = 0,
        weight_profile       = "default",
    ),
}


def get_jd_config(jd_slug: str) -> dict:
    """Return JD config for a slug, falling back to partial match or default."""
    if jd_slug in JD_CONFIGS:
        return JD_CONFIGS[jd_slug]
    # Try partial / normalised match
    slug_norm = jd_slug.replace("-", "_").lower()
    for key in JD_CONFIGS:
        if key.replace("-", "_").lower() in slug_norm or slug_norm in key.replace("-", "_").lower():
            log.info("JD config partial match: '%s' → '%s'", jd_slug, key)
            return JD_CONFIGS[key]
    log.warning("No JD config for '%s', using default", jd_slug)
    cfg = JD_CONFIGS["default"].copy()
    cfg["jd_id"] = jd_slug
    return cfg


# ════════════════════════════════════════════════════════════════
#  PIPELINE
# ════════════════════════════════════════════════════════════════

def run_single(
    resume_id:  str,
    jd_slug:    str,
    root:       Path = ROOT,
    verbose:    bool = False,
    no_export:  bool = False,
) -> None:
    log.info("Loading: %s vs %s", resume_id, jd_slug)
    loader = ATSDataLoader(root)
    cdata  = loader.load_one(resume_id, jd_slug)

    jd_cfg  = get_jd_config(jd_slug)
    profile = jd_cfg.get("weight_profile", detect_role_type(jd_cfg.get("job_title","")))
    scorer  = ATSScorer(weight_profile=profile)

    result  = scorer.score(
        cdata,
        job_title            = jd_cfg["job_title"],
        jd_required_skills   = jd_cfg.get("required_skills"),
        jd_preferred_skills  = jd_cfg.get("preferred_skills"),
        target_years         = jd_cfg.get("target_years", 3.0),
        role_keywords        = jd_cfg.get("role_keywords"),
        preferred_degrees    = jd_cfg.get("preferred_degrees"),
        preferred_fields     = jd_cfg.get("preferred_fields"),
        min_cert_count       = jd_cfg.get("min_cert_count", 0),
    )

    print_score_report(result, verbose=verbose)

    if not no_export:
        jp = write_json(result, OUT_DIR)
        mp = write_markdown(result, OUT_DIR)
        print(f"  [JSON]     {jp}")
        print(f"  [Markdown] {mp}\n")


def run_batch(
    root:      Path = ROOT,
    verbose:   bool = False,
    no_export: bool = False,
) -> None:
    loader = ATSDataLoader(root)
    all_cdata = loader.load_all()

    if not all_cdata:
        log.error("No candidates found. Check data directories.")
        return

    log.info("Scoring %d candidate×JD pair(s)...", len(all_cdata))
    all_results = []

    for cdata in all_cdata:
        jd_cfg  = get_jd_config(cdata.jd_slug)
        profile = jd_cfg.get("weight_profile", detect_role_type(jd_cfg.get("job_title","")))
        scorer  = ATSScorer(weight_profile=profile)

        result = scorer.score(
            cdata,
            job_title            = jd_cfg["job_title"],
            jd_required_skills   = jd_cfg.get("required_skills"),
            jd_preferred_skills  = jd_cfg.get("preferred_skills"),
            target_years         = jd_cfg.get("target_years", 3.0),
            role_keywords        = jd_cfg.get("role_keywords"),
            preferred_degrees    = jd_cfg.get("preferred_degrees"),
            preferred_fields     = jd_cfg.get("preferred_fields"),
            min_cert_count       = jd_cfg.get("min_cert_count", 0),
        )
        all_results.append(result)

        if verbose:
            print_score_report(result, verbose=True)

        if not no_export:
            write_json(result, OUT_DIR)
            write_markdown(result, OUT_DIR)

    print_leaderboard(all_results)

    if not no_export:
        jp, mp = write_batch_leaderboard(all_results, OUT_DIR)
        print(f"  [Leaderboard JSON] {jp}")
        print(f"  [Leaderboard MD]   {mp}\n")


# ════════════════════════════════════════════════════════════════
#  CLI
# ════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ATS Day 13 – Scoring Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_ats_scoring.py                          # batch all
  python scripts/run_ats_scoring.py --resume Amala_Resume_DS_DA_2026
  python scripts/run_ats_scoring.py --verbose
  python scripts/run_ats_scoring.py --audit
        """,
    )
    parser.add_argument("--resume", "-r", help="Score a single resume_id")
    parser.add_argument("--jd",          default=None,
                        help="JD slug (auto-detected from experience filename if omitted)")
    parser.add_argument("--verbose","-v", action="store_true",
                        help="Print full evidence trail")
    parser.add_argument("--no-export",   action="store_true",
                        help="Skip writing output files")
    parser.add_argument("--audit",       action="store_true",
                        help="Show file discovery audit and exit")
    parser.add_argument("--root",        default=str(ROOT),
                        help=f"Project root (default: {ROOT})")
    args = parser.parse_args()

    root = Path(args.root)

    if args.audit:
        ATSDataLoader(root).audit()
        return

    if args.resume:
        # Auto-discover JD slug if not given
        jd_slug = args.jd
        if not jd_slug:
            loader = ATSDataLoader(root)
            cfs    = loader.discover_candidates()
            match  = [c for c in cfs if c.resume_id == args.resume]
            if not match:
                log.error("resume_id '%s' not found", args.resume)
                sys.exit(1)
            jd_slug = match[0].jd_slug
        run_single(args.resume, jd_slug, root, args.verbose, args.no_export)
    else:
        run_batch(root, args.verbose, args.no_export)


if __name__ == "__main__":
    main()
