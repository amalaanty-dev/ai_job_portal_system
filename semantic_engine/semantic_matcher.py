"""
semantic_engine/semantic_matcher.py
─────────────────────────────────────
Core resume ↔ JD semantic matching engine.

FIXES in this version
─────────────────────
1. Uses resume_emb["_populated"] to pass the populated-sections map to
   weighted_similarity() so genuinely missing sections (empty [] in the
   resume JSON) have their weight redistributed instead of dragging
   the score to zero.

2. identify_gaps() receives the populated map so gaps are labelled
   "missing" vs "critical" correctly.

3. Thresholds default to TFIDF_THRESHOLDS from similarity.py — correctly
   calibrated for TF-IDF cosine score range instead of sentence-transformer
   range.

4. job_type inference — when the JD doesn't explicitly set "job_type",
   the matcher attempts to infer it from the JD title so the right
   weight profile and thresholds are applied automatically.

5. full_doc blending weight raised from 20% → 30%. The full-document
   embedding captures holistic fit better than section-level matching
   when individual sections are sparse/missing.

6. Section-level matchers: score clamped to avoid negative values;
   skills matcher checks preferred_skills and falls back gracefully
   when absent.
"""

from dataclasses import dataclass, field
from typing import Optional
import re
import numpy as np

from .embedder   import embed_resume, embed_jd, embed, _get_vectorizer, _N_DOMAINS
from .similarity import (
    cosine_similarity,
    cross_section_similarity,
    weighted_similarity,
    similarity_label,
    identify_gaps,
    DEFAULT_WEIGHTS,
    TFIDF_THRESHOLDS,
)


# ═══════════════════════════════════════════════════════════════
# RESULT DATACLASSES
# ═══════════════════════════════════════════════════════════════

@dataclass
class SectionScore:
    section:  str
    score:    float
    label:    str
    details:  dict = field(default_factory=dict)


@dataclass
class MatchResult:
    resume_id:        str
    jd_id:            str
    resume_name:      str
    jd_title:         str

    skills_score:     float = 0.0
    experience_score: float = 0.0
    projects_score:   float = 0.0
    education_score:  float = 0.0
    certs_score:      float = 0.0
    full_doc_score:   float = 0.0

    overall_score:    float = 0.0
    match_label:      str   = ""

    section_details:  list  = field(default_factory=list)
    gaps:             list  = field(default_factory=list)
    thresholds_used:  dict  = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "resume_id":       self.resume_id,
            "jd_id":           self.jd_id,
            "resume_name":     self.resume_name,
            "jd_title":        self.jd_title,
            "semantic_score":  round(self.overall_score * 100, 2),   # e.g. 40.53
            "match_label":     self.match_label,
            "section_scores": {
                "skills":             round(self.skills_score     * 100, 2),
                "experience_summary": round(self.experience_score * 100, 2),
                "projects":           round(self.projects_score   * 100, 2),
                "education":          round(self.education_score  * 100, 2),
                "certifications":     round(self.certs_score      * 100, 2),
                "full_document":      round(self.full_doc_score   * 100, 2),
            },
            "gaps":            self.gaps,
            "thresholds_used": self.thresholds_used,
        }


# ═══════════════════════════════════════════════════════════════
# JOB-TYPE INFERENCE
# ═══════════════════════════════════════════════════════════════

_JOB_TYPE_PATTERNS = [
    (r"healthcare|clinical|medical|health\s+data|patient|hipaa|ehr|epic|cerner|"
     r"revenue\s+cycle|claims|billing|epidemiol|public\s+health|genomic|"
     r"telehealth|wearable\s+health|population\s+health",   "healthcare_analytics"),
    (r"data\s+(analyst|scientist|engineer|analytics)|business\s+intelligence|"
     r"machine\s+learning\s+engineer|analytics\s+engineer",            "data_analytics"),
    (r"software\s+engineer|backend|frontend|full.?stack|devops|"
     r"platform\s+engineer|site\s+reliability|sre",                   "software_engineering"),
    (r"market(ing)?|brand|campaign|seo|sem|growth\s+hacker|"
     r"demand\s+generation|product\s+market",                          "marketing"),
    (r"mechanical|manufacturing|product\s+design|cad|solidworks|"
     r"ansys|fea|cnc|industrial\s+engineer",                           "mechanical_engineering"),
]


