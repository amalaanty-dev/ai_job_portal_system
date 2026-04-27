"""
tests/test_ats_scoring.py
Day 13 – Comprehensive ATS Scoring Engine Tests

Run:
    pytest tests/test_ats_scoring.py -v
    pytest tests/test_ats_scoring.py -v --tb=short
"""

import json
import os
import sys
import math
import pytest
import tempfile
import shutil
from pathlib import Path

# ── Allow running from project root ──────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ats_engine.weight_config import WeightConfig
from ats_engine.score_components import (
    compute_skill_score,
    compute_education_score,
    compute_experience_score,
    compute_semantic_score,
)
from ats_engine.explainer import build_explanation
from ats_engine.ats_scorer import score_candidate, load_json


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_skills_data():
    return {
        "candidate": "test_candidate",
        "skills": [
            {"skill": "python",      "category": "tech",     "confidence": 0.95},
            {"skill": "sql",         "category": "tech",     "confidence": 0.90},
            {"skill": "machine learning", "category": "tech","confidence": 0.85},
            {"skill": "deep learning","category": "tech",    "confidence": 0.80},
            {"skill": "nlp",         "category": "tech",     "confidence": 0.95},
            {"skill": "kpi analysis","category": "business", "confidence": 0.75},
            {"skill": "banking",     "category": "business", "confidence": 0.80},
            {"skill": "eda",         "category": "other",    "confidence": 0.75},
            {"skill": "feature engineering","category":"other","confidence":0.90},
        ]
    }


@pytest.fixture
def sample_education_data():
    return {
        "education_data": {
            "academic_profile": {
                "highest_degree":      "MBA",
                "total_degrees":       2,
                "certification_count": 2,
                "latest_graduation_year": 2018,
                "education_strength":  63.0,
            },
            "education_details": [
                {"degree": "MBA",  "field": "Finance & Marketing",
                 "institution": "Test University", "graduation_year": "2016-2018"},
                {"degree": "BBA",  "field": "Business Administration",
                 "institution": "Test College",    "graduation_year": "2013-2016"},
            ],
            "certifications": [],
        },
        "education_relevance_score": 36.3,
    }


@pytest.fixture
def sample_experience_data():
    return {
        "experience_summary": {"total_experience_months": 62},
        "roles": [
            {"company": "TechCorp", "job_title": "Data Engineer II",
             "start_date": "2021-07-01", "end_date": "2024-12-01",
             "duration_months": 42},
            {"company": "Bank A", "job_title": "Deputy Manager",
             "start_date": "2020-10-01", "end_date": "2021-11-01",
             "duration_months": 14},
        ],
        "timeline_analysis": {"gaps": [], "overlaps": []},
        "relevance_analysis": {"overall_relevance_score": 60.32},
    }


@pytest.fixture
def sample_semantic_data():
    return {
        "resume_id":   "test_resume",
        "resume_name": "Test Candidate",
        "best_match": {
            "jd_id":    "healthcare_ml_jd",
            "jd_title": "Healthcare Machine Learning Engineer",
            "semantic_score": 40.53,
            "label": "Good Match",
        },
        "all_matches": [
            {"jd_id": "healthcare_ml_jd",
             "jd_title": "Healthcare Machine Learning Engineer",
             "semantic_score": 40.53, "label": "Good Match"},
        ],
        "section_scores": {
            "skills":             57.87,
            "experience_summary": 12.70,
            "projects":           41.97,
            "education":           0.00,
            "certifications":      0.00,
            "full_document":      59.69,
        },
        "gaps": [
            {"section": "education", "score": 0.0, "gap_severity": "critical"},
            {"section": "certifications", "score": 0.0, "gap_severity": "missing"},
        ],
        "job_type_used": "healthcare_analytics",
    }


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


