"""
Score Calculator — Day 13
Zecpath AI Job Portal

Computes 4 dimension scores (0-100) using the ACTUAL schemas produced
by Day 8-12 parsers:

  SKILL file:
    {
      "candidate": "...",
      "skills": [
        {"skill": "python", "category": "tech", "confidence": 0.95},
        ...
      ]
    }

  EXPERIENCE file:
    {
      "experience_summary": {"total_experience_months": 62},
      "roles": [{"company": "...", "job_title": "...",
                 "start_date": "...", "end_date": "...",
                 "duration_months": 42}, ...],
      "timeline_analysis": {"gaps": [], "overlaps": [...]},
      "relevance_analysis": {"overall_relevance_score": 41.83}
    }

  EDUCATION file:
    {
      "education_data": {
        "academic_profile": {
          "highest_degree": "MBA",
          "total_degrees": 2,
          "certification_count": 0,
          "latest_graduation_year": 2018,
          "education_strength": 63.0
        },
        "education_details": [{"degree": "MBA", "field": "...",
                              "institution": "...",
                              "graduation_year": "..."}, ...],
        "certifications": []
      },
      "education_relevance_score": 36.3
    }

  SEMANTIC file (matrix — scores ALL JDs at once):
    {
      "resume_id": "...",
      "resume_name": "...",
      "best_match": {"jd_id": "...", "semantic_score": 56.62},
      "all_matches": [
        {"jd_id": "EHR_Data_Analyst_Electronic_Health_parsed_jd",
         "jd_title": "Ehr Data Analyst",
         "semantic_score": 56.62,
         "label": "Strong Match"},
        ...
      ],
      "section_scores": {"skills": 66.99, "full_document": 70.6, ...}
    }
"""

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# Education tier rankings
# ============================================================================
EDU_TIER: dict = {
    "phd": 5, "doctorate": 5, "doctoral": 5,
    "m.tech": 4, "mtech": 4, "m tech": 4,
    "m.e": 4, "me": 4,
    "mba": 4,
    "m.sc": 4, "msc": 4,
    "ms": 4, "m.s": 4,
    "mca": 4,
    "master": 4, "masters": 4,
    "pg": 4, "post graduate": 4,
    "b.tech": 3, "btech": 3, "b tech": 3,
    "b.e": 3, "be": 3,
    "bsc": 3, "b.sc": 3,
    "bca": 3,
    "bba": 3,
    "b.com": 2, "bcom": 2, "b com": 2,
    "ba": 2, "b.a": 2,
    "bachelor": 2, "bachelors": 2,
    "diploma": 1,
    "12th": 0, "hsc": 0, "ssc": 0, "10th": 0,
}


# ============================================================================
# General helpers
# ============================================================================

def _to_str(v: Any) -> str:
    """Extract a clean string from any value."""
    if v is None or isinstance(v, bool):
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dict):
        for k in ("name", "skill", "title", "value", "text", "label",
                  "degree", "field", "role", "position"):
            if k in v and v[k]:
                return _to_str(v[k])
    if isinstance(v, list) and v:
        return _to_str(v[0])
    return str(v).strip() if v else ""


def _to_float(v: Any, default: float = 0.0) -> float:
    """Safely coerce to float (handles '%', ',', dicts, etc.)."""
    if v is None or isinstance(v, bool):
        return default
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace("%", "").replace(",", "")
        try:
            return float(s)
        except ValueError:
            m = re.search(r"[-+]?\d*\.?\d+", s)
            if m:
                try:
                    return float(m.group())
                except ValueError:
                    return default
            return default
    if isinstance(v, dict):
        for k in ("score", "value", "years", "total", "number"):
            if k in v:
                return _to_float(v[k], default)
    if isinstance(v, list) and v:
        return _to_float(v[0], default)
    return default


def _norm_jd_id(jd_id: str) -> str:
    """Normalise a JD id for cross-file matching."""
    return re.sub(r"[^a-z0-9]", "", _to_str(jd_id).lower())


def _edu_tier(degree_text: str) -> int:
    """Return integer tier for a degree string (PhD=5, MBA=4, B.Tech=3...)."""
    t = _to_str(degree_text).lower()
    if not t:
        return 2
    # Match longest keys first (m.tech before tech)
    for key in sorted(EDU_TIER.keys(), key=len, reverse=True):
        if key in t:
            return EDU_TIER[key]
    return 2


# ============================================================================
# Score Calculator
# ============================================================================

