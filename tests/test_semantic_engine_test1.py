"""
tests/test_semantic_engine.py
───────────────────────────────
Unit and integration tests for Day 12 – Semantic Matching Engine.

Test groups:
  TestEmbedder         — embedding correctness and caching
  TestSimilarity       — cosine similarity and section scoring
  TestSemanticMatcher  — end-to-end matching logic
  TestThresholdTuner   — calibration logic
  TestValidator        — accuracy reporting
  TestIntegration      — full pipeline with sample data
"""

import sys
import os
import unittest
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from semantic_engine.embedder      import embed, embed_batch, embed_resume, embed_jd, normalise, cache_stats, _get_vectorizer, _N_DOMAINS
from semantic_engine.similarity    import (
    cosine_similarity, cosine_matrix, section_similarity,
    weighted_similarity, similarity_label, identify_gaps, DEFAULT_WEIGHTS,
)
from semantic_engine.semantic_matcher import SemanticMatcher, WEIGHT_PROFILES
from semantic_engine.threshold_tuner  import ThresholdTuner, get_thresholds, apply_thresholds
from semantic_engine.validator        import MatchingValidator
from data.sample_data import SAMPLE_RESUMES, SAMPLE_JDS, GROUND_TRUTH


# ═══════════════════════════════════════════════════════════════
# HELPER FIXTURES
# ═══════════════════════════════════════════════════════════════

def _resume(rid="resume_da_001"):
    return next(r for r in SAMPLE_RESUMES if r["id"] == rid)

def _jd(jid="jd_da_001"):
    return next(j for j in SAMPLE_JDS if j["id"] == jid)


# ═══════════════════════════════════════════════════════════════
# 1. EMBEDDER TESTS
# ═══════════════════════════════════════════════════════════════

class TestEmbedder(unittest.TestCase):

    def test_embed_returns_correct_shape(self):
        vec = embed("Python SQL Tableau data analytics")
        actual_dim = len(_get_vectorizer().vocabulary_) + _N_DOMAINS
        self.assertEqual(vec.shape, (actual_dim,))

    def test_embed_empty_string_returns_zeros(self):
        vec = embed("")
        self.assertTrue(np.all(vec == 0))

    def test_embed_none_returns_zeros(self):
        vec = embed(None)
        self.assertTrue(np.all(vec == 0))

    def test_embed_list_joins_items(self):
        vec_list = embed(["Python", "SQL", "Tableau"])
        vec_str  = embed("Python. SQL. Tableau")
        # Both should produce a non-zero vector; they may differ slightly
        self.assertTrue(np.any(vec_list != 0))
        self.assertTrue(np.any(vec_str  != 0))

    def test_embed_is_unit_normalised(self):
        vec  = embed("semantic matching engine test")
        norm = float(np.linalg.norm(vec))
        self.assertAlmostEqual(norm, 1.0, places=4)

    def test_embed_batch_shape(self):
        texts   = ["Python", "SQL", "Tableau", "Power BI"]
        matrix  = embed_batch(texts)
        actual_dim = len(_get_vectorizer().vocabulary_) + _N_DOMAINS
        self.assertEqual(matrix.shape, (4, actual_dim))

    def test_embed_batch_caches(self):
        texts = ["test caching sentence one", "test caching sentence two"]
        embed_batch(texts)
        stats_before = cache_stats()["cached_embeddings"]
        embed_batch(texts)   # second call — should hit cache
        stats_after  = cache_stats()["cached_embeddings"]
        self.assertEqual(stats_before, stats_after)

    def test_embed_resume_returns_all_sections(self):
        resume = _resume()
        emb    = embed_resume(resume)
        for section in ["skills", "experience_summary", "projects", "education", "certifications", "full"]:
            self.assertIn(section, emb)
            actual_dim = len(_get_vectorizer().vocabulary_) + _N_DOMAINS
            self.assertEqual(emb[section].shape, (actual_dim,))

    def test_embed_jd_returns_all_sections(self):
        jd  = _jd()
        emb = embed_jd(jd)
        for section in ["required_skills", "preferred_skills", "responsibilities", "qualifications", "full"]:
            self.assertIn(section, emb)

    def test_normalise_string(self):
        self.assertEqual(normalise("  hello  "), "hello")

    def test_normalise_list(self):
        result = normalise(["Python", "SQL"])
        self.assertIn("Python", result)
        self.assertIn("SQL",    result)

    def test_normalise_none(self):
        self.assertEqual(normalise(None), "")


