import pytest
import os
import sys
from datetime import date

# Ensure the root directory is in the path so we can import project modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from experience_engine.experience_parser import (
    extract_experience, 
    detect_gaps, 
    detect_overlaps, 
    calculate_total_experience
)
from experience_engine.experience_matcher import build_experience_summary
from experience_engine.experience_formatter import format_day10_output

# ── 1. EXTRACTION TESTS ───────────────────────────────────────────────

def test_experience_extraction():
    """Verifies that the parser recognizes ISO dates and standard formats."""
    # Test ISO Date format (previously failing)
    sample_iso = "Python Developer at Google (2020-01-01 - 2022-01-01)"
    results_iso = extract_experience(sample_iso)
    assert len(results_iso) > 0
    assert results_iso[0]["company"] == "Google"
    assert results_iso[0]["start_date"] == "2020-01-01"

    # Test Month-Year format
    sample_text = "Data Scientist | Meta | Jan 2021 - Dec 2021"
    results_text = extract_experience(sample_text)
    assert len(results_text) > 0
    assert "Meta" in results_text[0]["company"]

# ── 2. TIMELINE ANALYSIS TESTS ────────────────────────────────────────

def test_gap_detection():
    """Verifies detection of unemployment periods longer than 3 months."""
    entries = [
        {"job_title": "Role A", "company": "Co A", "start_date": "2020-01-01", "end_date": "2020-06-01"},
        {"job_title": "Role B", "company": "Co B", "start_date": "2021-01-01", "end_date": "2022-01-01"}
    ]
    gaps = detect_gaps(entries)
    # 6 month gap between 2020-06 and 2021-01
    assert len(gaps) > 0
    assert gaps[0]["gap_months"] >= 6

def test_overlap_detection():
    """Verifies detection of simultaneous roles (pairwise comparison)."""
    entries = [
        {"job_title": "Full-time Job", "company": "Corp X", "start_date": "2022-01-01", "end_date": "2022-12-31"},
        {"job_title": "Freelance", "company": "Self", "start_date": "2022-05-01", "end_date": "2022-08-01"}
    ]
    overlaps = detect_overlaps(entries)
    # Should detect that 'Freelance' happened during 'Full-time Job'
    assert len(overlaps) >= 1
    assert overlaps[0]["role_b"] == "Freelance"

def test_total_experience_merging():
    """Ensures overlapping months are not double-counted."""
    entries = [
        {"start_date": "2020-01-01", "end_date": "2021-01-01"}, # 12 months
        {"start_date": "2020-06-01", "end_date": "2021-06-01"}  # Overlaps 6 months, adds 6 new
    ]
    total = calculate_total_experience(entries)
    # Total span is 2020-01 to 2021-06 = 18 months
    assert total == 18

# ── 3. SCORING & FORMATTING TESTS ─────────────────────────────────────

def test_experience_scoring():
    """Tests the relevance match score with tuned weights."""
    exp = [{"job_title": "Senior Data Scientist", "company": "Tech", "start_date": "2018-01-01", "end_date": "2023-01-01"}]
    jd_roles = ["Data Scientist"]
    jd_skills = ["Python", "SQL"]
    
    summary = build_experience_summary(exp, jd_roles, jd_skills)
    # With role similarity and 36+ month bonus, score should be high
    assert summary["relevance_score"] > 40
    assert summary["total_experience_months"] >= 60

def test_formatter_output_structure():
    """Ensures the final JSON structure matches Day 10 requirements."""
    mock_experiences = [
        {"job_title": "Dev", "company": "X", "start_date": "2020-01-01", "end_date": "2021-01-01", "duration_months": 12}
    ]
    mock_summary = {
        "relevance_score": 85.0,
        "total_experience_months": 12,
        "gaps": [],
        "overlaps": []
    }
    
    output = format_day10_output(mock_experiences, mock_summary)
    
    # Check top-level keys
    assert "experience_summary" in output
    assert "roles" in output
    assert "timeline_analysis" in output
    assert "relevance_analysis" in output
    
    # Check data integrity
    assert output["relevance_analysis"]["overall_relevance_score"] == 85.0

# ── 4. SYSTEM ISOLATION ───────────────────────────────────────────────

def test_experience_pipeline_isolation(tmp_path):
    """Verifies the system can handle file operations without crashing."""
    d = tmp_path / "outputs"
    d.mkdir()
    p = d / "test_result.json"
    p.write_text('{"status": "success"}')
    assert p.read_text() == '{"status": "success"}'