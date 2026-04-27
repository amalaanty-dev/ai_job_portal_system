"""
Tests for KeywordDependencyReducer (Day 15)
Path: ai_job_portal_system/tests/test_keyword_dependency.py

Run:
    pytest tests/test_keyword_dependency.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fairness_engine.keyword_dependency_reducer import KeywordDependencyReducer


# ----------------------------------------------------------
# FIXTURES
# ----------------------------------------------------------
@pytest.fixture
def normalized_resume_with_evidence():
    """Resume where ai/nlp/deep learning are demonstrated in projects."""
    return {
        "candidate_id": "demonstrated",
        "professional_summary": "Data scientist with NLP experience.",
        "skills": {
            "all_skills_flat": ["python", "ai", "nlp", "deep learning",
                                "computer vision", "tensorflow"]
        },
        "experience": {
            "total_years": 5.0,
            "roles": [{
                "job_title": "Data Engineer",
                "duties": [
                    "Built nlp models for chatbot training",
                    "Trained ai pipelines using tensorflow"
                ]
            }]
        },
        "projects": [
            {"title": "Brain Tumor CNN | Deep Learning",
             "description": ["Built CNN with tensorflow",
                             "Image classification using deep learning"]}
        ],
        "education": [],
        "achievements": [],
    }


@pytest.fixture
def normalized_resume_keyword_stuffed():
    """Resume where skills are listed but never demonstrated."""
    return {
        "candidate_id": "stuffed",
        "professional_summary": "Looking for a job.",
        "skills": {
            "all_skills_flat": ["python", "ai", "nlp", "deep learning",
                                "kubernetes", "computer vision",
                                "healthcare analytics"]
        },
        "experience": {
            "total_years": 1.0,
            "roles": [{
                "job_title": "Intern",
                "duties": ["Did some work", "Helped with tasks"]
            }]
        },
        "projects": [],
        "education": [],
        "achievements": [],
    }


@pytest.fixture
def parsed_jd():
    return {
        "role": ["ai specialist"],
        "skills_required": ["ai", "nlp", "deep learning",
                            "computer vision", "healthcare analytics"],
    }


@pytest.fixture
def reducer(tmp_path):
    return KeywordDependencyReducer(output_dir=str(tmp_path))


# ----------------------------------------------------------
# TESTS
# ----------------------------------------------------------
def test_canonicalize_synonyms(reducer):
    """tf -> tensorflow, dl -> deep learning, cv -> computer vision."""
    canonical = reducer._canonicalize(["tf", "tensorflow", "dl", "cv", "py"])
    assert "tensorflow" in canonical
    assert "deep learning" in canonical
    assert "computer vision" in canonical
    assert "python" in canonical


def test_evidence_found_for_demonstrated_skills(
    reducer, normalized_resume_with_evidence, parsed_jd
):
    out = reducer.analyze(normalized_resume_with_evidence, parsed_jd, save=False)
    evidence = out["contextual_evidence"]
    assert len(evidence["nlp"]) > 0, "NLP should be found in duties"
    assert len(evidence["deep learning"]) > 0, "Deep learning should match CNN"


def test_low_dependency_for_demonstrated_resume(
    reducer, normalized_resume_with_evidence, parsed_jd
):
    out = reducer.analyze(normalized_resume_with_evidence, parsed_jd, save=False)
    # Evidence found for several skills -> low dependency ratio
    assert out["keyword_dependency_ratio"] <= 0.5


def test_high_dependency_for_stuffed_resume(
    reducer, normalized_resume_keyword_stuffed, parsed_jd
):
    out = reducer.analyze(normalized_resume_keyword_stuffed, parsed_jd, save=False)
    # All skills claimed but none demonstrated -> high ratio
    assert out["keyword_dependency_ratio"] > 0.5
    assert "keyword dependency" in out["interpretation"].lower()


def test_context_score_in_range(
    reducer, normalized_resume_with_evidence, parsed_jd
):
    out = reducer.analyze(normalized_resume_with_evidence, parsed_jd, save=False)
    assert 0 <= out["context_adjusted_skill_score"] <= 100


def test_context_score_higher_with_evidence(
    reducer, normalized_resume_with_evidence,
    normalized_resume_keyword_stuffed, parsed_jd
):
    """Demonstrated skills should yield higher context score."""
    out_demo = reducer.analyze(normalized_resume_with_evidence, parsed_jd, save=False)
    out_stuff = reducer.analyze(normalized_resume_keyword_stuffed, parsed_jd, save=False)
    assert out_demo["context_adjusted_skill_score"] > \
           out_stuff["context_adjusted_skill_score"]


def test_buzzword_penalty_applied(reducer, parsed_jd):
    """Resume with rockstar/ninja buzzwords should have positive count."""
    resume = {
        "candidate_id": "buzz",
        "professional_summary": "I am a rockstar developer and ninja.",
        "skills": {"all_skills_flat": ["python"]},
        "experience": {"total_years": 1, "roles": []},
        "projects": [],
        "education": [],
        "achievements": ["Hardworking team player and go-getter"],
    }
    out = reducer.analyze(resume, parsed_jd, save=False)
    assert out["buzzword_count"] >= 2


def test_handles_empty_jd_skills(reducer, normalized_resume_with_evidence):
    """JD with no skills_required should not crash."""
    jd = {"role": ["unknown"], "skills_required": []}
    out = reducer.analyze(normalized_resume_with_evidence, jd, save=False)
    assert out["keyword_dependency_ratio"] == 0.0
