import json
import pytest
import os
import sys
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from experience_engine.experience_parser import (
    extract_experience,
    detect_gaps,
    detect_overlaps,
    calculate_total_experience,
    parse_role_header,
    extract_from_role_headers,
)
from experience_engine.experience_matcher import build_experience_summary
from experience_engine.experience_formatter import format_day10_output
from experience_engine.experience_cleaner import clean_experiences


# ── 1. EXTRACTION TESTS ───────────────────────────────────────────────

def test_extract_pipe_format():
    """Parser correctly handles Role | Company | Date format."""
    text = "Data Scientist | Meta | Jan 2021 - Dec 2021"
    results = extract_experience(text)
    assert len(results) > 0
    assert results[0]["job_title"] == "Data Scientist"
    assert "Meta" in results[0]["company"]
    assert results[0]["start_date"] == "2021-01-01"
    assert results[0]["end_date"]   == "2021-12-01"


def test_extract_at_format():
    """Parser correctly handles Role at Company (Date - Date) format."""
    text = "Python Developer at Google (Jan 2020 - Jan 2022)"
    results = extract_experience(text)
    assert len(results) > 0
    assert results[0]["job_title"]  == "Python Developer"
    assert results[0]["company"]    == "Google"
    assert results[0]["start_date"] == "2020-01-01"
    assert results[0]["end_date"]   == "2022-01-01"


def test_extract_iso_date_format():
    """Parser supports ISO date strings inside role entries."""
    text = "Backend Engineer | Amazon | 2020-03-01 - 2023-06-01"
    results = extract_experience(text)
    assert len(results) > 0
    assert results[0]["start_date"] == "2020-03-01"
    assert results[0]["end_date"]   == "2023-06-01"


def test_extract_present_keyword():
    """'Present' end date resolves to today's date."""
    text = "Data Analyst | Acme Corp | Jan 2023 - Present"
    results = extract_experience(text)
    assert len(results) > 0
    end = date.fromisoformat(results[0]["end_date"])
    assert end >= date.today().replace(day=1)


def test_extract_deduplication():
    """Same role appearing twice is only extracted once."""
    text = (
        "Data Scientist | Meta | Jan 2021 - Dec 2021\n"
        "Data Scientist | Meta | Jan 2021 - Dec 2021"
    )
    results = extract_experience(text)
    assert len(results) == 1


# ── 2. ROLE HEADER PARSER (sectioned resume) ──────────────────────────

def test_parse_role_header_standard():
    """Parses a standard sectioned-resume role_header string."""
    header = "Data Engineer II | Gupshup Technologies India Pvt. Ltd.|Jul 2021 – Dec 2024"
    result = parse_role_header(header)
    assert result is not None
    assert result["job_title"]  == "Data Engineer II"
    assert "Gupshup" in result["company"]
    assert result["start_date"] == "2021-07-01"
    assert result["end_date"]   == "2024-12-01"
    assert result["duration_months"] == 41   # Jul 2021 → Dec 2024 = 41 months


def test_parse_role_header_with_dash_in_title():
    """role_header titles containing dashes are parsed correctly."""
    header = "Deputy Manager – Banking Operations | Axis Bank| Oct 2020 – Nov 2021"
    result = parse_role_header(header)
    assert result is not None
    assert "Banking Operations" in result["job_title"]
    assert result["company"] == "Axis Bank"


def test_parse_role_header_invalid():
    """Returns None for a string that does not match the expected pattern."""
    assert parse_role_header("") is None
    assert parse_role_header("Not a role header at all") is None
    assert parse_role_header(None) is None


def test_extract_from_role_headers_list():
    """Extracts multiple entries from a sectioned experience list."""
    experience_list = [
        {
            "role_header": "Data Engineer II | Gupshup Technologies India Pvt. Ltd.|Jul 2021 – Dec 2024",
            "duties": ["Built NLP models", "Trained chatbots"]
        },
        {
            "role_header": "Deputy Manager – Banking Operations | Axis Bank| Oct 2020 – Nov 2021",
            "duties": ["Managed banking ops"]
        },
    ]
    results = extract_from_role_headers(experience_list)
    assert len(results) == 2
    assert results[0]["job_title"] == "Data Engineer II"
    assert results[1]["company"]   == "Axis Bank"


# ── 3. CLEANER TESTS ──────────────────────────────────────────────────

def test_cleaner_strips_title_prefix():
    """Sectioner bleed-in words are stripped from job_title."""
    dirty = [
        {
            "job_title":  "tools clinical data analyst",
            "company":    "Brigham and Women's Hospital",
            "start_date": "2022-03-01",
            "end_date":   "2024-03-01",
            "duration_months": 24,
        }
    ]
    cleaned = clean_experiences(dirty)
    assert len(cleaned) == 1
    assert cleaned[0]["job_title"] == "clinical data analyst"