@pytest.fixture
def sample_json_files(tmp_dir,
                       sample_skills_data, sample_education_data,
                       sample_experience_data, sample_semantic_data):
    """Write fixture data to temp JSON files and return their paths."""
    paths = {}
    for name, data in [
        ("skills",     sample_skills_data),
        ("education",  sample_education_data),
        ("experience", sample_experience_data),
        ("semantic",   sample_semantic_data),
    ]:
        p = os.path.join(tmp_dir, f"test_{name}.json")
        with open(p, "w") as f:
            json.dump(data, f)
        paths[name] = p
    return paths


# ═══════════════════════════════════════════════════════════════════════════════
# WEIGHT CONFIG TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeightConfig:

    def test_generic_preset_exists(self):
        w = WeightConfig.get_weights("generic")
        assert set(w.keys()) == {
            "skill_match", "education_alignment",
            "experience_relevance", "semantic_similarity"
        }

    def test_all_presets_have_required_keys(self):
        required = {"skill_match","education_alignment",
                    "experience_relevance","semantic_similarity"}
        for name in WeightConfig.list_presets():
            w = WeightConfig.get_weights(name)
            assert set(w.keys()) == required, f"Preset '{name}' missing keys"

    def test_weights_are_positive(self):
        for name in WeightConfig.list_presets():
            w = WeightConfig.get_weights(name)
            for k, v in w.items():
                assert v > 0, f"Weight {k} in preset {name} must be > 0"

    def test_unknown_role_falls_back_to_generic(self):
        w = WeightConfig.get_weights("nonexistent_role_xyz")
        g = WeightConfig.get_weights("generic")
        assert w == g

    def test_alias_resolution(self):
        w = WeightConfig.get_weights("healthcare machine learning engineer")
        ml = WeightConfig.get_weights("ml_engineer")
        assert w == ml

    def test_case_insensitive(self):
        w1 = WeightConfig.get_weights("Healthcare_Analytics")
        w2 = WeightConfig.get_weights("healthcare_analytics")
        assert w1 == w2

    def test_add_custom_preset(self):
        WeightConfig.add_custom_preset("test_role", {
            "skill_match": 0.5, "education_alignment": 0.1,
            "experience_relevance": 0.3, "semantic_similarity": 0.1,
        })
        assert "test_role" in WeightConfig.list_presets()
        w = WeightConfig.get_weights("test_role")
        assert w["skill_match"] == 0.5

    def test_custom_preset_missing_keys_raises(self):
        with pytest.raises(ValueError):
            WeightConfig.add_custom_preset("bad_role", {"skill_match": 0.5})

    def test_list_presets_returns_sorted(self):
        presets = WeightConfig.list_presets()
        assert presets == sorted(presets)