def infer_job_type(title: str, jd: dict) -> str:
    """
    Infer job_type from JD title or role description when not explicitly set.
    Falls back to 'default'.
    """
    explicit = jd.get("job_type", "")
    if explicit and explicit != "default":
        return explicit

    # Search in title first, then in role/responsibilities text
    search_text = (title + " " + " ".join(
        str(v) for v in (
            jd.get("role", []) or
            jd.get("responsibilities", []) or []
        )
    )).lower()

    for pattern, jt in _JOB_TYPE_PATTERNS:
        if re.search(pattern, search_text, re.IGNORECASE):
            return jt

    return "default"


# ═══════════════════════════════════════════════════════════════
# WEIGHT PROFILES
# ═══════════════════════════════════════════════════════════════

WEIGHT_PROFILES = {
    "software_engineering": {
        "skills": 0.40, "experience_summary": 0.35,
        "projects": 0.18, "education": 0.04, "certifications": 0.03,
    },
    "data_analytics": {
        "skills": 0.38, "experience_summary": 0.33,
        "projects": 0.18, "education": 0.07, "certifications": 0.04,
    },
    # FIX: healthcare weights keep education meaningful but don't zero
    # the score when it's absent; certifications given a fair share.
    "healthcare_analytics": {
        "skills": 0.35, "experience_summary": 0.35,
        "projects": 0.12, "education": 0.10, "certifications": 0.08,
    },
    "marketing": {
        "skills": 0.30, "experience_summary": 0.38,
        "projects": 0.20, "education": 0.08, "certifications": 0.04,
    },
    "mechanical_engineering": {
        "skills": 0.36, "experience_summary": 0.28,
        "projects": 0.24, "education": 0.08, "certifications": 0.04,
    },
    "default": DEFAULT_WEIGHTS,
}


def get_weight_profile(job_type: str) -> dict:
    return WEIGHT_PROFILES.get(job_type, WEIGHT_PROFILES["default"])


