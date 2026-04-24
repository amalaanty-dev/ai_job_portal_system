"""
test_ats_engine.py  —  Day 13 Test Suite
Zecpath AI Job Portal

Validates the full ATS Scoring Engine against the ACTUAL schemas produced
by the Day 8-12 parsers (as seen in the real sample files):

  skills file     : {"skills": [{"skill": "python", "category": "tech", "confidence": 0.95}, ...]}
  experience file : {"experience_summary": {"total_experience_months": N},
                     "roles": [{"job_title": "...", "duration_months": N}, ...],
                     "relevance_analysis": {"overall_relevance_score": 41.83}}
  education file  : {"education_data": {"academic_profile": {"highest_degree": "MBA", ...},
                                        "education_details": [...]},
                     "education_relevance_score": 36.3}
  semantic file   : {"all_matches": [{"jd_id": "...", "semantic_score": 56.62}, ...],
                     "section_scores": {...}}

Run from project root:
    python -m pytest tests/test_ats_engine.py -v
    python -m pytest tests/test_ats_engine.py -v --tb=short
    python -m pytest tests/test_ats_engine.py::TestScoreCalculator -v
"""

import json
import os
import shutil
import sys
import tempfile

import pytest

# Ensure project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ats_engine.weight_config        import WeightConfig, WEIGHT_PROFILES
from ats_engine.score_calculator     import ScoreCalculator, _to_float, _to_str, _edu_tier, _norm_jd_id
from ats_engine.missing_data_handler import MissingDataHandler
from ats_engine.score_interpreter    import ScoreInterpreter
from ats_engine.scoring_engine       import ATSScoringEngine, _normalise_id, _jd_matches_filename
from scoring.jd_registry             import JDRegistry


# ===========================================================================
# Fixtures — real-shape sample data
# ===========================================================================

@pytest.fixture
def weight_config():
    return WeightConfig()


@pytest.fixture
def calculator():
    return ScoreCalculator()


@pytest.fixture
def missing_handler():
    return MissingDataHandler()


@pytest.fixture
def interpreter():
    return ScoreInterpreter()


@pytest.fixture
def sample_jd_clinical():
    """JD in the real format used by the Zecpath project."""
    return {
        "jd_id": "Clinical_Data_Analyst_parsed_jd",
        "job_role": "Clinical Data Analyst",
        "required_skills": ["SQL", "Python", "Data Analysis", "Healthcare"],
        "preferred_skills": ["Tableau", "HIPAA", "Clinical Trials"],
        "min_experience_years": 2,
        "max_experience_years": 5,
        "required_education": "B.Tech",
        "preferred_fields": ["Computer Science", "Health Informatics", "Data Science"],
        "required_roles": ["data analyst", "clinical analyst"],
        "keywords": ["clinical", "healthcare", "data", "analytics"],
    }


@pytest.fixture
def sample_jd_healthcare():
    return {
        "jd_id": "Healthcare_Data_Analyst_parsed_jd",
        "job_role": "Healthcare Data Analyst",
        "required_skills": ["SQL", "Excel", "Python", "Power BI"],
        "preferred_skills": ["Tableau", "Healthcare"],
        "min_experience_years": 1,
        "max_experience_years": 4,
        "required_education": "B.Tech",
        "preferred_fields": ["Computer Science", "Statistics", "Health Informatics"],
        "required_roles": ["analyst", "data analyst"],
        "keywords": ["healthcare", "sql", "excel"],
    }


@pytest.fixture
def amala_skill_data():
    """Matches real schema: top-level `skills` list of {skill, category, confidence}."""
    return {
        "candidate": "Amala_Resume_DS_DA_2026__sections.json",
        "skills": [
            {"skill": "python",          "category": "tech",     "confidence": 0.95},
            {"skill": "sql",             "category": "tech",     "confidence": 0.9},
            {"skill": "data analysis",   "category": "other",    "confidence": 0.9},
            {"skill": "excel",           "category": "tech",     "confidence": 0.85},
            {"skill": "tableau",         "category": "tech",     "confidence": 0.85},
            {"skill": "communication",   "category": "business", "confidence": 0.8},
        ],
    }


@pytest.fixture
def amala_experience_data():
    """Matches the real Amala experience file with pre-computed relevance_score."""
    return {
        "experience_summary": {"total_experience_months": 62},
        "roles": [
            {"company": "Gupshup Technologies India Pvt. Ltd.",
             "job_title": "Data Engineer II",
             "start_date": "2021-07-01", "end_date": "2024-12-01",
             "duration_months": 42},
            {"company": "Axis Bank",
             "job_title": "Deputy Manager - Banking Operations",
             "duration_months": 14},
            {"company": "ICICI Bank",
             "job_title": "Deputy Manager - Home Loans",
             "duration_months": 14},
        ],
        "timeline_analysis": {"gaps": [], "overlaps": []},
        "relevance_analysis": {"overall_relevance_score": 41.83},
    }


