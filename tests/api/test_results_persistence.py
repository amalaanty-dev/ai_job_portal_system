"""Verify every API call produces the right artifact under api_data_results/."""
from __future__ import annotations
import io
import json

from api.config import settings


def _upload_resume(client, pdf, name="r.pdf"):
    return client.post(
        "/v1/resume/upload",
        files={"file": (name, io.BytesIO(pdf), "application/pdf")},
    ).json()


def _upload_jd(client, jd):
    return client.post("/v1/jd/upload", json=jd).json()["job_id"]


def test_input_uploads_land_in_api_data(client, sample_pdf_bytes, sample_jd):
    cand = _upload_resume(client, sample_pdf_bytes)
    job_id = _upload_jd(client, sample_jd)

    # Resume bytes saved under api_data/raw_resumes/
    raw_files = list(settings.upload_dir.iterdir())
    assert any(f.name.startswith(cand["resume_id"]) for f in raw_files)
    assert raw_files[0].parent == settings.upload_dir
    assert "api_data" in str(settings.upload_dir)
    assert "raw_resumes" in str(settings.upload_dir)

    # JD JSON saved under api_data/jds/
    jd_files = list(settings.jd_dir.iterdir())
    assert any(f.name == f"{job_id}.json" for f in jd_files)
    assert "api_data" in str(settings.jd_dir)


def test_parse_persists_artifact_to_results_parsed(client, sample_pdf_bytes):
    cand = _upload_resume(client, sample_pdf_bytes)
    rid = cand["resume_id"]
    r = client.post("/v1/resume/parse", json={"resume_id": rid})
    assert r.status_code == 200

    artifact = settings.parsed_results_dir / f"{rid}.json"
    assert artifact.exists(), f"Expected parsed artifact at {artifact}"
    data = json.loads(artifact.read_text())
    assert data["artifact_type"] == "parsed_resume"
    assert data["resume_id"] == rid
    assert data["candidate_id"] == cand["candidate_id"]
    assert "parsed_profile" in data
    assert "generated_at" in data
    # Must live under api_data_results/parsed/
    assert "api_data_results" in str(artifact)
    assert artifact.parent.name == "parsed"


def test_score_persists_artifact_to_results_scores(client, sample_pdf_bytes, sample_jd):
    cand = _upload_resume(client, sample_pdf_bytes)
    job_id = _upload_jd(client, sample_jd)
    r = client.post(
        "/v1/ats/score",
        json={"candidate_id": cand["candidate_id"], "job_id": job_id},
    )
    assert r.status_code == 200

    artifact = settings.scores_results_dir / f"{cand['candidate_id']}__{job_id}.json"
    assert artifact.exists(), f"Expected score artifact at {artifact}"
    data = json.loads(artifact.read_text())
    assert data["artifact_type"] == "score"
    assert data["candidate_id"] == cand["candidate_id"]
    assert data["job_id"] == job_id
    assert 0 <= data["final_score"] <= 100
    assert set(data["breakdown"].keys()) == {"skills", "experience", "education", "semantic"}
    assert "api_data_results" in str(artifact)
    assert artifact.parent.name == "scores"


def test_score_batch_persists_one_artifact_per_pair(client, sample_pdf_bytes, sample_jd):
    cands = [_upload_resume(client, sample_pdf_bytes, f"r{i}.pdf") for i in range(2)]
    j1 = _upload_jd(client, sample_jd)
    j2 = _upload_jd(client, {**sample_jd, "job_title": "Frontend Dev"})

    r = client.post(
        "/v1/ats/score/batch",
        json={
            "candidate_ids": [c["candidate_id"] for c in cands],
            "job_ids": [j1, j2],
            "shortlist_threshold": 50,
        },
    )
    assert r.status_code == 200

    # 2 candidates × 2 JDs = 4 score files
    files = list(settings.scores_results_dir.glob("*.json"))
    assert len(files) == 4

    # Filename format: {candidate}__{job}.json
    for c in cands:
        for j in (j1, j2):
            assert (settings.scores_results_dir / f"{c['candidate_id']}__{j}.json").exists()


def test_shortlist_persists_artifact_to_results_shortlists(client, sample_pdf_bytes, sample_jd):
    cands = [_upload_resume(client, sample_pdf_bytes, f"r{i}.pdf") for i in range(3)]
    job_id = _upload_jd(client, sample_jd)

    client.post(
        "/v1/ats/score/batch",
        json={
            "candidate_ids": [c["candidate_id"] for c in cands],
            "job_ids": [job_id],
            "shortlist_threshold": 0,
        },
    )

    r = client.post("/v1/ats/shortlist", json={"job_ids": job_id, "threshold": 50})
    assert r.status_code == 200

    artifact = settings.shortlist_results_dir / f"{job_id}.json"
    assert artifact.exists(), f"Expected shortlist artifact at {artifact}"
    data = json.loads(artifact.read_text())
    assert data["artifact_type"] == "shortlist"
    assert data["job_id"] == job_id
    assert data["total_candidates"] >= 3
    assert isinstance(data["candidates"], list)
    assert "generated_at" in data
    assert "api_data_results" in str(artifact)
    assert artifact.parent.name == "shortlists"
