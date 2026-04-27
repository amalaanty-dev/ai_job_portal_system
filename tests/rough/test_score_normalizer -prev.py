"""
Tests for ScoreNormalizer (Day 15)
Path: ai_job_portal_system/tests/test_score_normalizer.py

Run:
    pytest tests/test_score_normalizer.py -v

Tests cover the new target output schema with:
  - per-JD grouping
  - normalized_final_score (0-1)
  - confidence_score, ranking, status, fairness_adjustments, flags, audit_trail
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fairness_engine.score_normalizer import ScoreNormalizer


# ----------------------------------------------------------
# FIXTURES
# ----------------------------------------------------------
@pytest.fixture
def sample_records():
    """3 candidates for the SAME JD (matches PRD batch behavior)."""
    return [
        {
            "identifiers": {"resume_id": "R001", "jd_id": "ai_specialist",
                            "job_role": "ai specialist"},
            "final_score": 84.0,
            "scoring_breakdown": {
                "skill_match": 90, "experience_relevance": 64,
                "education_alignment": 82, "semantic_similarity": 74,
            },
            "weighted_contributions": {
                "skills": 31.5, "experience": 19.2,
                "education": 8.2, "semantic": 14.8,
            },
            "weights": {"skills": 35, "experience": 30,
                        "education": 15, "semantic": 20},
            "score_interpretation": {"rating": "Strong"},
        },
        {
            "identifiers": {"resume_id": "R002", "jd_id": "ai_specialist"},
            "final_score": 57.3,
            "scoring_breakdown": {
                "skill_match": 90, "experience_relevance": 60,
                "education_alignment": 36, "semantic_similarity": 12,
            },
            "weighted_contributions": {
                "skills": 31.5, "experience": 18.0,
                "education": 5.4, "semantic": 2.4,
            },
            "weights": {"skills": 35, "experience": 30,
                        "education": 15, "semantic": 20},
            "score_interpretation": {"rating": "Partial"},
        },
        {
            "identifiers": {"resume_id": "R003", "jd_id": "ai_specialist"},
            "final_score": 35.0,
            "scoring_breakdown": {
                "skill_match": 30, "experience_relevance": 40,
                "education_alignment": 30, "semantic_similarity": 30,
            },
            "weighted_contributions": {
                "skills": 10.5, "experience": 12.0,
                "education": 4.5, "semantic": 6.0,
            },
            "weights": {"skills": 35, "experience": 30,
                        "education": 15, "semantic": 20},
            "score_interpretation": {"rating": "Weak"},
        },
    ]


@pytest.fixture
def multi_jd_records(sample_records):
    """Records for 2 different JDs to test per-JD grouping."""
    multi = list(sample_records)
    # add 2 candidates for a second JD
    multi.append({
        "identifiers": {"resume_id": "R004", "jd_id": "ui_ux_designer"},
        "final_score": 75.0,
        "scoring_breakdown": {"skill_match": 80, "experience_relevance": 70,
                              "education_alignment": 60, "semantic_similarity": 90},
        "weighted_contributions": {"skills": 28.0, "experience": 21.0,
                                   "education": 9.0, "semantic": 18.0},
        "weights": {"skills": 35, "experience": 30,
                    "education": 15, "semantic": 20},
    })
    multi.append({
        "identifiers": {"resume_id": "R005", "jd_id": "ui_ux_designer"},
        "final_score": 40.0,
        "scoring_breakdown": {"skill_match": 50, "experience_relevance": 30,
                              "education_alignment": 40, "semantic_similarity": 40},
        "weighted_contributions": {"skills": 17.5, "experience": 9.0,
                                   "education": 6.0, "semantic": 8.0},
        "weights": {"skills": 35, "experience": 30,
                    "education": 15, "semantic": 20},
    })
    return multi


# ============================================================
# CORE NORMALIZATION TESTS
# ============================================================
def test_min_max_normalization(sample_records, tmp_path):
    n = ScoreNormalizer(method="min_max", output_dir=str(tmp_path))
    out = n.normalize_batch(sample_records, save=False)
    scores = [r["normalized_final_score"] for r in out]
    # min becomes 0.0, max becomes 1.0 (was 0/100 -> 0/1)
    assert min(scores) == 0.0
    assert max(scores) == 1.0


def test_z_score_in_range(sample_records, tmp_path):
    n = ScoreNormalizer(method="z_score", output_dir=str(tmp_path))
    out = n.normalize_batch(sample_records, save=False)
    for r in out:
        assert 0 <= r["normalized_final_score"] <= 1.0


def test_percentile_correctness(sample_records, tmp_path):
    n = ScoreNormalizer(method="percentile", output_dir=str(tmp_path))
    out = n.normalize_batch(sample_records, save=False)
    sorted_recs = sorted(out, key=lambda r: r["audit_trail"]["raw_final_score"])
    assert sorted_recs[-1]["normalized_final_score"] >= \
           sorted_recs[0]["normalized_final_score"]


def test_robust_method(sample_records, tmp_path):
    n = ScoreNormalizer(method="robust", output_dir=str(tmp_path))
    out = n.normalize_batch(sample_records, save=False)
    assert all(0 <= r["normalized_final_score"] <= 1 for r in out)


def test_empty_input(tmp_path):
    n = ScoreNormalizer(method="min_max", output_dir=str(tmp_path))
    out = n.normalize_batch([], save=False)
    assert out == []


def test_invalid_method_raises():
    with pytest.raises(ValueError):
        ScoreNormalizer(method="bogus")


# ============================================================
# OUTPUT SCHEMA TESTS (target format compliance)
# ============================================================
def test_output_has_target_schema_keys(sample_records, tmp_path):
    n = ScoreNormalizer(method="min_max", output_dir=str(tmp_path))
    out = n.normalize_batch(sample_records, save=False)
    expected_keys = {
        "resume_id", "candidate_name_masked", "scores", "weighted_scores",
        "ats_score", "normalized_final_score", "confidence_score",
        "ranking", "status", "fairness_adjustments", "flags", "audit_trail",
    }
    for record in out:
        assert expected_keys.issubset(set(record.keys())), \
            f"Missing keys: {expected_keys - set(record.keys())}"


def test_scores_in_0_1_range(sample_records, tmp_path):
    n = ScoreNormalizer(method="min_max", output_dir=str(tmp_path))
    out = n.normalize_batch(sample_records, save=False)
    for r in out:
        for k, v in r["scores"].items():
            assert 0 <= v <= 1, f"{k}={v} out of range"


def test_candidate_name_masked_pattern(sample_records, tmp_path):
    n = ScoreNormalizer(method="min_max", output_dir=str(tmp_path))
    out = n.normalize_batch(sample_records, save=False)
    for r in out:
        assert r["candidate_name_masked"].startswith("CAND_")


def test_ranking_correctness(sample_records, tmp_path):
    n = ScoreNormalizer(method="min_max", output_dir=str(tmp_path))
    out = n.normalize_batch(sample_records, save=False)
    # output is sorted by rank; rank 1 has highest raw score
    assert out[0]["ranking"]["rank"] == 1
    assert out[0]["audit_trail"]["raw_final_score"] == 84.0
    assert out[-1]["ranking"]["rank"] == 3


def test_status_buckets_assigned(sample_records, tmp_path):
    n = ScoreNormalizer(method="min_max", output_dir=str(tmp_path))
    out = n.normalize_batch(sample_records, save=False)
    statuses = {r["status"] for r in out}
    valid = {"shortlisted", "on_hold", "rejected"}
    assert statuses.issubset(valid)


def test_confidence_score_value_in_range(sample_records, tmp_path):
    n = ScoreNormalizer(method="min_max", output_dir=str(tmp_path))
    out = n.normalize_batch(sample_records, save=False)
    for r in out:
        assert 0 <= r["confidence_score"]["value"] <= 1


def test_audit_trail_complete(sample_records, tmp_path):
    n = ScoreNormalizer(method="min_max", output_dir=str(tmp_path))
    out = n.normalize_batch(sample_records, save=False)
    for r in out:
        at = r["audit_trail"]
        assert "raw_final_score" in at
        assert "normalized_method" in at
        assert "weights_used" in at
        assert "calculation_check" in at
        assert at["calculation_check"]["rounding_applied"] is True


def test_flags_are_strings(sample_records, tmp_path):
    n = ScoreNormalizer(method="min_max", output_dir=str(tmp_path))
    out = n.normalize_batch(sample_records, save=False)
    for r in out:
        assert isinstance(r["flags"], list)
        for f in r["flags"]:
            assert isinstance(f, str)


# ============================================================
# PER-JD GROUPING TESTS
# ============================================================
def test_normalize_per_jd_groups_correctly(multi_jd_records, tmp_path):
    n = ScoreNormalizer(method="min_max", output_dir=str(tmp_path))
    out = n.normalize_per_jd(multi_jd_records, save=True)
    assert "ai_specialist" in out
    assert "ui_ux_designer" in out
    assert len(out["ai_specialist"]) == 3
    assert len(out["ui_ux_designer"]) == 2


def test_per_jd_files_saved(multi_jd_records, tmp_path):
    n = ScoreNormalizer(method="min_max", output_dir=str(tmp_path))
    n.normalize_per_jd(multi_jd_records, save=True)
    files = list(tmp_path.glob("*_normalized_scores.json"))
    file_names = {f.name for f in files}
    assert "ai_specialist_normalized_scores.json" in file_names
    assert "ui_ux_designer_normalized_scores.json" in file_names


def test_per_jd_normalization_independent(multi_jd_records, tmp_path):
    """Each JD's normalization is independent (each pool's max -> 1.0)."""
    n = ScoreNormalizer(method="min_max", output_dir=str(tmp_path))
    out = n.normalize_per_jd(multi_jd_records, save=False)
    # Each JD's top candidate should have normalized_final_score == 1.0
    for jd_id, recs in out.items():
        if len(recs) > 1:
            assert recs[0]["normalized_final_score"] == 1.0


def test_jd_id_canonicalization_groups_consistently(tmp_path):
    """
    Same JD with spaces vs underscores vs different case must group together.
    Tests the _canonicalize_jd_id fix.
    """
    n = ScoreNormalizer(method="min_max", output_dir=str(tmp_path))
    records = [
        # Same JD expressed three different ways (real-world bug scenario):
        {"identifiers": {"resume_id": "r1",
                          "jd_id": "ai specialist in healthcare_parsed_jd"},
         "final_score": 90.0, "scoring_breakdown": {}, "weighted_contributions": {},
         "weights": {}},
        {"identifiers": {"resume_id": "r2",
                          "jd_id": "ai_specialist_in_healthcare_parsed_jd"},
         "final_score": 70.0, "scoring_breakdown": {}, "weighted_contributions": {},
         "weights": {}},
        {"identifiers": {"resume_id": "r3",
                          "jd_id": "AI Specialist in Healthcare_parsed_jd"},
         "final_score": 50.0, "scoring_breakdown": {}, "weighted_contributions": {},
         "weights": {}},
    ]
    out = n.normalize_per_jd(records, save=False)
    # All 3 must collapse to ONE bucket
    assert len(out) == 1
    bucket_key = next(iter(out.keys()))
    assert "ai_specialist_in_healthcare" in bucket_key
    assert len(out[bucket_key]) == 3


# ============================================================
# FAIRNESS ADJUSTMENTS
# ============================================================
def test_fairness_adjustments_with_dep_report(sample_records, tmp_path):
    """When a dep report is supplied, adjustments should be non-zero."""
    n = ScoreNormalizer(method="min_max", output_dir=str(tmp_path))
    deps = [
        {"resume_id": "R001", "keyword_dependency_ratio": 0.1},  # well-supported
        {"resume_id": "R002", "keyword_dependency_ratio": 0.7},  # over-claimed
    ]
    dep_lookup = {d["resume_id"]: d for d in deps}
    out = n.normalize_batch(sample_records, dep_lookup=dep_lookup, save=False)
    # find R001 and R002
    r001 = next(r for r in out if r["resume_id"] == "R001")
    r002 = next(r for r in out if r["resume_id"] == "R002")
    # well-supported gets small negative bonus
    assert r001["fairness_adjustments"]["keyword_bias_reduction"] == -0.03
    # over-claimed gets larger negative
    assert r002["fairness_adjustments"]["keyword_bias_reduction"] < -0.03
