import pytest
import os
import json
import sys

# 1. Path Setup
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from education_engine.education_parser import extract_education
from education_engine.education_matcher import calculate_education_relevance
from education_engine.education_formatter import format_academic_profile

# --- UNIT TESTS ---

def test_parser_extraction_logic():
    """Verifies parser handles uppercase output correctly."""
    mock_resume = {"education": ["B.Tech in Computer Science, IIT Bombay, 2020-2024"]}
    result = extract_education(mock_resume)
    
    assert "education" in result
    first_entry = result["education"][0]
    assert first_entry["degree"] == "B.TECH" 
    assert "IIT Bombay" in first_entry["institution"]

def test_matcher_relevance_score():
    """Tests the matching score logic with the expected Dictionary structure."""
    # FIX: Your matcher expects a dict with "education_details" and "certifications"
    mock_input_data = {
        "education_details": [{"degree": "B.TECH", "field": "Computer Science"}],
        "certifications": []
    }
    jd_text = "Looking for a B.Tech graduate in Computer Science"

    # Now passing the dictionary instead of a list
    score = calculate_education_relevance(mock_input_data, jd_text)
    
    assert isinstance(score, (int, float))
    assert score > 0

def test_formatter_profile_output():
    """Ensures formatter returns your specific nested dictionary structure."""
    sample_parsed = {
        "education": [{"degree": "MBA", "institution": "IIM", "graduation_year": "2022"}],
        "certifications": []
    }
    report = format_academic_profile(sample_parsed, jd_text="Business Manager")

    # Navigating your specific nested keys
    academic_profile = report.get("education_data", {}).get("academic_profile", {})
    
    assert "education_strength" in academic_profile
    assert academic_profile["highest_degree"] == "MBA"
    assert "education_relevance_score" in report

# --- SAFE INTEGRATION TEST ---

def test_pipeline_isolation(tmp_path):
    """Saves to sandbox to protect your real data/education_outputs/."""
    sandbox = tmp_path / "day11_final_check"
    sandbox.mkdir()
    temp_file_path = os.path.join(str(sandbox), "test_candidate.json")
    
    mock_data = {"education": ["PHD in AI, Stanford, 2025"]}
    parsed = extract_education(mock_data)
    final_output = format_academic_profile(parsed)
    
    with open(temp_file_path, "w") as f:
        json.dump(final_output, f, indent=4)
    
    assert os.path.exists(temp_file_path)
    assert "day11_final_check" in temp_file_path