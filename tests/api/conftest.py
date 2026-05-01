"""Pytest fixtures: TestClient, sample resume bytes, sample JD."""
from __future__ import annotations
import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from api.main import create_app  # noqa: E402
from api.services import storage  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_storage():
    storage.reset_storage()
    yield
    storage.reset_storage()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Minimal valid PDF — 1 page with the text 'Python Django Resume'."""
    # Hand-crafted minimum PDF — works without any deps
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        b"4 0 obj<</Length 55>>stream\n"
        b"BT /F1 12 Tf 10 100 Td (Python Django React FastAPI) Tj ET\n"
        b"endstream endobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n"
        b"0000000009 00000 n \n0000000053 00000 n \n0000000098 00000 n \n"
        b"0000000189 00000 n \n0000000287 00000 n \n"
        b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n347\n%%EOF\n"
    )


@pytest.fixture
def sample_jd() -> dict:
    return {
        "job_title": "Backend Developer",
        "required_skills": ["Python", "Django", "FastAPI"],
        "preferred_skills": ["AWS", "Docker"],
        "experience_required": 2,
        "education_required": ["B.Tech"],
        "location": "Remote",
        "description": "Build & scale backend APIs.",
    }
