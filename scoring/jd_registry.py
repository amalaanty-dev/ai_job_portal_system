"""
JD Registry — Day 13
Zecpath AI Job Portal

Loads Job Descriptions from: data/job_descriptions/parsed_jd/
Each JD file must be a JSON with at minimum a "job_role" (or "title") field.

Supports:
  - Auto-loading all JDs from the parsed_jd folder (primary)
  - Built-in fallback JDs if folder is empty
  - Manual add/get by jd_id
  - save_to_dir() for exporting

JD JSON expected keys (any subset is fine):
  {
    "job_role": "Data Analyst",          <- or "title"
    "required_skills": [...],
    "preferred_skills": [...],
    "min_experience_years": 1,
    "max_experience_years": 4,
    "required_education": "B.Tech",
    "preferred_fields": [...],
    "required_roles": [...],
    "keywords": [...]
  }
"""

import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default JD folder path
# ---------------------------------------------------------------------------
DEFAULT_JD_DIR = os.path.join("data", "job_descriptions", "parsed_jd")

# ---------------------------------------------------------------------------
# Fallback built-in JDs (used only when parsed_jd folder is empty or missing)
# ---------------------------------------------------------------------------
BUILTIN_JDS: dict = {
    "JD_Data_Analyst_001": {
        "job_role": "Data Analyst",
        "required_skills": ["Python", "SQL", "Excel", "Tableau", "Power BI", "Data Analysis"],
        "preferred_skills": ["Pandas", "NumPy", "Matplotlib", "Seaborn", "R", "ETL"],
        "min_experience_years": 1, "max_experience_years": 4,
        "required_education": "B.Tech",
        "preferred_fields": ["Computer Science", "Statistics", "Mathematics"],
        "required_roles": ["analyst", "data analyst", "business analyst"],
        "keywords": ["sql", "python", "data visualization", "dashboard", "analytics", "excel"],
    },
    "JD_MERN_Developer_001": {
        "job_role": "MERN Stack Developer",
        "required_skills": ["MongoDB", "Express.js", "React", "Node.js", "JavaScript"],
        "preferred_skills": ["TypeScript", "Redux", "REST API", "GraphQL", "Docker", "AWS"],
        "min_experience_years": 2, "max_experience_years": 5,
        "required_education": "B.Tech",
        "preferred_fields": ["Computer Science", "Information Technology"],
        "required_roles": ["developer", "mern developer", "full stack developer"],
        "keywords": ["react", "node", "express", "mongodb", "javascript", "rest api"],
    },
    "JD_ML_Engineer_001": {
        "job_role": "Machine Learning Engineer",
        "required_skills": ["Python", "TensorFlow", "PyTorch", "Scikit-learn", "Machine Learning"],
        "preferred_skills": ["Deep Learning", "NLP", "Computer Vision", "MLOps"],
        "min_experience_years": 2, "max_experience_years": 6,
        "required_education": "M.Tech",
        "preferred_fields": ["Computer Science", "AI", "Data Science"],
        "required_roles": ["ml engineer", "machine learning engineer", "ai engineer"],
        "keywords": ["machine learning", "deep learning", "python", "tensorflow", "pytorch"],
    },
    "JD_UI_UX_Designer_001": {
        "job_role": "UI/UX Designer",
        "required_skills": ["Figma", "Adobe XD", "Wireframing", "Prototyping", "User Research"],
        "preferred_skills": ["Sketch", "InVision", "HTML", "CSS", "Design Systems"],
        "min_experience_years": 1, "max_experience_years": 4,
        "required_education": "B.Tech",
        "preferred_fields": ["Design", "Computer Science", "Human Computer Interaction"],
        "required_roles": ["ui designer", "ux designer", "product designer"],
        "keywords": ["figma", "wireframe", "prototype", "user research", "ui design"],
    },
    "JD_Sales_Executive_001": {
        "job_role": "Sales Executive",
        "required_skills": ["Sales", "CRM", "Communication", "Negotiation", "Lead Generation"],
        "preferred_skills": ["Salesforce", "HubSpot", "B2B Sales", "Cold Calling"],
        "min_experience_years": 0, "max_experience_years": 3,
        "required_education": "B.Com",
        "preferred_fields": ["Business Administration", "Marketing", "Commerce"],
        "required_roles": ["sales executive", "business development", "sales representative"],
        "keywords": ["sales", "lead generation", "crm", "client acquisition", "negotiation"],
    },
    "JD_DevOps_Engineer_001": {
        "job_role": "DevOps Engineer",
        "required_skills": ["Docker", "Kubernetes", "CI/CD", "Linux", "AWS", "Terraform"],
        "preferred_skills": ["Ansible", "Jenkins", "GitHub Actions", "Grafana"],
        "min_experience_years": 2, "max_experience_years": 6,
        "required_education": "B.Tech",
        "preferred_fields": ["Computer Science", "Information Technology"],
        "required_roles": ["devops engineer", "sre", "cloud engineer"],
        "keywords": ["docker", "kubernetes", "ci/cd", "aws", "terraform", "pipeline"],
    },
}


