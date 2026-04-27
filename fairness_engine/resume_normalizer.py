"""
Resume Normalizer - Task 1 (Day 15)
Path: ai_job_portal_system/fairness_engine/resume_normalizer.py

PURPOSE:
    Convert any parsed resume (varying structures from parsers/) into a
    STANDARD UNIFIED SCHEMA. This ensures that downstream scoring engines
    treat all resumes equally regardless of source format/parser quirks.

INPUTS:
    - parsed resume JSON  (e.g. Amala_Resume_DS_DA_2026_.json)
    - sections JSON       (e.g. Amala_Resume_DS_DA_2026__sections.json)

OUTPUT:
    - normalized resume JSON  -> fairness_engine_outputs/normalized_resumes/<resume_id>_normalized.json
"""

import re
import copy
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.fairness_utils import (
    clean_text, get_logger, get_resume_id,
    load_json, now_iso, save_json, tokenize_skills, ensure_dir,
)
from utils.normalization_constants import STANDARD_RESUME_SCHEMA, PII_PATTERNS

logger = get_logger("resume_normalizer")


class ResumeNormalizer:
    """Normalize a parsed resume into the standard schema."""

    # Categorize raw skill lines based on the leading category label
    SKILL_CATEGORIES = {
        "programming": ["programming", "language", "db", "database"],
        "ml_ai": ["ml", "ai", "machine learning", "artificial intelligence",
                  "deep learning", "nlp"],
        "frameworks": ["framework", "library", "libs"],
        "tools": ["tool", "platform", "environment"],
        "domain": ["domain", "industry"],
    }

    def __init__(self, output_dir: str = "fairness_engine_outputs/normalized_resumes"):
        self.output_dir = ensure_dir(output_dir)

    # ----------------------------------------------------------
    # PUBLIC ENTRY
    # ----------------------------------------------------------
    def normalize(
        self,
        parsed_resume_path: str,
        sections_path: Optional[str] = None,
        save: bool = True,
    ) -> Dict[str, Any]:
        """
        Normalize a single resume.

        Args:
            parsed_resume_path: path to <resume>.json from parsers/
            sections_path:      optional path to <resume>_sections.json
            save:               whether to write to disk

        Returns:
            Normalized resume dict matching STANDARD_RESUME_SCHEMA
        """
        logger.info(f"Normalizing resume: {parsed_resume_path}")
        parsed = load_json(parsed_resume_path)
        sections = load_json(sections_path) if sections_path else {}

        normalized = copy.deepcopy(STANDARD_RESUME_SCHEMA)

        # ---- Identifiers ----
        resume_id = get_resume_id(parsed_resume_path)
        normalized["candidate_id"] = resume_id

        # ---- Personal info ----
        normalized["personal_info"] = self._extract_personal_info(parsed)

        # ---- Professional summary ----
        normalized["professional_summary"] = self._extract_summary(parsed)

        # ---- Skills ----
        normalized["skills"] = self._normalize_skills(sections.get("skills", []))

        # ---- Experience ----
        normalized["experience"] = self._normalize_experience(parsed, sections)

        # ---- Education ----
        normalized["education"] = self._normalize_education(parsed, sections)

        # ---- Projects ----
        normalized["projects"] = self._normalize_projects(sections.get("projects", []))

        # ---- Certifications & Achievements ----
        normalized["certifications"] = sections.get("certifications", []) or []
        normalized["achievements"] = [
            clean_text(a) for a in sections.get("achievements", []) if clean_text(a)
        ]

        # ---- Metadata ----
        normalized["metadata"] = {
            "source_file": str(parsed_resume_path),
            "normalized_at": now_iso(),
            "schema_version": "1.0",
        }

        if save:
            out_path = self.output_dir / f"{resume_id}_normalized.json"
            save_json(normalized, out_path)
            logger.info(f"Saved normalized resume -> {out_path}")

        return normalized

    # ----------------------------------------------------------
    # PRIVATE HELPERS
    # ----------------------------------------------------------
    def _extract_personal_info(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Extract name/email/phone/location from clean_text and top-level fields."""
        clean_txt = parsed.get("clean_text", "") or ""
        # head = first ~6 lines where contact info typically lives
        head_lines = clean_txt.split("\n")[:6]
        head = "\n".join(head_lines)

        email = self._regex_first(PII_PATTERNS["email"], head) or \
                self._regex_first(PII_PATTERNS["email"], clean_txt)
        phone = self._regex_first(PII_PATTERNS["phone"], head)
        linkedin = self._regex_first(PII_PATTERNS["linkedin"], clean_txt)

        # location: look for a line containing comma + alpha that has
        # email/phone alongside (typical contact line) OR a standalone
        # geo line. Strip email/phone before saving.
        location = None
        for line in head_lines:
            if "," not in line:
                continue
            # candidate before bullet/dot separators
            candidate_segments = re.split(r"[•\u2022\|]", line)
            for seg in candidate_segments:
                seg_clean = seg.strip()
                if (seg_clean and "," in seg_clean and len(seg_clean) < 100
                        and not re.search(PII_PATTERNS["email"], seg_clean)
                        and not re.search(r"\d{6,}", seg_clean)):  # no phone digits
                    # must have at least one word starting with capital letter
                    if any(w[:1].isupper() for w in seg_clean.split()):
                        location = seg_clean
                        break
            if location:
                break

        return {
            "name": parsed.get("name"),
            "email": email,
            "phone": phone.strip() if phone else None,
            "location": location,
            "linkedin": linkedin,
        }

    def _extract_summary(self, parsed: Dict[str, Any]) -> str:
        """Pull professional summary block."""
        clean_txt = parsed.get("clean_text", "") or ""
        # crude: text between PROFESSIONAL SUMMARY and next ALL-CAPS section
        m = re.search(
            r"PROFESSIONAL SUMMARY\s*(.+?)(?=\n[A-Z][A-Z\s&]{4,}\n|\Z)",
            clean_txt, re.DOTALL,
        )
        return clean_text(m.group(1)) if m else ""

    def _normalize_skills(self, raw_skill_block: List[str]) -> Dict[str, List[str]]:
        """Categorize skills into buckets."""
        result = {
            "programming": [], "ml_ai": [], "frameworks": [],
            "tools": [], "domain": [], "soft_skills": [],
            "all_skills_flat": [],
        }
        if not raw_skill_block:
            return result

        # Known category prefixes that we strip before tokenizing
        category_prefixes = [
            "programming & db", "programming and db",
            "ml & ai", "ml and ai",
            "deep learning & nlp", "deep learning and nlp",
            "frameworks & libs", "frameworks and libs",
            "data analytics",
            "tools & platforms", "tools and platforms", "& platforms",
            "environments",
            "domain",
        ]

        for line in raw_skill_block:
            line_lower = line.lower()
            category = "all_skills_flat"
            for cat, kws in self.SKILL_CATEGORIES.items():
                if any(kw in line_lower for kw in kws):
                    category = cat
                    break

            # strip leading category label
            cleaned_line = line
            for prefix in category_prefixes:
                # case-insensitive prefix strip
                if line_lower.startswith(prefix):
                    cleaned_line = line[len(prefix):].lstrip(" :-")
                    break

            tokens = tokenize_skills([cleaned_line])
            tokens = [t for t in tokens if not self._is_label_token(t)]
            if category != "all_skills_flat":
                result[category].extend(tokens)
            result["all_skills_flat"].extend(tokens)

        # de-dupe each bucket preserving order
        for k in result:
            result[k] = list(dict.fromkeys(result[k]))
        return result

    def _normalize_experience(
        self, parsed: Dict[str, Any], sections: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Combine roles + duties from both files."""
        roles = parsed.get("roles", []) or []
        section_exp = sections.get("experience", []) or []

        # build duties lookup keyed by role_header substring
        duties_map = {}
        for entry in section_exp:
            header = entry.get("role_header", "")
            duties = [clean_text(d) for d in entry.get("duties", []) if clean_text(d)]
            duties_map[header.lower()] = duties

        normalized_roles = []
        for role in roles:
            title = role.get("job_title", "")
            company = role.get("company", "")
            # match duties
            duties = []
            for hdr, d in duties_map.items():
                if title.lower() in hdr or (company and company.lower()[:15] in hdr):
                    duties = d
                    break
            normalized_roles.append({
                "job_title": title,
                "company": company,
                "start_date": role.get("start_date"),
                "end_date": role.get("end_date"),
                "duration_months": role.get("duration_months", 0),
                "duties": duties,
            })

        return {
            "total_years": parsed.get("experience", 0.0),
            "roles": normalized_roles,
        }

    def _normalize_education(
        self, parsed: Dict[str, Any], sections: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract structured education from both sources."""
        result = []
        edu_list = parsed.get("education", []) or []
        section_edu = sections.get("education", []) or []

        # zip parsed degrees with section lines (institution + score)
        for i, edu in enumerate(edu_list):
            full_line = edu.get("full_line", "")
            # try to find adjacent institution+score line
            institution = None
            score = None
            try:
                inst_line = section_edu[i * 2 + 1] if (i * 2 + 1) < len(section_edu) else ""
                # split on '|' to get institution and score
                if "|" in inst_line:
                    parts = [p.strip() for p in inst_line.split("|")]
                    institution = parts[0]
                    if len(parts) > 1:
                        score = parts[1]
                else:
                    institution = inst_line.strip() or None
            except (IndexError, AttributeError):
                pass

            years = edu.get("years", []) or []
            result.append({
                "degree": edu.get("degree"),
                "institution": institution,
                "score": score,
                "start_year": years[0] if len(years) >= 1 else None,
                "end_year":   years[1] if len(years) >= 2 else None,
                "raw_line": full_line,
            })
        return result

    def _normalize_projects(self, raw_projects: List[str]) -> List[Dict[str, Any]]:
        """Group project bullets into project entries."""
        if not raw_projects:
            return []

        projects = []
        current = None
        for line in raw_projects:
            line = clean_text(line)
            if not line:
                continue
            # heuristic: lines containing '|' are likely titles
            if "|" in line and not line.startswith(("Built", "Developed", "Applied",
                                                    "Evaluated", "Performed",
                                                    "Segmented", "Structured",
                                                    "Conducted", "Identified",
                                                    "Curated", "Validated",
                                                    "Tracked", "Automated",
                                                    "Resolved", "Executed",
                                                    "Designed")):
                if current:
                    projects.append(current)
                title_parts = [p.strip() for p in line.split("|")]
                current = {
                    "title": title_parts[0] if title_parts else line,
                    "tags": title_parts[1:] if len(title_parts) > 1 else [],
                    "description": [],
                    "technologies": [],
                }
            else:
                if current is None:
                    current = {"title": "Untitled", "tags": [],
                               "description": [], "technologies": []}
                current["description"].append(line)

        if current:
            projects.append(current)
        return projects

    @staticmethod
    def _regex_first(pattern: str, text: str) -> Optional[str]:
        """Return first regex match or None."""
        if not text:
            return None
        m = re.search(pattern, text)
        return m.group(0) if m else None

    @staticmethod
    def _is_label_token(token: str) -> bool:
        """Skip tokens that are clearly category labels not skills."""
        labels = {
            "programming & db", "ml & ai", "deep learning & nlp",
            "frameworks & libs", "data analytics", "& platforms",
            "environments", "domain", "tools & platforms",
        }
        return token.lower() in labels


# ----------------------------------------------------------
# CLI entry
# ----------------------------------------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Normalize a resume to standard schema")
    parser.add_argument("--resume", required=True, help="parsed resume JSON path")
    parser.add_argument("--sections", required=False, help="sections JSON path")
    parser.add_argument("--output_dir", default="fairness_engine_outputs/normalized_resumes")
    args = parser.parse_args()

    normalizer = ResumeNormalizer(output_dir=args.output_dir)
    out = normalizer.normalize(args.resume, args.sections)
    print(f"Normalized -> candidate_id: {out['candidate_id']}")