# ═══════════════════════════════════════════════════════════════
# 2. SIMILARITY TESTS
# ═══════════════════════════════════════════════════════════════

class TestSimilarity(unittest.TestCase):

    def setUp(self):
        self.vec_a = embed("data analyst SQL Python Tableau business intelligence")
        self.vec_b = embed("data analyst SQL Python Tableau business intelligence")  # identical
        self.vec_c = embed("mechanical engineer SolidWorks ANSYS FEA manufacturing")
        self.zero  = np.zeros(384, dtype=np.float32)

    def test_identical_vectors_give_1(self):
        score = cosine_similarity(self.vec_a, self.vec_b)
        self.assertAlmostEqual(score, 1.0, places=4)

    def test_similar_texts_give_high_score(self):
        v1 = embed("senior data analyst machine learning Python SQL")
        v2 = embed("data science analyst Python SQL analytics")
        score = cosine_similarity(v1, v2)
        self.assertGreater(score, 0.55,
            f"Expected similar texts to score >0.55, got {score:.4f}")

    def test_different_domains_give_low_score(self):
        score = cosine_similarity(self.vec_a, self.vec_c)
        self.assertLess(score, 0.55,
            f"Expected cross-domain to score <0.55, got {score:.4f}")

    def test_zero_vector_gives_zero(self):
        score = cosine_similarity(self.zero, self.vec_a)
        self.assertEqual(score, 0.0)

    def test_cosine_matrix_shape(self):
        mat_a = embed_batch(["Python SQL", "SolidWorks ANSYS"])
        mat_b = embed_batch(["data analytics", "mechanical design", "marketing"])
        result = cosine_matrix(mat_a, mat_b)
        self.assertEqual(result.shape, (2, 3))

    def test_cosine_matrix_values_in_range(self):
        mat_a  = embed_batch(["Python SQL", "SolidWorks"])
        mat_b  = embed_batch(["analytics SQL", "CAD design"])
        result = cosine_matrix(mat_a, mat_b)
        self.assertTrue(np.all(result >= 0))
        self.assertTrue(np.all(result <= 1))

    def test_section_similarity_structure(self):
        result = section_similarity(self.vec_a, self.vec_b, label="skills")
        self.assertIn("score",      result)
        self.assertIn("confidence", result)
        self.assertIn("label",      result)

    def test_section_similarity_high_confidence(self):
        result = section_similarity(self.vec_a, self.vec_b, label="test")
        self.assertEqual(result["confidence"], "high")

    def test_weighted_similarity_correct(self):
        scores  = {"skills": 0.80, "experience_summary": 0.70, "projects": 0.60,
                   "education": 0.50, "certifications": 0.40}
        weights = {"skills": 0.35, "experience_summary": 0.30, "projects": 0.20,
                   "education": 0.10, "certifications": 0.05}
        result  = weighted_similarity(scores, weights)
        expected = 0.80*0.35 + 0.70*0.30 + 0.60*0.20 + 0.50*0.10 + 0.40*0.05
        self.assertAlmostEqual(result, expected, places=4)

    def test_weighted_similarity_empty(self):
        result = weighted_similarity({}, {})
        self.assertEqual(result, 0.0)

    def test_similarity_label_strong(self):
        self.assertIn("Strong", similarity_label(0.80))

    def test_similarity_label_mismatch(self):
        self.assertEqual(similarity_label(0.10), "Mismatch")

    def test_identify_gaps_returns_low_sections(self):
        scores = {"skills": 0.30, "experience_summary": 0.80, "projects": 0.20}
        gaps   = identify_gaps(scores, threshold=0.45)
        gap_sections = [g["section"] for g in gaps]
        self.assertIn("skills",   gap_sections)
        self.assertIn("projects", gap_sections)
        self.assertNotIn("experience_summary", gap_sections)

    def test_identify_gaps_sorted_ascending(self):
        scores = {"a": 0.40, "b": 0.10, "c": 0.30}
        gaps   = identify_gaps(scores, threshold=0.45)
        sc     = [g["score"] for g in gaps]
        self.assertEqual(sc, sorted(sc))