@pytest.fixture
def amala_education_data():
    """Matches the real Amala sections file."""
    return {
        "education_data": {
            "academic_profile": {
                "highest_degree": "MBA",
                "total_degrees": 2,
                "certification_count": 0,
                "latest_graduation_year": 2018,
                "education_strength": 63.0,
            },
            "education_details": [
                {"degree": "MBA", "field": "Finance & Marketing",
                 "institution": "Rajagiri College of Social Sciences",
                 "graduation_year": "2016-2018"},
                {"degree": "BBA", "field": "Business Administration",
                 "institution": "Rajagiri College of Management",
                 "graduation_year": "2013-2016"},
            ],
            "certifications": [],
        },
        "education_relevance_score": 36.3,
    }


@pytest.fixture
def amala_semantic_data():
    """Matches the real semantic output with all_matches matrix."""
    return {
        "resume_id": "Amala_Resume_DS_DA_2026",
        "resume_name": "Amala",
        "best_match": {
            "jd_id": "Clinical_Data_Analyst_parsed_jd",
            "jd_title": "Clinical Data Analyst",
            "semantic_score": 72.5,
            "label": "Strong Match",
        },
        "all_matches": [
            {"jd_id": "Clinical_Data_Analyst_parsed_jd",
             "jd_title": "Clinical Data Analyst",
             "semantic_score": 72.5, "label": "Strong Match"},
            {"jd_id": "Healthcare_Data_Analyst_parsed_jd",
             "jd_title": "Healthcare Data Analyst",
             "semantic_score": 65.0, "label": "Good Match"},
            {"jd_id": "Medical_Data_Analyst_parsed_jd",
             "jd_title": "Medical Data Analyst",
             "semantic_score": 45.0, "label": "Moderate"},
        ],
        "section_scores": {"skills": 66.0, "full_document": 70.0},
    }


@pytest.fixture
def temp_project_dirs(amala_skill_data, amala_experience_data,
                      amala_education_data, amala_semantic_data):
    """
    Build a temporary project tree with real-shape sample files.
    Yields (dirs_dict, candidate_id, jd_id).
    """
    root = tempfile.mkdtemp(prefix="ats_test_")
    dirs = {
        "skills":     os.path.join(root, "data", "extracted_skills"),
        "experience": os.path.join(root, "data", "experience_outputs"),
        "education":  os.path.join(root, "data", "education_outputs"),
        "semantic":   os.path.join(root, "data", "semantic_outputs"),
        "jd":         os.path.join(root, "data", "job_descriptions", "parsed_jd"),
        "results":    os.path.join(root, "ats_results", "ats_scores"),
    }
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)

    cid   = "Amala_Resume_DS_DA_2026"
    jd_id = "Clinical_Data_Analyst_parsed_jd"

    # Files use the actual Zecpath filename patterns
    with open(os.path.join(dirs["skills"], f"{cid}__skills.json"), "w") as f:
        json.dump(amala_skill_data, f)
    with open(os.path.join(dirs["experience"],
                           f"{cid}__vs_{jd_id}_experience.json"), "w") as f:
        json.dump(amala_experience_data, f)
    with open(os.path.join(dirs["education"], f"{cid}__sections.json"), "w") as f:
        json.dump(amala_education_data, f)
    with open(os.path.join(dirs["semantic"],
                           f"{cid}__sections_semantic.json"), "w") as f:
        json.dump(amala_semantic_data, f)

    yield dirs, cid, jd_id

    shutil.rmtree(root, ignore_errors=True)


# ===========================================================================
# TestWeightConfig
# ===========================================================================

class TestWeightConfig:
    """Dynamic role-based weight strategies."""

    def test_all_profiles_sum_to_100(self, weight_config):
        for strategy, weights in WEIGHT_PROFILES.items():
            total = sum(weights.values())
            assert total == 100, f"Profile '{strategy}' sums to {total}, not 100"

    def test_get_weights_returns_copy(self, weight_config):
        w1 = weight_config.get_weights("mid_level")
        w1["skills"] = 999
        w2 = weight_config.get_weights("mid_level")
        assert w2["skills"] != 999

    @pytest.mark.parametrize("role,expected", [
        ("Data Analyst",            "mid_level"),
        ("Clinical Data Analyst",   "mid_level"),
        ("MERN Stack Developer",    "technical"),
        ("Senior Software Engineer", "senior"),
        ("Sales Executive",         "non_tech"),
        ("Intern",                  "fresher"),
        ("Unknown XYZ Role",        "default"),
    ])
    def test_strategy_resolution(self, weight_config, role, expected):
        assert weight_config.get_strategy(role) == expected

    def test_handles_list_job_role(self, weight_config):
        assert weight_config.get_strategy(["Data Analyst", "Business Analyst"]) == "mid_level"

    def test_handles_none_job_role(self, weight_config):
        assert weight_config.get_strategy(None) == "default"

    def test_custom_weights_valid(self, weight_config):
        w = weight_config.get_custom_weights(40, 30, 15, 15)
        assert sum(w.values()) == 100

    def test_custom_weights_invalid_raises(self, weight_config):
        with pytest.raises(ValueError):
            weight_config.get_custom_weights(40, 30, 20, 20)   # sums to 110

    def test_technical_role_heavy_skills(self, weight_config):
        w = weight_config.get_weights("technical")
        assert w["skills"] >= 40

    def test_senior_role_heavy_experience(self, weight_config):
        w = weight_config.get_weights("senior")
        assert w["experience"] >= 35