def test_cleaner_strips_company_prefix():
    """Sectioner bleed-in words are stripped from company."""
    dirty = [
        {
            "job_title":  "Research Data Coordinator",
            "company":    "languages massachusetts general hospital",
            "start_date": "2021-07-01",
            "end_date":   "2022-02-01",
            "duration_months": 7,
        }
    ]
    cleaned = clean_experiences(dirty)
    assert len(cleaned) == 1
    assert cleaned[0]["company"] == "massachusetts general hospital"


def test_cleaner_drops_junk_entry():
    """An entry that reduces to an empty field after cleaning is dropped."""
    dirty = [
        {
            "job_title":  "tools",       # nothing left after stripping "tools"
            "company":    "Acme Corp",
            "start_date": "2020-01-01",
            "end_date":   "2021-01-01",
            "duration_months": 12,
        }
    ]
    cleaned = clean_experiences(dirty)
    assert len(cleaned) == 0


def test_cleaner_leaves_clean_entry_unchanged():
    """Clean entries are returned unchanged."""
    entry = {
        "job_title":  "Clinical Data Analyst",
        "company":    "Brigham and Women's Hospital",
        "start_date": "2022-03-01",
        "end_date":   "2024-03-01",
        "duration_months": 24,
    }
    cleaned = clean_experiences([entry])
    assert len(cleaned) == 1
    assert cleaned[0]["job_title"] == "Clinical Data Analyst"
    assert cleaned[0]["company"]   == "Brigham and Women's Hospital"


# ── 4. TIMELINE ANALYSIS TESTS ────────────────────────────────────────

def test_gap_detection():
    """Detects an employment gap of 7 months between two roles."""
    entries = [
        {"job_title": "Role A", "company": "Co A",
         "start_date": "2020-01-01", "end_date": "2020-06-01"},
        {"job_title": "Role B", "company": "Co B",
         "start_date": "2021-01-01", "end_date": "2022-01-01"},
    ]
    gaps = detect_gaps(entries)
    # Gap: Jun 2020 → Jan 2021 = (2021-2020)*12 + (1-6) = 7 months
    assert len(gaps) == 1
    assert gaps[0]["gap_months"] == 7
    assert gaps[0]["gap_start"]  == "2020-06-01"
    assert gaps[0]["gap_end"]    == "2021-01-01"


def test_no_gap_when_continuous():
    """No gaps reported for back-to-back roles."""
    entries = [
        {"job_title": "Role A", "company": "Co A",
         "start_date": "2020-01-01", "end_date": "2021-01-01"},
        {"job_title": "Role B", "company": "Co B",
         "start_date": "2021-01-01", "end_date": "2022-01-01"},
    ]
    gaps = detect_gaps(entries)
    assert len(gaps) == 0


def test_overlap_detection():
    """Detects simultaneous roles with correct company fields."""
    entries = [
        {"job_title": "Full-time Job", "company": "Corp X",
         "start_date": "2022-01-01", "end_date": "2022-12-31"},
        {"job_title": "Freelance", "company": "Self",
         "start_date": "2022-05-01", "end_date": "2022-08-01"},
    ]
    overlaps = detect_overlaps(entries)
    assert len(overlaps) >= 1
    assert overlaps[0]["role_a"]    == "Full-time Job"
    assert overlaps[0]["role_b"]    == "Freelance"
    assert overlaps[0]["company_a"] == "Corp X"
    assert overlaps[0]["company_b"] == "Self"
    # Overlap: May–Aug 2022 = 3 months
    assert overlaps[0]["overlap_months"] == 3


def test_no_overlap_for_sequential_roles():
    """No overlaps reported when roles are sequential."""
    entries = [
        {"job_title": "Role A", "company": "Co A",
         "start_date": "2020-01-01", "end_date": "2021-01-01"},
        {"job_title": "Role B", "company": "Co B",
         "start_date": "2021-02-01", "end_date": "2022-02-01"},
    ]
    overlaps = detect_overlaps(entries)
    assert len(overlaps) == 0


def test_total_experience_merging():
    """Overlapping months are not double-counted."""
    entries = [
        {"start_date": "2020-01-01", "end_date": "2021-01-01"},   # 12 months
        {"start_date": "2020-06-01", "end_date": "2021-06-01"},   # overlaps 7, adds 5
    ]
    total = calculate_total_experience(entries)
    # Merged span: 2020-01 → 2021-06 = (2021-2020)*12 + (6-1) = 17 months
    assert total == 17


