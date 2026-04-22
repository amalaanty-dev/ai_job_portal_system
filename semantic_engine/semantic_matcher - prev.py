"""
semantic_engine/semantic_matcher.py
─────────────────────────────────────
Core resume ↔ JD semantic matching engine.

Compares:
  • Skills          (resume skills  ↔  JD required + preferred skills)
  • Experience      (resume summary ↔  JD responsibilities)
  • Projects        (resume projects ↔ JD responsibilities + qualifications)
  • Education       (resume education ↔ JD qualifications)
  • Certifications  (resume certs ↔ JD preferred skills)
  • Full document   (combined representation ↔ full JD)

Produces a structured MatchResult with per-section scores,
an overall weighted score, a match label, and gap analysis.
"""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from .embedder   import embed_resume, embed_jd, embed
from .similarity import (
    cosine_similarity,
    cross_section_similarity,
    weighted_similarity,
    similarity_label,
    identify_gaps,
    DEFAULT_WEIGHTS,
)


# ═══════════════════════════════════════════════════════════════
# RESULT DATACLASS
# ═══════════════════════════════════════════════════════════════

@dataclass
class SectionScore:
    section:    str
    score:      float
    label:      str
    details:    dict = field(default_factory=dict)


@dataclass
class MatchResult:
    resume_id:       str
    jd_id:           str
    resume_name:     str
    jd_title:        str

    # Per-section scores
    skills_score:      float = 0.0
    experience_score:  float = 0.0
    projects_score:    float = 0.0
    education_score:   float = 0.0
    certs_score:       float = 0.0
    full_doc_score:    float = 0.0

    # Weighted overall
    overall_score:     float = 0.0
    match_label:       str   = ""

    # Detailed breakdown
    section_details:   list  = field(default_factory=list)
    gaps:              list  = field(default_factory=list)
    thresholds_used:   dict  = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "resume_id":       self.resume_id,
            "jd_id":           self.jd_id,
            "resume_name":     self.resume_name,
            "jd_title":        self.jd_title,
            "overall_score":   round(self.overall_score, 4),
            "match_label":     self.match_label,
            "section_scores": {
                "skills":             round(self.skills_score,     4),
                "experience_summary": round(self.experience_score, 4),
                "projects":           round(self.projects_score,   4),
                "education":          round(self.education_score,  4),
                "certifications":     round(self.certs_score,      4),
                "full_document":      round(self.full_doc_score,   4),
            },
            "gaps":            self.gaps,
            "thresholds_used": self.thresholds_used,
        }


# ═══════════════════════════════════════════════════════════════
# SECTION WEIGHT PROFILES  (per job type)
# Allows tuning weights for different job families
# ═══════════════════════════════════════════════════════════════

WEIGHT_PROFILES = {

    # Technical roles: skills and experience dominate
    "software_engineering": {
        "skills": 0.40, "experience_summary": 0.30,
        "projects": 0.20, "education": 0.05, "certifications": 0.05,
    },
    "data_analytics": {
        "skills": 0.35, "experience_summary": 0.30,
        "projects": 0.20, "education": 0.10, "certifications": 0.05,
    },
    "healthcare_analytics": {
        "skills": 0.30, "experience_summary": 0.30,
        "projects": 0.15, "education": 0.15, "certifications": 0.10,
    },

    # Business / creative roles: experience and education matter more
    "marketing": {
        "skills": 0.30, "experience_summary": 0.35,
        "projects": 0.20, "education": 0.10, "certifications": 0.05,
    },
    "mechanical_engineering": {
        "skills": 0.35, "experience_summary": 0.25,
        "projects": 0.25, "education": 0.10, "certifications": 0.05,
    },

    # Generic fallback
    "default": DEFAULT_WEIGHTS,
}


def get_weight_profile(job_type: str) -> dict:
    return WEIGHT_PROFILES.get(job_type, WEIGHT_PROFILES["default"])


# ═══════════════════════════════════════════════════════════════
# SEMANTIC MATCHER
# ═══════════════════════════════════════════════════════════════

