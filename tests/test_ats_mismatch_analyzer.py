"""
tests/test_ats_mismatch_analyzer.py
====================================
Pytest: validates the mismatch analyzer logic
(keyword / role / experience / soft-skill detectors).

Run:
    pytest tests/test_ats_mismatch_analyzer.py -v

Day: 17
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.backlog_generator import (
    analyze_mismatches,
    generate_backlog,
    _detect_keyword_mismatch,
    _detect_role_misclassification,
    _detect_experience_misinterpretation,
    _detect_soft_skill_miss,
)
from utils.metrics_calculator import compute_metrics, ConfusionMatrix


# ----------------------------- Unit tests -------------------------------------
def test_keyword_mismatch_js_javascript():
    record = {
        "matched_skills": ["JavaScript"],
        "missing_skills": ["JS"],
    }
    assert _detect_keyword_mismatch(record) is True


def test_keyword_mismatch_no_false_positive():
    record = {
        "matched_skills": ["Python", "Django"],
        "missing_skills": ["Flask"],
    }
    assert _detect_keyword_mismatch(record) is False


def test_role_misclassification_partial_overlap():
    record = {
        "identifiers": {"job_role": "Analyst"},
        "hr_expected_role": "Business Analyst",
    }
    assert _detect_role_misclassification(record) is True


def test_role_misclassification_exact_match():
    record = {
        "identifiers": {"job_role": "Data Scientist"},
        "hr_expected_role": "Data Scientist",
    }
    assert _detect_role_misclassification(record) is False


def test_experience_misinterpretation_intern_as_fulltime():
    record = {
        "experience": {"candidate_years": 1, "required_years": 3},
        "category": "fresher",
        "ai_decision": "Shortlisted",
        "hr_decision": "Rejected",
    }
    assert _detect_experience_misinterpretation(record) is True


def test_soft_skill_miss_low_score_non_tech():
    record = {"category": "non_tech", "final_score": 45}
    assert _detect_soft_skill_miss(record) is True


def test_soft_skill_miss_skipped_for_tech():
    record = {"category": "tech", "final_score": 45}
    assert _detect_soft_skill_miss(record) is False


# ----------------------------- Integration tests ------------------------------
def test_analyze_mismatches_counts():
    records = [
        {
            "ai_decision": "Shortlisted", "hr_decision": "Rejected",
            "category": "non_tech", "final_score": 55,
            "identifiers": {"resume_id": "R1", "jd_id": "JD1", "job_role": "Marketing"},
            "matched_skills": [], "missing_skills": [],
        },
        {
            "ai_decision": "Rejected", "hr_decision": "Shortlisted",
            "category": "tech", "final_score": 65,
            "identifiers": {"resume_id": "R2", "jd_id": "JD2", "job_role": "Backend"},
            "matched_skills": ["JavaScript"], "missing_skills": ["JS"],
        },
        {
            "ai_decision": "Shortlisted", "hr_decision": "Shortlisted",
            "category": "tech", "final_score": 90,
            "identifiers": {"resume_id": "R3", "jd_id": "JD3", "job_role": "Backend"},
            "matched_skills": [], "missing_skills": [],
        },
    ]
    analysis = analyze_mismatches(records)
    # R3 is a match, so it shouldn't count.
    # R1: soft_skill_miss
    # R2: keyword_mismatch
    assert analysis["counts"].get("soft_skill_miss", 0) >= 1
    assert analysis["counts"].get("keyword_mismatch", 0) >= 1


def test_generate_backlog_structure():
    records = [
        {
            "ai_decision": "Shortlisted", "hr_decision": "Rejected",
            "category": "non_tech", "final_score": 50,
            "identifiers": {"resume_id": "R1", "jd_id": "JD1", "job_role": "Marketing"},
            "matched_skills": [], "missing_skills": [],
        },
    ]
    cat_metrics = {
        "non_tech": compute_metrics(ConfusionMatrix(tp=2, fp=2, fn=2, tn=4)),  # ~60% acc
        "tech": compute_metrics(ConfusionMatrix(tp=8, fp=1, fn=1, tn=2)),
    }
    backlog = generate_backlog(records, cat_metrics)
    assert "high" in backlog and "medium" in backlog and "low" in backlog
    assert len(backlog["low"]) >= 1  # always has standard low items
    # non_tech accuracy is below 0.85, so high should have non-tech improvement
    high_titles = [b["title"] for b in backlog["high"]]
    assert any("non-tech" in t.lower() for t in high_titles)