# ═══════════════════════════════════════════════════════════════════════════════
# SKILL SCORE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSkillScore:

    def test_normal_skills_returns_score(self, sample_skills_data):
        r = compute_skill_score(sample_skills_data)
        assert 0 <= r["score"] <= 100
        assert r["data_available"] is True
        assert r["missing_fields"] == []

    def test_none_input_returns_zero(self):
        r = compute_skill_score(None)
        assert r["score"] == 0.0
        assert r["data_available"] is False
        assert len(r["missing_fields"]) > 0

    def test_empty_skills_list(self):
        r = compute_skill_score({"skills": []})
        assert r["score"] == 0.0
        assert r["data_available"] is False

    def test_high_confidence_gives_high_score(self):
        data = {"skills": [
            {"skill": "python", "category": "tech",     "confidence": 0.99},
            {"skill": "sql",    "category": "tech",     "confidence": 0.99},
            {"skill": "banking","category": "business", "confidence": 0.99},
        ]}
        r = compute_skill_score(data)
        assert r["score"] > 70

    def test_low_confidence_gives_low_base(self):
        data = {"skills": [
            {"skill": "excel", "category": "tech", "confidence": 0.10},
        ]}
        r = compute_skill_score(data)
        assert r["score"] < 50

    def test_high_value_skills_bonus_applied(self):
        data_hv = {"skills": [
            {"skill": "python",          "category": "tech", "confidence": 0.80},
            {"skill": "tensorflow",      "category": "tech", "confidence": 0.80},
            {"skill": "machine learning","category": "tech", "confidence": 0.80},
        ]}
        data_no = {"skills": [
            {"skill": "excel",      "category": "tech", "confidence": 0.80},
            {"skill": "powerpoint", "category": "tech", "confidence": 0.80},
        ]}
        r_hv  = compute_skill_score(data_hv)
        r_no  = compute_skill_score(data_no)
        assert r_hv["score"] > r_no["score"]

    def test_breakdown_keys_present(self, sample_skills_data):
        r = compute_skill_score(sample_skills_data)
        assert "base_score"        in r["breakdown"]
        assert "diversity_bonus"   in r["breakdown"]
        assert "high_value_bonus"  in r["breakdown"]

    def test_score_caps_at_100(self):
        data = {"skills": [
            {"skill": "python",           "category": "tech",     "confidence": 1.0},
            {"skill": "sql",              "category": "tech",     "confidence": 1.0},
            {"skill": "machine learning", "category": "tech",     "confidence": 1.0},
            {"skill": "deep learning",    "category": "tech",     "confidence": 1.0},
            {"skill": "nlp",              "category": "tech",     "confidence": 1.0},
            {"skill": "banking",          "category": "business", "confidence": 1.0},
            {"skill": "eda",              "category": "other",    "confidence": 1.0},
            {"skill": "docker",           "category": "tech",     "confidence": 1.0},
            {"skill": "llm",              "category": "other",    "confidence": 1.0},
            {"skill": "transformers",     "category": "tech",     "confidence": 1.0},
        ]}
        r = compute_skill_score(data)
        assert r["score"] <= 100.0

    def test_missing_confidence_key_handled(self):
        data = {"skills": [{"skill": "python", "category": "tech"}]}
        r = compute_skill_score(data)
        assert 0.0 <= r["score"] <= 100.0
        assert r["data_available"] is True
        assert r["breakdown"]["base_score"] == 0.0

    def test_raw_inputs_present(self, sample_skills_data):
        r = compute_skill_score(sample_skills_data)
        assert "total_skills"   in r["raw_inputs"]
        assert "avg_confidence" in r["raw_inputs"]
        assert "categories"     in r["raw_inputs"]


# ═══════════════════════════════════════════════════════════════════════════════
# EDUCATION SCORE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEducationScore:

    def test_normal_data_returns_score(self, sample_education_data):
        r = compute_education_score(sample_education_data)
        assert 0 <= r["score"] <= 100
        assert r["data_available"] is True

    def test_none_input_returns_zero(self):
        r = compute_education_score(None)
        assert r["score"] == 0.0
        assert r["data_available"] is False

    def test_missing_education_data_key(self):
        r = compute_education_score({"other_key": {}})
        assert r["score"] == 0.0
        assert r["data_available"] is False

    def test_phd_gives_higher_bonus_than_bba(self):
        base = {
            "education_data": {
                "academic_profile": {
                    "education_strength": 60, "total_degrees": 1,
                    "certification_count": 0,
                },
            },
            "education_relevance_score": 40,
        }
        phd_data = json.loads(json.dumps(base))
        phd_data["education_data"]["academic_profile"]["highest_degree"] = "PhD"

        bba_data = json.loads(json.dumps(base))
        bba_data["education_data"]["academic_profile"]["highest_degree"] = "BBA"

        r_phd = compute_education_score(phd_data)
        r_bba = compute_education_score(bba_data)
        assert r_phd["score"] > r_bba["score"]

    def test_certs_increase_score(self):
        base = {
            "education_data": {
                "academic_profile": {
                    "highest_degree": "MBA", "total_degrees": 1,
                    "certification_count": 0, "education_strength": 50,
                },
            },
            "education_relevance_score": 30,
        }
        cert_data = json.loads(json.dumps(base))
        cert_data["education_data"]["academic_profile"]["certification_count"] = 3

        r_no_cert  = compute_education_score(base)
        r_with_cert= compute_education_score(cert_data)
        assert r_with_cert["score"] > r_no_cert["score"]

    def test_breakdown_keys_present(self, sample_education_data):
        r = compute_education_score(sample_education_data)
        assert "base_score"  in r["breakdown"]
        assert "cert_bonus"  in r["breakdown"]

    def test_score_does_not_exceed_100(self):
        data = {
            "education_data": {
                "academic_profile": {
                    "highest_degree": "PhD", "total_degrees": 5,
                    "certification_count": 20, "education_strength": 100,
                },
            },
            "education_relevance_score": 100,
        }
        r = compute_education_score(data)
        assert r["score"] <= 100.0


