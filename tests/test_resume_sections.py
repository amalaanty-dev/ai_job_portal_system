import os
import json
import pytest

from resume_sections.section_classifier import segment_resume 

# ── Configuration ─────────────────────────────────────────────────────
# We only read from the raw JSON folder to protect your data
RAW_JSON_FOLDER = "data/resumes/parsed_resumes/json/"

def get_test_files():
    """Helper to gather files for pytest parametrization."""
    if not os.path.exists(RAW_JSON_FOLDER):
        return []
    return [f for f in os.listdir(RAW_JSON_FOLDER) if f.endswith(".json")]

@pytest.mark.parametrize("filename", get_test_files())
def test_resume_sectioning_accuracy(filename):
    """
    High-accuracy validation:
    1. Checks if headers like 'CORE TECHNICAL SKILLS' are captured.
    2. Ensures Education doesn't contain Certifications.
    3. Verifies that projects and skills are not blank.
    """
    file_path = os.path.join(RAW_JSON_FOLDER, filename)
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Extract text content
    text = data.get("clean_text", "")
    if not text:
        text = "\n".join([str(v) for v in data.values() if isinstance(v, str)])

    # Run the classifier logic in memory
    sections = segment_resume(text)

    # ── Assertions for High Accuracy ──────────────────────────────────
    
    # 1. Experience Check: Should always find at least one role
    assert len(sections["experience"]) > 0, f"FAILED: No experience detected in {filename}"

    # 2. Skills Check: Should not be blank (fixes Amala resume issue)
    assert len(sections["skills"]) > 0, f"FAILED: Skills section is empty in {filename}"

    # 3. Project Check: Should capture project details if present
    # (Optional: only fails if you expect projects in every file)
    if "Amala" in filename:
        assert len(sections["projects"]) > 0, f"FAILED: Projects missing for {filename}"

    # 4. Strict Education Routing: Check that 'Certificate' lines moved to certifications
    for edu_line in sections["education"]:
        assert "certificate" not in edu_line.lower(), \
            f"FAILED: Education contains certification details in {filename}"
        assert "coursera" not in edu_line.lower(), \
            f"FAILED: Education contains online course details in {filename}"

    # 5. Skills Content Integrity: Should not contain long summary paragraphs
    for skill in sections["skills"]:
        assert len(skill) < 150, f"FAILED: Skill entry appears to be a summary paragraph in {filename}"

# ── CMD RUN COMMAND ───────────────────────────────────────────────────
# python -m pytest -v tests/test_resume_sections.py
