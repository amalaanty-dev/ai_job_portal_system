"""
ranking_config.py
------------------
Central configuration for the Candidate Ranking & Shortlisting Engine.

Defines:
  - Score thresholds (shortlist / review / reject zones)
  - Weightage for composite scoring across 5 dimensions:
        skill_score, experience_score, education_score, semantic_score, ats_score
  - Default top-N cutoff
  - Role-specific overrides (MERN, UI/UX, Sales Executive, etc.)

PRD Reference: Day 14 - Candidate Ranking & Shortlisting

Two scoring modes are supported by run_ranking.py:
  * PASS-THROUGH (default): Use Day 13's pre-computed final_score directly.
                            These weights are NOT used for ranking, only
                            recorded in the audit trail.
  * RECOMPUTE  (--recompute): Re-weight the four sub-scores using these
                              weights (skill, experience, education, semantic).
                              `ats_score` is excluded in this mode because
                              it IS the composite we are recomputing.
"""

from pathlib import Path

# ---------------------------------------------------------------------
# PROJECT PATHS (relative to ai_job_portal_system/)
# ---------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Input: Day 13 ATS scoring results
INPUT_DIR = PROJECT_ROOT / "ats_results" / "ats_scores"

# Output: Day 14 ranking + shortlisting artifacts
OUTPUT_DIR = PROJECT_ROOT / "ranking_engine_results"
RANKED_DIR = OUTPUT_DIR / "ranked"
SHORTLISTED_DIR = OUTPUT_DIR / "shortlisted"
REVIEW_DIR = OUTPUT_DIR / "review"
REJECTED_DIR = OUTPUT_DIR / "rejected"
REPORTS_DIR = OUTPUT_DIR / "reports"

LOG_DIR = PROJECT_ROOT / "logs"

# ---------------------------------------------------------------------
# SCORING WEIGHTS  (used only in --recompute mode; must sum to 1.0)
# ---------------------------------------------------------------------
# Mirrors Day 13's default weight strategy:
#   skills 35 | experience 30 | education 15 | semantic 20
DEFAULT_WEIGHTS = {
    "skill_score":      0.35,
    "experience_score": 0.30,
    "education_score":  0.15,
    "semantic_score":   0.20,
}

# ---------------------------------------------------------------------
# SHORTLISTING THRESHOLDS (0 - 100 scale)
# ---------------------------------------------------------------------
# Aligned with Day 13's score_band interpretation:
#   80-100 = Strong/Good Fit  -> shortlist
#   60-79  = Partial Fit      -> review (manual)
#   <60                       -> reject
THRESHOLDS = {
    "shortlist": 70.0,   # auto-shortlist (Day 13 "Good Fit" boundary)
    "review":    50.0,   # review zone (Day 13 "Partial Fit" boundary)
}

# Top-N candidates featured in the recruiter's top_candidates report
DEFAULT_TOP_N = 10

# ---------------------------------------------------------------------
# HARD FILTERS (applied BEFORE scoring; any failure -> auto-reject)
# ---------------------------------------------------------------------
HARD_FILTERS = {
    "min_experience_years": 0,
    "required_skills":      [],
    "blocked_reason_tag":   "hard_filter_failed",
}

# ---------------------------------------------------------------------
# ROLE-SPECIFIC OVERRIDES
# ---------------------------------------------------------------------
ROLE_OVERRIDES = {
    "mern_stack_developer": {
        "weights": {
            "skill_score":      0.45,
            "experience_score": 0.25,
            "education_score":  0.10,
            "semantic_score":   0.20,
        },
        "thresholds": {"shortlist": 75.0, "review": 55.0},
    },
    "ui_ux_designer": {
        "weights": {
            "skill_score":      0.40,
            "experience_score": 0.25,
            "education_score":  0.10,
            "semantic_score":   0.25,
        },
        "thresholds": {"shortlist": 72.0, "review": 50.0},
    },
    "sales_executive": {
        "weights": {
            "skill_score":      0.20,
            "experience_score": 0.45,
            "education_score":  0.10,
            "semantic_score":   0.25,
        },
        "thresholds": {"shortlist": 70.0, "review": 50.0},
    },
    "ai_specialist_in_healthcare_analytics": {
        "weights": {
            "skill_score":      0.40,
            "experience_score": 0.30,
            "education_score":  0.15,
            "semantic_score":   0.15,
        },
        "thresholds": {"shortlist": 70.0, "review": 50.0},
    },
}


def get_config_for_role(job_role: str | None) -> dict:
    """Return weights + thresholds for a given job_role, falling back to defaults."""
    key = (job_role or "").strip().lower().replace(" ", "_").replace("-", "_")
    override = ROLE_OVERRIDES.get(key, {})
    config = {
        "weights":    {**DEFAULT_WEIGHTS, **override.get("weights", {})},
        "thresholds": {**THRESHOLDS, **override.get("thresholds", {})},
        "role_key":   key or "default",
    }
    _validate_config(config)
    return config


def get_output_paths(root: Path) -> dict[str, Path]:
    """Return the standard ranking-engine output subpath mapping under `root`."""
    root = Path(root)
    return {
        "ranked":      root / "ranked",
        "shortlisted": root / "shortlisted",
        "review":      root / "review",
        "rejected":    root / "rejected",
        "reports":     root / "reports",
    }


def _validate_config(config: dict) -> None:
    """Guardrails: weights sum to 1.0, thresholds are ordered, scores in [0,100]."""
    weight_sum = sum(config["weights"].values())
    if abs(weight_sum - 1.0) > 1e-6:
        raise ValueError(
            f"Weights for role={config['role_key']!r} must sum to 1.0, got {weight_sum}"
        )
    th = config["thresholds"]
    if not (0 <= th["review"] <= th["shortlist"] <= 100):
        raise ValueError(
            f"Invalid thresholds for role={config['role_key']!r}: "
            f"need 0 <= review ({th['review']}) <= shortlist ({th['shortlist']}) <= 100"
        )
