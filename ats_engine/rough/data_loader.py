"""
ats_engine/data_loader.py
─────────────────────────
Loads candidate data from the four input folders:
  data/extracted_skills/     → {resume_id}__skills.json
  data/education_outputs/    → {resume_id}__sections.json
  data/experience_outputs/   → {resume_id}__vs_{jd_slug}_experience.json
  data/semantic_outputs/     → {resume_id}__sections_semantic.json

Resolves candidates by scanning the skills folder and cross-matching
the other three folders using the same resume_id stem.
"""

from __future__ import annotations

import json
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── Folder names (relative to project root) ──────────────────────────────────
SKILLS_DIR     = Path("data/extracted_skills")
EDUCATION_DIR  = Path("data/education_outputs")
EXPERIENCE_DIR = Path("data/experience_outputs")
SEMANTIC_DIR   = Path("data/semantic_outputs")

# ── Filename patterns ─────────────────────────────────────────────────────────
RE_SKILLS     = re.compile(r"^(.+?)__skills\.json$")
RE_EDUCATION  = re.compile(r"^(.+?)__sections\.json$")
RE_EXPERIENCE = re.compile(r"^(.+?)__vs_(.+?)_experience\.json$")
RE_SEMANTIC   = re.compile(r"^(.+?)__sections_semantic\.json$")


@dataclass
class CandidateFiles:
    """All four file paths for one candidate × one JD pair."""
    resume_id:      str
    jd_slug:        str
    skills_path:    Optional[Path] = None
    education_path: Optional[Path] = None
    experience_path: Optional[Path] = None
    semantic_path:  Optional[Path] = None

    @property
    def missing_files(self) -> list[str]:
        missing = []
        if not self.skills_path:    missing.append("skills")
        if not self.education_path: missing.append("education")
        if not self.experience_path:missing.append("experience")
        if not self.semantic_path:  missing.append("semantic")
        return missing

    @property
    def is_complete(self) -> bool:
        return len(self.missing_files) == 0


@dataclass
class CandidateData:
    """Parsed JSON payload for all four sections."""
    resume_id:       str
    jd_slug:         str
    skills_data:     Optional[dict] = None
    education_data:  Optional[dict] = None
    experience_data: Optional[dict] = None
    semantic_data:   Optional[dict] = None
    load_errors:     list[str] = field(default_factory=list)


def _load_json(path: Optional[Path], label: str) -> tuple[Optional[dict], Optional[str]]:
    """Safe JSON loader.  Returns (data, error_message)."""
    if path is None:
        return None, f"{label}: file not found"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"{label}: JSON parse error – {e}"
    except OSError as e:
        return None, f"{label}: I/O error – {e}"