def _zero_vec() -> np.ndarray:
    vect = _get_vectorizer()
    return np.zeros(len(vect.vocabulary_) + _N_DOMAINS, dtype=np.float32)


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
                        Defaults to TFIDF_THRESHOLDS (calibrated for TF-IDF range).
        """
        # FIX: default to TF-IDF-calibrated thresholds, not the old sentence-transformer ones
        self.thresholds = thresholds or TFIDF_THRESHOLDS

    # ───────────────────────────────────────────────────────────
    # MAIN MATCH
    # ───────────────────────────────────────────────────────────

    def match(self, resume: dict, jd: dict) -> MatchResult:
        """
        Full semantic match of resume against JD.

        Returns MatchResult with per-section scores and overall score.
        """
        jd_title = jd.get("title", "") or jd.get("id", "")

        # FIX: infer job_type if not explicitly set on the JD
        job_type = infer_job_type(jd_title, jd)
        weights  = get_weight_profile(job_type)

        # ── Embed both documents ──
        resume_emb = embed_resume(resume)
        jd_emb     = embed_jd(jd)

        # FIX: extract populated map so weight redistribution works
        populated = resume_emb.pop("_populated", None)

        # ── Section-level matching ──
        skills_score     = self._match_skills(resume_emb, jd_emb)
        experience_score = self._match_experience(resume_emb, jd_emb)
        projects_score   = self._match_projects(resume_emb, jd_emb)
        education_score  = self._match_education(resume_emb, jd_emb)
        certs_score      = self._match_certifications(resume_emb, jd_emb, populated)
        full_doc_score   = cosine_similarity(resume_emb["full"], jd_emb["full"])

        section_scores = {
            "skills":             skills_score,
            "experience_summary": experience_score,
            "projects":           projects_score,
            "education":          education_score,
            "certifications":     certs_score,
        }

        # FIX: pass populated map so empty sections don't crush the weighted score
        weighted = weighted_similarity(section_scores, weights, populated=populated)

        # FIX: raised full_doc blend from 20% → 30%
        # Full-document embedding is more robust when section text is sparse.
        overall = round(weighted * 0.70 + full_doc_score * 0.30, 4)

        # ── Gap analysis ──
        # FIX: pass populated so missing sections are labelled "missing" not "critical"
        gaps = identify_gaps(
            section_scores,
            threshold=self.thresholds.get("partial_match", 0.28),
            populated=populated,
        )

        # ── Build result ──
        result = MatchResult(
            resume_id        = resume.get("id",    "unknown"),
            jd_id            = jd.get("id",        "unknown"),
            resume_name      = resume.get("name",  ""),
            jd_title         = jd_title,
            skills_score     = skills_score,
            experience_score = experience_score,
            projects_score   = projects_score,
            education_score  = education_score,
            certs_score      = certs_score,
            full_doc_score   = full_doc_score,
            overall_score    = overall,
            match_label      = similarity_label(overall, self.thresholds),
            gaps             = gaps,
            thresholds_used  = self.thresholds,
        )

        return result

    # ───────────────────────────────────────────────────────────
    # SECTION MATCHERS
    # ───────────────────────────────────────────────────────────

    def _match_skills(self, resume_emb: dict, jd_emb: dict) -> float:
        skills_vec = resume_emb["skills"]
        req_score  = cosine_similarity(skills_vec, jd_emb["required_skills"])

        # FIX: graceful fallback when preferred_skills vector is zero
        pref_vec   = jd_emb.get("preferred_skills", _zero_vec())
        pref_score = cosine_similarity(skills_vec, pref_vec) if np.any(pref_vec) else req_score * 0.6

        resp_score = cosine_similarity(skills_vec, jd_emb["responsibilities"])

        score = req_score * 0.55 + pref_score * 0.25 + resp_score * 0.20
        return round(max(0.0, score), 4)

    def _match_experience(self, resume_emb: dict, jd_emb: dict) -> float:
        exp_vec    = resume_emb["experience_summary"]
        resp_score = cosine_similarity(exp_vec, jd_emb["responsibilities"])
        qual_score = cosine_similarity(exp_vec, jd_emb["qualifications"])
        req_score  = cosine_similarity(exp_vec, jd_emb["required_skills"])

        # FIX: also match experience vs required skills (catches role-specific keywords)
        score = resp_score * 0.55 + qual_score * 0.25 + req_score * 0.20
        return round(max(0.0, score), 4)

    def _match_projects(self, resume_emb: dict, jd_emb: dict) -> float:
        proj_vec   = resume_emb["projects"]
        resp_score = cosine_similarity(proj_vec, jd_emb["responsibilities"])
        req_score  = cosine_similarity(proj_vec, jd_emb["required_skills"])

        score = resp_score * 0.70 + req_score * 0.30
        return round(max(0.0, score), 4)

    def _match_education(self, resume_emb: dict, jd_emb: dict) -> float:
        edu_vec = resume_emb["education"]
        score   = cosine_similarity(edu_vec, jd_emb["qualifications"])
        # FIX: also compare education vs required skills (degree-field overlap)
        skill_score = cosine_similarity(edu_vec, jd_emb["required_skills"])
        return round(max(0.0, score * 0.70 + skill_score * 0.30), 4)

    def _match_certifications(self, resume_emb: dict, jd_emb: dict,
                               populated: dict | None = None) -> float:
        cert_vec = resume_emb["certifications"]

        # FIX: when certs are genuinely missing, return 0.0 rather than using
        # the fallback full-text vector (avoids inflating certs score artificially)
        if populated is not None and not populated.get("certifications", True):
            return 0.0

        if not np.any(cert_vec):
            return 0.0

        pref_vec   = jd_emb.get("preferred_skills", _zero_vec())
        pref_score = cosine_similarity(cert_vec, pref_vec) if np.any(pref_vec) else 0.0
        qual_score = cosine_similarity(cert_vec, jd_emb["qualifications"])
        req_score  = cosine_similarity(cert_vec, jd_emb["required_skills"])

        score = pref_score * 0.45 + qual_score * 0.35 + req_score * 0.20
        return round(max(0.0, score), 4)

    # ───────────────────────────────────────────────────────────
    # BATCH MATCHING
    # ───────────────────────────────────────────────────────────

    def match_batch(
        self,
        resumes: list,
        jds:     list,
    ) -> list:
        """Match every resume against every JD (all-pairs)."""
        results = []
        total   = len(resumes) * len(jds)
        count   = 0
        for resume in resumes:
            for jd in jds:
                result = self.match(resume, jd)
                results.append(result)
                count += 1
                print(f"  [{count}/{total}] {resume.get('name','?'):<20} "
                      f"↔  {jd.get('title','?'):<35}  "
                      f"{result.overall_score:.3f}  {result.match_label}")
        return results

    def best_jd_for_resume(
        self,
        resume: dict,
        jds:    list,
    ) -> tuple:
        """Find the best-matching JD for a given resume."""
        all_results = [self.match(resume, jd) for jd in jds]
        all_results.sort(key=lambda r: r.overall_score, reverse=True)
        return all_results[0], all_results

    def best_resume_for_jd(
        self,
        jd:      dict,
        resumes: list,
    ) -> tuple:
        """Rank all resumes against a single JD."""
        all_results = [self.match(resume, jd) for resume in resumes]
        all_results.sort(key=lambda r: r.overall_score, reverse=True)
        return all_results[0], all_results