"""
test_semantic_engine.py
────────────────────────
Comprehensive test suite for the Semantic Matching Engine.

Covers:
  1. Embedder tests        — embed(), embed_batch(), embed_resume(), embed_jd()
  2. Similarity tests      — cosine_similarity(), weighted_similarity(), similarity_label(), identify_gaps()
  3. SemanticMatcher tests — match(), match_batch(), best_jd_for_resume(), best_resume_for_jd()
  4. ThresholdTuner tests  — get_thresholds(), apply_thresholds(), tune()
  5. Validator tests       — validate(), print_report()
  6. Integration tests     — full pipeline end-to-end
  7. Edge-case tests       — empty inputs, zero vectors, missing sections

Usage:
    python test_semantic_engine.py              # run all tests
    python test_semantic_engine.py --verbose    # show per-test output
    python test_semantic_engine.py --section embedder   # run one section
"""

import sys
import os
import json
import argparse
import traceback
import numpy as np
from datetime import datetime

# ── Path setup ──────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from semantic_engine import (
    SemanticMatcher,
    ThresholdTuner,
    MatchingValidator,
    embed,
    embed_batch,
    embed_resume,
    embed_jd,
    cache_stats,
    cosine_similarity,
    weighted_similarity,
    similarity_label,
    identify_gaps,
    get_thresholds,
    apply_thresholds,
)

# ── Bring in sample data ─────────────────────────────────────────────────────
try:
    from data.sample_data import SAMPLE_RESUMES, SAMPLE_JDS, GROUND_TRUTH
except ImportError:
    # Fallback: define minimal inline samples so tests still run
    SAMPLE_RESUMES = [
        {
            "id": "resume_da_001", "name": "Priya Nair",
            "skills": ["Python", "SQL", "Tableau", "Pandas", "data visualisation", "ETL"],
            "experience": [{"role_header": "Data Analyst · Infosys · 2021–Present",
                            "duties": ["Built Tableau dashboards", "Automated ETL in Python"]}],
            "projects": ["Customer churn prediction using logistic regression."],
            "education": ["B.Sc. Statistics – Mumbai – 2019"],
            "certifications": ["Google Data Analytics Certificate – 2021"],
        },
        {
            "id": "resume_hda_001", "name": "James Thornton",
            "skills": ["Python", "SQL", "R", "Epic", "ICD-10", "HIPAA", "clinical data"],
            "experience": [{"role_header": "Medical Data Analyst · Emory Healthcare · 2022–Present",
                            "duties": ["Analysed 200k+ medical records", "Built predictive models"]}],
            "projects": [],
            "education": ["B.S. Biological Sciences – Georgia State – 2020"],
            "certifications": ["Healthcare Data Analytics – Johns Hopkins – 2021"],
        },
        {
            "id": "resume_mismatch_001", "name": "Maria Costa",
            "skills": ["customer service", "front desk", "Opera PMS", "hotel management"],
            "experience": [{"role_header": "Hotel Manager · Taj Hotels · 2017–Present",
                            "duties": ["Managed 120-room property", "Guest satisfaction"]}],
            "projects": [],
            "education": ["Bachelor of Hotel Management – IHM Mumbai – 2017"],
            "certifications": ["Certified Hospitality Supervisor – 2019"],
        },
    ]
    SAMPLE_JDS = [
        {
            "id": "jd_da_001", "title": "Data Analyst", "job_type": "data_analytics",
            "role": ["Analyse large datasets", "Build dashboards in Tableau or Power BI"],
            "skills_required": ["Python", "SQL", "Tableau", "Pandas", "data visualisation", "ETL"],
            "experience_required": "2+ years in data analyst role",
            "education_required": "Bachelor's in Statistics or related field",
        },
        {
            "id": "jd_hda_001", "title": "Healthcare Data Analyst", "job_type": "healthcare_analytics",
            "role": ["Analyse clinical data", "Build predictive models for patient outcomes"],
            "skills_required": ["Python", "SQL", "R", "Epic", "HIPAA", "ICD-10", "healthcare analytics"],
            "experience_required": "2+ years in healthcare data",
            "education_required": "Bachelor's in Health Informatics or Biological Sciences",
        },
        {
            "id": "jd_se_001", "title": "Software Engineer", "job_type": "software_engineering",
            "role": ["Design microservices", "Deploy on Kubernetes"],
            "skills_required": ["Java", "Python", "Spring Boot", "Docker", "Kubernetes", "AWS"],
            "experience_required": "3+ years backend development",
            "education_required": "B.Tech Computer Science",
        },
    ]
    GROUND_TRUTH = [
        ("resume_da_001",  "jd_da_001",  "Strong Match",  (0.55, 1.00)),
        ("resume_hda_001", "jd_hda_001", "Strong Match",  (0.55, 1.00)),
        ("resume_da_001",  "jd_hda_001", "Partial Match", (0.30, 0.65)),
        ("resume_mismatch_001", "jd_se_001", "Mismatch",  (0.00, 0.35)),
    ]


