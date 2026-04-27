"""
Tests for PIIMasker (Day 15)
Path: ai_job_portal_system/tests/test_pii_masker.py
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fairness_engine.pii_masker import PIIMasker
from utils.normalization_constants import MASK_PLACEHOLDERS


@pytest.fixture
def normalized_resume():
    return {
        "candidate_id": "test_resume",
        "personal_info": {
            "name": "AMALA P ANTY",
            "email": "amalaanty@gmail.com",
            "phone": "+91 9037394914",
            "location": "Bangalore, Karnataka, India",
            "linkedin": "linkedin.com/in/amala",
        },
        "professional_summary": (
            "Mrs. Amala is a 28 years old data scientist. Contact: "
            "amala@test.com or +91-9999999999."
        ),
        "skills": {"all_skills_flat": ["python", "sql"]},
        "experience": {"total_years": 5.2, "roles": []},
        "education": [
            {"degree": "B.Tech", "institution": "IIT Bombay", "score": "85%"}
        ],
        "projects": [],
        "certifications": [],
        "achievements": ["Top performer; he was awarded ..."],
    }


@pytest.fixture
def masker(tmp_path):
    return PIIMasker(output_dir=str(tmp_path))


def test_personal_info_masked(masker, normalized_resume):
    out = masker.mask(normalized_resume, save=False)
    pi = out["masked_resume"]["personal_info"]
    assert pi["name"] == MASK_PLACEHOLDERS["name"]
    assert pi["email"] == MASK_PLACEHOLDERS["email"]
    assert pi["phone"] == MASK_PLACEHOLDERS["phone"]
    assert pi["location"] == MASK_PLACEHOLDERS["location"]


def test_summary_email_phone_masked(masker, normalized_resume):
    out = masker.mask(normalized_resume, save=False)
    summary = out["masked_resume"]["professional_summary"]
    assert "amala@test.com" not in summary
    assert "9999999999" not in summary
    assert MASK_PLACEHOLDERS["email"] in summary or \
           MASK_PLACEHOLDERS["phone"] in summary


def test_gender_term_masked(masker, normalized_resume):
    out = masker.mask(normalized_resume, save=False)
    summary = out["masked_resume"]["professional_summary"]
    achievements = " ".join(out["masked_resume"]["achievements"])
    # 'Mrs.' should be masked
    assert "Mrs" not in summary or MASK_PLACEHOLDERS["gender"] in summary
    # 'he' should be masked
    assert "he was" not in achievements


def test_age_pattern_masked(masker, normalized_resume):
    out = masker.mask(normalized_resume, save=False)
    summary = out["masked_resume"]["professional_summary"]
    assert "28 years old" not in summary
    assert MASK_PLACEHOLDERS["age"] in summary


def test_audit_total_count_positive(masker, normalized_resume):
    out = masker.mask(normalized_resume, save=False)
    assert out["audit"]["total_masks_applied"] > 0


def test_college_tier_masking_optional(normalized_resume, tmp_path):
    profile = {"name": False, "email": False, "phone": False,
               "location": False, "linkedin": False, "gender": False,
               "age": False, "marital_status": False,
               "caste_religion": False, "college_tier": True}
    masker = PIIMasker(mask_profile=profile, output_dir=str(tmp_path))
    out = masker.mask(normalized_resume, save=False)
    assert out["masked_resume"]["education"][0]["institution"] == \
           MASK_PLACEHOLDERS["college_tier"]
