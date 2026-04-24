"""
ATS Scoring Engine — Day 13
Zecpath AI Job Portal

Compares every resume against every Job Description using:
  - Skill Match          (data/extracted_skills/)
  - Experience Relevance (data/experience_outputs/)
  - Education Alignment  (data/education_outputs/)
  - Semantic Similarity  (data/semantic_outputs/)

Actual filename patterns observed in Zecpath project:

  SKILLS      : {candidate_id}_skills.json
                e.g. Resume_4_Medical_Data_Analyst_skills.json
                e.g. Amala_Resume_DS_DA_2026__skills.json

  EDUCATION   : {candidate_id}_sections.json
                e.g. Amala_Resume_DS_DA_2026__sections.json
                (contains `education_data` + `education_relevance_score`)

  EXPERIENCE  : {candidate_id}__vs_{jd_id}_experience.json   <- per-JD!
                e.g. Amala_Resume_DS_DA_2026__vs_Clinical_Data_Analyst_parsed_jd_experience.json

  SEMANTIC    : {candidate_id}_sections_semantic.json        <- one per candidate, contains
                all JDs pre-scored in `all_matches[]`
                e.g. Resume_7_Health_Informatics_Analyst_sections_semantic.json
"""

import json
import os
import re
import logging
from datetime import datetime
from typing import Optional

from ats_engine.weight_config     import WeightConfig
from ats_engine.score_calculator  import ScoreCalculator
from ats_engine.missing_data_handler import MissingDataHandler
from ats_engine.score_interpreter import ScoreInterpreter

logger = logging.getLogger(__name__)


# ============================================================================
# Filename normalisation — maps all candidate filename variants to one key
# ============================================================================

# Section-name suffixes: these differ across folders and must be stripped FIRST
_SECTION_SUFFIXES = (
    "_sections_semantic", "_semantic_sections",
    "_sections", "_section",
    "__skills", "_skills", "__skill", "_skill",
    "__experience", "_experience", "__exp", "_exp",
    "__education", "_education", "__edu", "_edu",
    "__semantic", "_semantic", "__sem", "_sem",
)

# Generic role/doc suffixes
_GENERIC_SUFFIXES = (
    "_resume", "_cv", "_profile",
    "_dataanalyst", "_data_analyst", "_da",
    "_mern", "_developer", "_engineer",
    "_ds", "_ml", "_ai",
)


def _normalise_id(name: str) -> str:
    """
    Normalise filename stem to a stable key for cross-folder matching.

    E.g. all of these normalise to 'amalaresumedsda':
      'Amala_Resume_DS_DA_2026__skills'
      'Amala_Resume_DS_DA_2026__sections'
      'Amala_Resume_DS_DA_2026__sections_semantic'
      'Amala_Resume_DS_DA_2026'
    """
    n = name.lower().strip()

    # Strip __vs_{jd_id}_experience (per-JD experience files)
    n = re.sub(r"__vs_.+?_experience$", "", n)
    n = re.sub(r"_vs_.+?_experience$", "", n)

    # Strip section-name suffixes (iteratively)
    changed = True
    while changed:
        changed = False
        for suf in _SECTION_SUFFIXES:
            if n.endswith(suf):
                n = n[: -len(suf)]
                changed = True

    # Strip year suffix
    n = re.sub(r"_20\d{2}$", "", n)

    # Strip generic suffixes
    changed = True
    while changed:
        changed = False
        for suf in _GENERIC_SUFFIXES:
            if n.endswith(suf):
                n = n[: -len(suf)]
                changed = True

    # Strip trailing year/underscores again and non-alphanumerics
    n = re.sub(r"_20\d{2}$", "", n)
    n = n.rstrip("_ -")
    n = re.sub(r"[^a-z0-9]", "", n)
    return n


