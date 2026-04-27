"""
Tests for FairnessPipeline (Day 15)
Path: ai_job_portal_system/tests/test_fairness_pipeline.py
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fairness_engine.fairness_pipeline import FairnessPipeline


@pytest.fixture
def fixture_files(tmp_path):
    parsed_resume = {
        "resume_name": "T.pdf",
        "name": "AMALA P ANTY",
        "roles": [{"job_title": "Data Engineer II",
                   "company": "Gupshup", "start_date": "2021-07-01",
                   "end_date": "2024-12-01", "duration_months": 42}],
        "experience": 5.2,
        "education": [{"degree": "MBA",
                       "full_line": "MBA – Finance 2016 – 2018",
                       "years": ["2016", "2018"]}],
        "clean_text": ("AMALA P ANTY\nBangalore • amalaanty@gmail.com\n"
                       "PROFESSIONAL SUMMARY\nResults-driven scientist...\n"),
    }
    sections = {
        "skills": ["Programming & DB Python, SQL", "ML & AI ai, nlp"],
        "experience": [{"role_header": "Data Engineer II | Gupshup",
                        "duties": ["Built ai models", "nlp pipelines"]}],
        "education": ["MBA – Finance 2016 – 2018",
                      "Rajagiri | 70%"],
        "projects": ["Churn Prediction | Classification",
                     "Used ai and nlp"],
        "achievements": ["Top performer"],
    }
    parsed_jd = {
        "role": ["ai specialist"],
        "skills_required": ["ai", "nlp", "deep learning"],
        "experience_required": "Not specified",
        "education_required": "master",
    }
    pr_path = tmp_path / "p.json"
    sec_path = tmp_path / "s.json"
    jd_path = tmp_path / "jd.json"
    pr_path.write_text(json.dumps(parsed_resume))
    sec_path.write_text(json.dumps(sections))
    jd_path.write_text(json.dumps(parsed_jd))
    return str(pr_path), str(sec_path), str(jd_path)


def test_run_single_completes(fixture_files, tmp_path):
    pipe = FairnessPipeline(data_root=str(tmp_path))
    pr, sec, jd = fixture_files
    out = pipe.run_single(pr, sec, jd)
    assert "candidate_id" in out
    assert out["dependency_report"]["context_adjusted_skill_score"] >= 0
    assert out["masked_resume_audit"]["total_masks_applied"] >= 1


def test_run_batch_pass_with_clean_inputs(tmp_path):
    pipe = FairnessPipeline(data_root=str(tmp_path))
    ats_records = [
        {"identifiers": {"resume_id": f"r{i}", "jd_id": "test_jd"},
         "final_score": 50 + i,
         "scoring_breakdown": {"skill_match": 60, "experience_relevance": 50,
                               "education_alignment": 50, "semantic_similarity": 50},
         "weighted_contributions": {"skills": 21, "experience": 15,
                                    "education": 7.5, "semantic": 10},
         "weights": {"skills": 35, "experience": 30,
                     "education": 15, "semantic": 20},
         "score_interpretation": {"rating": "ok"}}
        for i in range(4)
    ]
    out = pipe.run_batch(ats_records, run_id="test_batch")
    assert out["n_total_candidates"] == 4
    assert out["n_jds"] == 1
    assert out["bias_verdict"] in {"PASS", "REVIEW_NEEDED"}
    # per_jd summary should exist
    assert "test_jd" in out["per_jd_summaries"]
