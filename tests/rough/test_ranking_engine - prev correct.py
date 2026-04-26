"""
test_ranking_engine.py
-----------------------
Unit tests for the Day 14 Ranking & Shortlisting Engine.

Aligned with the Day 13 ATS engine output shape:
  {
    "identifiers": {"resume_id": "...", "jd_id": "...", "job_role": "..."},
    "final_score": 57.3,
    "scoring_breakdown": {
        "skill_match": ..., "experience_relevance": ...,
        "education_alignment": ..., "semantic_similarity": ...
    },
    ...
  }

Also verifies the consolidated_exporter (single-jd_id grouping).

Run with:
    pytest tests/test_ranking_engine.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ranking_engine.config import ranking_config as cfg
from ranking_engine.core.filters import apply_hard_filters
from ranking_engine.core.ranker import rank_candidates
from ranking_engine.core.shortlister import Zone, assign_zone, bucket_candidates
from ranking_engine.exporters.consolidated_exporter import (
    _candidate_jd_id,
    _candidate_job_role,
    write_consolidated,
)
from utils.score_utils import (
    compute_composite_score,
    extract_sub_scores,
    normalize_score,
    passthrough_score,
)


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------
@pytest.fixture
def weights():
    return dict(cfg.DEFAULT_WEIGHTS)


@pytest.fixture
def thresholds():
    return dict(cfg.THRESHOLDS)


def _make_candidate(resume_id: str, jd_id: str, role: str, final: float,
                    skill: int = 80, exp: int = 70, edu: int = 60, sem: int = 50,
                    years: int = 3, skills: list[str] = None) -> dict:
    return {
        "identifiers": {"resume_id": resume_id, "jd_id": jd_id, "job_role": role},
        "final_score": final,
        "scoring_breakdown": {
            "skill_match":          skill,
            "experience_relevance": exp,
            "education_alignment":  edu,
            "semantic_similarity":  sem,
        },
        "score_interpretation": {
            "rating":         "Partial Fit",
            "recommendation": "Review manually",
            "priority":       "Medium",
        },
        "total_experience_years": years,
        "skills": skills or ["python", "ml"],
    }


@pytest.fixture
def sample_candidates():
    """Three candidates, all under the same JD."""
    return [
        _make_candidate("Resume_Alice", "ai_specialist_parsed_jd",
                        "ai specialist in healthcare analytics",
                        final=85.0, skill=90, exp=85, edu=80, sem=75, years=5,
                        skills=["python", "ml", "healthcare"]),
        _make_candidate("Resume_Bob", "ai_specialist_parsed_jd",
                        "ai specialist in healthcare analytics",
                        final=60.0, skill=70, exp=55, edu=60, sem=40, years=2,
                        skills=["javascript", "react"]),
        _make_candidate("Resume_Carol", "ai_specialist_parsed_jd",
                        "ai specialist in healthcare analytics",
                        final=35.0, skill=40, exp=30, edu=35, sem=25, years=0,
                        skills=["word", "excel"]),
    ]


@pytest.fixture
def multi_jd_candidates():
    """Six candidates across two different JDs."""
    return [
        _make_candidate("R1", "jd_alpha", "Backend Developer", final=82),
        _make_candidate("R2", "jd_alpha", "Backend Developer", final=58),
        _make_candidate("R3", "jd_alpha", "Backend Developer", final=33),
        _make_candidate("R4", "jd_beta",  "Frontend Developer", final=78),
        _make_candidate("R5", "jd_beta",  "Frontend Developer", final=45),
        _make_candidate("R6", "jd_beta",  "Frontend Developer", final=20),
    ]


# ---------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------
class TestNormalizeScore:
    def test_none_returns_none(self):           assert normalize_score(None) is None
    def test_fraction_scaled(self):             assert normalize_score(0.75) == 75.0
    def test_percentage_passthrough(self):      assert normalize_score(82) == 82.0
    def test_negative_clamped(self):            assert normalize_score(-5) == 0.0
    def test_over_100_clamped(self):            assert normalize_score(150) == 100.0
    def test_garbage_returns_none(self):        assert normalize_score("abc") is None
    def test_zero_passthrough(self):            assert normalize_score(0) == 0.0


# ---------------------------------------------------------------------
# Sub-score extraction (Day 13 shape)
# ---------------------------------------------------------------------
class TestExtractSubScores:
    def test_day13_shape(self, sample_candidates):
        subs = extract_sub_scores(sample_candidates[0])
        assert subs["ats_score"] == 85.0
        assert subs["skill_score"] == 90.0
        assert subs["experience_score"] == 85.0
        assert subs["education_score"] == 80.0
        assert subs["semantic_score"] == 75.0

    def test_returns_none_for_missing(self):
        c = {"identifiers": {"resume_id": "X"}}
        subs = extract_sub_scores(c)
        assert all(v is None for v in subs.values())


# ---------------------------------------------------------------------
# Pass-through score
# ---------------------------------------------------------------------
class TestPassthrough:
    def test_returns_day13_final_score(self, sample_candidates):
        assert passthrough_score(sample_candidates[0]) == 85.0
        assert passthrough_score(sample_candidates[1]) == 60.0

    def test_returns_none_when_missing(self):
        assert passthrough_score({"identifiers": {}}) is None


# ---------------------------------------------------------------------
# Composite score (used in --recompute mode)
# ---------------------------------------------------------------------
class TestCompositeScore:
    def test_all_present(self, weights):
        subs = {"skill_score": 90, "experience_score": 85,
                "education_score": 80, "semantic_score": 75}
        score, eff = compute_composite_score(subs, weights)
        expected = 90 * 0.35 + 85 * 0.30 + 80 * 0.15 + 75 * 0.20
        assert score == round(expected, 2)
        assert sum(eff.values()) == pytest.approx(1.0, abs=1e-3)

    def test_missing_redistributes(self, weights):
        subs = {"skill_score": 90, "experience_score": 85,
                "education_score": 80, "semantic_score": None}
        score, eff = compute_composite_score(subs, weights)
        assert "semantic_score" not in eff
        assert sum(eff.values()) == pytest.approx(1.0, abs=1e-3)

    def test_all_missing(self, weights):
        score, eff = compute_composite_score({k: None for k in weights}, weights)
        assert score == 0.0
        assert eff == {}


# ---------------------------------------------------------------------
# Hard filters
# ---------------------------------------------------------------------
class TestHardFilters:
    def test_experience_passes(self, sample_candidates):
        passed, _ = apply_hard_filters(
            sample_candidates[0], {"min_experience_years": 3, "required_skills": []}
        )
        assert passed

    def test_experience_fails(self, sample_candidates):
        passed, reasons = apply_hard_filters(
            sample_candidates[1], {"min_experience_years": 5, "required_skills": []}
        )
        assert not passed
        assert any("min_experience_not_met" in r for r in reasons)

    def test_required_skill_missing(self, sample_candidates):
        passed, reasons = apply_hard_filters(
            sample_candidates[0], {"min_experience_years": 0, "required_skills": ["sales"]}
        )
        assert not passed

    def test_required_skill_present(self, sample_candidates):
        passed, _ = apply_hard_filters(
            sample_candidates[0], {"min_experience_years": 0, "required_skills": ["python"]}
        )
        assert passed


# ---------------------------------------------------------------------
# Ranker - PASS-THROUGH mode (default)
# ---------------------------------------------------------------------
class TestRankerPassthrough:
    def test_uses_day13_final_score(self, sample_candidates, weights):
        ranked = rank_candidates(sample_candidates, weights)
        assert ranked[0]["final_score"] == 85.0
        assert ranked[1]["final_score"] == 60.0
        assert ranked[2]["final_score"] == 35.0

    def test_resolves_id_from_identifiers(self, sample_candidates, weights):
        ranked = rank_candidates(sample_candidates, weights)
        assert ranked[0]["candidate_id"] == "Resume_Alice"

    def test_carries_job_role(self, sample_candidates, weights):
        ranked = rank_candidates(sample_candidates, weights)
        assert ranked[0]["job_role"] == "ai specialist in healthcare analytics"

    def test_rank_numbers(self, sample_candidates, weights):
        ranked = rank_candidates(sample_candidates, weights)
        assert [c["rank"] for c in ranked] == [1, 2, 3]

    def test_scoring_mode_recorded(self, sample_candidates, weights):
        ranked = rank_candidates(sample_candidates, weights)
        assert all(c["scoring_mode"] == "passthrough" for c in ranked)


# ---------------------------------------------------------------------
# Ranker - RECOMPUTE mode
# ---------------------------------------------------------------------
class TestRankerRecompute:
    def test_recomputes_from_subscores(self, sample_candidates, weights):
        ranked = rank_candidates(sample_candidates, weights, recompute=True)
        # Alice: 90*0.35 + 85*0.30 + 80*0.15 + 75*0.20 = 84.0
        assert ranked[0]["final_score"] == 84.0
        assert ranked[0]["scoring_mode"] == "recomputed"


# ---------------------------------------------------------------------
# Shortlister
# ---------------------------------------------------------------------
class TestShortlister:
    def test_assign_zone_boundaries(self, thresholds):
        assert assign_zone(70.0, thresholds) == Zone.SHORTLIST
        assert assign_zone(69.99, thresholds) == Zone.REVIEW
        assert assign_zone(50.0, thresholds) == Zone.REVIEW
        assert assign_zone(49.99, thresholds) == Zone.REJECTED

    def test_bucket_split(self, sample_candidates, weights, thresholds):
        ranked = rank_candidates(sample_candidates, weights)
        buckets = bucket_candidates(ranked, thresholds)
        assert len(buckets["shortlisted"]) == 1
        assert len(buckets["review"]) == 1
        assert len(buckets["rejected"]) == 1


# ---------------------------------------------------------------------
# Consolidated exporter (NEW)
# ---------------------------------------------------------------------
class TestConsolidatedExporter:
    def test_jd_id_resolution(self, sample_candidates):
        assert _candidate_jd_id(sample_candidates[0]) == "ai_specialist_parsed_jd"

    def test_jd_id_unknown_fallback(self):
        assert _candidate_jd_id({}) == "unknown_jd"

    def test_job_role_resolution(self, sample_candidates):
        assert _candidate_job_role(sample_candidates[0]) == "ai specialist in healthcare analytics"

    def test_single_jd_envelope(self, tmp_path, sample_candidates, weights):
        ranked = rank_candidates(sample_candidates, weights)
        result = write_consolidated(ranked, "ranked", tmp_path)
        env = json.loads(result["main"].read_text())
        assert env["jd_id"] == "ai_specialist_parsed_jd"
        assert env["job_role"] == "ai specialist in healthcare analytics"
        assert env["category"] == "ranked"
        assert env["total_candidates"] == 3
        assert "generated_at" in env
        assert len(env["candidates"]) == 3
        # Per-jd subfolder NOT created when only one JD present
        assert result["per_jd_dir"] is None

    def test_multi_jd_envelope(self, tmp_path, multi_jd_candidates, weights):
        ranked = rank_candidates(multi_jd_candidates, weights)
        result = write_consolidated(ranked, "ranked", tmp_path)
        env = json.loads(result["main"].read_text())
        # Multiple JDs -> synthetic identifier, but each jd_id is listed
        assert env["jd_id"] == "_all"
        assert sorted(env["jd_ids"]) == ["jd_alpha", "jd_beta"]
        assert env["total_candidates"] == 6
        # Per-jd subfolder gets one file per JD
        assert result["per_jd_dir"] is not None
        per_jd_files = sorted(p.name for p in result["per_jd_dir"].iterdir())
        assert per_jd_files == ["jd_alpha.json", "jd_beta.json"]
        # Each per-jd file has its own envelope
        alpha = json.loads((result["per_jd_dir"] / "jd_alpha.json").read_text())
        assert alpha["jd_id"] == "jd_alpha"
        assert alpha["total_candidates"] == 3

    def test_skip_per_jd_flag(self, tmp_path, multi_jd_candidates, weights):
        ranked = rank_candidates(multi_jd_candidates, weights)
        result = write_consolidated(ranked, "ranked", tmp_path, write_per_jd=False)
        assert result["per_jd_dir"] is None


# ---------------------------------------------------------------------
# End-to-end pipeline smoke tests
# ---------------------------------------------------------------------
def test_end_to_end_passthrough(tmp_path, sample_candidates):
    from scripts.run_ranking_engine import main as run_main

    input_dir = tmp_path / "ats_scores"
    input_dir.mkdir()
    output_dir = tmp_path / "ranking_engine_results"

    for c in sample_candidates:
        rid = c["identifiers"]["resume_id"]
        (input_dir / f"{rid}.json").write_text(json.dumps(c))

    rc = run_main(["--input-dir", str(input_dir), "--output-dir", str(output_dir)])
    assert rc == 0

    # All consolidated JSONs exist with correct envelope
    for cat in ("ranked", "shortlisted", "review", "rejected"):
        path = output_dir / cat / f"{cat}_candidates.json"
        assert path.exists(), f"missing {path}"
        env = json.loads(path.read_text())
        assert env["category"] == cat
        assert "jd_id" in env
        assert "candidates" in env
        assert env["total_candidates"] == len(env["candidates"])

    # Consolidated ranked uses the single jd_id (not "_all")
    ranked_env = json.loads((output_dir / "ranked" / "ranked_candidates.json").read_text())
    assert ranked_env["jd_id"] == "ai_specialist_parsed_jd"
    assert ranked_env["total_candidates"] == 3

    # CSVs still produced
    assert (output_dir / "ranked" / "ranked_candidates.csv").exists()
    assert (output_dir / "shortlisted" / "shortlisted_candidates.csv").exists()
    assert (output_dir / "shortlisted" / "call_queue.json").exists()
    assert (output_dir / "reports" / "summary.json").exists()


def test_end_to_end_multi_jd(tmp_path, multi_jd_candidates):
    """Verify multi-JD inputs produce per-JD breakdowns."""
    from scripts.run_ranking_engine import main as run_main

    input_dir = tmp_path / "ats_scores"
    input_dir.mkdir()
    output_dir = tmp_path / "out_multi"

    for c in multi_jd_candidates:
        rid = c["identifiers"]["resume_id"]
        jd  = c["identifiers"]["jd_id"]
        (input_dir / f"{rid}_{jd}.json").write_text(json.dumps(c))

    rc = run_main(["--input-dir", str(input_dir), "--output-dir", str(output_dir)])
    assert rc == 0

    ranked_env = json.loads((output_dir / "ranked" / "ranked_candidates.json").read_text())
    assert ranked_env["jd_id"] == "_all"
    assert sorted(ranked_env["jd_ids"]) == ["jd_alpha", "jd_beta"]

    per_jd_dir = output_dir / "ranked" / "ranked_per_jd"
    assert per_jd_dir.exists()
    assert (per_jd_dir / "jd_alpha.json").exists()
    assert (per_jd_dir / "jd_beta.json").exists()


def test_no_per_jd_flag(tmp_path, multi_jd_candidates):
    from scripts.run_ranking_engine import main as run_main

    input_dir = tmp_path / "ats_scores"
    input_dir.mkdir()
    output_dir = tmp_path / "out_no_per_jd"

    for c in multi_jd_candidates:
        rid = c["identifiers"]["resume_id"]
        jd  = c["identifiers"]["jd_id"]
        (input_dir / f"{rid}_{jd}.json").write_text(json.dumps(c))

    rc = run_main(["--input-dir", str(input_dir), "--output-dir", str(output_dir),
                   "--no-per-jd"])
    assert rc == 0

    # Top-level still written
    assert (output_dir / "ranked" / "ranked_candidates.json").exists()
    # Per-jd subfolders NOT written
    assert not (output_dir / "ranked" / "ranked_per_jd").exists()


def test_end_to_end_array_file(tmp_path, sample_candidates):
    """Verify support for ranked_*.json wrapper files."""
    from scripts.run_ranking_engine import main as run_main

    input_dir = tmp_path / "ats_scores"
    input_dir.mkdir()
    output_dir = tmp_path / "out_array"

    wrapper = {
        "jd_id": "ai_specialist_parsed_jd",
        "job_role": "ai specialist in healthcare analytics",
        "total_candidates": len(sample_candidates),
        "ranked_candidates": sample_candidates,
    }
    (input_dir / "ranked_ai_specialist_parsed_jd.json").write_text(json.dumps(wrapper))

    rc = run_main(["--input-dir", str(input_dir), "--output-dir", str(output_dir)])
    assert rc == 0
    summary = json.loads((output_dir / "reports" / "summary.json").read_text())
    assert summary["total_candidates"] == 3