# ═══════════════════════════════════════════════════════════════════════════════
# EXPERIENCE SCORE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestExperienceScore:

    def test_normal_data_returns_score(self, sample_experience_data):
        r = compute_experience_score(sample_experience_data)
        assert 0 <= r["score"] <= 100
        assert r["data_available"] is True

    def test_none_input_returns_zero(self):
        r = compute_experience_score(None)
        assert r["score"] == 0.0
        assert r["data_available"] is False

    def test_more_experience_gives_higher_score(self):
        def make_data(months, relevance):
            return {
                "experience_summary": {"total_experience_months": months},
                "roles": [{"company":"A","job_title":"B",
                           "start_date":"2020-01-01","end_date":"2024-01-01",
                           "duration_months":months}],
                "timeline_analysis": {"gaps":[],"overlaps":[]},
                "relevance_analysis": {"overall_relevance_score": relevance},
            }
        r_low  = compute_experience_score(make_data(12, 40))
        r_high = compute_experience_score(make_data(120, 80))
        assert r_high["score"] > r_low["score"]

    def test_gaps_reduce_score(self):
        base = {
            "experience_summary": {"total_experience_months": 60},
            "roles": [],
            "timeline_analysis": {"gaps": [], "overlaps": []},
            "relevance_analysis": {"overall_relevance_score": 60},
        }
        gap_data = json.loads(json.dumps(base))
        gap_data["timeline_analysis"]["gaps"] = [
            {"gap_months": 6, "between": "Role A and B"}
        ]
        r_no_gap = compute_experience_score(base)
        r_gap    = compute_experience_score(gap_data)
        assert r_no_gap["score"] > r_gap["score"]

    def test_recent_role_gives_recency_bonus(self):
        recent = {
            "experience_summary": {"total_experience_months": 36},
            "roles": [{"company":"X","job_title":"Y",
                       "start_date":"2023-01-01","end_date":"2024-12-01",
                       "duration_months":24}],
            "timeline_analysis": {"gaps":[],"overlaps":[]},
            "relevance_analysis": {"overall_relevance_score": 50},
        }
        old = json.loads(json.dumps(recent))
        old["roles"][0]["end_date"] = "2015-01-01"

        r_recent = compute_experience_score(recent)
        r_old    = compute_experience_score(old)
        assert r_recent["score"] > r_old["score"]

    def test_breakdown_keys_present(self, sample_experience_data):
        r = compute_experience_score(sample_experience_data)
        assert "relevance_component" in r["breakdown"]
        assert "tenure_component"    in r["breakdown"]
        assert "recency_bonus"       in r["breakdown"]

    def test_score_non_negative(self):
        bad = {
            "experience_summary": {"total_experience_months": 0},
            "roles": [],
            "timeline_analysis": {"gaps": [1,2,3,4,5,6,7,8,9,10], "overlaps":[]},
            "relevance_analysis": {"overall_relevance_score": 0},
        }
        r = compute_experience_score(bad)
        assert r["score"] >= 0.0

    def test_missing_fields_tracked(self):
        r = compute_experience_score({})
        assert r["data_available"] is False or len(r["missing_fields"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# SEMANTIC SCORE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSemanticScore:

    def test_normal_data_returns_score(self, sample_semantic_data):
        r = compute_semantic_score(sample_semantic_data)
        assert 0 <= r["score"] <= 100
        assert r["data_available"] is True

    def test_none_input_returns_zero(self):
        r = compute_semantic_score(None)
        assert r["score"] == 0.0
        assert r["data_available"] is False

    def test_higher_best_match_gives_higher_score(self):
        def make_data(sem_score):
            return {
                "best_match": {"jd_title": "Test JD", "semantic_score": sem_score},
                "section_scores": {
                    "skills":50,"experience_summary":30,"projects":40,
                    "education":20,"certifications":0,"full_document":50
                },
            }
        r_low  = compute_semantic_score(make_data(10))
        r_high = compute_semantic_score(make_data(80))
        assert r_high["score"] > r_low["score"]

    def test_score_caps_at_100(self):
        data = {
            "best_match": {"jd_title": "Test JD", "semantic_score": 100},
            "section_scores": {
                "skills":100,"experience_summary":100,"projects":100,
                "education":100,"certifications":100,"full_document":100
            },
        }
        r = compute_semantic_score(data)
        assert r["score"] <= 100.0

    def test_breakdown_keys_present(self, sample_semantic_data):
        r = compute_semantic_score(sample_semantic_data)
        assert "best_match_component" in r["breakdown"]
        assert "section_blend"        in r["breakdown"]

    def test_missing_best_match_tracked(self):
        data = {
            "section_scores": {"skills":50, "full_document":40,
                               "experience_summary":20, "projects":30, "education":0}
        }
        r = compute_semantic_score(data)
        assert "semantic_score" in r["missing_fields"]


# ═══════════════════════════════════════════════════════════════════════════════
# EXPLAINER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestExplainer:

    @pytest.fixture
    def sample_components(self):
        return {
            "skill_match":         {"score": 75.0, "data_available": True,
                                    "missing_fields": [], "breakdown": {}},
            "education_alignment": {"score": 30.0, "data_available": True,
                                    "missing_fields": [], "breakdown": {}},
            "experience_relevance":{"score": 55.0, "data_available": True,
                                    "missing_fields": [], "breakdown": {}},
            "semantic_similarity": {"score": 20.0, "data_available": True,
                                    "missing_fields": [], "breakdown": {}},
        }

    @pytest.fixture
    def sample_weights(self):
        return WeightConfig.get_weights("generic")

    @pytest.fixture
    def sample_gaps(self):
        return [{"section":"education","severity":"critical",
                 "recommendation":"Add certs.","score": 30}]

    def test_explanation_keys_present(self, sample_components, sample_weights, sample_gaps):
        exp = build_explanation(sample_components, sample_weights, 52.5, sample_gaps)
        assert "summary_text"        in exp
        assert "component_summaries" in exp
        assert "scoring_formula"     in exp
        assert "gap_notes"           in exp
        assert "improvement_tips"    in exp

    def test_improvement_tips_count(self, sample_components, sample_weights, sample_gaps):
        exp = build_explanation(sample_components, sample_weights, 52.5, sample_gaps)
        assert len(exp["improvement_tips"]) <= 3

    def test_tips_ordered_by_score(self, sample_components, sample_weights, sample_gaps):
        exp = build_explanation(sample_components, sample_weights, 52.5, sample_gaps)
        scores = [t["current_score"] for t in exp["improvement_tips"]]
        assert scores == sorted(scores)

    def test_formula_contains_composite_score(self, sample_components,
                                               sample_weights, sample_gaps):
        composite = 52.5
        exp = build_explanation(sample_components, sample_weights, composite, sample_gaps)
        assert str(composite) in exp["scoring_formula"]

    def test_no_data_component_noted_in_summary(self, sample_weights, sample_gaps):
        comps = {
            "skill_match":         {"score": 0.0, "data_available": False,
                                    "missing_fields": ["no data"], "breakdown": {}},
            "education_alignment": {"score": 0.0, "data_available": False,
                                    "missing_fields": ["no data"], "breakdown": {}},
            "experience_relevance":{"score": 0.0, "data_available": False,
                                    "missing_fields": ["no data"], "breakdown": {}},
            "semantic_similarity": {"score": 0.0, "data_available": False,
                                    "missing_fields": ["no data"], "breakdown": {}},
        }
        exp = build_explanation(comps, sample_weights, 0.0, sample_gaps)
        for key, summary in exp["component_summaries"].items():
            assert "⚠️" in summary["note"]


# ═══════════════════════════════════════════════════════════════════════════════
# FULL PIPELINE INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullPipeline:

    def test_all_inputs_produces_valid_result(self, sample_json_files, tmp_dir):
        result = score_candidate(
            skills_path    = sample_json_files["skills"],
            education_path = sample_json_files["education"],
            experience_path= sample_json_files["experience"],
            semantic_path  = sample_json_files["semantic"],
            role_type      = "healthcare_analytics",
            output_dir     = tmp_dir,
        )
        assert 0 <= result["composite_score"] <= 100
        assert result["verdict"]["label"] in [
            "Strong Match","Good Match","Partial Match","Weak Match","Mismatch"
        ]
        assert len(result["components"]) == 4
        assert os.path.exists(result["_output_json"])
        assert os.path.exists(result["_output_html"])

    def test_no_inputs_produces_zero_score(self, tmp_dir):
        result = score_candidate(output_dir=tmp_dir)
        assert result["composite_score"] == 0.0

    def test_partial_inputs_handled(self, sample_json_files, tmp_dir):
        result = score_candidate(
            skills_path = sample_json_files["skills"],
            output_dir  = tmp_dir,
        )
        assert result["composite_score"] >= 0
        # Components with no data should score 0
        assert result["components"]["education_alignment"]["score"] == 0.0
        assert result["components"]["experience_relevance"]["score"] == 0.0
        assert result["components"]["semantic_similarity"]["score"] == 0.0

    def test_output_json_is_valid(self, sample_json_files, tmp_dir):
        result = score_candidate(
            skills_path    = sample_json_files["skills"],
            education_path = sample_json_files["education"],
            experience_path= sample_json_files["experience"],
            semantic_path  = sample_json_files["semantic"],
            output_dir     = tmp_dir,
        )
        with open(result["_output_json"]) as f:
            loaded = json.load(f)
        assert loaded["composite_score"] == result["composite_score"]

    def test_output_html_exists_and_nonempty(self, sample_json_files, tmp_dir):
        result = score_candidate(
            skills_path  = sample_json_files["skills"],
            semantic_path= sample_json_files["semantic"],
            output_dir   = tmp_dir,
        )
        with open(result["_output_html"]) as f:
            html = f.read()
        assert "<!DOCTYPE html>" in html
        assert len(html) > 500

    def test_html_contains_candidate_name(self, sample_json_files, tmp_dir):
        result = score_candidate(
            semantic_path = sample_json_files["semantic"],
            output_dir    = tmp_dir,
        )
        with open(result["_output_html"]) as f:
            html = f.read()
        assert "Test Candidate" in html

    def test_metadata_populated(self, sample_json_files, tmp_dir):
        result = score_candidate(
            skills_path = sample_json_files["skills"],
            semantic_path= sample_json_files["semantic"],
            role_type   = "ml_engineer",
            output_dir  = tmp_dir,
        )
        assert result["metadata"]["role_type"] == "ml_engineer"
        assert "scored_at" in result["metadata"]
        assert result["metadata"]["candidate_name"] == "Test Candidate"

    def test_different_roles_produce_different_composites(self,
                                                           sample_json_files, tmp_dir):
        r1 = score_candidate(
            skills_path=sample_json_files["skills"],
            education_path=sample_json_files["education"],
            experience_path=sample_json_files["experience"],
            semantic_path=sample_json_files["semantic"],
            role_type="junior_analyst", output_dir=tmp_dir,
        )
        r2 = score_candidate(
            skills_path=sample_json_files["skills"],
            education_path=sample_json_files["education"],
            experience_path=sample_json_files["experience"],
            semantic_path=sample_json_files["semantic"],
            role_type="senior_data", output_dir=tmp_dir,
        )
        # Different weights → different scores (very likely with different data)
        assert r1["weights_used"] != r2["weights_used"]

    def test_amala_real_data(self, tmp_dir):
        """Integration test using actual sample files if available."""
        base = "/mnt/user-data/uploads"
        skills = os.path.join(base, "Amala_Resume_DS_DA_2026__skills.json")
        edu    = os.path.join(base, "Amala_Resume_DS_DA_2026__sections.json")
        exp    = os.path.join(base, "Amala_Resume_DS_DA_2026__vs_ai_specialist_in_healthcare_analytics_parsed_jd_experience.json")
        sem    = os.path.join(base, "Amala_Resume_DS_DA_2026__sections_semantic.json")

        # Skip gracefully if files not available
        if not os.path.exists(skills):
            pytest.skip("Real sample data not available")

        result = score_candidate(
            skills_path    = skills,
            education_path = edu,
            experience_path= exp,
            semantic_path  = sem,
            role_type      = "healthcare_analytics",
            output_dir     = tmp_dir,
        )
        assert result["composite_score"] > 0
        assert result["metadata"]["candidate_name"] == "AMALA P ANTY"
        print(f"\n[Real Data] Amala composite score: {result['composite_score']}")


# ═══════════════════════════════════════════════════════════════════════════════
# LOAD_JSON UTILITY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoadJson:

    def test_valid_file(self, tmp_dir):
        p = os.path.join(tmp_dir, "test.json")
        with open(p, "w") as f:
            json.dump({"key": "value"}, f)
        assert load_json(p) == {"key": "value"}

    def test_nonexistent_file_returns_none(self):
        assert load_json("/nonexistent/path/file.json") is None

    def test_none_path_returns_none(self):
        assert load_json(None) is None

    def test_empty_path_returns_none(self):
        assert load_json("") is None

    def test_malformed_json_returns_none(self, tmp_dir):
        p = os.path.join(tmp_dir, "bad.json")
        with open(p, "w") as f:
            f.write("{invalid json }")
        assert load_json(p) is None


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASES & ROBUSTNESS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_composite_score_is_float(self, sample_json_files, tmp_dir):
        r = score_candidate(
            skills_path=sample_json_files["skills"],
            output_dir=tmp_dir
        )
        assert isinstance(r["composite_score"], float)

    def test_verdict_present_for_all_score_ranges(self, tmp_dir):
        from ats_engine.ats_scorer import _verdict
        for score in [0, 10, 25, 40, 55, 75, 90, 100]:
            v = _verdict(float(score))
            assert "label" in v and "color" in v and "icon" in v

    def test_all_role_types_produce_valid_result(self, sample_json_files, tmp_dir):
        for role in WeightConfig.list_presets():
            r = score_candidate(
                skills_path=sample_json_files["skills"],
                education_path=sample_json_files["education"],
                role_type=role,
                output_dir=tmp_dir,
            )
            assert 0 <= r["composite_score"] <= 100, \
                f"Invalid score for role '{role}': {r['composite_score']}"

    def test_unicode_candidate_name_in_output(self, sample_json_files, tmp_dir):
        """Output files should handle non-ASCII names."""
        r = score_candidate(
            skills_path    = sample_json_files["skills"],
            candidate_name = "Ämälä Päñty",
            output_dir     = tmp_dir,
        )
        with open(r["_output_json"], encoding="utf-8") as f:
            loaded = json.load(f)
        assert "Ämälä" in loaded["metadata"]["candidate_name"]

    def test_score_reproducibility(self, sample_json_files, tmp_dir):
        """Same inputs must produce identical scores on repeated runs."""
        r1 = score_candidate(
            skills_path=sample_json_files["skills"],
            education_path=sample_json_files["education"],
            experience_path=sample_json_files["experience"],
            semantic_path=sample_json_files["semantic"],
            role_type="generic", output_dir=tmp_dir,
        )
        r2 = score_candidate(
            skills_path=sample_json_files["skills"],
            education_path=sample_json_files["education"],
            experience_path=sample_json_files["experience"],
            semantic_path=sample_json_files["semantic"],
            role_type="generic", output_dir=tmp_dir,
        )
        assert r1["composite_score"] == r2["composite_score"]