# ════════════════════════════════════════════════════════════════════════════
# TEST HARNESS
# ════════════════════════════════════════════════════════════════════════════

_PASS = 0
_FAIL = 0
_SKIP = 0
_LOG  = []
_VERBOSE = False

def _result(name: str, passed: bool, note: str = "", expected=None, actual=None) -> None:
    global _PASS, _FAIL
    icon = "✅" if passed else "❌"
    if passed:
        _PASS += 1
    else:
        _FAIL += 1
    msg = f"  {icon}  {name}"
    if note:
        msg += f"  [{note}]"
    if not passed and expected is not None:
        msg += f"\n       Expected: {expected}"
        msg += f"\n       Actual:   {actual}"
    _LOG.append(msg)
    if _VERBOSE or not passed:
        print(msg)


def _section(title: str) -> None:
    bar = "─" * 70
    line = f"\n{bar}\n  {title}\n{bar}"
    _LOG.append(line)
    print(line)


def _run(name: str, fn) -> None:
    """Run a single test function, catching all exceptions."""
    global _FAIL
    try:
        fn()
    except Exception as e:
        _FAIL += 1
        msg = f"  💥  {name}  →  EXCEPTION: {e}"
        _LOG.append(msg)
        _LOG.append(traceback.format_exc())
        print(msg)
        if _VERBOSE:
            print(traceback.format_exc())


# ════════════════════════════════════════════════════════════════════════════
# SECTION 1 — EMBEDDER TESTS
# ════════════════════════════════════════════════════════════════════════════

def test_embedder():
    _section("SECTION 1 — EMBEDDER")

    # 1.1 embed() returns a numpy array
    def t1():
        v = embed("Python SQL Tableau data analytics")
        _result("embed() returns np.ndarray", isinstance(v, np.ndarray),
                f"dtype={v.dtype}, shape={v.shape}")

    # 1.2 embed() output is L2-normalised (norm ≈ 1.0)
    def t2():
        v    = embed("Python SQL Tableau data analytics")
        norm = np.linalg.norm(v)
        _result("embed() output is unit-normalised", abs(norm - 1.0) < 1e-3,
                f"norm={norm:.4f}", expected="≈1.0", actual=round(norm, 4))

    # 1.3 embed_batch() returns correct shape
    def t3():
        texts = ["Python SQL", "machine learning", "HIPAA compliance"]
        mat   = embed_batch(texts)
        _result("embed_batch() shape matches input length",
                mat.shape[0] == 3,
                f"shape={mat.shape}", expected="(3, D)", actual=mat.shape)

    # 1.4 embed("") returns zero vector (empty text → all zeros)
    def t4():
        v = embed("")
        _result("embed('') returns all-zeros vector",
                np.allclose(v, 0),
                f"norm={np.linalg.norm(v):.4f}")

    # 1.5 Two identical texts produce identical embeddings
    def t5():
        a = embed("deep learning neural network")
        b = embed("deep learning neural network")
        _result("Identical texts → identical embeddings",
                np.allclose(a, b), f"max_diff={np.max(np.abs(a-b)):.6f}")

    # 1.6 Different texts produce different embeddings
    def t6():
        a = embed("Python SQL data analytics")
        b = embed("Java Spring Boot microservices Docker")
        sim = cosine_similarity(a, b)
        _result("Different-domain texts → low similarity (<0.80)",
                sim < 0.80, f"sim={sim:.4f}",
                expected="<0.80", actual=round(sim, 4))

    # 1.7 embed_resume() returns all required keys
    def t7():
        r   = SAMPLE_RESUMES[0]
        emb = embed_resume(r)
        required_keys = {"skills", "experience_summary", "projects", "education", "certifications", "full"}
        missing = required_keys - set(emb.keys())
        _result("embed_resume() returns all section keys",
                len(missing) == 0, f"keys={list(emb.keys())}", expected=required_keys, actual=set(emb.keys()))

    # 1.8 embed_jd() returns all required keys
    def t8():
        jd  = SAMPLE_JDS[0]
        emb = embed_jd(jd)
        required_keys = {"required_skills", "preferred_skills", "responsibilities", "qualifications", "full"}
        missing = required_keys - set(emb.keys())
        _result("embed_jd() returns all section keys",
                len(missing) == 0, f"keys={list(emb.keys())}", expected=required_keys, actual=set(emb.keys()))

    # 1.9 cache_stats() returns expected keys
    def t9():
        stats = cache_stats()
        _result("cache_stats() has 'cached_embeddings' key",
                "cached_embeddings" in stats, str(stats))

    # 1.10 embed_resume() — resume with empty projects/certs → zero vector
    def t10():
        r = {**SAMPLE_RESUMES[2], "projects": [], "certifications": []}
        emb = embed_resume(r)
        _result("embed_resume() handles empty projects/certifications gracefully",
                isinstance(emb["projects"], np.ndarray),
                f"projects_norm={np.linalg.norm(emb['projects']):.4f}")

    for fn in [t1, t2, t3, t4, t5, t6, t7, t8, t9, t10]:
        _run(fn.__name__, fn)


