"""
Keyword Dependency Reducer - Task 2 (Day 15)
Path: ai_job_portal_system/fairness_engine/keyword_dependency_reducer.py

PURPOSE:
    Reduce ATS over-reliance on raw keyword presence by:
      1. Mapping skill synonyms to canonical forms (TF -> tensorflow, etc.)
      2. Computing CONTEXTUAL relevance (skill must appear in projects/experience,
         not just in skills section).
      3. Returning a "keyword dependency ratio" that flags keyword-stuffed resumes.
      4. Producing a context-weighted skill match score that complements raw
         keyword match.

INPUTS:
    - normalized resume JSON (from ResumeNormalizer)
    - parsed JD JSON

OUTPUT:
    - dependency analysis JSON with:
        * canonical_skills
        * contextual_evidence (skill -> [evidence_snippets])
        * keyword_dependency_ratio
        * context_adjusted_skill_score
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.fairness_utils import (
    clean_text, ensure_dir, get_logger, load_json,
    normalize_skill_token, now_iso, round_score, safe_divide, save_json,
)
from utils.normalization_constants import GENERIC_BUZZWORDS, SKILL_SYNONYMS

logger = get_logger("keyword_dependency_reducer")


class KeywordDependencyReducer:
    """Reduce over-dependence on keywords for fairer skill matching."""

    def __init__(self, output_dir: str = "fairness_engine_outputs/dependency_reports"):
        self.output_dir = ensure_dir(output_dir)

    # ----------------------------------------------------------
    # PUBLIC ENTRY
    # ----------------------------------------------------------
    def analyze(
        self,
        normalized_resume: Dict[str, Any],
        parsed_jd: Dict[str, Any],
        save: bool = True,
    ) -> Dict[str, Any]:
        """Run keyword dependency analysis."""
        resume_id = normalized_resume.get("candidate_id", "unknown")
        jd_role = (parsed_jd.get("role") or ["unknown"])[0]

        # 1. Canonicalize candidate skills
        candidate_skills_raw = normalized_resume.get("skills", {}).get(
            "all_skills_flat", []
        )
        canonical_skills = self._canonicalize(candidate_skills_raw)

        # 2. Canonicalize JD required skills
        jd_skills_raw = parsed_jd.get("skills_required", []) or []
        canonical_jd_skills = self._canonicalize(jd_skills_raw)

        # 3. Find contextual evidence (where each JD skill appears
        #    in candidate's experience/projects)
        evidence = self._gather_evidence(canonical_jd_skills, normalized_resume)

        # 4. Compute keyword dependency ratio
        dependency_ratio = self._dependency_ratio(canonical_skills, evidence)

        # 5. Compute context-adjusted skill score
        ctx_score = self._context_adjusted_score(canonical_jd_skills, evidence)

        # 6. Detect generic buzzwords (fluff penalty)
        buzzword_count = self._buzzword_count(normalized_resume)

        result = {
            "resume_id": resume_id,
            "job_role": jd_role,
            "canonical_skills": canonical_skills,
            "canonical_jd_skills": canonical_jd_skills,
            "contextual_evidence": evidence,
            "keyword_dependency_ratio": round_score(dependency_ratio, 3),
            "context_adjusted_skill_score": round_score(ctx_score, 2),
            "buzzword_count": buzzword_count,
            "fluff_penalty": min(buzzword_count * 2, 10),  # cap at 10
            "interpretation": self._interpret(dependency_ratio, ctx_score),
            "analyzed_at": now_iso(),
        }

        if save:
            out_path = self.output_dir / f"{resume_id}__{jd_role}_dependency.json"
            save_json(result, out_path)
            logger.info(f"Saved dependency analysis -> {out_path}")
        return result

    # ----------------------------------------------------------
    # PRIVATE HELPERS
    # ----------------------------------------------------------
    @staticmethod
    def _canonicalize(skills: List[str]) -> List[str]:
        """Lower + map synonyms + de-dupe."""
        out = []
        seen = set()
        for s in skills:
            s_clean = clean_text(s).lower()
            if not s_clean:
                continue
            canonical = normalize_skill_token(s_clean, SKILL_SYNONYMS)
            if canonical not in seen:
                seen.add(canonical)
                out.append(canonical)
        return out

    @staticmethod
    def _gather_evidence(
        jd_skills: List[str], resume: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """
        For each JD skill, find sentences in experience+projects+achievements
        that contain it OR any of its synonyms. Empty list = skill listed but
        never demonstrated.
        """
        # Build searchable corpus from "use" sections (not from skills section)
        corpus_lines: List[str] = []
        # experience duties
        for role in resume.get("experience", {}).get("roles", []):
            corpus_lines.extend(role.get("duties", []) or [])
        # projects
        for proj in resume.get("projects", []):
            corpus_lines.append(proj.get("title", ""))
            corpus_lines.extend(proj.get("description", []) or [])
        # achievements
        corpus_lines.extend(resume.get("achievements", []) or [])
        # summary
        corpus_lines.append(resume.get("professional_summary", ""))

        corpus_lines = [clean_text(l).lower() for l in corpus_lines if l]

        evidence = {}
        for skill in jd_skills:
            # build a list of search terms = canonical + all known synonyms
            search_terms = [skill]
            if skill in SKILL_SYNONYMS:
                search_terms = list(set(SKILL_SYNONYMS[skill]))  # full forms
            # de-dupe by length descending so longer matches win first
            search_terms = sorted(set(search_terms), key=len, reverse=True)

            matches = []
            seen_lines = set()
            for term in search_terms:
                pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
                for line in corpus_lines:
                    if line in seen_lines:
                        continue
                    if pattern.search(line):
                        matches.append(line[:200])
                        seen_lines.add(line)
                        if len(matches) >= 3:
                            break
                if len(matches) >= 3:
                    break
            evidence[skill] = matches
        return evidence

    @staticmethod
    def _dependency_ratio(
        candidate_skills: List[str], evidence: Dict[str, List[str]]
    ) -> float:
        """
        Ratio = (skills only in skills-section) / (total candidate skills).
        High ratio means resume is keyword-stuffed without evidence.
        We compute this only for the JD-required skills the candidate claims.
        """
        if not candidate_skills:
            return 0.0
        claimed_jd_skills = [s for s in evidence.keys() if s in candidate_skills]
        if not claimed_jd_skills:
            return 0.0
        unsupported = [s for s in claimed_jd_skills if not evidence.get(s)]
        return safe_divide(len(unsupported), len(claimed_jd_skills))

    @staticmethod
    def _context_adjusted_score(
        jd_skills: List[str], evidence: Dict[str, List[str]]
    ) -> float:
        """
        Each JD skill is worth 1 point only if backed by evidence.
        Score is normalized to 0-100.
        Skills with evidence get full credit; merely-listed get half credit.
        """
        if not jd_skills:
            return 0.0
        total = 0.0
        for s in jd_skills:
            if evidence.get(s):
                total += 1.0          # demonstrated
            elif s in evidence:        # in dict (claimed) but no evidence
                total += 0.0           # no credit (it's still a claim issue)
        max_possible = len(jd_skills)
        return safe_divide(total * 100, max_possible)

    @staticmethod
    def _buzzword_count(resume: Dict[str, Any]) -> int:
        """Count generic buzzwords across resume text."""
        text_blob = " ".join([
            resume.get("professional_summary", ""),
            " ".join(resume.get("achievements", []) or []),
        ]).lower()
        return sum(1 for b in GENERIC_BUZZWORDS if b in text_blob)

    @staticmethod
    def _interpret(dep_ratio: float, ctx_score: float) -> str:
        """Human-readable interpretation."""
        if dep_ratio > 0.6:
            return "High keyword dependency - many skills claimed without evidence"
        if dep_ratio > 0.3:
            return "Moderate keyword dependency - some skills lack supporting context"
        if ctx_score >= 70:
            return "Strong contextual evidence for required skills"
        return "Low keyword dependency - skills well demonstrated"


# ----------------------------------------------------------
# CLI entry
# ----------------------------------------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reduce keyword dependency")
    parser.add_argument("--resume", required=True, help="normalized resume JSON")
    parser.add_argument("--jd", required=True, help="parsed JD JSON")
    parser.add_argument("--output_dir", default="fairness_engine_outputs/dependency_reports")
    args = parser.parse_args()

    reducer = KeywordDependencyReducer(output_dir=args.output_dir)
    res = reducer.analyze(load_json(args.resume), load_json(args.jd))
    print(f"Keyword Dependency Ratio: {res['keyword_dependency_ratio']}")
    print(f"Context-Adjusted Score:  {res['context_adjusted_skill_score']}")
    print(f"Interpretation:           {res['interpretation']}")