"""Tests for /resume/* and /jd/* routes."""
from __future__ import annotations
import io


def _upload(client, pdf_bytes, name="resume.pdf"):
    return client.post(
        "/v1/resume/upload",
        files={"file": (name, io.BytesIO(pdf_bytes), "application/pdf")},
        data={"job_id": "J123"},
    )


def test_upload_single_resume(client, sample_pdf_bytes):
    r = _upload(client, sample_pdf_bytes)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "success"
    assert body["resume_id"].startswith("R")
    assert body["candidate_id"].startswith("C")
    assert body["filename"] == "resume.pdf"
    assert "X-Request-ID" in r.headers


def test_upload_invalid_extension(client):
    r = client.post(
        "/v1/resume/upload",
        files={"file": ("hack.exe", io.BytesIO(b"bad"), "application/octet-stream")},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["status"] == "error"
    assert body["error_code"] == "INVALID_INPUT"


def test_batch_upload_resumes(client, sample_pdf_bytes):
    r = client.post(
        "/v1/resume/upload/batch",
        files=[
            ("files", ("a.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")),
            ("files", ("b.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")),
            ("files", ("c.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")),
        ],
        data={"job_id": "J123"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3
    assert body["succeeded"] == 3
    assert len(body["items"]) == 3


def test_parse_resume(client, sample_pdf_bytes):
    rid = _upload(client, sample_pdf_bytes).json()["resume_id"]
    r = client.post("/v1/resume/parse", json={"resume_id": rid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["resume_id"] == rid
    assert "skills" in body["parsed_profile"]


def test_parse_unknown_resume(client):
    r = client.post("/v1/resume/parse", json={"resume_id": "RDOESNOTEXIST"})
    assert r.status_code == 404
    assert r.json()["error_code"] == "NOT_FOUND"


def test_jd_upload(client, sample_jd):
    r = client.post("/v1/jd/upload", json=sample_jd)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "success"
    assert body["job_id"].startswith("J")


def test_jd_batch_upload(client, sample_jd):
    r = client.post("/v1/jd/upload/batch", json={"jobs": [sample_jd, sample_jd, sample_jd]})
    assert r.status_code == 200
    assert r.json()["total"] == 3