# ════════════════════════════════════════════════════════════════════════════
# SECTION 2 — SIMILARITY TESTS
# ════════════════════════════════════════════════════════════════════════════

def test_similarity():
    _section("SECTION 2 — SIMILARITY")

    # 2.1 cosine_similarity of identical vectors = 1.0
    def t1():
        v = embed("healthcare analytics HIPAA clinical data")
        s = cosine_similarity(v, v)
        _result("cosine_similarity(v, v) == 1.0",
                abs(s - 1.0) < 1e-4, f"score={s:.4f}", expected=1.0, actual=round(s, 4))

    # 2.2 cosine_similarity of zero vectors = 0.0
    def t2():
        z = np.zeros(100, dtype=np.float32)
        s = cosine_similarity(z, z)
        _result("cosine_similarity(zeros, zeros) == 0.0",
                s == 0.0, f"score={s}", expected=0.0, actual=s)

    # 2.3 cosine_similarity is in [0, 1]
    def t3():
        a = embed("Python SQL Tableau business intelligence")
        b = embed("Java Docker Kubernetes microservices AWS")
        s = cosine_similarity(a, b)
        _result("cosine_similarity in [0, 1]",
                0.0 <= s <= 1.0, f"score={s:.4f}", expected="[0,1]", actual=round(s, 4))

    # 2.4 cosine_similarity is symmetric
    def t4():
        a = embed("machine learning scikit-learn Python")
        b = embed("deep learning TensorFlow neural networks")
        _result("cosine_similarity is symmetric",
                abs(cosine_similarity(a, b) - cosine_similarity(b, a)) < 1e-6)

    # 2.5 cosine_similarity(None, None) returns 0.0
    def t5():
        s = cosine_similarity(None, None)
        _result("cosine_similarity(None, None) returns 0.0",
                s == 0.0, f"score={s}", expected=0.0, actual=s)

    # 2.6 weighted_similarity with equal weights
    def t6():
        scores  = {"skills": 0.8, "experience_summary": 0.6, "projects": 0.4, "education": 0.2, "certifications": 0.1}
        weights = {"skills": 0.2, "experience_summary": 0.2, "projects": 0.2, "education": 0.2, "certifications": 0.2}
        ws  = weighted_similarity(scores, weights)
        exp = round((0.8+0.6+0.4+0.2+0.1) / 5, 4)
        _result("weighted_similarity with equal weights = arithmetic mean",
                abs(ws - exp) < 1e-3, f"ws={ws:.4f} exp={exp:.4f}", expected=exp, actual=ws)

    # 2.7 weighted_similarity with zero weights = 0.0
    def t7():
        scores  = {"skills": 0.9}
        weights = {"skills": 0.0}
        ws = weighted_similarity(scores, weights)
        _result("weighted_similarity with all-zero weights = 0.0",
                ws == 0.0, f"ws={ws}", expected=0.0, actual=ws)

    # 2.8 similarity_label — all label boundaries
    def t8():
        pairs = [
            (0.80, "Strong Match"),
            (0.60, "Good Match"),
            (0.45, "Partial Match"),
            (0.30, "Weak Match"),
            (0.10, "Mismatch"),
        ]
        for score, expected_label in pairs:
            label = similarity_label(score)
            _result(f"similarity_label({score}) == '{expected_label}'",
                    label == expected_label, f"got='{label}'", expected=expected_label, actual=label)

    # 2.9 identify_gaps — returns sections below threshold
    def t9():
        section_scores = {
            "skills":             0.60,
            "experience_summary": 0.20,   # gap
            "projects":           0.10,   # gap
            "education":          0.50,
            "certifications":     0.05,   # gap
        }
        gaps = identify_gaps(section_scores, threshold=0.40)
        gap_sections = [g["section"] for g in gaps]
        expected = {"experience_summary", "projects", "certifications"}
        _result("identify_gaps() finds all sub-threshold sections",
                set(gap_sections) == expected, f"gaps={gap_sections}", expected=expected, actual=set(gap_sections))

    # 2.10 identify_gaps — gap_severity classification
    def t10():
        section_scores = {"skills": 0.10, "experience_summary": 0.30, "projects": 0.38}
        gaps = {g["section"]: g["gap_severity"] for g in identify_gaps(section_scores, threshold=0.40)}
        _result("gap_severity 'critical' for score<0.25",
                gaps.get("skills") == "critical",
                f"skills_severity={gaps.get('skills')}", expected="critical", actual=gaps.get("skills"))
        _result("gap_severity 'moderate' for 0.25≤score<0.35",
                gaps.get("experience_summary") == "moderate",
                f"exp_severity={gaps.get('experience_summary')}", expected="moderate", actual=gaps.get("experience_summary"))
        _result("gap_severity 'minor' for 0.35≤score<threshold",
                gaps.get("projects") == "minor",
                f"proj_severity={gaps.get('projects')}", expected="minor", actual=gaps.get("projects"))

    for fn in [t1, t2, t3, t4, t5, t6, t7, t8, t9, t10]:
        _run(fn.__name__, fn)


