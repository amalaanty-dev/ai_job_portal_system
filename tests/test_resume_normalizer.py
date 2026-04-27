"""
Tests for ResumeNormalizer (Day 15)
Path: ai_job_portal_system/tests/test_resume_normalizer.py

Run:
    pytest tests/test_resume_normalizer.py -v
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fairness_engine.resume_normalizer import ResumeNormalizer


# ----------------------------------------------------------
# FIXTURES (mirror the actual sample files)
# ----------------------------------------------------------
@pytest.fixture
def parsed_resume_data():
    return {
        "resume_name": "Amala_Resume_DS_DA_2026_.pdf",
        "name": "AMALA P ANTY",
        "roles": [
            {
                "job_title": "Data Engineer II",
                "company": "Gupshup Technologies India Pvt. Ltd.",
                "start_date": "2021-07-01",
                "end_date": "2024-12-01",
                "duration_months": 42,
            }
        ],
        "experience": 5.2,
        "education": [
            {
                "degree": "MBA",
                "full_line": "MBA – Finance & Marketing 2016 – 2018",
                "years": ["2016", "2018"],
            }
        ],
        "clean_text": (
            "AMALA P ANTY\nData Analyst | Data Scientist\n"
            "Bangalore, Karnataka, India • +91 9037394914 • amalaanty@gmail.com\n"
            "PROFESSIONAL SUMMARY\nResults-driven Data Scientist...\n"
            "CORE TECHNICAL SKILLS\n"
        ),
    }


@pytest.fixture
def sections_data():
    return {
        "skills": [
            "Programming & DB Python, SQL, Regex",
            "ML & AI Supervised Learning, XGBoost",
            "Frameworks & Libs Scikit-learn, TensorFlow",
        ],
        "experience": [
            {
                "role_header": "Data Engineer II | Gupshup India",
                "duties": ["Built NLP datasets", "Trained chatbots"],
            }
        ],
        "education": [
            "MBA – Finance & Marketing 2016 – 2018",
            "Rajagiri College of Social Sciences | 70%",
        ],
        "projects": [
            "E-Commerce Customer Churn Prediction | Supervised Learning",
            "Built an XGBoost classifier with 92% accuracy.",
        ],
        "certifications": [],
        "achievements": ["Top performer 2019"],
        "other": ["AMALA P ANTY"],
    }


@pytest.fixture
def normalizer(tmp_path):
    return ResumeNormalizer(output_dir=str(tmp_path))


# ----------------------------------------------------------
# TESTS
# ----------------------------------------------------------
def test_normalize_returns_standard_keys(
    normalizer, parsed_resume_data, sections_data, tmp_path
):
    # write inputs
    pr_path = tmp_path / "p.json"
    sec_path = tmp_path / "s.json"
    pr_path.write_text(json.dumps(parsed_resume_data))
    sec_path.write_text(json.dumps(sections_data))

    out = normalizer.normalize(str(pr_path), str(sec_path), save=False)

    expected_keys = {
        "candidate_id", "personal_info", "professional_summary",
        "skills", "experience", "education", "projects",
        "certifications", "achievements", "metadata",
    }
    assert expected_keys.issubset(set(out.keys()))


def test_personal_info_extracted(normalizer, parsed_resume_data,
                                 sections_data, tmp_path):
    pr_path = tmp_path / "p.json"
    sec_path = tmp_path / "s.json"
    pr_path.write_text(json.dumps(parsed_resume_data))
    sec_path.write_text(json.dumps(sections_data))

    out = normalizer.normalize(str(pr_path), str(sec_path), save=False)

    assert out["personal_info"]["name"] == "AMALA P ANTY"
    assert out["personal_info"]["email"] == "amalaanty@gmail.com"
    assert out["personal_info"]["phone"] is not None


def test_skills_categorized(normalizer, parsed_resume_data,
                            sections_data, tmp_path):
    pr_path = tmp_path / "p.json"
    sec_path = tmp_path / "s.json"
    pr_path.write_text(json.dumps(parsed_resume_data))
    sec_path.write_text(json.dumps(sections_data))

    out = normalizer.normalize(str(pr_path), str(sec_path), save=False)

    assert len(out["skills"]["all_skills_flat"]) > 0
    # programming skills bucket should have python or sql
    prog = " ".join(out["skills"]["programming"]).lower()
    assert "python" in prog or "sql" in prog


def test_experience_total_years(normalizer, parsed_resume_data,
                                sections_data, tmp_path):
    pr_path = tmp_path / "p.json"
    sec_path = tmp_path / "s.json"
    pr_path.write_text(json.dumps(parsed_resume_data))
    sec_path.write_text(json.dumps(sections_data))

    out = normalizer.normalize(str(pr_path), str(sec_path), save=False)
    assert out["experience"]["total_years"] == 5.2
    assert len(out["experience"]["roles"]) == 1


def test_education_parsed(normalizer, parsed_resume_data,
                          sections_data, tmp_path):
    pr_path = tmp_path / "p.json"
    sec_path = tmp_path / "s.json"
    pr_path.write_text(json.dumps(parsed_resume_data))
    sec_path.write_text(json.dumps(sections_data))

    out = normalizer.normalize(str(pr_path), str(sec_path), save=False)
    assert len(out["education"]) >= 1
    assert out["education"][0]["degree"] == "MBA"


def test_handles_missing_sections_file(normalizer, parsed_resume_data, tmp_path):
    pr_path = tmp_path / "p.json"
    pr_path.write_text(json.dumps(parsed_resume_data))
    out = normalizer.normalize(str(pr_path), sections_path=None, save=False)
    assert out["candidate_id"] == "p"
    assert out["skills"]["all_skills_flat"] == []