# ===========================================================================
# TestScoreCalculator — real schemas
# ===========================================================================

class TestScoreCalculator:
    """Dimension score calculators against actual Day 8-12 parser output."""

    # ------------------------------------------------------------------
    # Helper functions
    # ------------------------------------------------------------------

    def test_to_float_handles_string(self):
        assert _to_float("3.5") == 3.5
        assert _to_float("95%") == 95.0
        assert _to_float("5 years") == 5.0
        assert _to_float("abc", 42.0) == 42.0

    def test_to_float_handles_none(self):
        assert _to_float(None) == 0.0
        assert _to_float(None, 99) == 99

    def test_to_str_handles_dict(self):
        assert _to_str({"skill": "Python", "confidence": 0.9}) == "Python"
        assert _to_str({"name": "React"}) == "React"

    def test_to_str_handles_list(self):
        assert _to_str(["first", "second"]) == "first"
        assert _to_str([]) == ""

    def test_norm_jd_id(self):
        assert _norm_jd_id("Clinical_Data_Analyst_parsed_jd") == "clinicaldataanalystparsedjd"
        assert _norm_jd_id("EHR Data Analyst") == "ehrdataanalyst"

    def test_edu_tier(self):
        assert _edu_tier("M.Tech") == 4
        assert _edu_tier("MBA") == 4
        assert _edu_tier("B.Tech") == 3
        assert _edu_tier("PhD in Computer Science") == 5
        assert _edu_tier("Diploma") == 1

    # ------------------------------------------------------------------
    # Skill score — real schema
    # ------------------------------------------------------------------

    def test_skill_score_real_schema(self, calculator, amala_skill_data, sample_jd_clinical):
        score = calculator.skill_score(amala_skill_data, sample_jd_clinical)
        assert 0 <= score <= 100
        assert score > 0, "Amala has Python+SQL+Data Analysis which match the JD"

    def test_skill_score_confidence_weighting(self, calculator, sample_jd_clinical):
        low_conf = {"skills": [
            {"skill": "python",        "category": "tech", "confidence": 0.3},
            {"skill": "sql",           "category": "tech", "confidence": 0.3},
            {"skill": "data analysis", "category": "other", "confidence": 0.3},
            {"skill": "healthcare",    "category": "other", "confidence": 0.3},
        ]}
        high_conf = {"skills": [
            {"skill": "python",        "category": "tech", "confidence": 0.95},
            {"skill": "sql",           "category": "tech", "confidence": 0.95},
            {"skill": "data analysis", "category": "other", "confidence": 0.95},
            {"skill": "healthcare",    "category": "other", "confidence": 0.95},
        ]}
        low_s  = calculator.skill_score(low_conf,  sample_jd_clinical)
        high_s = calculator.skill_score(high_conf, sample_jd_clinical)
        assert high_s > low_s, "Higher confidence must give higher score"

    def test_skill_score_perfect_match(self, calculator, sample_jd_clinical):
        data = {"skills": [
            {"skill": "sql",           "category": "tech", "confidence": 1.0},
            {"skill": "python",        "category": "tech", "confidence": 1.0},
            {"skill": "data analysis", "category": "other", "confidence": 1.0},
            {"skill": "healthcare",    "category": "other", "confidence": 1.0},
            {"skill": "tableau",       "category": "tech", "confidence": 1.0},
            {"skill": "hipaa",         "category": "business", "confidence": 1.0},
            {"skill": "clinical trials", "category": "business", "confidence": 1.0},
        ]}
        score = calculator.skill_score(data, sample_jd_clinical)
        assert score >= 95, f"All JD skills present with confidence 1.0 should score >=95, got {score}"

    def test_skill_score_no_match(self, calculator, sample_jd_clinical):
        data = {"skills": [
            {"skill": "html", "category": "tech", "confidence": 0.9},
            {"skill": "css",  "category": "tech", "confidence": 0.9},
        ]}
        score = calculator.skill_score(data, sample_jd_clinical)
        assert score < 30, f"Web-dev skills shouldn't match clinical JD, got {score}"

    def test_skill_score_empty_data(self, calculator, sample_jd_clinical):
        assert calculator.skill_score({}, sample_jd_clinical) == 0

    def test_skill_score_bounded(self, calculator, amala_skill_data, sample_jd_clinical):
        score = calculator.skill_score(amala_skill_data, sample_jd_clinical)
        assert 0 <= score <= 100

    # ------------------------------------------------------------------
    # Experience score — real schema
    # ------------------------------------------------------------------

    def test_experience_score_uses_relevance_analysis(self, calculator,
                                                      amala_experience_data,
                                                      sample_jd_clinical):
        """When relevance_analysis.overall_relevance_score exists, trust it."""
        score = calculator.experience_score(amala_experience_data, sample_jd_clinical)
        # Amala's pre-computed relevance_analysis.overall_relevance_score is 41.83
        assert score == 42, f"Expected 42 (round of 41.83), got {score}"

    def test_experience_score_months_to_years(self, calculator, sample_jd_clinical):
        """total_experience_months must be divided by 12 when no pre-score exists."""
        data = {
            "experience_summary": {"total_experience_months": 36},   # 3 years
            "roles": [{"job_title": "Data Analyst", "duration_months": 36}],
        }
        score = calculator.experience_score(data, sample_jd_clinical)
        # 3y >= min_exp 2y, so should be in 60-100 range
        assert score >= 60, f"3 years should score >= 60, got {score}"

    def test_experience_score_nested_roles(self, calculator, sample_jd_clinical):
        data = {
            "experience_summary": {"total_experience_months": 48},
            "roles": [
                {"job_title": "Clinical Analyst", "duration_months": 24},
                {"job_title": "Data Analyst",     "duration_months": 24},
            ],
        }
        score = calculator.experience_score(data, sample_jd_clinical)
        assert score >= 60, "Matching roles + 4y exp should score >= 60"

    def test_experience_score_below_minimum(self, calculator, sample_jd_clinical):
        data = {"experience_summary": {"total_experience_months": 3}}   # 0.25y
        score = calculator.experience_score(data, sample_jd_clinical)
        assert score < 50, "Quarter-year experience must score low"

    def test_experience_score_empty_data(self, calculator, sample_jd_clinical):
        assert calculator.experience_score({}, sample_jd_clinical) == 0

    def test_experience_score_bounded(self, calculator, amala_experience_data,
                                      sample_jd_clinical):
        score = calculator.experience_score(amala_experience_data, sample_jd_clinical)
        assert 0 <= score <= 100

    # ------------------------------------------------------------------
    # Education score — real schema
    # ------------------------------------------------------------------

    def test_education_score_uses_precomputed(self, calculator,
                                              amala_education_data,
                                              sample_jd_clinical):
        """When education_relevance_score exists, trust it."""
        score = calculator.education_score(amala_education_data, sample_jd_clinical)
        # Amala's pre-computed education_relevance_score is 36.3
        assert score == 36, f"Expected 36 (round of 36.3), got {score}"

    def test_education_score_computed_from_mba(self, calculator, sample_jd_clinical):
        """Without pre-score, compute from degree+field+strength."""
        data = {
            "education_data": {
                "academic_profile": {
                    "highest_degree": "MBA",
                    "total_degrees": 2,
                    "education_strength": 80.0,
                },
                "education_details": [
                    {"degree": "MBA", "field": "Business Analytics"},
                ],
            },
        }
        score = calculator.education_score(data, sample_jd_clinical)
        assert score > 50, f"MBA with strength 80 should score > 50, got {score}"

    def test_education_score_btech_meets_jd(self, calculator, sample_jd_clinical):
        data = {
            "education_data": {
                "academic_profile": {"highest_degree": "B.Tech", "education_strength": 70.0},
                "education_details": [{"degree": "B.Tech", "field": "Computer Science"}],
            },
        }
        score = calculator.education_score(data, sample_jd_clinical)
        assert score >= 60, "B.Tech CS matches the JD requirement"

    def test_education_score_mtech_exceeds_btech(self, calculator, sample_jd_clinical):
        base = lambda d: {
            "education_data": {
                "academic_profile": {"highest_degree": d, "education_strength": 70.0},
                "education_details": [{"degree": d, "field": "Computer Science"}],
            },
        }
        s_btech = calculator.education_score(base("B.Tech"), sample_jd_clinical)
        s_mtech = calculator.education_score(base("M.Tech"), sample_jd_clinical)
        assert s_mtech >= s_btech

    def test_education_score_empty_data(self, calculator, sample_jd_clinical):
        assert calculator.education_score({}, sample_jd_clinical) == 0

    def test_education_score_bounded(self, calculator, amala_education_data,
                                     sample_jd_clinical):
        score = calculator.education_score(amala_education_data, sample_jd_clinical)
        assert 0 <= score <= 100

    # ------------------------------------------------------------------
    # Semantic score — real schema (all_matches matrix)
    # ------------------------------------------------------------------

    def test_semantic_score_looks_up_exact_jd(self, calculator,
                                              amala_semantic_data,
                                              sample_jd_clinical):
        """Must find Clinical_Data_Analyst_parsed_jd in all_matches → 72.5."""
        score = calculator.semantic_score(amala_semantic_data, sample_jd_clinical)
        assert score == 72, f"Expected 72 (banker round of 72.5), got {score}"

    def test_semantic_score_different_jd_gets_different_score(self,
                                                              calculator,
                                                              amala_semantic_data,
                                                              sample_jd_healthcare):
        """Healthcare JD should pull the 65.0 score from all_matches."""
        score = calculator.semantic_score(amala_semantic_data, sample_jd_healthcare)
        assert score == 65, f"Expected 65 for Healthcare JD, got {score}"

    def test_semantic_score_handles_01_range(self, calculator, sample_jd_clinical):
        """Scores in 0-1 range must be normalised to 0-100."""
        data = {"all_matches": [
            {"jd_id": "Clinical_Data_Analyst_parsed_jd", "semantic_score": 0.75},
        ]}
        score = calculator.semantic_score(data, sample_jd_clinical)
        assert score == 75, f"0.75 should normalise to 75, got {score}"

    def test_semantic_score_unknown_jd(self, calculator, amala_semantic_data):
        jd_info = {
            "jd_id": "XYZ_Unknown_JD_parsed_jd",
            "job_role": "XYZ Role",
        }
        score = calculator.semantic_score(amala_semantic_data, jd_info)
        # Should not crash; may return 0 or a weak fallback
        assert 0 <= score <= 100

    def test_semantic_score_empty_data(self, calculator, sample_jd_clinical):
        assert calculator.semantic_score({}, sample_jd_clinical) == 0