# ════════════════════════════════════════════════════════════════════════════
# SECTION 3 — SEMANTIC MATCHER TESTS
# ════════════════════════════════════════════════════════════════════════════

def test_semantic_matcher():
    _section("SECTION 3 — SEMANTIC MATCHER")

    matcher = SemanticMatcher()
    r_map   = {r["id"]: r for r in SAMPLE_RESUMES}
    jd_map  = {j["id"]: j for j in SAMPLE_JDS}

    # 3.1 match() returns a MatchResult object
    def t1():
        result = matcher.match(r_map["resume_da_001"], jd_map["jd_da_001"])
        from semantic_engine.semantic_matcher import MatchResult
        _result("match() returns MatchResult", isinstance(result, MatchResult), type(result).__name__)

    # 3.2 overall_score is in [0, 1]
    def t2():
        result = matcher.match(r_map["resume_da_001"], jd_map["jd_da_001"])
        _result("overall_score in [0, 1]",
                0.0 <= result.overall_score <= 1.0,
                f"score={result.overall_score}", expected="[0,1]", actual=result.overall_score)

    # 3.3 Ideal match scores higher than cross-domain
    def t3():
        ideal   = matcher.match(r_map["resume_da_001"], jd_map["jd_da_001"]).overall_score
        cross   = matcher.match(r_map["resume_da_001"], jd_map["jd_hda_001"]).overall_score
        _result("Ideal match score > cross-domain score",
                ideal > cross,
                f"ideal={ideal:.4f}  cross={cross:.4f}", expected=f">{cross:.4f}", actual=round(ideal, 4))

    # 3.4 Mismatch produces score below 0.40
    def t4():
        result = matcher.match(r_map["resume_mismatch_001"], jd_map["jd_se_001"])
        _result("Mismatch resume → SE JD scores < 0.40",
                result.overall_score < 0.40,
                f"score={result.overall_score:.4f}", expected="<0.40", actual=round(result.overall_score, 4))

    # 3.5 to_dict() contains all expected keys
    def t5():
        result = matcher.match(r_map["resume_da_001"], jd_map["jd_da_001"])
        d      = result.to_dict()
        keys   = {"resume_id", "jd_id", "overall_score", "match_label", "section_scores", "gaps"}
        missing = keys - set(d.keys())
        _result("to_dict() contains all expected keys",
                len(missing) == 0, f"missing={missing}", expected=keys, actual=set(d.keys()))

    # 3.6 section_scores dict has all expected sections
    def t6():
        result    = matcher.match(r_map["resume_da_001"], jd_map["jd_da_001"])
        ss_keys   = set(result.to_dict()["section_scores"].keys())
        expected  = {"skills", "experience_summary", "projects", "education", "certifications", "full_document"}
        _result("section_scores contains all 6 sections",
                ss_keys == expected, f"keys={ss_keys}", expected=expected, actual=ss_keys)

    # 3.7 gaps list is a list of dicts with required keys
    def t7():
        result = matcher.match(r_map["resume_da_001"], jd_map["jd_hda_001"])
        gaps   = result.gaps
        ok = all({"section", "score", "gap_severity"} <= set(g.keys()) for g in gaps)
        _result("gaps list has required keys",
                ok or len(gaps) == 0, f"gaps count={len(gaps)}")

    # 3.8 match_batch() returns correct number of results
    def t8():
        resumes = SAMPLE_RESUMES[:2]
        jds     = SAMPLE_JDS[:2]
        results = matcher.match_batch(resumes, jds)
        expected_count = len(resumes) * len(jds)
        _result("match_batch() returns len(resumes) × len(jds) results",
                len(results) == expected_count,
                f"got={len(results)}", expected=expected_count, actual=len(results))

    # 3.9 best_jd_for_resume() returns top result as first element
    def t9():
        best, all_r = matcher.best_jd_for_resume(r_map["resume_da_001"], SAMPLE_JDS)
        sorted_scores = [r.overall_score for r in all_r]
        _result("best_jd_for_resume() returns results sorted descending",
                sorted_scores == sorted(sorted_scores, reverse=True),
                f"top={sorted_scores[:3]}")
        _result("best_jd_for_resume() best == all_r[0]",
                best.overall_score == all_r[0].overall_score)

    # 3.10 best_resume_for_jd() returns top result as first
    def t10():
        best, all_r = matcher.best_resume_for_jd(jd_map["jd_da_001"], SAMPLE_RESUMES)
        sorted_scores = [r.overall_score for r in all_r]
        _result("best_resume_for_jd() returns results sorted descending",
                sorted_scores == sorted(sorted_scores, reverse=True),
                f"top={sorted_scores[:3]}")

    # 3.11 Healthcare resume should rank top for Healthcare JD
    def t11():
        if "resume_hda_001" not in r_map or "jd_hda_001" not in jd_map:
            _result("Healthcare resume ranks #1 for Healthcare JD", False, note="data not available")
            return
        best, all_r = matcher.best_resume_for_jd(jd_map["jd_hda_001"], SAMPLE_RESUMES)
        _result("Healthcare resume ranks #1 for Healthcare JD",
                best.resume_id == "resume_hda_001",
                f"best_resume={best.resume_id}", expected="resume_hda_001", actual=best.resume_id)

    # 3.12 Custom thresholds are respected
    def t12():
        custom_thresholds = {
            "strong_match": 0.99, "good_match": 0.95,
            "partial_match": 0.90, "weak_match": 0.85,
        }
        m      = SemanticMatcher(thresholds=custom_thresholds)
        result = m.match(r_map["resume_da_001"], jd_map["jd_da_001"])
        _result("Custom high thresholds → label is Mismatch or Weak Match",
                result.match_label in ("Mismatch", "Weak Match"),
                f"label={result.match_label}")

    for fn in [t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12]:
        _run(fn.__name__, fn)