class ATSDataLoader:
    """
    Scans the four data directories and assembles CandidateData objects.

    Usage
    ─────
    loader = ATSDataLoader(root=".")          # project root
    candidates = loader.load_all()            # list[CandidateData]
    single     = loader.load_one("Amala_Resume_DS_DA_2026",
                                  "ai_specialist_in_healthcare_analytics_parsed_jd")
    """

    def __init__(self, root: str | Path = "."):
        self.root = Path(root)
        self.skills_dir     = self.root / SKILLS_DIR
        self.education_dir  = self.root / EDUCATION_DIR
        self.experience_dir = self.root / EXPERIENCE_DIR
        self.semantic_dir   = self.root / SEMANTIC_DIR

    # ── Discovery ──────────────────────────────────────────────────────────────

    def discover_candidates(self) -> list[CandidateFiles]:
        """
        Primary discovery: scan extracted_skills/ to get all resume_ids,
        then match the other three folders.
        """
        if not self.skills_dir.exists():
            log.warning("Skills directory not found: %s", self.skills_dir)
            return []

        # Build lookup maps: resume_id → path, for each folder
        edu_map  = self._index_folder(self.education_dir,  RE_EDUCATION,  group=1)
        sem_map  = self._index_folder(self.semantic_dir,   RE_SEMANTIC,   group=1)
        exp_map  = self._index_experience_folder()  # resume_id → {jd_slug: path}

        results: list[CandidateFiles] = []
        for skill_file in sorted(self.skills_dir.glob("*.json")):
            m = RE_SKILLS.match(skill_file.name)
            if not m:
                log.debug("Skipping non-matching file: %s", skill_file.name)
                continue

            resume_id = m.group(1)

            # Find all JD slugs available for this resume_id in experience folder
            jd_slugs = list(exp_map.get(resume_id, {}).keys())
            if not jd_slugs:
                # Still include candidate, just without experience file
                jd_slugs = ["unknown_jd"]

            for jd_slug in jd_slugs:
                cf = CandidateFiles(
                    resume_id       = resume_id,
                    jd_slug         = jd_slug,
                    skills_path     = skill_file,
                    education_path  = edu_map.get(resume_id),
                    experience_path = exp_map.get(resume_id, {}).get(jd_slug),
                    semantic_path   = sem_map.get(resume_id),
                )
                results.append(cf)

        log.info("Discovered %d candidate×JD pairs", len(results))
        return results

    def _index_folder(self, folder: Path, pattern: re.Pattern, group: int) -> dict[str, Path]:
        """Build resume_id → Path mapping for a folder."""
        index: dict[str, Path] = {}
        if not folder.exists():
            log.warning("Directory not found: %s", folder)
            return index
        for f in folder.glob("*.json"):
            m = pattern.match(f.name)
            if m:
                index[m.group(group)] = f
        return index

    def _index_experience_folder(self) -> dict[str, dict[str, Path]]:
        """
        Build resume_id → {jd_slug → Path} mapping for the experience folder.
        Multiple JDs per resume are supported.
        """
        index: dict[str, dict[str, Path]] = {}
        if not self.experience_dir.exists():
            log.warning("Experience directory not found: %s", self.experience_dir)
            return index
        for f in self.experience_dir.glob("*.json"):
            m = RE_EXPERIENCE.match(f.name)
            if m:
                resume_id, jd_slug = m.group(1), m.group(2)
                index.setdefault(resume_id, {})[jd_slug] = f
        return index

    # ── Loading ────────────────────────────────────────────────────────────────

    def load_one(self, resume_id: str, jd_slug: str) -> CandidateData:
        """Load a single candidate×JD by explicit IDs."""
        cf = CandidateFiles(
            resume_id       = resume_id,
            jd_slug         = jd_slug,
            skills_path     = self.skills_dir / f"{resume_id}__skills.json",
            education_path  = self.education_dir / f"{resume_id}__sections.json",
            experience_path = self.experience_dir / f"{resume_id}__vs_{jd_slug}_experience.json",
            semantic_path   = self.semantic_dir / f"{resume_id}__sections_semantic.json",
        )
        # Validate file existence
        for attr in ("skills_path", "education_path", "experience_path", "semantic_path"):
            p = getattr(cf, attr)
            if p and not p.exists():
                setattr(cf, attr, None)
        return self._load_files(cf)

    def load_all(self) -> list[CandidateData]:
        """Load all discovered candidates."""
        return [self._load_files(cf) for cf in self.discover_candidates()]

    def _load_files(self, cf: CandidateFiles) -> CandidateData:
        """Parse JSON for all four files of a CandidateFiles record."""
        errors: list[str] = []

        skills_raw,  e1 = _load_json(cf.skills_path,    "skills")
        edu_raw,     e2 = _load_json(cf.education_path, "education")
        exp_raw,     e3 = _load_json(cf.experience_path,"experience")
        sem_raw,     e4 = _load_json(cf.semantic_path,  "semantic")

        for e in (e1, e2, e3, e4):
            if e:
                errors.append(e)
                log.warning("[%s] %s", cf.resume_id, e)

        # Normalise education: the real file uses key "education_data"
        education_data = None
        if edu_raw:
            education_data = edu_raw.get("education_data", edu_raw)
            # Attach top-level relevance score into the education_data dict
            education_data["education_relevance_score"] = edu_raw.get(
                "education_relevance_score",
                education_data.get("education_relevance_score", 0.0)
            )

        if errors:
            log.warning("[%s vs %s] Load errors: %s", cf.resume_id, cf.jd_slug, errors)

        return CandidateData(
            resume_id       = cf.resume_id,
            jd_slug         = cf.jd_slug,
            skills_data     = skills_raw,
            education_data  = education_data,
            experience_data = exp_raw,
            semantic_data   = sem_raw,
            load_errors     = errors,
        )

    # ── Diagnostics ────────────────────────────────────────────────────────────

    def audit(self) -> None:
        """Print a discovery audit to stdout."""
        cfs = self.discover_candidates()
        print(f"\n{'═'*60}")
        print(f"  DATA LOADER AUDIT")
        print(f"  Root: {self.root.resolve()}")
        print(f"{'═'*60}")
        print(f"  {'RESUME ID':<45} {'JD SLUG':<35} {'FILES'}")
        print(f"  {'─'*45} {'─'*35} {'─'*10}")
        for cf in cfs:
            status = "COMPLETE" if cf.is_complete else f"MISSING: {cf.missing_files}"
            print(f"  {cf.resume_id:<45} {cf.jd_slug:<35} {status}")
        print(f"\n  Total pairs: {len(cfs)}")
        print(f"{'═'*60}\n")


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    ATSDataLoader(root).audit()