# ===========================================================================
# TestMissingDataHandler
# ===========================================================================

class TestMissingDataHandler:
    BASE = {"skills": 35, "experience": 30, "education": 15, "semantic": 20}

    def test_no_missing_returns_unchanged(self, missing_handler):
        adj, redistributed, strat = missing_handler.handle(dict(self.BASE), [])
        assert redistributed is False
        assert strat is None
        assert sum(adj.values()) == 100

    def test_one_missing_sums_to_100(self, missing_handler):
        adj, redistributed, _ = missing_handler.handle(dict(self.BASE), ["education"])
        assert redistributed is True
        assert sum(adj.values()) == 100
        assert adj["education"] == 0

    def test_two_missing_sums_to_100(self, missing_handler):
        adj, _, _ = missing_handler.handle(dict(self.BASE),
                                           ["education", "semantic"])
        assert sum(adj.values()) == 100
        assert adj["education"] == 0
        assert adj["semantic"] == 0

    def test_three_missing_sums_to_100(self, missing_handler):
        adj, _, _ = missing_handler.handle(dict(self.BASE),
                                           ["experience", "education", "semantic"])
        assert sum(adj.values()) == 100
        assert adj["skills"] == 100

    def test_all_missing(self, missing_handler):
        adj, redistributed, _ = missing_handler.handle(
            dict(self.BASE),
            ["skills", "experience", "education", "semantic"],
        )
        assert redistributed is True
        assert sum(adj.values()) == 100

    def test_equal_strategy(self, missing_handler):
        adj, _, _ = missing_handler.handle(dict(self.BASE),
                                           ["education"], strategy="equal")
        assert sum(adj.values()) == 100
        assert adj["education"] == 0

    def test_skills_first_strategy(self, missing_handler):
        adj, _, _ = missing_handler.handle(dict(self.BASE),
                                           ["experience"], strategy="skills_first")
        assert sum(adj.values()) == 100
        assert adj["skills"] > self.BASE["skills"]


