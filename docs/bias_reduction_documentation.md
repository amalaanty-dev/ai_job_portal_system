# Bias Reduction Documentation – Day 15

## Module: `fairness_engine/`

This module implements the Day-15 deliverables of Zecpath's AI Job Portal:
**Fairness, Normalization & Bias Reduction**.

It introduces five complementary mechanisms that wrap around the existing
ATS scoring pipeline (Phase 2 of PRD) without modifying it.

---

## 1. Resume Normalization (`resume_normalizer.py`)

**Goal:** Force every parsed resume into the same shape so that downstream
scoring is not biased by parser quirks (e.g. one parser puts skills in a
flat list, another in a dict).

**Standard schema:** `STANDARD_RESUME_SCHEMA` in
`utils/normalization_constants.py`.

**Why it reduces bias:** Two equally-qualified candidates whose resumes were
parsed with slightly different parsers are now scored on identical structural
ground.

---

## 2. Keyword-Dependency Reduction (`keyword_dependency_reducer.py`)

**Problem:** Naive ATS systems reward whoever stuffs the most JD keywords in
their skills section. This punishes honest candidates and rewards keyword
gaming.

**Solution:**
- **Synonym canonicalization** — `tf` ≡ `tensorflow`, `ml` ≡ `machine learning`.
- **Contextual evidence search** — A skill is "demonstrated" only if it appears
  inside experience-duty / project / achievement text, not only the skills
  section.
- **Keyword-dependency ratio** — `unsupported_skills / claimed_skills`. Higher
  ratio = more keyword stuffing.
- **Context-adjusted skill score** — A 0–100 alternative score that gives
  credit only for evidenced skills.
- **Buzzword penalty** — Generic fluff like "rockstar", "ninja",
  "go-getter" lowers the score slightly.

**Threshold:** `BIAS_THRESHOLDS["max_acceptable_keyword_dependency"] = 0.60`.
Anything above that is flagged.

---

## 3. Score Normalization (`score_normalizer.py`)

**Problem:** Raw ATS scores depend on weight choices and JD strictness.
Comparing 57 across two job postings is meaningless.

**Methods supported (configurable):**

| Method      | Formula                                       | Use case                           |
|-------------|-----------------------------------------------|------------------------------------|
| `min_max`   | (x – min)/(max – min) × 100                   | Default; pool-relative ranking     |
| `z_score`   | (x – μ)/σ → CDF × 100                         | Normally-distributed score pools   |
| `percentile`| rank/N × 100 (handles ties)                   | Heavy-tailed distributions         |
| `robust`    | (x – median)/IQR → sigmoid × 100              | Outlier-resistant normalization    |

Stats (mean, median, stdev) are produced for the auditor.

---

## 4. PII Masking (`pii_masker.py`)

**Default profile (Day-15 selection):** `Name, Email, Phone, Location,
LinkedIn, Gender, Age, Marital status` — masked.
**Opt-in:** `Caste/Religion`, `College tier`.

**Mechanism:**
- Top-level `personal_info.*` fields replaced by placeholder constants.
- A recursive tree-walker scrubs **email**, **phone**, **URLs**, **gender
  pronouns/honorifics**, **age phrases**, **marital status**, etc. inside
  every string in the resume tree (summary, achievements, project bullets,
  duties).
- An **audit dict** records exactly which fields were masked and how many
  substitutions were applied per category — enabling Task-5 to verify
  masking effectiveness.

**Why it matters:** Removing names/genders/photos from the input that the
scoring engine sees forces the model to score on skills + experience, not
demographic cues.

---

## 5. Bias Evaluation (`bias_evaluator.py`)

Runs at the **pool level** and emits a JSON audit report with five indicators:

1. **Score distribution** — mean / stdev / variance ratio.
2. **Cohort disparity** — mean-score gap between groups (gender, location,
   etc.) when a `cohort_map` is supplied.
3. **Keyword-dependency aggregate** — average dependency ratio across the
   pool.
4. **PII masking effectiveness** — total masks applied; useful for QA.
5. **Elite-institution gap** — placeholder; activated when
   `cohort_map` includes `is_elite`.

Each indicator is compared against `BIAS_THRESHOLDS` and emits a `flag` if
crossed. Final verdict is `PASS` or `REVIEW_NEEDED`.

---

## Pipeline Diagram

```
parsed_resume.json + sections.json + parsed_jd.json + ats_scores.json
                                |
                                v
               +-----------------------------------+
               |    fairness_engine.pipeline       |
               +-----------------------------------+
                  |          |          |
                  v          v          v
           [Normalize]  [Reduce KW]  [Mask PII]      <-- per resume
                                 |
                                 v
                          [Normalize Scores]          <-- batch
                                 |
                                 v
                          [Evaluate Bias]             <-- batch
                                 |
                                 v
                       fairness_engine_outputs/bias_reports/<run_id>_*.json
```

---

## Running

```bash
# Per-resume + batch
python -m scripts.run_fairness_pipeline \
    --resume   data/parsed/Amala_Resume_DS_DA_2026_.json \
    --sections data/parsed/Amala_Resume_DS_DA_2026__sections.json \
    --jd       data/parsed_jds/ai_specialist_in_healthcare_analytics_parsed_jd.json \
    --ats_dir  ats_results \
    --method   min_max \
    --run_id   day15_run

# Standalone bias audit
python -m scripts.run_bias_audit \
    --scores_dir ats_results \
    --deps_dir   fairness_engine_outputs/normalized_scores \
    --masks_dir  fairness_engine_outputs/masked_resumes \
    --cohort_file data/cohort_map.json
```

## Tests

```bash
pytest tests/test_fairness_pipeline.py
pytest tests/test_jd_parser.py
pytest tests/test_keyword_dependency.py
pytest tests/test_pii_masker.py
pytest tests/test_resume_normalizer.py
pytest tests/test_score_normalizer.py

```

---

## Compliance Note

This module implements the **bias-reduction & GDPR-style data-minimization**
requirements highlighted in PRD Phase 2 ("Bias-reduced candidate scoring")
and Phase 10 ("Data encryption / consent"). Masked resumes must be stored
separately from raw resumes and only un-masked under explicit recruiter
authorization.
