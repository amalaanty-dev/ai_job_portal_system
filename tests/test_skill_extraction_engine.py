import pytest
import json
# Import the updated function name
from skill_engine.skill_extractor import extract_skills, calculate_weighted_confidence, correct_spelling
from skill_engine.skill_dictionary import normalize_skill, get_skill_category

# ── Test Data ─────────────────────────────────────────────────────────

TEST_CASES = [
    {
        "text": "Experienced in Python programming and machine learning. Used Python for data analysis.",
        "sections": {
            "skills": "Python, machine learning",
            "experience": "Used Python for data analysis",
            "projects": ""
        },
        "expected_skills": ["python", "machine learning", "data analysis"],
        "expected_categories": {"python": "tech", "machine learning": "tech"},
        "expected_confidence": {"python": 0.95}  # 2 mentions + experience bonus
    },
    {
        "text": "Familiar with ML, AI, and PowerBI. Expert in MS Excel.",
        "expected_skills": ["machine learning", "artificial intelligence", "power bi", "excel"],
        "note": "Testing normalization of synonyms"
    },
    {
        "text": "Specialist in Pithon, Javaascript, and SQL.",
        "expected_skills": ["python", "javascript", "sql"],
        "note": "Testing spelling correction logic with 0.8 cutoff"
    }
]

# ── Test Functions ────────────────────────────────────────────────────

def test_extract_skills_exact_and_synonyms():
    """Verifies that both exact matches and synonyms are captured."""
    for case in TEST_CASES:
        skills = extract_skills(case["text"])
        for expected in case["expected_skills"]:
            assert expected in skills, f"Failed to find {expected} in {case.get('note')}"

def test_spelling_correction_threshold():
    """Ensures typos are corrected but 'hallucinations' are blocked by 0.8 cutoff."""
    # Should correct obvious typos
    assert correct_spelling("pithon") == "python"
    # Should NOT match 'learning' to 'lean' (0.6 would match, 0.8 won't)
    assert correct_spelling("learning") is None 

def test_weighted_confidence_scoring():
    """
    Validates the new Weighted Confidence logic:
    - Base frequency scoring
    - +0.1 Bonus for appearing in Experience/Projects
    """
    sec_texts = {
        "skills": "Python",
        "experience": "I used Python at my last job",
        "projects": ""
    }
    
    # Python appears twice (0.85) + experience bonus (+0.1) = 0.95
    score = calculate_weighted_confidence("python", sec_texts)
    assert score == 0.95
    
    # Skill only in 'skills' section once = 0.75
    sec_texts_low = {"skills": "Java", "experience": "", "projects": ""}
    assert calculate_weighted_confidence("java", sec_texts_low) == 0.75

def test_skill_categorization():
    """Ensures skills are mapped to the correct high-level categories."""
    assert get_skill_category("python") == "tech"
    assert get_skill_category("project management") == "business"
    assert get_skill_category("tableau") == "creative"

def test_normalization():
    """Verifies the synonym mapping defined in the dictionary."""
    assert normalize_skill("ml") == "machine learning"
    assert normalize_skill("ms excel") == "excel"
    assert normalize_skill("sklearn") == "scikit-learn"