# ════════════════════════════════════════════════════════════════════════════
# SECTION 4 — THRESHOLD TUNER TESTS
# ════════════════════════════════════════════════════════════════════════════

def test_threshold_tuner():
    _section("SECTION 4 — THRESHOLD TUNER")

    # 4.1 get_thresholds() for known job types
    def t1():
        for jt in ["data_analytics", "software_engineering", "healthcare_analytics", "default"]:
            t = get_thresholds(jt)
            ok = all(k in t for k in ["strong_match", "good_match", "partial_match", "weak_match"])
            _result(f"get_thresholds('{jt}') has all 4 keys", ok, str(t))

    # 4.2 get_thresholds() for unknown job type → fallback to default
    def t2():
        t_unknown  = get_thresholds("unknown_job_type_xyz")
        t_default  = get_thresholds("default")
        _result("get_thresholds(unknown) falls back to default",
                t_unknown == t_default, f"unknown={t_unknown}")

    # 4.3 apply_thresholds() returns a valid label string
    def t3():
        valid_labels = {"Strong Match", "Good Match", "Partial Match", "Weak Match", "Mismatch"}
        for score in [0.80, 0.60, 0.45, 0.30, 0.10]:
            label = apply_thresholds(score, "data_analytics")
            _result(f"apply_thresholds({score}) returns valid label",
                    label in valid_labels, f"label='{label}'", expected=valid_labels, actual=label)

    # 4.4 ThresholdTuner.tune() runs without errors
    def t4():
        matcher = SemanticMatcher()
        tuner   = ThresholdTuner(steps=5)   # small steps for speed

        r_map  = {r["id"]: r for r in SAMPLE_RESUMES}
        jd_map = {j["id"]: j for j in SAMPLE_JDS}

        scored_pairs = []
        for (rid, jid, label, score_range) in GROUND_TRUTH[:4]:
            r = r_map.get(rid);  j = jd_map.get(jid)
            if r and j:
                result = matcher.match(r, j)
                scored_pairs.append({
                    "resume_id":    rid,
                    "jd_id":        jid,
                    "overall_score": result.overall_score,
                    "job_type":     j.get("job_type", "default"),
                })

        tuning_results = tuner.tune(scored_pairs, GROUND_TRUTH[:4])
        _result("ThresholdTuner.tune() completes without exception",
                isinstance(tuning_results, dict), f"job_types={list(tuning_results.keys())}")

    # 4.5 Threshold ordering is preserved (strong > good > partial > weak)
    def t5():
        for jt in ["data_analytics", "healthcare_analytics", "default"]:
            t = get_thresholds(jt)
            ordered = (t["strong_match"] > t["good_match"] > t["partial_match"] > t["weak_match"])
            _result(f"Threshold ordering strong>good>partial>weak for '{jt}'",
                    ordered, str(t))

    for fn in [t1, t2, t3, t4, t5]:
        _run(fn.__name__, fn)