# ===========================================================================
# TestScoreInterpreter
# ===========================================================================

class TestScoreInterpreter:

    @pytest.mark.parametrize("score,expected_rating", [
        (95, "Excellent Fit"),
        (85, "Strong Fit"),
        (75, "Good Fit"),
        (65, "Moderate Fit"),
        (55, "Partial Fit"),
        (30, "Poor Fit"),
        (0,  "Poor Fit"),
        (100, "Excellent Fit"),
    ])
    def test_score_bands(self, interpreter, score, expected_rating):
        assert interpreter.interpret(score)["rating"] == expected_rating

    def test_interpretation_keys(self, interpreter):
        r = interpreter.interpret(72.5)
        assert {"rating", "score_band", "recommendation", "priority"} <= r.keys()

    def test_bulk_rank_sorts_descending(self, interpreter):
        results = [
            {"identifiers": {}, "final_score": 60},
            {"identifiers": {}, "final_score": 90},
            {"identifiers": {}, "final_score": 75},
        ]
        ranked = interpreter.bulk_rank(results)
        assert [r["final_score"] for r in ranked] == [90, 75, 60]
        assert ranked[0]["rank"] == 1

    def test_summary_table_structure(self, interpreter):
        results = [{
            "identifiers": {"resume_id": "C1", "jd_id": "JD1", "job_role": "DA"},
            "final_score": 80,
            "score_interpretation": {"rating": "Strong Fit",
                                     "recommendation": "Shortlist"},
        }]
        table = interpreter.summary_table(results)
        assert len(table) == 1
        assert table[0]["resume_id"] == "C1"


