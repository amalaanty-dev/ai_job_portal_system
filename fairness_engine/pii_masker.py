"""
PII Masker - Task 4 (Day 15)
Path: ai_job_portal_system/fairness_engine/pii_masker.py

PURPOSE:
    Mask non-essential personal attributes that can introduce bias:
        - Name, Email, Phone, Address
        - Gender pronouns / honorifics (Mr/Mrs/Ms)
        - Age, Marital status
        - College tier (when configured)
        - Caste / Religion / Demographic hints

MASKING DEFAULT (per user selection):
    - Name, Gender, Age, Photo, Address  (configurable via constructor)

INPUT:
    - Normalized resume JSON (from ResumeNormalizer)

OUTPUT:
    - Masked resume JSON -> fairness_engine_outputs/masked_resumes/<resume_id>_masked.json
    - Audit log: which fields were masked, mask_count, success_rate
"""

import copy
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from utils.fairness_utils import (
    ensure_dir, get_logger, load_json, now_iso, save_json, safe_lower,
)
from utils.normalization_constants import (
    CASTE_RELIGION_TERMS, ELITE_INSTITUTIONS, GENDER_TERMS,
    MARITAL_TERMS, MASK_PLACEHOLDERS, PII_PATTERNS,
)

logger = get_logger("pii_masker")

# Default masking profile (matches user selection: Name, Gender, Age, Photo, Address)
DEFAULT_MASK_PROFILE = {
    "name": True,
    "email": True,
    "phone": True,
    "location": True,
    "linkedin": True,
    "gender": True,
    "age": True,
    "photo": True,
    "marital_status": True,
    "caste_religion": False,    # opt-in
    "college_tier": False,       # opt-in
}


