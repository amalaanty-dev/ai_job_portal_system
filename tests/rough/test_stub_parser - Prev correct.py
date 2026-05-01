"""Tests for the upgraded built-in heuristic parser & scorer."""
from __future__ import annotations
from api.services import ats_adapter


# --- Skill extraction (fuzzy substring + multi-word phrases) ---

def test_skills_extracted_from_text():
    text = """
    PROFESSIONAL SUMMARY
    Healthcare reporting analyst with experience in dashboard development,
    KPI monitoring, and ICD-10 coding. Tools: Python, SQL, Tableau, Power BI.
    Built ETL pipelines on AWS using Airflow and Snowflake.
    """
    skills = ats_adapter._extract_skills(text)
    expected = {"Python", "SQL", "Tableau", "Power Bi", "AWS", "Snowflake", "Etl",
                 "Healthcare Reporting", "Dashboard Development", "Kpi Monitoring",
                 "ICD-10"}
    found = {s for s in skills}
    # Allow case differences in compound names
    assert "Python" in found
    assert "SQL" in found
    assert any("Tableau" in s for s in found)
    assert any("Aws" in s.lower() or "AWS" in s for s in found)
    assert any("Healthcare" in s for s in found)
    assert any("Dashboard" in s for s in found)


def test_skill_matching_handles_variants():
    cand = ["Python 3.10", "MySQL", "AWS Lambda"]
    score = ats_adapter._skill_match_score(cand, ["Python", "SQL", "AWS"], [])
    assert score >= 99.0


def test_skill_score_zero_when_no_overlap():
    score = ats_adapter._skill_match_score(["Java"], ["Python"], [])
    assert score == 0.0


# --- Experience extraction ---

def test_total_experience_years_explicit_phrase():
    text = "Backend engineer with 5 years of experience building scalable APIs."
    assert ats_adapter._extract_total_experience_years(text) == 5.0


def test_total_experience_years_with_plus():
    text = "8+ years experience in healthcare analytics."
    assert ats_adapter._extract_total_experience_years(text) == 8.0


def test_total_experience_years_picks_max():
    text = "1 year at Acme. 7 years at Globex. 3 yrs at Initech."
    assert ats_adapter._extract_total_experience_years(text) == 7.0


def test_total_experience_none_when_absent():
    assert ats_adapter._extract_total_experience_years("Just a regular bio.") is None


# --- Education extraction ---

def test_education_extracted():
    text = "Education: B.Tech in Computer Science, M.Sc in Data Science."
    edu = ats_adapter._extract_education(text)
    assert any("BTECH" in e or "B.TECH" in e or "B.E." in e for e in edu) or any("MSC" in e or "M.SC" in e for e in edu)
    assert "DATA SCIENCE" in edu or "COMPUTER SCIENCE" in edu


# --- Name extraction ---

def test_name_extracted_from_top():
    text = "Sofia Martinez\nHealthcare Reporting Analyst\nsofia@example.com"
    assert ats_adapter._extract_name(text) == "Sofia Martinez"


def test_name_skips_email_lines():
    text = "alice@example.com\nAlice Wonder\nBackend Engineer"
    name = ats_adapter._extract_name(text)
    assert name == "Alice Wonder"


# --- Score breakdown is non-zero with a real-looking profile ---

def test_score_non_zero_for_relevant_match():
    parsed = {
        "skills": ["Python", "SQL", "Tableau", "Healthcare Reporting"],
        "total_experience_years": 4.0,
        "education": ["BTECH", "DATA SCIENCE"],
        "raw_text_preview": "Healthcare reporting analyst with Python SQL Tableau dashboards",
    }
    jd = {
        "job_title": "Healthcare Data Analyst",
        "required_skills": ["Python", "SQL", "Healthcare Reporting"],
        "preferred_skills": ["Tableau"],
        "experience_required": 3,
        "education_required": ["B.Tech"],
        "description": "Analyze healthcare data, build reports.",
    }
    res = ats_adapter._stub_score(parsed, jd)
    assert res["skills"] >= 90.0   # all 3 required matched
    assert res["experience"] >= 70.0
    assert res["education"] >= 60.0
    assert res["semantic"] > 0
    assert res["final_score"] > 50.0


def test_score_with_empty_profile_still_returns_numbers():
    res = ats_adapter._stub_score(
        {"skills": [], "total_experience_years": None, "education": [], "raw_text_preview": ""},
        {"job_title": "Dev", "required_skills": ["Python"], "experience_required": 0, "education_required": []},
    )
    assert res["skills"] == 0.0
    assert res["semantic"] == 0.0
    assert res["final_score"] >= 0.0
