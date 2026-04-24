"""
ats_engine/ats_scorer.py
────────────────────────
Core ATS scoring engine.
Reads real data shapes from:
  extracted_skills/  → skills.data  list[{skill, category, confidence}]
  education_outputs/ → education_data.academic_profile + education_details + certifications
  experience_outputs/→ experience_summary, roles, timeline_analysis, relevance_analysis
  semantic_outputs/  → section_scores, all_matches, gaps, best_match
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

log = logging.getLogger(__name__)

# ── Weight profiles ────────────────────────────────────────────────────────────

WEIGHT_PROFILES: dict[str, dict[str, float]] = {
    "healthcare_analytics": {
        "skill_match":            0.30,
        "experience_relevance":   0.25,
        "education_alignment":    0.20,
        "semantic_similarity":    0.25,
    },
    "ml_engineering": {
        "skill_match":            0.40,
        "experience_relevance":   0.30,
        "education_alignment":    0.10,
        "semantic_similarity":    0.20,
    },
    "data_science": {
        "skill_match":            0.35,
        "experience_relevance":   0.30,
        "education_alignment":    0.15,
        "semantic_similarity":    0.20,
    },
    "business_analyst": {
        "skill_match":            0.25,
        "experience_relevance":   0.35,
        "education_alignment":    0.25,
        "semantic_similarity":    0.15,
    },
    "entry_level": {
        "skill_match":            0.30,
        "experience_relevance":   0.15,
        "education_alignment":    0.35,
        "semantic_similarity":    0.20,
    },
    "senior_ic": {
        "skill_match":            0.35,
        "experience_relevance":   0.40,
        "education_alignment":    0.10,
        "semantic_similarity":    0.15,
    },
    "default": {
        "skill_match":            0.30,
        "experience_relevance":   0.30,
        "education_alignment":    0.20,
        "semantic_similarity":    0.20,
    },
}

GRADE_THRESHOLDS = [
    (85, "A", "Strong Match – Recommend for Interview"),
    (70, "B", "Good Match – Consider for Interview"),
    (55, "C", "Partial Match – Screen with Caution"),
    (40, "D", "Weak Match – Not Recommended"),
    (0,  "F", "Mismatch – Do Not Proceed"),
]

DEGREE_WEIGHT: dict[str, float] = {
    "phd": 100, "doctorate": 100,
    "msc": 90, "ms": 90, "m.s": 90, "mtech": 90, "m.tech": 90,
    "mba": 75,
    "btech": 70, "b.tech": 70, "bsc": 65, "bs": 65, "b.s": 65,
    "bba": 55, "bca": 55, "ba": 50, "b.a": 50,
    "diploma": 35, "certificate": 25,
}


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class ScoreComponent:
    name:           str
    raw_score:      float       # 0-100 before weight
    weight:         float       # effective weight used
    weighted_score: float       # raw_score * weight
    confidence:     float       # 0-1 data reliability
    evidence:       list[str] = field(default_factory=list)
    missing_data:   bool = False
    penalty_applied: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ATSResult:
    resume_id:         str
    jd_slug:           str
    job_title:         str
    final_score:       float
    grade:             str
    recommendation:    str
    components:        list[ScoreComponent]
    weight_profile:    str
    gap_analysis:      list[dict]
    strengths:         list[str]
    improvement_areas: list[str]
    load_errors:       list[str] = field(default_factory=list)
    metadata:          dict      = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["components"] = [c.to_dict() for c in self.components]
        return d


# ── Grade helper ──────────────────────────────────────────────────────────────

def _grade(score: float) -> tuple[str, str]:
    for threshold, grade, rec in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade, rec
    return "F", "Mismatch – Do Not Proceed"


# ════════════════════════════════════════════════════════════════
#  SUB-SCORERS  (each reads the real JSON schema)
# ════════════════════════════════════════════════════════════════

def score_skill_match(
    skills_data: Optional[dict],
    jd_required_skills: list[str] | None = None,
    jd_preferred_skills: list[str] | None = None,
) -> ScoreComponent:
    """
    Reads: skills_data["skills"] → list[{skill, category, confidence}]
    """
    evidence: list[str] = []

    if not skills_data:
        return ScoreComponent(
            name="skill_match", raw_score=0.0, weight=0.0,
            weighted_score=0.0, confidence=0.0,
            evidence=["No skills data available"],
            missing_data=True, penalty_applied=0.0,
        )

    skill_list: list[dict] = skills_data.get("skills", [])
    if not skill_list:
        return ScoreComponent(
            name="skill_match", raw_score=0.0, weight=0.0,
            weighted_score=0.0, confidence=0.0,
            evidence=["Skills list is empty"],
            missing_data=True, penalty_applied=0.0,
        )

    candidate_skills: dict[str, dict] = {
        s["skill"].lower(): s for s in skill_list if "skill" in s
    }

    # Average detection confidence → baseline quality
    avg_conf = sum(s.get("confidence", 0) for s in skill_list) / len(skill_list)
    raw = avg_conf * 100

    penalty = 0.0

    if jd_required_skills or jd_preferred_skills:
        req  = {s.lower() for s in (jd_required_skills  or [])}
        pref = {s.lower() for s in (jd_preferred_skills or [])}
        cand = set(candidate_skills.keys())

        req_matched  = req  & cand
        pref_matched = pref & cand
        missing_req  = req  - cand

        req_score  = (len(req_matched)  / len(req)  * 100) if req  else 50.0
        pref_score = (len(pref_matched) / len(pref) * 100) if pref else 50.0

        overlap = req_score * 0.70 + pref_score * 0.30
        raw = avg_conf * 100 * 0.30 + overlap * 0.70

        evidence.append(
            f"Required skills matched: {sorted(req_matched)} ({len(req_matched)}/{len(req)})"
        )
        evidence.append(
            f"Preferred skills matched: {sorted(pref_matched)} ({len(pref_matched)}/{len(pref)})"
        )
        if missing_req:
            penalty = len(missing_req) / max(len(req), 1) * 10
            evidence.append(f"Missing required skills: {sorted(missing_req)} → -{penalty:.1f} pts")
    else:
        by_cat: dict[str, int] = {}
        for s in skill_list:
            by_cat[s.get("category", "other")] = by_cat.get(s.get("category", "other"), 0) + 1
        evidence.append(f"Skills by category: {by_cat}")
        evidence.append(f"Total skills detected: {len(candidate_skills)}")

    high_conf = [s["skill"] for s in skill_list if s.get("confidence", 0) >= 0.90]
    evidence.append(f"High-confidence skills ({len(high_conf)}): {high_conf}")
    evidence.append(f"Average skill confidence: {avg_conf:.2f}")

    raw = max(0.0, min(100.0, raw - penalty))
    confidence = min(1.0, len(candidate_skills) / 20)

    return ScoreComponent(
        name="skill_match",
        raw_score=round(raw, 2),
        weight=0.0,
        weighted_score=0.0,
        confidence=round(confidence, 2),
        evidence=evidence,
        missing_data=False,
        penalty_applied=round(penalty, 2),
    )


def score_experience_relevance(
    experience_data: Optional[dict],
    target_years: float = 3.0,
    role_keywords: list[str] | None = None,
) -> ScoreComponent:
    """
    Reads: experience_summary.total_experience_months,
           roles[],  timeline_analysis, relevance_analysis.overall_relevance_score
    """
    evidence: list[str] = []

    if not experience_data:
        return ScoreComponent(
            name="experience_relevance", raw_score=0.0, weight=0.0,
            weighted_score=0.0, confidence=0.0,
            evidence=["No experience data available"],
            missing_data=True, penalty_applied=0.0,
        )

    total_months = (experience_data
                    .get("experience_summary", {})
                    .get("total_experience_months", 0))
    total_years  = total_months / 12

    pre_relevance = (experience_data
                     .get("relevance_analysis", {})
                     .get("overall_relevance_score", None))

    roles: list[dict] = experience_data.get("roles", [])
    timeline:   dict  = experience_data.get("timeline_analysis", {})

    # Years score — logistic saturation
    ratio      = total_years / max(target_years, 0.01)
    years_score = 100 * (1 - math.exp(-1.5 * ratio))
    evidence.append(
        f"Total experience: {total_years:.1f} yrs "
        f"(target: {target_years} yrs) → years_score={years_score:.1f}"
    )

    # Role keyword match
    kw_score = 50.0
    if role_keywords and roles:
        all_titles = " ".join(r.get("job_title", "").lower() for r in roles)
        matched_kw = [kw for kw in role_keywords if kw.lower() in all_titles]
        kw_score   = min(100.0, len(matched_kw) / max(len(role_keywords), 1) * 100)
        evidence.append(f"Role keywords matched: {matched_kw}")

    # Blend
    if pre_relevance is not None:
        raw = pre_relevance * 0.50 + years_score * 0.30 + kw_score * 0.20
        evidence.append(f"Pre-computed relevance score: {pre_relevance}")
    else:
        raw = years_score * 0.60 + kw_score * 0.40

    # Timeline penalties
    penalty = 0.0
    gaps     = timeline.get("gaps", [])
    overlaps = timeline.get("overlaps", [])
    if gaps:
        penalty += len(gaps) * 3
        evidence.append(f"Career gaps detected: {len(gaps)} → -{len(gaps)*3} pts")
    if overlaps:
        penalty += len(overlaps) * 1
        evidence.append(f"Role overlaps (minor): {len(overlaps)} → -{len(overlaps)} pts")

    for r in roles:
        evidence.append(
            f"  • {r.get('job_title')} @ {r.get('company')} "
            f"({r.get('duration_months','?')} months)"
        )

    raw = max(0.0, min(100.0, raw - penalty))

    return ScoreComponent(
        name="experience_relevance",
        raw_score=round(raw, 2),
        weight=0.0,
        weighted_score=0.0,
        confidence=0.9 if roles else 0.3,
        evidence=evidence,
        missing_data=False,
        penalty_applied=round(penalty, 2),
    )


def score_education_alignment(
    education_data: Optional[dict],
    preferred_degrees: list[str] | None = None,
    preferred_fields:  list[str] | None = None,
    min_cert_count: int = 0,
) -> ScoreComponent:
    """
    Reads: education_data.academic_profile.{highest_degree, certification_count},
           education_data.education_details[],
           education_data.education_relevance_score   (top-level, injected by data_loader)
    """
    evidence: list[str] = []

    if not education_data:
        return ScoreComponent(
            name="education_alignment", raw_score=0.0, weight=0.0,
            weighted_score=0.0, confidence=0.0,
            evidence=["No education data available"],
            missing_data=True, penalty_applied=0.0,
        )

    profile  = education_data.get("academic_profile", {})
    details  = education_data.get("education_details", [])
    pre_score = education_data.get("education_relevance_score", None)

    highest    = profile.get("highest_degree", "").lower()
    cert_count = profile.get("certification_count", 0)
    edu_strength = profile.get("education_strength", None)

    # Degree level score
    degree_score = next(
        (v for k, v in DEGREE_WEIGHT.items() if k in highest), 40.0
    )
    evidence.append(
        f"Highest degree: {profile.get('highest_degree','Unknown')} "
        f"→ degree_score={degree_score:.0f}"
    )

    # Field relevance
    field_score = 50.0
    if preferred_fields and details:
        all_fields = " ".join(d.get("field", "").lower() for d in details)
        matched_f  = [f for f in preferred_fields if f.lower() in all_fields]
        if matched_f:
            field_score = min(100.0, 50 + len(matched_f) * 25)
            evidence.append(f"Relevant field(s) matched: {matched_f}")
        else:
            field_score = 30.0
            evidence.append("No preferred field match found in education history")
    else:
        for d in details:
            evidence.append(
                f"  • {d.get('degree')} in {d.get('field')} "
                f"– {d.get('institution')} ({d.get('graduation_year','')})"
            )

    # Certification score
    penalty = 0.0
    if min_cert_count > 0:
        cert_score = min(100.0, cert_count / min_cert_count * 100)
        if cert_count == 0:
            penalty += 10.0
            evidence.append(
                f"No certifications found; {min_cert_count} required → -10 pts"
            )
        else:
            evidence.append(f"Certifications: {cert_count}/{min_cert_count} required")
    else:
        cert_score = min(100.0, cert_count * 20)
        evidence.append(f"Certifications found: {cert_count}")

    # Use pre-computed score if available
    if pre_score is not None:
        raw = pre_score * 0.50 + degree_score * 0.25 + field_score * 0.15 + cert_score * 0.10
        evidence.append(f"Pre-computed education relevance: {pre_score}")
    elif edu_strength is not None:
        raw = edu_strength * 0.40 + degree_score * 0.30 + field_score * 0.20 + cert_score * 0.10
        evidence.append(f"Education strength score: {edu_strength}")
    else:
        raw = degree_score * 0.45 + field_score * 0.35 + cert_score * 0.20

    raw = max(0.0, min(100.0, raw - penalty))

    return ScoreComponent(
        name="education_alignment",
        raw_score=round(raw, 2),
        weight=0.0,
        weighted_score=0.0,
        confidence=0.85 if details else 0.4,
        evidence=evidence,
        missing_data=False,
        penalty_applied=round(penalty, 2),
    )


def score_semantic_similarity(
    semantic_data: Optional[dict],
    jd_slug: str | None = None,
) -> ScoreComponent:
    """
    Reads: section_scores.{skills, experience_summary, projects, education,
                            certifications, full_document},
           all_matches[{jd_id, semantic_score, label}],
           best_match, gaps[{section, score, gap_severity}]
    """
    evidence: list[str] = []

    if not semantic_data:
        return ScoreComponent(
            name="semantic_similarity", raw_score=0.0, weight=0.0,
            weighted_score=0.0, confidence=0.0,
            evidence=["No semantic data available"],
            missing_data=True, penalty_applied=0.0,
        )

    section_scores = semantic_data.get("section_scores", {})
    all_matches    = semantic_data.get("all_matches",    [])
    best_match     = semantic_data.get("best_match",     {})
    gaps           = semantic_data.get("gaps",           [])

    # Section breakdown
    full_doc = section_scores.get("full_document", 0.0)
    skills_s = section_scores.get("skills",             0.0)
    exp_s    = section_scores.get("experience_summary", 0.0)
    proj_s   = section_scores.get("projects",           0.0)
    edu_s    = section_scores.get("education",          0.0)
    cert_s   = section_scores.get("certifications",     0.0)

    evidence.append(f"Full document semantic score: {full_doc:.2f}")
    evidence.append(
        f"Section scores → skills:{skills_s}, experience:{exp_s}, "
        f"projects:{proj_s}, education:{edu_s}, certifications:{cert_s}"
    )

    # Target JD score
    target_score = full_doc
    if jd_slug and all_matches:
        # Try exact match first, then substring match
        jd_slug_norm = jd_slug.replace("-", "_").lower()
        match = next(
            (m for m in all_matches
             if m.get("jd_id", "").replace("-", "_").lower() == jd_slug_norm),
            None,
        )
        if match is None:
            # Partial key match
            match = next(
                (m for m in all_matches
                 if jd_slug_norm in m.get("jd_id", "").replace("-", "_").lower()),
                None,
            )
        if match:
            target_score = match.get("semantic_score", full_doc)
            evidence.append(
                f"Targeted JD '{match.get('jd_id')}' → "
                f"score={target_score:.2f} ({match.get('label','')})"
            )
        else:
            bm = best_match
            evidence.append(
                f"JD '{jd_slug}' not found; using best match: "
                f"{bm.get('jd_title','')} (score={bm.get('semantic_score','?')}, "
                f"{bm.get('label','')})"
            )
    else:
        bm = best_match
        evidence.append(
            f"Best JD match: {bm.get('jd_title','')} "
            f"(score={bm.get('semantic_score','?')}, {bm.get('label','')})"
        )

    # Weighted section blend
    raw = (
        target_score * 0.50
        + skills_s   * 0.20
        + proj_s     * 0.15
        + exp_s      * 0.10
        + edu_s      * 0.05
    )

    # Gap penalties
    penalty = 0.0
    for g in gaps:
        sev = g.get("gap_severity", "")
        if   sev == "critical": penalty += 5
        elif sev == "missing":  penalty += 3
        evidence.append(
            f"Gap: {g.get('section','?')} "
            f"(severity={sev}, score={g.get('score',0):.3f})"
        )

    raw = max(0.0, min(100.0, raw - penalty))

    return ScoreComponent(
        name="semantic_similarity",
        raw_score=round(raw, 2),
        weight=0.0,
        weighted_score=0.0,
        confidence=0.85 if section_scores else 0.4,
        evidence=evidence,
        missing_data=False,
        penalty_applied=round(penalty, 2),
    )


# ════════════════════════════════════════════════════════════════
#  ORCHESTRATOR
# ════════════════════════════════════════════════════════════════

class ATSScorer:
    """
    Main ATS scoring orchestrator.

    scorer = ATSScorer(weight_profile="healthcare_analytics")
    result = scorer.score(candidate_data, job_title="...", ...)
    """

    def __init__(
        self,
        weight_profile: str = "default",
        custom_weights: dict[str, float] | None = None,
    ):
        if custom_weights:
            total = sum(custom_weights.values())
            if abs(total - 1.0) > 0.01:
                raise ValueError(
                    f"Custom weights must sum to 1.0; got {total:.4f}"
                )
            self.weights      = custom_weights
            self.profile_name = "custom"
        elif weight_profile in WEIGHT_PROFILES:
            self.weights      = WEIGHT_PROFILES[weight_profile]
            self.profile_name = weight_profile
        else:
            log.warning("Unknown weight profile '%s'; using 'default'", weight_profile)
            self.weights      = WEIGHT_PROFILES["default"]
            self.profile_name = "default"

    def score(
        self,
        candidate_data,                          # CandidateData or plain dict
        job_title:           str = "Unknown Position",
        jd_required_skills:  list[str] | None = None,
        jd_preferred_skills: list[str] | None = None,
        target_years:        float = 3.0,
        role_keywords:       list[str] | None = None,
        preferred_degrees:   list[str] | None = None,
        preferred_fields:    list[str] | None = None,
        min_cert_count:      int = 0,
    ) -> ATSResult:

        # Support both CandidateData objects and plain dicts
        if hasattr(candidate_data, "resume_id"):
            resume_id       = candidate_data.resume_id
            jd_slug         = candidate_data.jd_slug
            skills_data     = candidate_data.skills_data
            education_data  = candidate_data.education_data
            experience_data = candidate_data.experience_data
            semantic_data   = candidate_data.semantic_data
            load_errors     = candidate_data.load_errors
        else:
            resume_id       = candidate_data.get("candidate_id", "unknown")
            jd_slug         = candidate_data.get("jd_slug", "unknown")
            skills_data     = candidate_data.get("skills_data")
            education_data  = candidate_data.get("education_data")
            experience_data = candidate_data.get("experience_data")
            semantic_data   = candidate_data.get("semantic_data")
            load_errors     = candidate_data.get("load_errors", [])

        # ── 1. Sub-scores ────────────────────────────────────────────────────
        skill_comp = score_skill_match(skills_data, jd_required_skills, jd_preferred_skills)
        exp_comp   = score_experience_relevance(experience_data, target_years, role_keywords)
        edu_comp   = score_education_alignment(education_data, preferred_degrees,
                                               preferred_fields, min_cert_count)
        sem_comp   = score_semantic_similarity(semantic_data, jd_slug)

        components = [skill_comp, exp_comp, edu_comp, sem_comp]
        dim_map = {
            "skill_match":          skill_comp,
            "experience_relevance": exp_comp,
            "education_alignment":  edu_comp,
            "semantic_similarity":  sem_comp,
        }

        # ── 2. Weight redistribution for missing data ────────────────────────
        effective_weights = dict(self.weights)
        missing_w = sum(
            effective_weights[k] for k, c in dim_map.items() if c.missing_data
        )
        present_keys = [k for k, c in dim_map.items() if not c.missing_data]
        if present_keys and missing_w > 0:
            bonus = missing_w / len(present_keys)
            for k in present_keys:
                effective_weights[k] += bonus

        # ── 3. Weighted + confidence-adjusted scoring ─────────────────────────
        final_score = 0.0
        for k, comp in dim_map.items():
            w  = effective_weights[k]
            comp.weight         = round(w, 4)
            comp.weighted_score = round(comp.raw_score * w, 4)

            conf = comp.confidence
            # Low confidence pulls toward neutral midpoint
            adjusted = comp.raw_score * w * conf + w * 50 * (1 - conf)
            if comp.missing_data:
                adjusted *= 0.60  # hard penalty for missing data
            final_score += adjusted

        final_score = round(max(0.0, min(100.0, final_score)), 2)

        # ── 4. Grade + recommendation ─────────────────────────────────────────
        grade, recommendation = _grade(final_score)

        # ── 5. Gap analysis ───────────────────────────────────────────────────
        gap_analysis: list[dict] = []
        for comp in components:
            if comp.raw_score < 40:
                gap_analysis.append({
                    "dimension": comp.name,
                    "score":     comp.raw_score,
                    "severity":  "critical" if comp.raw_score < 20 else "moderate",
                    "action":    f"Improve {comp.name.replace('_', ' ')}",
                })

        # ── 6. Strengths / improvement areas ──────────────────────────────────
        sorted_comps = sorted(components, key=lambda c: c.raw_score, reverse=True)
        strengths = [
            f"{c.name.replace('_',' ').title()} ({c.raw_score:.1f}/100)"
            for c in sorted_comps[:2] if c.raw_score >= 50
        ]
        improvement_areas = [
            f"{c.name.replace('_',' ').title()} ({c.raw_score:.1f}/100)"
            for c in sorted_comps if c.raw_score < 50
        ]

        return ATSResult(
            resume_id        = resume_id,
            jd_slug          = jd_slug,
            job_title        = job_title,
            final_score      = final_score,
            grade            = grade,
            recommendation   = recommendation,
            components       = components,
            weight_profile   = self.profile_name,
            gap_analysis     = gap_analysis,
            strengths        = strengths,
            improvement_areas= improvement_areas,
            load_errors      = load_errors,
            metadata={
                "effective_weights":       {k: round(v, 4) for k, v in effective_weights.items()},
                "missing_data_components": [c.name for c in components if c.missing_data],
                "target_years":            target_years,
            },
        )

    def batch_score(
        self,
        candidates: list,
        **kwargs,
    ) -> list[ATSResult]:
        results = [self.score(c, **kwargs) for c in candidates]
        return sorted(results, key=lambda r: r.final_score, reverse=True)