class JDRegistry:
    """
    Manages Job Description data for the ATS Scoring Engine.

    Primary source: data/job_descriptions/parsed_jd/*.json
    Fallback:       BUILTIN_JDS (when folder is empty or missing)
    """

    def __init__(self, jd_dir: Optional[str] = None):
        self._registry: dict = {}
        resolved_dir = jd_dir or DEFAULT_JD_DIR

        # Try to load from the parsed_jd folder first
        loaded = self._load_from_dir(resolved_dir)

        if not self._registry:
            # Folder missing or empty — use built-ins and warn
            logger.warning(
                "No JD files found in: %s\n"
                "  Using %d built-in fallback JDs.\n"
                "  To use your own JDs, place parsed JSON files in that folder.",
                os.path.abspath(resolved_dir),
                len(BUILTIN_JDS),
            )
            self._registry = dict(BUILTIN_JDS)
        else:
            logger.info(
                "Loaded %d JD(s) from: %s",
                loaded, os.path.abspath(resolved_dir),
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_all(self) -> dict:
        """Return the full JD registry dict."""
        return self._registry

    def get(self, jd_id: str) -> Optional[dict]:
        """Return a single JD by its ID."""
        return self._registry.get(jd_id)

    def add(self, jd_id: str, jd_data: dict):
        """Add or overwrite a JD entry."""
        self._registry[jd_id] = jd_data
        logger.info("Added JD: %s", jd_id)

    def list_ids(self) -> list:
        """Return all JD IDs."""
        return list(self._registry.keys())

    def save_to_dir(self, jd_dir: str):
        """Export all loaded JDs as individual JSON files."""
        os.makedirs(jd_dir, exist_ok=True)
        for jd_id, jd_data in self._registry.items():
            path = os.path.join(jd_dir, f"{jd_id}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(jd_data, f, indent=2, ensure_ascii=False)
        logger.info("Saved %d JDs to: %s", len(self._registry), jd_dir)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_from_dir(self, jd_dir: str) -> int:
        """
        Load all *.json files from jd_dir into the registry.
        File stem (name without .json) becomes the jd_id.

        JD files may store job_role under "job_role", "title", or "role".
        We normalise to always store under "job_role".

        Returns count of successfully loaded JDs.
        """
        abs_dir = os.path.abspath(jd_dir)
        if not os.path.isdir(abs_dir):
            logger.warning("JD folder not found: %s", abs_dir)
            return 0

        loaded = 0
        for fname in sorted(os.listdir(abs_dir)):
            if not fname.endswith(".json"):
                continue
            jd_id = fname[:-5]   # strip .json
            path  = os.path.join(abs_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Normalise job_role — always store as a plain string
                raw_role = (
                    data.get("job_role")
                    or data.get("title")
                    or data.get("role")
                    or data.get("job_title")
                    or jd_id.replace("_", " ").title()
                )
                # Some JDs store job_role as a list — take first element
                if isinstance(raw_role, list):
                    raw_role = raw_role[0] if raw_role else jd_id.replace("_", " ").title()
                data["job_role"] = str(raw_role).strip()

                # Ensure required list fields exist (default to empty list)
                for list_field in (
                    "required_skills", "preferred_skills",
                    "preferred_fields", "required_roles", "keywords",
                ):
                    if list_field not in data:
                        data[list_field] = []

                self._registry[jd_id] = data
                loaded += 1

            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Failed to load JD file %s: %s", path, exc)

        return loaded