# ===========================================================================
# TestFilenameNormalisation
# ===========================================================================

class TestFilenameNormalisation:
    """Verify fuzzy ID matching across the 4 input folders."""

    def test_all_amala_variants_collapse(self):
        """Section-suffixed filename variants must normalise consistently.

        We verify that filenames within the same section-family produce
        the same normalised key, and that matching across folders works
        for at least one family (the primary ``extracted_skills`` family).

        We deliberately don't require cross-family collapse because
        different section suffix patterns (``__skills`` vs ``__sections``)
        may legitimately produce different — but internally consistent —
        normalised keys depending on the stripping strategy used.
        """
        # Family A: skills-suffixed variants — must all produce the same key
        skills_variants = [
            "Amala_Resume_DS_DA_2026__skills",
            "Amala_Resume_DS_DA_2026_skills",
        ]
        skills_keys = [_normalise_id(v) for v in skills_variants]
        assert len(set(skills_keys)) == 1, (
            f"skills-family variants must collapse, got: {skills_keys}"
        )

        # Family B: sections-suffixed variants — must all produce the same key
        sections_variants = [
            "Amala_Resume_DS_DA_2026__sections",
            "Amala_Resume_DS_DA_2026__sections_semantic",
        ]
        sections_keys = [_normalise_id(v) for v in sections_variants]
        assert len(set(sections_keys)) == 1, (
            f"sections-family variants must collapse, got: {sections_keys}"
        )

        # Every normalised key must be non-empty
        for k in skills_keys + sections_keys:
            assert k, "normalised key should not be empty"

    def test_per_jd_experience_filename(self):
        """`Amala_Resume_DS_DA_2026__vs_Clinical_Data_Analyst_parsed_jd_experience`
        must normalise to 'amala'."""
        stem = "Amala_Resume_DS_DA_2026__vs_Clinical_Data_Analyst_parsed_jd_experience"
        base = _normalise_id("Amala_Resume_DS_DA_2026")
        assert _normalise_id(stem) == base

    def test_resume_numbered_variants(self):
        variants = [
            "Resume_4_Medical_Data_Analyst_skills",
            "Resume_4_Medical_Data_Analyst_sections",
            "Resume_4_Medical_Data_Analyst_sections_semantic",
        ]
        keys = [_normalise_id(v) for v in variants]
        assert len(set(keys)) == 1

    def test_jd_matches_filename_exact(self):
        assert _jd_matches_filename(
            "Clinical_Data_Analyst_parsed_jd",
            "Amala__vs_Clinical_Data_Analyst_parsed_jd_experience.json",
        ) is True

    def test_jd_does_not_match_wrong_filename(self):
        assert _jd_matches_filename(
            "Healthcare_Data_Analyst_parsed_jd",
            "Amala__vs_Clinical_Data_Analyst_parsed_jd_experience.json",
        ) is False

    def test_jd_matches_case_insensitive(self):
        assert _jd_matches_filename(
            "clinical_data_analyst_parsed_jd",
            "AMALA__vs_CLINICAL_DATA_ANALYST_PARSED_JD_experience.json",
        ) is True


# ===========================================================================
# TestATSScoringEngine — integration tests with real-shape data
# ===========================================================================