class ScoreCalculator:
    """
    Computes individual dimension scores (0-100) for each ATS parameter.

    Contract for every method:
      - Input data may be None (caller handles via weight redistribution)
      - Returns int in range [0, 100]
      - Returns 0 when data cannot be usefully scored (with WARNING log)
      - Trusts pre-computed scores when present in expected fields
    """

    # ------------------------------------------------------------------
    # 1. SKILL MATCH SCORE
    # ------------------------------------------------------------------

    def skill_score(self, skill_data: dict, jd_info: dict) -> int:
        try:
            # (A) Extract candidate skills (list of {skill, category, confidence})
            raw_skills = skill_data.get("skills", [])
            if not isinstance(raw_skills, list):
                raw_skills = []

            candidate: dict = {}        # { skill_name_lower: confidence }
            categories: dict = {}       # { skill_name_lower: category }
            for item in raw_skills:
                if isinstance(item, dict):
                    name = _to_str(item.get("skill") or item.get("name"))
                    conf = _to_float(item.get("confidence"), 1.0)
                    cat  = _to_str(item.get("category"))
                elif isinstance(item, str):
                    name, conf, cat = item.strip(), 1.0, ""
                else:
                    continue
                if name:
                    low = name.lower()
                    candidate[low] = max(candidate.get(low, 0.0), conf)
                    if cat:
                        categories[low] = cat.lower()

            if not candidate:
                logger.warning(
                    "skill_score: no skills extracted. Top-level keys: %s",
                    list(skill_data.keys()) if isinstance(skill_data, dict) else type(skill_data).__name__,
                )
                return 0

            # (B) Pre-computed score at top level?
            for k in ("match_score", "skill_match_score", "skill_score"):
                if k in skill_data and skill_data[k] is not None:
                    v = _to_float(skill_data[k])
                    if 0 < v <= 1.0:
                        v *= 100
                    if 0 < v <= 100:
                        return round(v)

            # (C) JD skills (required + preferred)
            req  = [_to_str(s).lower() for s in (jd_info.get("required_skills") or []) if _to_str(s)]
            pref = [_to_str(s).lower() for s in (jd_info.get("preferred_skills") or []) if _to_str(s)]

            if not req and not pref:
                # No JD skills specified — score by candidate skill breadth/confidence
                avg_conf = sum(candidate.values()) / len(candidate)
                breadth = min(1.0, len(candidate) / 15)   # 15+ skills = full breadth
                return round((avg_conf * 60 + breadth * 40))

            # (D) Weighted intersection (substring tolerance + confidence weighting)
            def match_strength(jd_skills: list) -> float:
                if not jd_skills:
                    return 100.0
                total_weight = 0.0
                for js in jd_skills:
                    best = 0.0
                    for cs, conf in candidate.items():
                        if js == cs:
                            best = max(best, conf)              # exact match
                        elif js in cs or cs in js:
                            best = max(best, conf * 0.9)        # partial match
                    total_weight += best
                return (total_weight / len(jd_skills)) * 100

            req_s  = match_strength(req) if req else 100.0
            pref_s = match_strength(pref) if pref else 100.0
            final  = (req_s * 0.7) + (pref_s * 0.3)
            return max(0, min(100, round(final)))

        except Exception as exc:
            logger.error("skill_score error: %s", exc, exc_info=True)
            return 0

    # ------------------------------------------------------------------
    # 2. EXPERIENCE RELEVANCE SCORE
    # ------------------------------------------------------------------

    def experience_score(self, exp_data: dict, jd_info: dict) -> int:
        try:
            # (A) Trust pre-computed `relevance_analysis.overall_relevance_score`
            rel = exp_data.get("relevance_analysis") or {}
            if isinstance(rel, dict):
                for k in ("overall_relevance_score", "relevance_score", "score"):
                    if k in rel and rel[k] is not None:
                        v = _to_float(rel[k])
                        if 0 < v <= 1.0:
                            v *= 100
                        if 0 <= v <= 100:
                            return round(v)

            # Also accept top-level
            for k in ("overall_relevance_score", "relevance_score",
                      "experience_score", "experience_relevance_score"):
                if k in exp_data and exp_data[k] is not None:
                    v = _to_float(exp_data[k])
                    if 0 < v <= 1.0:
                        v *= 100
                    if 0 < v <= 100:
                        return round(v)

            # (B) Compute from raw: months -> years
            summary = exp_data.get("experience_summary") or {}
            total_months = 0.0
            if isinstance(summary, dict):
                total_months = _to_float(
                    summary.get("total_experience_months")
                    or summary.get("total_months"),
                    0,
                )
            if total_months == 0:
                total_months = _to_float(
                    exp_data.get("total_experience_months")
                    or exp_data.get("total_months"),
                    0,
                )
            # Fallback: sum durations from roles list
            roles_list = exp_data.get("roles") or []
            if total_months == 0 and isinstance(roles_list, list):
                for r in roles_list:
                    if isinstance(r, dict):
                        total_months += _to_float(r.get("duration_months"), 0)

            total_years = total_months / 12.0

            # (C) Role titles
            candidate_roles: list = []
            if isinstance(roles_list, list):
                for r in roles_list:
                    if isinstance(r, dict):
                        t = _to_str(
                            r.get("job_title")
                            or r.get("title")
                            or r.get("role")
                            or r.get("position")
                        )
                        if t:
                            candidate_roles.append(t.lower())
                    elif isinstance(r, str):
                        candidate_roles.append(r.lower())

            if total_years == 0 and not candidate_roles:
                logger.warning(
                    "experience_score: no experience data. Top-level keys: %s",
                    list(exp_data.keys()) if isinstance(exp_data, dict) else type(exp_data).__name__,
                )
                return 0

            # (D) Quantity score (60%)
            min_exp = _to_float(
                jd_info.get("min_experience_years")
                or jd_info.get("min_experience"),
                0,
            )
            max_exp = _to_float(
                jd_info.get("max_experience_years")
                or jd_info.get("max_experience"),
                max(min_exp + 5, 5),
            )
            if total_years >= min_exp:
                if max_exp > min_exp:
                    qty = min(100, ((total_years - min_exp) / (max_exp - min_exp)) * 40 + 60)
                else:
                    qty = 100
            else:
                qty = (total_years / min_exp * 60) if min_exp > 0 else 50

            # (E) Role relevance (40%)
            req_roles = [
                _to_str(r).lower()
                for r in (jd_info.get("required_roles") or [])
                if _to_str(r)
            ]
            job_role_str = _to_str(jd_info.get("job_role") or jd_info.get("title")).lower()
            # Extract key phrases from job_role string (e.g. "data analyst", "healthcare")
            role_phrases = set(req_roles)
            if job_role_str:
                role_phrases.add(job_role_str)
                # Also split into words for substring matching
                for word in job_role_str.split():
                    if len(word) > 3:
                        role_phrases.add(word)

            if role_phrases and candidate_roles:
                hits = sum(
                    1 for rp in role_phrases
                    if any(rp in cr or cr in rp for cr in candidate_roles)
                )
                role_s = min(100, (hits / max(1, len(req_roles) if req_roles else 2)) * 100)
            elif candidate_roles:
                role_s = 50
            else:
                role_s = 30

            final = (qty * 0.6) + (role_s * 0.4)
            return max(0, min(100, round(final)))

        except Exception as exc:
            logger.error("experience_score error: %s", exc, exc_info=True)
            return 0

    # ------------------------------------------------------------------
    # 3. EDUCATION ALIGNMENT SCORE
    # ------------------------------------------------------------------

    def education_score(self, edu_data: dict, jd_info: dict) -> int:
        try:
            # (A) Trust pre-computed education_relevance_score
            for k in ("education_relevance_score", "education_score",
                      "alignment_score", "relevance_score"):
                if k in edu_data and edu_data[k] is not None:
                    v = _to_float(edu_data[k])
                    if 0 < v <= 1.0:
                        v *= 100
                    if 0 < v <= 100:
                        return round(v)

            # (B) Compute from raw
            ed = edu_data.get("education_data") or edu_data
            if not isinstance(ed, dict):
                ed = {}
            profile = ed.get("academic_profile") or {}
            details = ed.get("education_details") or []
            if not isinstance(profile, dict):
                profile = {}

            # Collect degrees + fields
            highest = _to_str(
                profile.get("highest_degree")
                or ed.get("highest_degree")
                or edu_data.get("highest_degree")
            )
            degrees: list = [highest] if highest else []
            fields: list = []
            institutions: list = []
            if isinstance(details, list):
                for e in details:
                    if isinstance(e, dict):
                        d = _to_str(e.get("degree"))
                        f = _to_str(e.get("field") or e.get("field_of_study") or e.get("specialization"))
                        inst = _to_str(e.get("institution") or e.get("university"))
                        if d: degrees.append(d)
                        if f: fields.append(f.lower())
                        if inst: institutions.append(inst.lower())

            if not degrees and not fields:
                logger.warning(
                    "education_score: no degrees/fields. Top-level keys: %s",
                    list(edu_data.keys()) if isinstance(edu_data, dict) else type(edu_data).__name__,
                )
                return 0

            # (C) Degree tier score (50%)
            tiers = [_edu_tier(d) for d in degrees if d]
            candidate_tier = max(tiers) if tiers else 2
            req_tier = _edu_tier(_to_str(jd_info.get("required_education")))
            if candidate_tier >= req_tier:
                tier_s = 100
            elif req_tier > 0:
                tier_s = (candidate_tier / req_tier) * 70
            else:
                tier_s = 70

            # (D) Field relevance (30%)
            pref_fields = [
                _to_str(f).lower()
                for f in (jd_info.get("preferred_fields") or [])
                if _to_str(f)
            ]
            if pref_fields and fields:
                match = any(
                    any(word in f for word in pf.split()) or any(word in pf for word in f.split())
                    for pf in pref_fields for f in fields
                )
                field_s = 100 if match else 40
            elif fields:
                field_s = 60
            else:
                field_s = 50

            # (E) Education strength / certification bonus (20%)
            strength = _to_float(profile.get("education_strength"), 0)
            cert_count = _to_float(profile.get("certification_count"), 0)
            total_deg = _to_float(profile.get("total_degrees"), len(degrees))
            if strength > 0:
                bonus = min(100, strength)
            else:
                bonus = min(100, 50 + cert_count * 10 + total_deg * 5)

            final = (tier_s * 0.5) + (field_s * 0.3) + (bonus * 0.2)
            return max(0, min(100, round(final)))

        except Exception as exc:
            logger.error("education_score error: %s", exc, exc_info=True)
            return 0

    # ------------------------------------------------------------------
    # 4. SEMANTIC SIMILARITY SCORE
    # ------------------------------------------------------------------

    def semantic_score(self, sem_data: dict, jd_info: dict) -> int:
        """
        Look up THIS JD's pre-computed semantic_score inside the resume's
        `all_matches` array. This is the primary signal — the semantic
        engine has already scored the resume against every JD.
        """
        try:
            target_jd    = _to_str(jd_info.get("jd_id") or jd_info.get("id"))
            target_role  = _to_str(jd_info.get("job_role") or jd_info.get("title"))
            target_jd_n  = _norm_jd_id(target_jd)
            target_role_n = _norm_jd_id(target_role)

            # (A) Look inside `all_matches` for the exact JD
            all_matches = sem_data.get("all_matches") or []
            if isinstance(all_matches, list):
                # Pass 1: exact jd_id match
                for m in all_matches:
                    if not isinstance(m, dict):
                        continue
                    mid_n = _norm_jd_id(_to_str(m.get("jd_id")))
                    if target_jd_n and mid_n == target_jd_n:
                        v = _to_float(m.get("semantic_score") or m.get("score"))
                        if 0 < v <= 1.0:
                            v *= 100
                        if 0 <= v <= 100:
                            return round(v)

                # Pass 2: substring match on jd_id
                for m in all_matches:
                    if not isinstance(m, dict):
                        continue
                    mid_n = _norm_jd_id(_to_str(m.get("jd_id")))
                    if target_jd_n and mid_n and (target_jd_n in mid_n or mid_n in target_jd_n):
                        v = _to_float(m.get("semantic_score") or m.get("score"))
                        if 0 < v <= 1.0:
                            v *= 100
                        if 0 <= v <= 100:
                            return round(v)

                # Pass 3: match on jd_title / job_role
                for m in all_matches:
                    if not isinstance(m, dict):
                        continue
                    mt_n = _norm_jd_id(_to_str(m.get("jd_title") or m.get("title")))
                    if target_role_n and mt_n and (target_role_n == mt_n
                                                   or target_role_n in mt_n
                                                   or mt_n in target_role_n):
                        v = _to_float(m.get("semantic_score") or m.get("score"))
                        if 0 < v <= 1.0:
                            v *= 100
                        if 0 <= v <= 100:
                            return round(v)

            # (B) Top-level semantic score fields
            for k in ("similarity_score", "semantic_score", "cosine_similarity",
                      "resume_jd_cosine_similarity", "score"):
                if k in sem_data and sem_data[k] is not None:
                    v = _to_float(sem_data[k])
                    if 0 < v <= 1.0:
                        v *= 100
                    if 0 < v <= 100:
                        return round(v)

            # (C) section_scores.full_document as a fallback
            section_scores = sem_data.get("section_scores") or {}
            if isinstance(section_scores, dict):
                v = _to_float(section_scores.get("full_document"), 0)
                if 0 < v <= 1.0:
                    v *= 100
                if 0 < v <= 100:
                    return round(v)

            # (D) best_match (absolute last resort — not a per-JD signal!)
            best = sem_data.get("best_match")
            if isinstance(best, dict):
                v = _to_float(best.get("semantic_score") or best.get("score"))
                if 0 < v <= 1.0:
                    v *= 100
                if 0 < v <= 100:
                    # This is the best-match score — only use if current JD is close
                    return round(v / 2)    # penalise to avoid inflating every JD

            logger.warning(
                "semantic_score: no usable data for jd_id=%r. Top-level keys: %s",
                target_jd,
                list(sem_data.keys()) if isinstance(sem_data, dict) else type(sem_data).__name__,
            )
            return 0

        except Exception as exc:
            logger.error("semantic_score error: %s", exc, exc_info=True)
            return 0
