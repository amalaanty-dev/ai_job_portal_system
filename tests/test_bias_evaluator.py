"""
Tests for BiasEvaluator (Day 15)
Path: ai_job_portal_system/tests/test_bias_evaluator.py
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fairness_engine.bias_evaluator import BiasEvaluator


@pytest.fixture
def normalized_records():
    """Records in new schema format with normalized_final_score (0-1)."""
    return [
        {"resume_id": "r1", "normalized_final_score": 0.9},
        {"resume_id": "r2", "normalized_final_score": 0.5},
        {"resume_id": "r3", "normalized_final_score": 0.3},
    ]


@pytest.fixture
def evaluator(tmp_path):
    return BiasEvaluator(output_dir=str(tmp_path))


def test_score_distribution_computed(evaluator, normalized_records):
    out = evaluator.evaluate(normalized_records, run_id="t", save=False)
    assert "score_distribution" in out["indicators"]
    assert out["indicators"]["score_distribution"]["n"] == 3


def test_no_data_returns_no_data(evaluator):
    out = evaluator.evaluate([], run_id="t", save=False)
    assert out["summary_verdict"] == "no_data"


def test_cohort_disparity_detected(evaluator, normalized_records):
    cohort_map = {
        "r1": {"gender": "male"},
        "r2": {"gender": "female"},
        "r3": {"gender": "female"},
    }
    out = evaluator.evaluate(normalized_records, cohort_map=cohort_map,
                             run_id="t", save=False)
    cd = out["indicators"]["cohort_disparity"]
    assert "gender" in cd
    # male=90, female_avg=40 -> gap=50 (>10) -> flagged
    assert any("cohort_gap" in f["type"] for f in out["flags"])


def test_keyword_dependency_high_flagged(evaluator, normalized_records):
    deps = [
        {"keyword_dependency_ratio": 0.8, "context_adjusted_skill_score": 30},
        {"keyword_dependency_ratio": 0.7, "context_adjusted_skill_score": 35},
    ]
    out = evaluator.evaluate(normalized_records, dependency_reports=deps,
                             run_id="t", save=False)
    assert any(f["type"] == "high_keyword_dependency" for f in out["flags"])


def test_pass_verdict_when_clean(evaluator):
    # tight, clean distribution
    recs = [
        {"resume_id": f"r{i}", "normalized_final_score": (50.0 + i) / 100.0}
        for i in range(5)
    ]
    deps = [{"keyword_dependency_ratio": 0.1,
             "context_adjusted_skill_score": 80}] * 5
    out = evaluator.evaluate(recs, dependency_reports=deps,
                             run_id="t", save=False)
    assert out["summary_verdict"] == "PASS"