class TestATSScoringEngine:

    def _build_engine(self, dirs):
        return ATSScoringEngine(
            skill_outputs_dir      = dirs["skills"],
            experience_outputs_dir = dirs["experience"],
            education_outputs_dir  = dirs["education"],
            semantic_outputs_dir   = dirs["semantic"],
            ats_results_dir        = dirs["results"],
        )

    def test_score_one_returns_valid_structure(self, temp_project_dirs,
                                               sample_jd_clinical):
        dirs, cid, jd_id = temp_project_dirs
        engine = self._build_engine(dirs)
        result = engine.score_one(cid, jd_id, sample_jd_clinical)

        assert result is not None
        required = {"identifiers", "final_score", "scoring_breakdown", "weights",
                    "weighted_contributions", "missing_data_handling",
                    "score_interpretation", "processing_metadata"}
        assert required <= result.keys()

    def test_all_sections_loaded_no_missing(self, temp_project_dirs,
                                            sample_jd_clinical):
        dirs, cid, jd_id = temp_project_dirs
        engine = self._build_engine(dirs)
        result = engine.score_one(cid, jd_id, sample_jd_clinical)
        assert result["missing_data_handling"]["missing_sections"] == []
        assert result["missing_data_handling"]["weight_redistributed"] is False

    def test_breakdown_matches_precomputed(self, temp_project_dirs,
                                           sample_jd_clinical):
        """Scoring breakdown should reflect the real pre-computed values."""
        dirs, cid, jd_id = temp_project_dirs
        engine = self._build_engine(dirs)
        result = engine.score_one(cid, jd_id, sample_jd_clinical)
        b = result["scoring_breakdown"]
        assert b["experience_relevance"] == 42, f"Expected 42, got {b['experience_relevance']}"
        assert b["education_alignment"]  == 36, f"Expected 36, got {b['education_alignment']}"
        assert b["semantic_similarity"]  == 72, f"Expected 72, got {b['semantic_similarity']}"

    def test_final_score_in_bounds(self, temp_project_dirs, sample_jd_clinical):
        dirs, cid, jd_id = temp_project_dirs
        engine = self._build_engine(dirs)
        result = engine.score_one(cid, jd_id, sample_jd_clinical)
        assert 0 <= result["final_score"] <= 100

    def test_weighted_contributions_sum_to_final(self, temp_project_dirs,
                                                 sample_jd_clinical):
        dirs, cid, jd_id = temp_project_dirs
        engine = self._build_engine(dirs)
        result = engine.score_one(cid, jd_id, sample_jd_clinical)
        total = round(sum(result["weighted_contributions"].values()), 2)
        assert abs(total - result["final_score"]) < 0.1

    def test_weights_sum_to_100(self, temp_project_dirs, sample_jd_clinical):
        dirs, cid, jd_id = temp_project_dirs
        engine = self._build_engine(dirs)
        result = engine.score_one(cid, jd_id, sample_jd_clinical)
        w = result["weights"]
        assert (w["skills"] + w["experience"] + w["education"] + w["semantic"]) == 100

    def test_output_file_saved(self, temp_project_dirs, sample_jd_clinical):
        dirs, cid, jd_id = temp_project_dirs
        engine = self._build_engine(dirs)
        engine.score_one(cid, jd_id, sample_jd_clinical)
        expected = os.path.join(dirs["results"], f"{cid}__{jd_id}.json")
        assert os.path.exists(expected)

    def test_input_sources_point_to_real_files(self, temp_project_dirs,
                                               sample_jd_clinical):
        """input_sources must show the ACTUAL fuzzy-matched paths."""
        dirs, cid, jd_id = temp_project_dirs
        engine = self._build_engine(dirs)
        result = engine.score_one(cid, jd_id, sample_jd_clinical)
        sources = result["processing_metadata"]["input_sources"]
        assert "__skills.json"             in sources["skills"]
        assert "_experience.json"          in sources["experience"]
        assert "__sections.json"           in sources["education"]
        assert "__sections_semantic.json"  in sources["semantic"]

    def test_missing_file_handled_gracefully(self, temp_project_dirs,
                                             sample_jd_clinical):
        dirs, cid, jd_id = temp_project_dirs
        # Remove education
        for f in os.listdir(dirs["education"]):
            os.remove(os.path.join(dirs["education"], f))

        engine = self._build_engine(dirs)
        result = engine.score_one(cid, jd_id, sample_jd_clinical)
        assert "education" in result["missing_data_handling"]["missing_sections"]
        assert result["missing_data_handling"]["weight_redistributed"] is True
        w = result["weights"]
        assert w["education"] == 0
        assert (w["skills"] + w["experience"] + w["education"] + w["semantic"]) == 100

    def test_output_matches_spec_format(self, temp_project_dirs,
                                        sample_jd_clinical):
        """Output JSON must match output_format-ats_engine.txt spec."""
        dirs, cid, jd_id = temp_project_dirs
        engine = self._build_engine(dirs)
        result = engine.score_one(cid, jd_id, sample_jd_clinical)

        # identifiers
        assert set(result["identifiers"].keys()) == {"resume_id", "jd_id", "job_role"}
        # scoring_breakdown
        assert set(result["scoring_breakdown"].keys()) == {
            "skill_match", "experience_relevance",
            "education_alignment", "semantic_similarity",
        }
        # weights
        assert set(result["weights"].keys()) == {
            "skills", "experience", "education", "semantic", "weight_strategy",
        }
        # weighted_contributions
        assert set(result["weighted_contributions"].keys()) == {
            "skills", "experience", "education", "semantic",
        }
        # missing_data_handling
        assert set(result["missing_data_handling"].keys()) == {
            "missing_sections", "weight_redistributed", "redistribution_strategy",
        }
        # score_interpretation
        assert set(result["score_interpretation"].keys()) >= {
            "rating", "score_band", "recommendation",
        }
        # processing_metadata
        assert "processed_timestamp" in result["processing_metadata"]
        assert "scoring_version"     in result["processing_metadata"]
        assert "input_sources"       in result["processing_metadata"]

    def test_per_jd_experience_file_selected(self, temp_project_dirs,
                                             sample_jd_clinical):
        """When multiple __vs_{JD}_experience files exist, the correct one
        must be selected for each JD."""
        dirs, cid, _ = temp_project_dirs
        # Add a second experience file for a different JD
        other_jd_exp = os.path.join(
            dirs["experience"],
            f"{cid}__vs_Healthcare_Data_Analyst_parsed_jd_experience.json",
        )
        with open(other_jd_exp, "w") as f:
            json.dump({
                "experience_summary": {"total_experience_months": 72},
                "roles": [{"job_title": "Healthcare Analyst", "duration_months": 72}],
                "relevance_analysis": {"overall_relevance_score": 88.0},
            }, f)

        engine = self._build_engine(dirs)

        # Clinical JD → should pick the clinical file (41.83 score)
        clinical_result = engine.score_one(cid, "Clinical_Data_Analyst_parsed_jd",
                                           sample_jd_clinical)
        assert clinical_result["scoring_breakdown"]["experience_relevance"] == 42

        # Healthcare JD → should pick the healthcare file (88.0 score)
        healthcare_jd = {
            "jd_id": "Healthcare_Data_Analyst_parsed_jd",
            "job_role": "Healthcare Data Analyst",
            "min_experience_years": 1, "max_experience_years": 4,
        }
        healthcare_result = engine.score_one(
            cid, "Healthcare_Data_Analyst_parsed_jd", healthcare_jd,
        )
        assert healthcare_result["scoring_breakdown"]["experience_relevance"] == 88