# ═══════════════════════════════════════════════════════════════
# 3. SEMANTIC MATCHER TESTS
# ═══════════════════════════════════════════════════════════════

class TestSemanticMatcher(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.matcher = SemanticMatcher()
        cls.resume_da  = _resume("resume_da_001")
        cls.resume_se  = _resume("resume_se_001")
        cls.resume_mis = _resume("resume_mismatch_001")
        cls.jd_da      = _jd("jd_da_001")
        cls.jd_se      = _jd("jd_se_001")
        cls.jd_me      = _jd("jd_me_001")

    def test_match_returns_result_object(self):
        from semantic_engine.semantic_matcher import MatchResult
        result = self.matcher.match(self.resume_da, self.jd_da)
        self.assertIsInstance(result, MatchResult)

    def test_ideal_pair_scores_high(self):
        result = self.matcher.match(self.resume_da, self.jd_da)
        self.assertGreater(result.overall_score, 0.55,
            f"Expected DA resume ↔ DA JD >0.55, got {result.overall_score:.4f}")

    def test_mismatch_pair_scores_low(self):
        result = self.matcher.match(self.resume_mis, self.jd_se)
        self.assertLess(result.overall_score, 0.40,
            f"Expected hospitality ↔ SE JD <0.40, got {result.overall_score:.4f}")

    def test_ideal_better_than_cross_domain(self):
        ideal = self.matcher.match(self.resume_se, self.jd_se)
        cross = self.matcher.match(self.resume_se, self.jd_me)
        self.assertGreater(ideal.overall_score, cross.overall_score,
            "SE resume should score higher on SE JD than mechanical JD")

    def test_match_result_has_section_scores(self):
        result = self.matcher.match(self.resume_da, self.jd_da)
        self.assertGreater(result.skills_score,     0.0)
        self.assertGreater(result.experience_score, 0.0)

    def test_match_result_has_label(self):
        result = self.matcher.match(self.resume_da, self.jd_da)
        self.assertIn(result.match_label,
            ["Strong Match", "Good Match", "Partial Match", "Weak Match", "Mismatch"])

    def test_to_dict_structure(self):
        result = self.matcher.match(self.resume_da, self.jd_da)
        d      = result.to_dict()
        for key in ["resume_id", "jd_id", "overall_score", "match_label",
                    "section_scores", "gaps"]:
            self.assertIn(key, d)

    def test_section_scores_in_range(self):
        result = self.matcher.match(self.resume_da, self.jd_da)
        d      = result.to_dict()
        for sec, sc in d["section_scores"].items():
            self.assertGreaterEqual(sc, 0.0, f"{sec} score < 0")
            self.assertLessEqual(sc,    1.0, f"{sec} score > 1")

    def test_best_jd_for_resume_returns_correct_type(self):
        best, all_r = self.matcher.best_jd_for_resume(self.resume_da, SAMPLE_JDS)
        from semantic_engine.semantic_matcher import MatchResult
        self.assertIsInstance(best, MatchResult)
        self.assertEqual(len(all_r), len(SAMPLE_JDS))

    def test_best_jd_for_resume_sorted_descending(self):
        _, all_r = self.matcher.best_jd_for_resume(self.resume_da, SAMPLE_JDS)
        scores   = [r.overall_score for r in all_r]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_custom_thresholds_applied(self):
        matcher = SemanticMatcher(thresholds={
            "strong_match":  0.01,
            "good_match":    0.005,
            "partial_match": 0.002,
            "weak_match":    0.001,
        })
        result = matcher.match(self.resume_da, self.jd_da)
        self.assertEqual(result.match_label, "Strong Match")

    def test_weight_profiles_sum_to_one(self):
        for profile_name, weights in WEIGHT_PROFILES.items():
            total = sum(weights.values())
            self.assertAlmostEqual(total, 1.0, places=6,
                msg=f"Weight profile '{profile_name}' sums to {total}, expected 1.0")


# ═══════════════════════════════════════════════════════════════
# 4. THRESHOLD TUNER TESTS
# ═══════════════════════════════════════════════════════════════

class TestThresholdTuner(unittest.TestCase):

    def test_get_thresholds_returns_dict(self):
        t = get_thresholds("data_analytics")
        self.assertIn("strong_match",  t)
        self.assertIn("partial_match", t)

    def test_get_thresholds_unknown_falls_back_to_default(self):
        t = get_thresholds("unknown_job_type_xyz")
        self.assertIn("strong_match", t)

    def test_apply_thresholds_high_score(self):
        label = apply_thresholds(0.90, "data_analytics")
        self.assertIn("Strong", label)

    def test_apply_thresholds_low_score(self):
        label = apply_thresholds(0.05, "data_analytics")
        self.assertEqual(label, "Mismatch")

    def test_tuner_runs_without_error(self):
        matcher      = SemanticMatcher()
        tuner        = ThresholdTuner(steps=5)
        resume_map   = {r["id"]: r for r in SAMPLE_RESUMES}
        jd_map       = {j["id"]: j for j in SAMPLE_JDS}

        scored_pairs = []
        for (rid, jid, label, _) in GROUND_TRUTH[:5]:
            if rid in resume_map and jid in jd_map:
                r = matcher.match(resume_map[rid], jd_map[jid])
                scored_pairs.append({
                    "resume_id":    rid,
                    "jd_id":        jid,
                    "overall_score": r.overall_score,
                    "job_type":     jd_map[jid].get("job_type", "default"),
                })

        results = tuner.tune(scored_pairs, GROUND_TRUTH[:5])
        self.assertIsInstance(results, dict)

    def test_tuner_summary_has_expected_keys(self):
        tuner = ThresholdTuner(steps=3)
        # Prime with a fake result
        from semantic_engine.threshold_tuner import TuningResult
        tuner._results["test_job"] = TuningResult(
            job_type="test_job",
            best_thresholds={"strong_match": 0.7, "good_match": 0.55,
                             "partial_match": 0.4, "weak_match": 0.25},
            f1_score=0.85, precision=0.82, recall=0.88,
            n_samples=5, sweep_results=[]
        )
        summary = tuner.summary()
        self.assertTrue(len(summary) > 0)
        row = summary[0]
        for key in ["job_type", "n_samples", "f1_score", "strong_thresh", "partial_thresh"]:
            self.assertIn(key, row)


# ═══════════════════════════════════════════════════════════════
# 5. VALIDATOR TESTS
# ═══════════════════════════════════════════════════════════════

class TestValidator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        matcher    = SemanticMatcher()
        resume_map = {r["id"]: r for r in SAMPLE_RESUMES}
        jd_map     = {j["id"]: j for j in SAMPLE_JDS}

        cls.results = []
        for (rid, jid, label, score_range) in GROUND_TRUTH:
            if rid in resume_map and jid in jd_map:
                cls.results.append(matcher.match(resume_map[rid], jd_map[jid]))

        validator     = MatchingValidator()
        cls.report    = validator.validate(cls.results, GROUND_TRUTH, SAMPLE_JDS)
        cls.validator = validator

    def test_report_has_correct_total(self):
        self.assertEqual(self.report.total_pairs, len(GROUND_TRUTH))

    def test_range_accuracy_above_threshold(self):
        self.assertGreater(self.report.range_accuracy, 0.50,
            f"Expected range accuracy > 50%, got {self.report.range_accuracy*100:.1f}%")

    def test_label_accuracy_above_threshold(self):
        self.assertGreater(self.report.label_accuracy, 0.40,
            f"Expected label accuracy > 40%, got {self.report.label_accuracy*100:.1f}%")

    def test_confusion_matrix_is_dict(self):
        self.assertIsInstance(self.report.confusion_matrix, dict)

    def test_per_job_type_has_entries(self):
        self.assertGreater(len(self.report.per_job_type), 0)

    def test_to_json_is_valid(self):
        import json
        json_str = self.validator.to_json(self.report)
        data     = json.loads(json_str)
        self.assertIn("summary",      data)
        self.assertIn("pair_results", data)

    def test_print_report_runs(self):
        # Should not raise
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.validator.print_report(self.report)
        output = buf.getvalue()
        self.assertIn("ACCURACY REPORT", output)


# ═══════════════════════════════════════════════════════════════
# 6. INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestIntegration(unittest.TestCase):
    """
    End-to-end tests verifying that the full pipeline produces
    sensible results on all 5 job types.
    """

    @classmethod
    def setUpClass(cls):
        cls.matcher    = SemanticMatcher()
        cls.resume_map = {r["id"]: r for r in SAMPLE_RESUMES}
        cls.jd_map     = {j["id"]: j for j in SAMPLE_JDS}

    def _score(self, rid, jid):
        return self.matcher.match(self.resume_map[rid], self.jd_map[jid]).overall_score

    def test_da_resume_higher_on_da_jd_than_me_jd(self):
        da_score = self._score("resume_da_001", "jd_da_001")
        me_score = self._score("resume_da_001", "jd_me_001")
        self.assertGreater(da_score, me_score)

    def test_se_resume_higher_on_se_jd_than_mm_jd(self):
        se_score = self._score("resume_se_001", "jd_se_001")
        mm_score = self._score("resume_se_001", "jd_mm_001")
        self.assertGreater(se_score, mm_score)

    def test_hda_resume_higher_on_hda_jd_than_me_jd(self):
        hda_score = self._score("resume_hda_001", "jd_hda_001")
        me_score  = self._score("resume_hda_001", "jd_me_001")
        self.assertGreater(hda_score, me_score)

    def test_mm_resume_higher_on_mm_jd_than_se_jd(self):
        mm_score = self._score("resume_mm_001", "jd_mm_001")
        se_score = self._score("resume_mm_001", "jd_se_001")
        self.assertGreater(mm_score, se_score)

    def test_me_resume_higher_on_me_jd_than_mm_jd(self):
        me_score = self._score("resume_me_001", "jd_me_001")
        mm_score = self._score("resume_me_001", "jd_mm_001")
        self.assertGreater(me_score, mm_score)

    def test_mismatch_resume_lowest_on_se_jd(self):
        mis_score   = self._score("resume_mismatch_001", "jd_se_001")
        other_scores = [
            self._score("resume_se_001",  "jd_se_001"),
            self._score("resume_da_001",  "jd_se_001"),
        ]
        for sc in other_scores:
            self.assertGreater(sc, mis_score,
                f"Mismatch resume ({mis_score:.3f}) should score lower than relevant resume ({sc:.3f})")

    def test_batch_returns_all_combinations(self):
        resumes = SAMPLE_RESUMES[:3]
        jds     = SAMPLE_JDS[:3]
        results = self.matcher.match_batch(resumes, jds)
        self.assertEqual(len(results), 9)   # 3 × 3

    def test_all_scores_in_valid_range(self):
        for rid, jid, *_ in GROUND_TRUTH:
            if rid in self.resume_map and jid in self.jd_map:
                score = self._score(rid, jid)
                self.assertGreaterEqual(score, 0.0, f"Score < 0 for {rid} ↔ {jid}")
                self.assertLessEqual(score,    1.0, f"Score > 1 for {rid} ↔ {jid}")


# ═══════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main(verbosity=2)
