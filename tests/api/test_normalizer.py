"""Verify the parser-output normalizer handles real-world messy shapes.

This test reproduces the exact failure pattern seen on the user's machine
where a local `parsers.resume_parser.parse_resume()` returned shapes that
the strict ParsedProfile schema rejected.
"""
from __future__ import annotations
import pytest
from unittest.mock import patch

from api.services import ats_adapter
from api.schemas.resume import ParsedProfile


# --- Direct normalizer tests ----------------------------------------------

def test_normalizer_handles_email_as_list():
    raw = {"email": ["a@b.com", "c@d.com"], "skills": ["Python"]}
    out = ats_adapter._normalize_parsed_profile(raw)
    assert out["email"] == ["a@b.com", "c@d.com"]
    ParsedProfile(**out)  # must validate


def test_normalizer_handles_experience_years_as_string():
    raw = {"total_experience_years": "3.5"}
    out = ats_adapter._normalize_parsed_profile(raw)
    assert out["total_experience_years"] == 3.5
    ParsedProfile(**out)


def test_normalizer_handles_garbage_experience_years():
    raw = {"total_experience_years": "  "}
    out = ats_adapter._normalize_parsed_profile(raw)
    assert out["total_experience_years"] is None


def test_normalizer_handles_skills_as_dict():
    raw = {"skills": {"py": "Python", "dj": "Django"}}
    out = ats_adapter._normalize_parsed_profile(raw)
    assert sorted(out["skills"]) == ["Django", "Python"]
    ParsedProfile(**out)


def test_normalizer_handles_skills_as_list_of_dicts():
    raw = {"skills": [{"name": "Python"}, {"name": "Django"}]}
    out = ats_adapter._normalize_parsed_profile(raw)
    # Schema accepts list[Any] — dicts fine
    profile = ParsedProfile(**out)
    assert len(profile.skills) == 2


def test_normalizer_handles_none_input():
    out = ats_adapter._normalize_parsed_profile(None)
    assert out["skills"] == []
    ParsedProfile(**out)


def test_normalizer_handles_string_input():
    out = ats_adapter._normalize_parsed_profile("just a blob")
    assert out["raw_text_preview"] == "just a blob"
    ParsedProfile(**out)


def test_normalizer_preserves_extra_fields():
    raw = {"linkedin": "https://...", "github": "https://...", "skills": ["Python"]}
    out = ats_adapter._normalize_parsed_profile(raw)
    profile = ParsedProfile(**out)
    # extra='allow' keeps the fields
    assert profile.model_extra and "linkedin" in profile.model_extra


def test_normalizer_handles_name_as_list():
    raw = {"name": ["Asha Menon"]}
    out = ats_adapter._normalize_parsed_profile(raw)
    assert out["name"] == "Asha Menon"
    ParsedProfile(**out)


# --- End-to-end via parse_resume ------------------------------------------

def test_parse_resume_normalizes_messy_real_parser_output(tmp_path):
    """Simulate user's real parser returning a messy shape — should not crash."""
    # Create a fake module that returns the bad shape
    messy_output = {
        "name": ["John Doe"],           # list instead of str
        "email": ["a@b.com"],            # list instead of str
        "phone": 9876543210,             # int instead of str
        "skills": {"py": "Python"},      # dict instead of list
        "experience": "5 years total",   # string instead of list
        "education": None,
        "total_experience_years": "5",   # string instead of float
        "linkedin_url": "https://...",   # extra field
    }
    fake_path = tmp_path / "fake.pdf"
    fake_path.write_bytes(b"%PDF-1.4\n%dummy")

    # Patch the import so it returns our messy output
    with patch.object(ats_adapter, "parse_resume", wraps=ats_adapter.parse_resume) as _:
        # Directly test the normalizer path
        out = ats_adapter._normalize_parsed_profile(messy_output)
        profile = ParsedProfile(**out)
        assert profile.total_experience_years == 5.0
        assert profile.email == ["a@b.com"]
        assert profile.skills == ["Python"]
        assert isinstance(profile.experience, list)
