"""
Weight Configuration — Day 13
Zecpath AI Job Portal

Dynamic, role-based weight system for ATS scoring.
Each role maps to a strategy; each strategy defines percentage weights
that always sum to 100.

Strategies:
  fresher     — heavier education & skills, lighter experience
  mid_level   — balanced; standard for most roles
  senior      — heavier experience & semantic, lighter education
  technical   — heavier skills & semantic
  non_tech    — heavier experience & education
  custom      — caller provides explicit weights
"""

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Strategy Weight Profiles  (must sum to 100)
# ---------------------------------------------------------------------------
WEIGHT_PROFILES: dict[str, dict] = {
    "fresher": {
        "skills": 35,
        "experience": 10,
        "education": 35,
        "semantic": 20,
    },
    "mid_level": {
        "skills": 35,
        "experience": 30,
        "education": 15,
        "semantic": 20,
    },
    "senior": {
        "skills": 30,
        "experience": 40,
        "education": 10,
        "semantic": 20,
    },
    "technical": {
        "skills": 45,
        "experience": 25,
        "education": 10,
        "semantic": 20,
    },
    "non_tech": {
        "skills": 20,
        "experience": 40,
        "education": 20,
        "semantic": 20,
    },
    "default": {
        "skills": 35,
        "experience": 30,
        "education": 15,
        "semantic": 20,
    },
}

# ---------------------------------------------------------------------------
# Role → Strategy Mapping
# ---------------------------------------------------------------------------
ROLE_STRATEGY_MAP: dict[str, str] = {
    # Technical roles
    "mern stack developer": "technical",
    "frontend developer": "technical",
    "backend developer": "technical",
    "full stack developer": "technical",
    "software engineer": "technical",
    "data engineer": "technical",
    "devops engineer": "technical",
    "cloud engineer": "technical",
    "machine learning engineer": "technical",
    "ai engineer": "technical",
    "data scientist": "technical",

    # Analyst / Data roles
    "data analyst": "mid_level",
    "business analyst": "mid_level",
    "product analyst": "mid_level",
    "bi analyst": "mid_level",

    # Design / Creative
    "ui/ux designer": "mid_level",
    "graphic designer": "mid_level",
    "product designer": "mid_level",

    # Non-technical / Sales
    "sales executive": "non_tech",
    "business development executive": "non_tech",
    "marketing executive": "non_tech",
    "hr executive": "non_tech",
    "recruiter": "non_tech",
    "customer support": "non_tech",

    # Senior / Leadership
    "senior software engineer": "senior",
    "tech lead": "senior",
    "engineering manager": "senior",
    "project manager": "senior",
    "product manager": "senior",

    # Fresher / Internship
    "fresher": "fresher",
    "intern": "fresher",
    "graduate trainee": "fresher",
    "junior developer": "fresher",
}


class WeightConfig:
    """Provides weight strategy resolution for any job role."""

    def get_strategy(self, job_role) -> str:
        """Map a job role string to the nearest strategy name.
        Safely handles list, None, int or any non-string value from JD JSON.
        """
        # Normalise to string — handles list, None, int, etc.
        if isinstance(job_role, list):
            job_role = job_role[0] if job_role else "unknown"
        if not job_role or not isinstance(job_role, str):
            job_role = "unknown"
        role_lower = job_role.lower().strip()

        # Exact match
        if role_lower in ROLE_STRATEGY_MAP:
            return ROLE_STRATEGY_MAP[role_lower]

        # Partial match
        for key, strategy in ROLE_STRATEGY_MAP.items():
            if key in role_lower or role_lower in key:
                return strategy

        # Keyword-based fallback
        if any(kw in role_lower for kw in ["senior", "lead", "head", "director", "manager"]):
            return "senior"
        if any(kw in role_lower for kw in ["intern", "fresher", "trainee", "junior", "entry"]):
            return "fresher"
        if any(kw in role_lower for kw in [
            "developer", "engineer", "devops", "cloud", "architect", "qa", "sre"
        ]):
            return "technical"
        if any(kw in role_lower for kw in ["sales", "marketing", "hr", "support", "executive"]):
            return "non_tech"

        logger.warning("No strategy found for role '%s'. Using 'default'.", job_role)
        return "default"

    def get_weights(self, strategy: str) -> dict:
        """Return weight dict for a given strategy."""
        weights = WEIGHT_PROFILES.get(strategy, WEIGHT_PROFILES["default"])
        assert sum(weights.values()) == 100, f"Weights for '{strategy}' do not sum to 100!"
        return dict(weights)  # Return a copy

    def get_custom_weights(
        self,
        skills: int,
        experience: int,
        education: int,
        semantic: int,
    ) -> dict:
        """Build custom weights. Raises ValueError if they don't sum to 100."""
        total = skills + experience + education + semantic
        if total != 100:
            raise ValueError(
                f"Custom weights must sum to 100. Got {total} "
                f"(skills={skills}, exp={experience}, edu={education}, sem={semantic})"
            )
        return {
            "skills": skills,
            "experience": experience,
            "education": education,
            "semantic": semantic,
        }

    def list_strategies(self) -> dict:
        """Return all available strategies and their weights."""
        return dict(WEIGHT_PROFILES)

    def list_role_mappings(self) -> dict:
        """Return the full role→strategy mapping."""
        return dict(ROLE_STRATEGY_MAP)