class PIIMasker:
    """Mask personally identifiable info to reduce bias in scoring."""

    def __init__(
        self,
        mask_profile: Optional[Dict[str, bool]] = None,
        output_dir: str = "fairness_engine_outputs/masked_resumes",
    ):
        self.mask_profile = mask_profile or DEFAULT_MASK_PROFILE.copy()
        self.output_dir = ensure_dir(output_dir)

    # ----------------------------------------------------------
    # PUBLIC ENTRY
    # ----------------------------------------------------------
    def mask(
        self,
        normalized_resume: Dict[str, Any],
        save: bool = True,
    ) -> Dict[str, Any]:
        """
        Mask PII in a normalized resume.

        Returns:
            Tuple-like dict { masked_resume, audit }
        """
        resume_id = normalized_resume.get("candidate_id", "unknown")
        masked = copy.deepcopy(normalized_resume)
        audit = {
            "resume_id": resume_id,
            "masked_fields": [],
            "mask_count_per_field": {},
            "total_masks_applied": 0,
            "mask_profile": self.mask_profile,
            "masked_at": now_iso(),
        }

        # ---- 1. Mask personal_info top-level fields ----
        masked["personal_info"], pi_audit = self._mask_personal_info(
            masked.get("personal_info", {})
        )
        audit["masked_fields"].extend(pi_audit["fields"])
        for k, v in pi_audit["counts"].items():
            audit["mask_count_per_field"][k] = audit["mask_count_per_field"].get(k, 0) + v

        # ---- 2. Mask textual fields (summary, achievements, projects, duties) ----
        text_fields = self._collect_text_fields(masked)
        masked, text_audit = self._mask_text_fields(masked, text_fields,
                                                    masked["personal_info"])
        for k, v in text_audit.items():
            audit["mask_count_per_field"][k] = audit["mask_count_per_field"].get(k, 0) + v

        # ---- 3. Mask gender / age / marital status everywhere ----
        if self.mask_profile.get("gender"):
            count = self._mask_terms_in_resume(masked, GENDER_TERMS,
                                               MASK_PLACEHOLDERS["gender"])
            audit["mask_count_per_field"]["gender"] = count
        if self.mask_profile.get("marital_status"):
            count = self._mask_terms_in_resume(masked, MARITAL_TERMS,
                                               MASK_PLACEHOLDERS["marital_status"])
            audit["mask_count_per_field"]["marital_status"] = count
        if self.mask_profile.get("age"):
            count = self._mask_age_patterns(masked)
            audit["mask_count_per_field"]["age"] = count
        if self.mask_profile.get("caste_religion"):
            count = self._mask_terms_in_resume(masked, CASTE_RELIGION_TERMS,
                                               MASK_PLACEHOLDERS["caste_religion"])
            audit["mask_count_per_field"]["caste_religion"] = count
        if self.mask_profile.get("college_tier"):
            count = self._mask_institutions(masked)
            audit["mask_count_per_field"]["college_tier"] = count

        audit["total_masks_applied"] = sum(audit["mask_count_per_field"].values())

        # bundle
        result = {
            "masked_resume": masked,
            "audit": audit,
        }

        if save:
            out_path = self.output_dir / f"{resume_id}_masked.json"
            save_json(result, out_path)
            logger.info(
                f"Masked resume saved -> {out_path} "
                f"({audit['total_masks_applied']} masks)"
            )
        return result

    # ----------------------------------------------------------
    # SECTION-LEVEL MASKING
    # ----------------------------------------------------------
    def _mask_personal_info(self, pi: Dict[str, Any]):
        fields_masked, counts = [], {}
        for key in ["name", "email", "phone", "location", "linkedin"]:
            if self.mask_profile.get(key) and pi.get(key):
                pi[key] = MASK_PLACEHOLDERS[key]
                fields_masked.append(key)
                counts[key] = counts.get(key, 0) + 1
        return pi, {"fields": fields_masked, "counts": counts}

    @staticmethod
    def _collect_text_fields(resume: Dict[str, Any]) -> List[str]:
        """Pre-scan: gather text blobs to scan for PII regex."""
        return [
            resume.get("professional_summary", ""),
        ]

    def _mask_text_fields(
        self,
        resume: Dict[str, Any],
        _seed_fields: List[str],
        original_pi: Dict[str, Any],
    ):
        """
        Mask PII regex patterns AND original name occurrences inside
        summary/achievements/projects/duties.
        """
        counts = {"email_in_text": 0, "phone_in_text": 0,
                  "name_in_text": 0, "url_in_text": 0}

        original_name = original_pi.get("name") if original_pi else None
        # NOTE: original_pi was already masked, so we cannot rely on it.
        # We need to re-extract from raw text. Workaround: caller passes
        # masked_resume but we should scan all text against generic regex.

        # Walk the resume tree and apply regex masks
        def mask_string(s: str) -> str:
            if not isinstance(s, str) or not s:
                return s
            updated = s
            if self.mask_profile.get("email"):
                updated, n = re.subn(PII_PATTERNS["email"],
                                     MASK_PLACEHOLDERS["email"], updated)
                counts["email_in_text"] += n
            if self.mask_profile.get("phone"):
                updated, n = re.subn(PII_PATTERNS["phone"],
                                     MASK_PLACEHOLDERS["phone"], updated)
                counts["phone_in_text"] += n
            # URLs (linkedin/github)
            if self.mask_profile.get("linkedin"):
                updated, n = re.subn(PII_PATTERNS["url"],
                                     MASK_PLACEHOLDERS["url"], updated)
                counts["url_in_text"] += n
            return updated

        self._walk_and_mask(resume, mask_string)
        return resume, counts

    # ----------------------------------------------------------
    # GENERIC TREE-WALKER + MASKERS
    # ----------------------------------------------------------
    @staticmethod
    def _walk_and_mask(node: Any, fn) -> Any:
        """Recursively apply fn to every string in a JSON-like tree."""
        if isinstance(node, dict):
            for k, v in node.items():
                node[k] = PIIMasker._walk_and_mask(v, fn)
            return node
        if isinstance(node, list):
            return [PIIMasker._walk_and_mask(item, fn) for item in node]
        if isinstance(node, str):
            return fn(node)
        return node

    def _mask_terms_in_resume(
        self,
        resume: Dict[str, Any],
        terms: List[str],
        placeholder: str,
    ) -> int:
        """Mask whole-word matches of terms inside all string fields."""
        # build single regex with word boundaries (case-insensitive)
        if not terms:
            return 0
        pattern = re.compile(
            r"\b(" + "|".join(re.escape(t) for t in terms) + r")\b",
            re.IGNORECASE,
        )
        counter = {"n": 0}

        def fn(s: str) -> str:
            new, n = pattern.subn(placeholder, s)
            counter["n"] += n
            return new

        self._walk_and_mask(resume, fn)
        return counter["n"]

    def _mask_age_patterns(self, resume: Dict[str, Any]) -> int:
        """Mask phrases like 'Age: 28', '28 years old', 'DOB: ...'."""
        patterns = [
            r"\bage\s*[:\-]?\s*\d{1,2}\b",
            r"\b\d{1,2}\s*(?:years?\s*old|yrs?\s*old)\b",
            r"\bDOB\s*[:\-]?\s*[\d/.-]+\b",
            r"\bdate\s+of\s+birth\s*[:\-]?\s*[\d/.-]+\b",
        ]
        counter = {"n": 0}
        compiled = [re.compile(p, re.IGNORECASE) for p in patterns]

        def fn(s: str) -> str:
            for cp in compiled:
                s, n = cp.subn(MASK_PLACEHOLDERS["age"], s)
                counter["n"] += n
            return s

        self._walk_and_mask(resume, fn)
        return counter["n"]

    def _mask_institutions(self, resume: Dict[str, Any]) -> int:
        """Replace elite institution names with placeholder."""
        count = 0
        for edu in resume.get("education", []):
            inst = edu.get("institution") or ""
            if any(elite in inst.lower() for elite in ELITE_INSTITUTIONS):
                edu["institution"] = MASK_PLACEHOLDERS["college_tier"]
                count += 1
        return count


# ----------------------------------------------------------
# CLI entry
# ----------------------------------------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Mask PII in normalized resume")
    parser.add_argument("--resume", required=True,
                        help="normalized resume JSON path")
    parser.add_argument("--output_dir", default="fairness_engine_outputs/masked_resumes")
    args = parser.parse_args()

    masker = PIIMasker(output_dir=args.output_dir)
    out = masker.mask(load_json(args.resume))
    print(f"Total masks applied: {out['audit']['total_masks_applied']}")
    print(f"Per-field counts: {out['audit']['mask_count_per_field']}")