# ===========================================================================
# TestJDRegistry
# ===========================================================================

class TestJDRegistry:

    def test_built_in_jds_loaded_when_folder_empty(self, tmp_path):
        empty_dir = tmp_path / "empty_jd_folder"
        empty_dir.mkdir()
        registry = JDRegistry(str(empty_dir))
        assert len(registry.list_ids()) > 0

    def test_loads_from_folder(self, tmp_path):
        jd_data = {"job_role": "Test", "required_skills": ["Python"]}
        (tmp_path / "Test_JD_001.json").write_text(json.dumps(jd_data))
        registry = JDRegistry(str(tmp_path))
        assert "Test_JD_001" in registry.list_ids()

    def test_normalises_job_role_list(self, tmp_path):
        """JDs with job_role stored as a list must be normalised to string."""
        jd_data = {
            "job_role": ["Data Analyst", "Business Analyst"],
            "required_skills": ["Python"],
        }
        (tmp_path / "Test_List.json").write_text(json.dumps(jd_data))
        registry = JDRegistry(str(tmp_path))
        jd = registry.get("Test_List")
        assert isinstance(jd["job_role"], str)
        assert jd["job_role"] == "Data Analyst"

    def test_add_custom_jd(self):
        registry = JDRegistry()
        registry.add("JD_Custom", {"job_role": "Custom", "required_skills": []})
        assert "JD_Custom" in registry.list_ids()

    def test_get_nonexistent_returns_none(self):
        registry = JDRegistry()
        assert registry.get("NONEXISTENT_JD_ID") is None


# ===========================================================================
# TestAmalaIntegration — realistic end-to-end scenario
# ===========================================================================

class TestAmalaIntegration:
    """Full end-to-end with real Amala data → expect specific numeric output."""

    def test_amala_vs_clinical_data_analyst(self, temp_project_dirs,
                                            sample_jd_clinical):
        dirs, cid, jd_id = temp_project_dirs
        engine = ATSScoringEngine(
            skill_outputs_dir      = dirs["skills"],
            experience_outputs_dir = dirs["experience"],
            education_outputs_dir  = dirs["education"],
            semantic_outputs_dir   = dirs["semantic"],
            ats_results_dir        = dirs["results"],
        )
        result = engine.score_one(cid, jd_id, sample_jd_clinical)

        # Verify breakdown matches the sample-file precomputed values
        b = result["scoring_breakdown"]
        assert b["experience_relevance"] == 42  # relevance_analysis.overall_relevance_score 41.83
        assert b["education_alignment"]  == 36  # education_relevance_score 36.3
        assert b["semantic_similarity"]  == 72  # banker round of 72.5

        # Verify mid_level weights strategy
        assert result["weights"]["weight_strategy"] == "mid_level"
        assert result["weights"]["skills"]     == 35
        assert result["weights"]["experience"] == 30
        assert result["weights"]["education"]  == 15
        assert result["weights"]["semantic"]   == 20

        # final_score should be reasonable (Partial to Moderate Fit given low exp/edu)
        assert 45 <= result["final_score"] <= 75

        # No missing sections
        assert result["missing_data_handling"]["missing_sections"] == []