# ════════════════════════════════════════════════════════════════════════════
# SECTION 5 — VALIDATOR TESTS
# ════════════════════════════════════════════════════════════════════════════

def test_validator():
    _section("SECTION 5 — VALIDATOR")

    matcher   = SemanticMatcher()
    validator = MatchingValidator()
    r_map     = {r["id"]: r for r in SAMPLE_RESUMES}
    jd_map    = {j["id"]: j for j in SAMPLE_JDS}

    # Build results for all GT pairs
    results = []
    for (rid, jid, label, score_range) in GROUND_TRUTH:
        r = r_map.get(rid);  j = jd_map.get(jid)
        if r and j:
            results.append(matcher.match(r, j))

    # 5.1 validate() returns a ValidationReport
    def t1():
        from semantic_engine.validator import ValidationReport
        report = validator.validate(results, GROUND_TRUTH, SAMPLE_JDS)
        _result("validate() returns ValidationReport",
                isinstance(report, ValidationReport), type(report).__name__)

    # 5.2 total_pairs matches the number of GT pairs that have data
    def t2():
        report = validator.validate(results, GROUND_TRUTH, SAMPLE_JDS)
        _result("ValidationReport.total_pairs > 0",
                report.total_pairs > 0, f"total_pairs={report.total_pairs}")

    # 5.3 label_accuracy is between 0 and 1
    def t3():
        report = validator.validate(results, GROUND_TRUTH, SAMPLE_JDS)
        _result("label_accuracy in [0, 1]",
                0.0 <= report.label_accuracy <= 1.0,
                f"label_accuracy={report.label_accuracy:.2%}")

    # 5.4 range_accuracy is between 0 and 1
    def t4():
        report = validator.validate(results, GROUND_TRUTH, SAMPLE_JDS)
        _result("range_accuracy in [0, 1]",
                0.0 <= report.range_accuracy <= 1.0,
                f"range_accuracy={report.range_accuracy:.2%}")

    # 5.5 to_json() serialises successfully
    def t5():
        report  = validator.validate(results, GROUND_TRUTH, SAMPLE_JDS)
        js      = validator.to_json(report)
        parsed  = json.loads(js)
        _result("to_json() produces valid JSON with 'summary' key",
                "summary" in parsed, f"keys={list(parsed.keys())}")

    # 5.6 confusion_matrix has expected labels as keys
    def t6():
        report  = validator.validate(results, GROUND_TRUTH, SAMPLE_JDS)
        cm_keys = set(report.confusion_matrix.keys())
        # Normalised labels used internally: strong_match, partial_match, mismatch
        valid   = {"strong_match", "partial_match", "mismatch"}
        _result("confusion_matrix uses normalised label keys",
                cm_keys.issubset(valid),
                f"keys={cm_keys}", expected=valid, actual=cm_keys)

    for fn in [t1, t2, t3, t4, t5, t6]:
        _run(fn.__name__, fn)