def _jd_matches_filename(jd_id: str, filename: str) -> bool:
    """Check if a filename contains a given JD id (case-insensitive, fuzzy)."""
    jd_n   = re.sub(r"[^a-z0-9]", "", jd_id.lower())
    file_n = re.sub(r"[^a-z0-9]", "", filename.lower())
    return bool(jd_n) and jd_n in file_n


# ============================================================================
# ATS Scoring Engine
# ============================================================================

class ATSScoringEngine:
    """
    Core ATS Scoring Engine for the Zecpath platform.

    For every candidate discovered in data/extracted_skills/:
      1. Fuzzy-find the corresponding experience, education, semantic files
      2. Score against every JD using the 4 dimensions
      3. Apply dynamic role-based weights
      4. Redistribute weights for any missing sections
      5. Produce explainable JSON output per (candidate, JD) pair
    """

    VERSION = "v1.0"

    DEFAULT_SKILL_DIR   = os.path.join("data", "extracted_skills")
    DEFAULT_EXP_DIR     = os.path.join("data", "experience_outputs")
    DEFAULT_EDU_DIR     = os.path.join("data", "education_outputs")
    DEFAULT_SEM_DIR     = os.path.join("data", "semantic_outputs")
    DEFAULT_RESULTS_DIR = os.path.join("ats_results", "ats_scores")

    def __init__(
        self,
        skill_outputs_dir:      str = None,
        experience_outputs_dir: str = None,
        education_outputs_dir:  str = None,
        semantic_outputs_dir:   str = None,
        ats_results_dir:        str = None,
    ):
        self.skill_outputs_dir      = skill_outputs_dir      or self.DEFAULT_SKILL_DIR
        self.experience_outputs_dir = experience_outputs_dir or self.DEFAULT_EXP_DIR
        self.education_outputs_dir  = education_outputs_dir  or self.DEFAULT_EDU_DIR
        self.semantic_outputs_dir   = semantic_outputs_dir   or self.DEFAULT_SEM_DIR
        self.ats_results_dir        = ats_results_dir        or self.DEFAULT_RESULTS_DIR

        self.weight_config   = WeightConfig()
        self.calculator      = ScoreCalculator()
        self.missing_handler = MissingDataHandler()
        self.interpreter     = ScoreInterpreter()

        os.makedirs(self.ats_results_dir, exist_ok=True)

        # Pre-build file indexes for each section (fuzzy matching)
        self._build_file_indexes()
        self._log_startup_diagnostics()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score_all(self, jd_registry: dict) -> list:
        """Score every candidate x every JD."""
        candidates = self._discover_candidates()
        if not candidates:
            logger.error("No candidates found in: %s",
                         os.path.abspath(self.skill_outputs_dir))
            return []

        if not jd_registry:
            logger.error("JD registry is empty.")
            return []

        logger.info(
            "Scoring %d candidate(s) x %d JD(s) = %d total pairs",
            len(candidates), len(jd_registry),
            len(candidates) * len(jd_registry),
        )

        results = []
        for candidate_id in candidates:
            for jd_id, jd_info in jd_registry.items():
                # Ensure JD info carries its own id so semantic lookup works
                jd_info_with_id = dict(jd_info)
                jd_info_with_id.setdefault("jd_id", jd_id)
                r = self.score_one(candidate_id, jd_id, jd_info_with_id)
                if r:
                    results.append(r)

        logger.info("Scoring complete. %d results generated.", len(results))
        return results

    def score_one(self, candidate_id: str, jd_id: str, jd_info: dict) -> Optional[dict]:
        """Score a single candidate against a single JD."""
        # Normalise job_role (may be list, dict, etc.)
        raw_role = (
            jd_info.get("job_role")
            or jd_info.get("title")
            or jd_info.get("role")
            or "Unknown"
        )
        if isinstance(raw_role, list):
            raw_role = raw_role[0] if raw_role else "Unknown"
        if isinstance(raw_role, dict):
            raw_role = raw_role.get("name") or raw_role.get("title") or "Unknown"
        job_role = str(raw_role).strip() if raw_role else "Unknown"

        # Ensure JD id is carried inside jd_info for semantic matching
        jd_info = dict(jd_info)
        jd_info.setdefault("jd_id", jd_id)

        # Load all 4 sections with fuzzy matching
        skill_data = self._load_section(self.skill_outputs_dir,      candidate_id, "skills",     jd_id)
        exp_data   = self._load_section(self.experience_outputs_dir, candidate_id, "experience", jd_id)
        edu_data   = self._load_section(self.education_outputs_dir,  candidate_id, "education",  jd_id)
        sem_data   = self._load_section(self.semantic_outputs_dir,   candidate_id, "semantic",   jd_id)

        # Missing sections → weight redistribution
        section_map = {
            "skills":     skill_data,
            "experience": exp_data,
            "education":  edu_data,
            "semantic":   sem_data,
        }
        missing_sections = [k for k, v in section_map.items() if v is None]

        strategy = self.weight_config.get_strategy(job_role)
        weights  = self.weight_config.get_weights(strategy)
        adjusted_weights, redistributed, redistribution_strategy = (
            self.missing_handler.handle(weights, missing_sections)
        )

        # Calculate individual dimension scores
        skill_score = self.calculator.skill_score(skill_data, jd_info)     if skill_data else 0
        exp_score   = self.calculator.experience_score(exp_data, jd_info)  if exp_data   else 0
        edu_score   = self.calculator.education_score(edu_data, jd_info)   if edu_data   else 0
        sem_score   = self.calculator.semantic_score(sem_data, jd_info)    if sem_data   else 0

        contributions = {
            "skills":     round(skill_score * adjusted_weights["skills"]     / 100, 2),
            "experience": round(exp_score   * adjusted_weights["experience"] / 100, 2),
            "education":  round(edu_score   * adjusted_weights["education"]  / 100, 2),
            "semantic":   round(sem_score   * adjusted_weights["semantic"]   / 100, 2),
        }
        final_score = round(sum(contributions.values()), 2)
        interpretation = self.interpreter.interpret(final_score, job_role)

        result = {
            "identifiers": {
                "resume_id": candidate_id,
                "jd_id":     jd_id,
                "job_role":  job_role,
            },
            "final_score": final_score,
            "scoring_breakdown": {
                "skill_match":          skill_score,
                "experience_relevance": exp_score,
                "education_alignment":  edu_score,
                "semantic_similarity":  sem_score,
            },
            "weights": {
                "skills":          adjusted_weights["skills"],
                "experience":      adjusted_weights["experience"],
                "education":       adjusted_weights["education"],
                "semantic":        adjusted_weights["semantic"],
                "weight_strategy": strategy,
            },
            "weighted_contributions": contributions,
            "missing_data_handling": {
                "missing_sections":        missing_sections,
                "weight_redistributed":    redistributed,
                "redistribution_strategy": redistribution_strategy,
            },
            "score_interpretation": interpretation,
            "processing_metadata": {
                "processed_timestamp": datetime.now().isoformat(timespec="seconds"),
                "scoring_version":     self.VERSION,
                "input_sources": {
                    "skills":     self._last_loaded_path.get("skills",     "[not found]"),
                    "experience": self._last_loaded_path.get("experience", "[not found]"),
                    "education":  self._last_loaded_path.get("education",  "[not found]"),
                    "semantic":   self._last_loaded_path.get("semantic",   "[not found]"),
                },
            },
        }

        self._save_result(candidate_id, jd_id, result)
        logger.info(
            "Scored %-35s vs %-40s -> %5.1f  [%s]",
            candidate_id[:35], jd_id[:40], final_score, interpretation["rating"],
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers — file discovery + fuzzy matching
    # ------------------------------------------------------------------

    def _build_file_indexes(self):
        """
        Build { normalised_id: [actual_filenames] } for each section folder.
        A list because experience folder has multiple files per candidate
        (one per JD).
        """
        self._indexes: dict = {}
        self._last_loaded_path: dict = {}
        folders = {
            "skills":     self.skill_outputs_dir,
            "experience": self.experience_outputs_dir,
            "education":  self.education_outputs_dir,
            "semantic":   self.semantic_outputs_dir,
        }
        for section, folder in folders.items():
            idx: dict = {}
            if os.path.isdir(folder):
                for fname in os.listdir(folder):
                    if fname.endswith(".json"):
                        stem = fname[:-5]
                        key = _normalise_id(stem)
                        idx.setdefault(key, []).append(fname)
            self._indexes[section] = idx

    def _log_startup_diagnostics(self):
        dirs = {
            "extracted_skills  (skills)":  self.skill_outputs_dir,
            "experience_outputs (exp)":    self.experience_outputs_dir,
            "education_outputs  (edu)":    self.education_outputs_dir,
            "semantic_outputs   (sem)":    self.semantic_outputs_dir,
        }
        logger.info("-- ATS Engine input folder diagnostics --")
        for label, path in dirs.items():
            abs_path = os.path.abspath(path)
            if os.path.isdir(abs_path):
                files = [f for f in os.listdir(abs_path) if f.endswith(".json")]
                logger.info("  OK %-38s | %3d JSON file(s) | %s",
                            label, len(files), abs_path)
            else:
                logger.warning("  MISSING %-38s | FOLDER NOT FOUND | %s",
                               label, abs_path)
        logger.info("-- Output -> %s", os.path.abspath(self.ats_results_dir))

    def _discover_candidates(self) -> list:
        """Return unique candidate IDs (JSON stems) from extracted_skills/."""
        abs_path = os.path.abspath(self.skill_outputs_dir)
        if not os.path.isdir(abs_path):
            logger.error("Skill folder NOT FOUND: %s", abs_path)
            return []
        ids = sorted(f[:-5] for f in os.listdir(abs_path) if f.endswith(".json"))
        logger.info("Discovered %d candidate(s) in: %s", len(ids), abs_path)
        return ids

    def _load_section(
        self,
        directory:    str,
        candidate_id: str,
        section:      str,
        jd_id:        str = "",
    ) -> Optional[dict]:
        """
        Load a section JSON using fuzzy matching.

        For `experience` section: files are per-candidate-PER-JD, so we
        additionally filter by JD id in the filename.
        For other sections: single file per candidate suffices.
        """
        target_norm = _normalise_id(candidate_id)
        idx = self._indexes.get(section, {})
        candidates_list = idx.get(target_norm, [])

        # Fallback: substring match on normalised key
        if not candidates_list:
            for key, fnames in idx.items():
                if target_norm and (target_norm in key or key in target_norm):
                    candidates_list = fnames
                    break

        if not candidates_list:
            self._last_loaded_path[section] = f"[not found: {candidate_id}]"
            return None

        # For experience section, prefer files that mention the JD id
        chosen: Optional[str] = None
        if section == "experience" and jd_id:
            for fname in candidates_list:
                if _jd_matches_filename(jd_id, fname):
                    chosen = fname
                    break
        if not chosen:
            # Prefer exact-stem match, else first
            exact = f"{candidate_id}.json"
            if exact in candidates_list:
                chosen = exact
            else:
                chosen = candidates_list[0]

        path = os.path.join(directory, chosen)
        self._last_loaded_path[section] = path
        return self._read_json(path)

    def _read_json(self, path: str) -> Optional[dict]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return {"items": data}
            if not isinstance(data, dict):
                return {"value": data}
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read %s: %s", path, exc)
            return None

    def _save_result(self, candidate_id: str, jd_id: str, result: dict):
        """Persist individual result JSON."""
        safe_cid = re.sub(r"[^A-Za-z0-9_\-]", "_", candidate_id)
        safe_jd  = re.sub(r"[^A-Za-z0-9_\-]", "_", jd_id)
        filename = f"{safe_cid}__{safe_jd}.json"
        path     = os.path.join(self.ats_results_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