def test_total_experience_no_overlap():
    """Non-overlapping roles are summed directly."""
    entries = [
        {"start_date": "2019-01-01", "end_date": "2020-01-01"},   # 12 months
        {"start_date": "2020-06-01", "end_date": "2021-06-01"},   # 12 months
    ]
    total = calculate_total_experience(entries)
    # Gap of 5 months between them; total = 12 + 12 = 24
    assert total == 24


def test_total_experience_single_entry():
    """Single role returns its own duration."""
    entries = [{"start_date": "2021-07-01", "end_date": "2024-12-01"}]
    total = calculate_total_experience(entries)
    # Jul 2021 → Dec 2024 = (2024-2021)*12 + (12-7) = 36 + 5 = 41
    assert total == 41


def test_total_experience_empty():
    """Empty list returns 0."""
    assert calculate_total_experience([]) == 0


# ── 5. SCORING & FORMATTING TESTS ─────────────────────────────────────

def test_experience_scoring_high_match():
    """High role similarity + 36+ months returns score above 40."""
    exp = [{
        "job_title":  "Senior Data Scientist",
        "company":    "Tech Corp",
        "start_date": "2018-01-01",
        "end_date":   "2023-01-01",
    }]
    summary = build_experience_summary(exp, ["Data Scientist"], ["Python", "SQL"])
    # Jan 2018 → Jan 2023 = (2023-2018)*12 + (1-1) = 60 months
    assert summary["total_experience_months"] == 60
    assert summary["relevance_score"] > 40
    assert summary["gaps"]     == []
    assert summary["overlaps"] == []


def test_experience_scoring_empty_experiences():
    """Empty experience list returns zero score."""
    summary = build_experience_summary([], ["Data Scientist"])
    assert summary["relevance_score"] == 0.0
    assert summary["total_experience_months"] == 0


def test_experience_scoring_no_skills():
    """Score is still computed when jd_skills is not provided."""
    exp = [{
        "job_title":  "Data Analyst",
        "company":    "Acme",
        "start_date": "2020-01-01",
        "end_date":   "2023-01-01",
    }]
    summary = build_experience_summary(exp, ["Data Analyst"])
    assert summary["relevance_score"] > 0


def test_formatter_output_structure():
    """Final JSON matches the Day-10 output schema exactly."""
    mock_experiences = [{
        "job_title":       "Clinical Data Analyst",
        "company":         "Brigham and Women's Hospital",
        "start_date":      "2022-03-01",
        "end_date":        "2024-03-01",
        "duration_months": 24,
    }]
    mock_summary = {
        "relevance_score":         85.0,
        "total_experience_months": 24,
        "gaps":                    [],
        "overlaps":                [],
    }

    output = format_day10_output(mock_experiences, mock_summary)

    # Top-level keys
    assert "experience_summary"  in output
    assert "roles"               in output
    assert "timeline_analysis"   in output
    assert "relevance_analysis"  in output

    # experience_summary
    assert output["experience_summary"]["total_experience_months"] == 24

    # roles
    assert len(output["roles"]) == 1
    assert output["roles"][0]["job_title"] == "Clinical Data Analyst"
    assert output["roles"][0]["company"]   == "Brigham and Women's Hospital"

    # timeline_analysis
    assert output["timeline_analysis"]["gaps"]     == []
    assert output["timeline_analysis"]["overlaps"] == []

    # relevance_analysis
    assert output["relevance_analysis"]["overall_relevance_score"] == 85.0


# ── 6. END-TO-END PIPELINE TEST ───────────────────────────────────────

def test_pipeline_end_to_end(tmp_path):
    """
    Full pipeline: structured experiences → summary → formatted output → JSON file.
    Verifies the complete flow without touching disk-based resume/JD folders.
    """
    experiences = [
        {
            "job_title":       "Clinical Data Analyst",
            "company":         "Brigham and Women's Hospital",
            "start_date":      "2022-03-01",
            "end_date":        "2024-03-01",
            "duration_months": 24,
        },
        {
            "job_title":       "Research Data Coordinator",
            "company":         "Massachusetts General Hospital",
            "start_date":      "2021-01-01",
            "end_date":        "2022-02-01",
            "duration_months": 13,
        },
    ]
    jd_roles  = ["Clinical Data Analyst"]
    jd_skills = ["SQL", "EHR", "Python"]

    summary      = build_experience_summary(experiences, jd_roles, jd_skills)
    final_output = format_day10_output(experiences, summary)

    # Write to tmp file
    output_file = tmp_path / "test_output.json"
    output_file.write_text(json.dumps(final_output, indent=4))

    # Read back and validate
    result = json.loads(output_file.read_text())

    assert result["experience_summary"]["total_experience_months"] > 0
    assert len(result["roles"]) == 2
    assert result["relevance_analysis"]["overall_relevance_score"] > 0
    assert "gaps"     in result["timeline_analysis"]
    assert "overlaps" in result["timeline_analysis"]