# ════════════════════════════════════════════════════════════════════════════
# SECTION 6 — INTEGRATION TESTS
# ════════════════════════════════════════════════════════════════════════════

def test_integration():
    _section("SECTION 6 — INTEGRATION (Full Pipeline)")

    matcher = SemanticMatcher()
    r_map   = {r["id"]: r for r in SAMPLE_RESUMES}
    jd_map  = {j["id"]: j for j in SAMPLE_JDS}

    # 6.1 Full pipeline: embed → match → label → gap for DA pair
    def t1():
        result = matcher.match(r_map["resume_da_001"], jd_map["jd_da_001"])
        ss = result.to_dict()["section_scores"]
        ok = (
            result.overall_score > 0
            and result.match_label in {"Strong Match", "Good Match", "Partial Match", "Weak Match", "Mismatch"}
            and isinstance(ss, dict)
        )
        _result("Full pipeline runs for DA resume ↔ DA JD",
                ok, f"score={result.overall_score:.4f}  label={result.match_label}")

    # 6.2 Scores are stable across two calls (determinism)
    def t2():
        r1 = matcher.match(r_map["resume_da_001"], jd_map["jd_da_001"]).overall_score
        r2 = matcher.match(r_map["resume_da_001"], jd_map["jd_da_001"]).overall_score
        _result("match() is deterministic across two calls",
                r1 == r2, f"run1={r1}  run2={r2}", expected=r1, actual=r2)

    # 6.3 Healthcare resume vs Healthcare JD should be better than vs SE JD
    def t3():
        if "resume_hda_001" not in r_map:
            _result("Healthcare resume matches Healthcare JD better than SE JD", False, "resume not in sample data")
            return
        s_hda = matcher.match(r_map["resume_hda_001"], jd_map["jd_hda_001"]).overall_score
        s_se  = matcher.match(r_map["resume_hda_001"], jd_map["jd_se_001"]).overall_score
        _result("Healthcare resume scores higher on Healthcare JD than SE JD",
                s_hda > s_se,
                f"hda_score={s_hda:.4f}  se_score={s_se:.4f}")

    # 6.4 Batch + validator accuracy >= 50% on ground truth
    def t4():
        results = []
        for (rid, jid, label, score_range) in GROUND_TRUTH:
            r = r_map.get(rid);  j = jd_map.get(jid)
            if r and j:
                results.append(matcher.match(r, j))
        if not results:
            _result("Batch + validate accuracy >= 50%", False, "no results produced")
            return
        validator = MatchingValidator()
        report    = validator.validate(results, GROUND_TRUTH, SAMPLE_JDS)
        _result("Batch + validate: range_accuracy >= 50%",
                report.range_accuracy >= 0.50,
                f"range_accuracy={report.range_accuracy:.2%}",
                expected=">=50%", actual=f"{report.range_accuracy:.2%}")

    # 6.5 JSON serialisability of all match results
    def t5():
        result = matcher.match(r_map["resume_da_001"], jd_map["jd_da_001"])
        try:
            serialised = json.dumps(result.to_dict())
            ok = True
        except Exception as e:
            ok = False
            serialised = str(e)
        _result("to_dict() output is JSON-serialisable", ok, f"len={len(serialised)}")

    for fn in [t1, t2, t3, t4, t5]:
        _run(fn.__name__, fn)


# ════════════════════════════════════════════════════════════════════════════
# SECTION 7 — EDGE CASE TESTS
# ════════════════════════════════════════════════════════════════════════════