class SemanticMatcher:
    """
    Computes semantic similarity between a resume and a job description.

    Usage:
        matcher = SemanticMatcher()
        result  = matcher.match(resume_dict, jd_dict)
        print(result.overall_score, result.match_label)
    """

    def __init__(self, thresholds: dict | None = None):
        """
        Args:
            thresholds: custom similarity thresholds dict.
                        Keys: strong_match, good_match, partial_match, weak_match
        """
        self.thresholds = thresholds or {
            "strong_match":  0.75,
            "good_match":    0.55,
            "partial_match": 0.40,
            "weak_match":    0.25,
        }

    # ───────────────────────────────────────────────────────────
    # MAIN MATCH ENTRY POINT
    # ───────────────────────────────────────────────────────────

    def match(self, resume: dict, jd: dict) -> MatchResult:
        """
        Full semantic match of resume against JD.

        Args:
            resume: structured resume dict (see sample_data.py)
            jd:     structured JD dict (see sample_data.py)

        Returns:
            MatchResult with per-section scores and overall score.
        """
        job_type = jd.get("job_type", "default")
        weights  = get_weight_profile(job_type)

        # ── Embed both documents ──
        resume_emb = embed_resume(resume)
        jd_emb     = embed_jd(jd)

        # ── Section-level matching ──
        skills_score     = self._match_skills(resume_emb, jd_emb)
        experience_score = self._match_experience(resume_emb, jd_emb)
        projects_score   = self._match_projects(resume_emb, jd_emb)
        education_score  = self._match_education(resume_emb, jd_emb)
        certs_score      = self._match_certifications(resume_emb, jd_emb)
        full_doc_score   = cosine_similarity(resume_emb["full"], jd_emb["full"])

        section_scores = {
            "skills":             skills_score,
            "experience_summary": experience_score,
            "projects":           projects_score,
            "education":          education_score,
            "certifications":     certs_score,
        }

        # ── Weighted overall score ──
        overall = weighted_similarity(section_scores, weights)

        # Blend with full-document score for smoothing
        # (full_doc captures holistic fit beyond section-level noise)
        overall = round(overall * 0.80 + full_doc_score * 0.20, 4)

        # ── Gap analysis ──
        gaps = identify_gaps(section_scores, threshold=self.thresholds["partial_match"])

        # ── Build result ──
        result = MatchResult(
            resume_id      = resume.get("id", "unknown"),
            jd_id          = jd.get("id",     "unknown"),
            resume_name    = resume.get("name", ""),
            jd_title       = jd.get("title",   ""),
            skills_score      = skills_score,
            experience_score  = experience_score,
            projects_score    = projects_score,
            education_score   = education_score,
            certs_score       = certs_score,
            full_doc_score    = full_doc_score,
            overall_score     = overall,
            match_label       = similarity_label(overall, self.thresholds),
            gaps              = gaps,
            thresholds_used   = self.thresholds,
        )

        return result

    # ───────────────────────────────────────────────────────────
    # SECTION MATCHERS
    # ───────────────────────────────────────────────────────────

    def _match_skills(self, resume_emb: dict, jd_emb: dict) -> float:
        """
        Skills matching: compare resume skills against BOTH required
        and preferred JD skills; take the weighted best.
        """
        skills_vec = resume_emb["skills"]

        # Skills vs required skills  (higher weight)
        req_score  = cosine_similarity(skills_vec, jd_emb["required_skills"])
        # Skills vs preferred skills (lower weight)
        pref_score = cosine_similarity(skills_vec, jd_emb.get("preferred_skills",
                                                               np.zeros(384, dtype=np.float32)))
        # Skills vs full JD responsibilities  (catches implicit skill needs)
        resp_score = cosine_similarity(skills_vec, jd_emb["responsibilities"])

        # Weighted combination: required > preferred > responsibilities
        score = req_score * 0.55 + pref_score * 0.25 + resp_score * 0.20
        return round(score, 4)

    def _match_experience(self, resume_emb: dict, jd_emb: dict) -> float:
        """
        Experience matching: resume summary ↔ JD responsibilities + qualifications.
        """
        exp_vec = resume_emb["experience_summary"]

        resp_score = cosine_similarity(exp_vec, jd_emb["responsibilities"])
        qual_score = cosine_similarity(exp_vec, jd_emb["qualifications"])

        score = resp_score * 0.65 + qual_score * 0.35
        return round(score, 4)

    def _match_projects(self, resume_emb: dict, jd_emb: dict) -> float:
        """
        Projects matching: resume projects ↔ JD responsibilities.
        Projects demonstrate applied skill — compare to what the role does.
        """
        proj_vec = resume_emb["projects"]

        resp_score = cosine_similarity(proj_vec, jd_emb["responsibilities"])
        req_score  = cosine_similarity(proj_vec, jd_emb["required_skills"])

        score = resp_score * 0.70 + req_score * 0.30
        return round(score, 4)

    def _match_education(self, resume_emb: dict, jd_emb: dict) -> float:
        """
        Education matching: resume education ↔ JD qualifications.
        """
        edu_vec = resume_emb["education"]
        score   = cosine_similarity(edu_vec, jd_emb["qualifications"])
        return round(score, 4)

    def _match_certifications(self, resume_emb: dict, jd_emb: dict) -> float:
        """
        Certifications matching: resume certs ↔ JD preferred skills + qualifications.
        """
        cert_vec = resume_emb["certifications"]
        if not np.any(cert_vec):          # no certifications listed
            return 0.0

        pref_score = cosine_similarity(cert_vec, jd_emb.get("preferred_skills",
                                                              np.zeros(384, dtype=np.float32)))
        qual_score = cosine_similarity(cert_vec, jd_emb["qualifications"])

        score = pref_score * 0.60 + qual_score * 0.40
        return round(score, 4)

    # ───────────────────────────────────────────────────────────
    # BATCH MATCHING
    # ───────────────────────────────────────────────────────────

    def match_batch(
        self,
        resumes: list[dict],
        jds:     list[dict],
    ) -> list[MatchResult]:
        """
        Match every resume against every JD (all-pairs).
        Returns a flat list of MatchResult objects.
        """
        results = []
        total   = len(resumes) * len(jds)
        count   = 0

        for resume in resumes:
            for jd in jds:
                result = self.match(resume, jd)
                results.append(result)
                count += 1
                print(f"  [{count}/{total}] {resume.get('name','?'):<20} ↔  {jd.get('title','?'):<35}  {result.overall_score:.3f}  {result.match_label}")

        return results

    def best_jd_for_resume(
        self,
        resume:  dict,
        jds:     list[dict],
    ) -> tuple[MatchResult, list[MatchResult]]:
        """
        Find the best-matching JD for a given resume.

        Returns:
            (best_result, all_results_sorted_descending)
        """
        all_results = [self.match(resume, jd) for jd in jds]
        all_results.sort(key=lambda r: r.overall_score, reverse=True)
        return all_results[0], all_results

    def best_resume_for_jd(
        self,
        jd:      dict,
        resumes: list[dict],
    ) -> tuple[MatchResult, list[MatchResult]]:
        """
        Rank all resumes against a single JD.

        Returns:
            (best_result, all_results_sorted_descending)
        """
        all_results = [self.match(resume, jd) for resume in resumes]
        all_results.sort(key=lambda r: r.overall_score, reverse=True)
        return all_results[0], all_results
