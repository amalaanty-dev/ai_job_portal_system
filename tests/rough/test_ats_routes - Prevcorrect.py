"""Tests for /ats/score, /ats/score/batch, /ats/shortlist, /jobs/*."""
from __future__ import annotations
import io
import time


def _upload_resume(client, pdf, name="r.pdf"):
    return client.post(
        "/v1/resume/upload",
        files={"file": (name, io.BytesIO(pdf), "application/pdf")},
    ).json()


def _upload_jd(client, jd):
    return client.post("/v1/jd/upload", json=jd).json()["job_id"]


def test_score_one(client, sample_pdf_bytes, sample_jd):
    cand = _upload_resume(client, sample_pdf_bytes)
    job_id = _upload_jd(client, sample_jd)
    r = client.post("/v1/ats/score", json={"candidate_id": cand["candidate_id"], "job_id": job_id})
    assert r.status_code == 200, r.text
    body = r.json()
    assert 0 <= body["final_score"] <= 100
    assert set(body["breakdown"].keys()) == {"skills", "experience", "education", "semantic"}
    assert body["matched_status"] in ("Shortlisted", "Rejected")


def test_score_batch_NxM(client, sample_pdf_bytes, sample_jd):
    candidates = [_upload_resume(client, sample_pdf_bytes, f"r{i}.pdf") for i in range(3)]
    jd2 = {**sample_jd, "job_title": "Frontend Dev", "required_skills": ["React"]}
    j1 = _upload_jd(client, sample_jd)
    j2 = _upload_jd(client, jd2)

    r = client.post(
        "/v1/ats/score/batch",
        json={
            "candidate_ids": [c["candidate_id"] for c in candidates],
            "job_ids": [j1, j2],
            "shortlist_threshold": 50,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_pairs"] == 6  # 3 × 2
    assert len(body["scores"]) == 6


def test_shortlist(client, sample_pdf_bytes, sample_jd):
    candidates = [_upload_resume(client, sample_pdf_bytes, f"r{i}.pdf") for i in range(4)]
    j = _upload_jd(client, sample_jd)

    client.post(
        "/v1/ats/score/batch",
        json={
            "candidate_ids": [c["candidate_id"] for c in candidates],
            "job_ids": [j],
            "shortlist_threshold": 0,
        },
    )

    r = client.post("/v1/ats/shortlist", json={"job_id": j, "threshold": 50, "top_n": 3})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["job_id"] == j
    assert len(body["candidates"]) <= 3
    assert all(c["rank"] >= 1 for c in body["candidates"])


def test_async_job_lifecycle(client, sample_pdf_bytes, sample_jd):
    cand = _upload_resume(client, sample_pdf_bytes)
    j = _upload_jd(client, sample_jd)

    start = client.post(
        "/v1/jobs/start",
        json={
            "kind": "score_batch",
            "payload": {
                "candidate_ids": [cand["candidate_id"]],
                "job_ids": [j],
                "shortlist_threshold": 50,
            },
        },
    )
    assert start.status_code == 200, start.text
    job_id = start.json()["job_id"]

    # Poll status
    for _ in range(30):
        s = client.get(f"/v1/jobs/status/{job_id}")
        assert s.status_code == 200
        if s.json()["status"] == "completed":
            break
        time.sleep(0.1)
    else:
        raise AssertionError("Async job didn't complete in time")

    res = client.get(f"/v1/jobs/result/{job_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "completed"
    assert res.json()["result"]["total_pairs"] == 1


def test_unknown_job_status_returns_404(client):
    r = client.get("/v1/jobs/status/JOBNOPE")
    assert r.status_code == 404
    assert r.json()["error_code"] == "NOT_FOUND"