def test_edge_cases():
    _section("SECTION 7 — EDGE CASES")

    matcher = SemanticMatcher()

    # 7.1 Resume with all empty sections
    def t1():
        empty_resume = {
            "id": "resume_empty", "name": "Empty Candidate",
            "skills": [], "experience": [], "projects": [],
            "education": [], "certifications": [],
        }
        jd = SAMPLE_JDS[0]
        result = matcher.match(empty_resume, jd)
        _result("Match with all-empty resume doesn't crash",
                0.0 <= result.overall_score <= 1.0,
                f"score={result.overall_score:.4f}")

    # 7.2 JD with minimal fields
    def t2():
        minimal_jd = {
            "id": "jd_minimal", "title": "Analyst", "job_type": "default",
            "role": [], "skills_required": [],
            "experience_required": "", "education_required": "",
        }
        result = matcher.match(SAMPLE_RESUMES[0], minimal_jd)
        _result("Match with minimal JD doesn't crash",
                0.0 <= result.overall_score <= 1.0,
                f"score={result.overall_score:.4f}")

    # 7.3 Very long skill list
    def t3():
        big_resume = {
            **SAMPLE_RESUMES[0],
            "skills": ["skill_" + str(i) for i in range(500)],
        }
        result = matcher.match(big_resume, SAMPLE_JDS[0])
        _result("Match with 500-skill resume doesn't crash",
                0.0 <= result.overall_score <= 1.0,
                f"score={result.overall_score:.4f}")

    # 7.4 embed_batch with a single empty string in batch
    def t4():
        texts  = ["Python SQL", "", "HIPAA compliance"]
        mat    = embed_batch(texts)
        middle = mat[1]
        _result("embed_batch handles empty string in middle of batch gracefully",
                np.allclose(middle, 0),
                f"middle_norm={np.linalg.norm(middle):.4f}")

    # 7.5 cosine_similarity with shape mismatch → 0.0
    def t5():
        a = np.ones(50, dtype=np.float32)
        b = np.ones(100, dtype=np.float32)
        s = cosine_similarity(a, b)
        _result("cosine_similarity with shape mismatch returns 0.0",
                s == 0.0, f"score={s}", expected=0.0, actual=s)

    # 7.6 identify_gaps with all high scores → empty list
    def t6():
        scores = {"skills": 0.9, "experience_summary": 0.85, "projects": 0.80}
        gaps   = identify_gaps(scores, threshold=0.40)
        _result("identify_gaps with all high scores returns empty list",
                len(gaps) == 0, f"gaps={gaps}", expected=[], actual=gaps)

    # 7.7 Resume missing 'projects' key entirely
    def t7():
        no_proj = {k: v for k, v in SAMPLE_RESUMES[0].items() if k != "projects"}
        result  = matcher.match(no_proj, SAMPLE_JDS[0])
        _result("match() with resume missing 'projects' key doesn't crash",
                0.0 <= result.overall_score <= 1.0,
                f"score={result.overall_score:.4f}")

    # 7.8 Numeric score edge: score exactly at threshold boundaries
    def t8():
        thresholds = {"strong_match": 0.75, "good_match": 0.55, "partial_match": 0.40, "weak_match": 0.25}
        for score, expected in [(0.75, "Strong Match"), (0.55, "Good Match"),
                                 (0.40, "Partial Match"), (0.25, "Weak Match"), (0.24, "Mismatch")]:
            label = similarity_label(score, thresholds)
            _result(f"similarity_label({score}) at exact boundary = '{expected}'",
                    label == expected, f"got='{label}'", expected=expected, actual=label)

    for fn in [t1, t2, t3, t4, t5, t6, t7, t8]:
        _run(fn.__name__, fn)


# ════════════════════════════════════════════════════════════════════════════
# FINAL REPORT
# ════════════════════════════════════════════════════════════════════════════

def _print_summary():
    total = _PASS + _FAIL
    W     = 70
    print(f"\n{'═'*W}")
    print(f"  SEMANTIC ENGINE TEST SUMMARY")
    print(f"{'═'*W}")
    print(f"  Total   : {total}")
    print(f"  ✅ Passed: {_PASS}")
    print(f"  ❌ Failed: {_FAIL}")
    if total > 0:
        print(f"  Score   : {_PASS/total*100:.1f}%")
    print(f"{'═'*W}\n")

    if _FAIL == 0:
        print("  🎉 All tests passed!\n")
    else:
        print(f"  ⚠️  {_FAIL} test(s) failed. Review output above.\n")


# ════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

SECTIONS = {
    "embedder":  test_embedder,
    "similarity": test_similarity,
    "matcher":   test_semantic_matcher,
    "tuner":     test_threshold_tuner,
    "validator": test_validator,
    "integration": test_integration,
    "edge":      test_edge_cases,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Semantic Engine Test Suite")
    parser.add_argument("--verbose",  action="store_true", help="Print all test results (not just failures)")
    parser.add_argument("--section",  choices=list(SECTIONS.keys()), help="Run only one section")
    args = parser.parse_args()

    _VERBOSE = args.verbose

    print(f"\n{'═'*70}")
    print(f"  SEMANTIC ENGINE — FULL TEST SUITE   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*70}")

    if args.section:
        SECTIONS[args.section]()
    else:
        for name, fn in SECTIONS.items():
            _run(f"SECTION:{name}", fn)

    _print_summary()
