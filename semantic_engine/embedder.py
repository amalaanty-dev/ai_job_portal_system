"""
semantic_engine/embedder.py
────────────────────────────
Universal Section Extractor: Handles Strings, Lists, and Nested Dicts.

FIXES in this version
─────────────────────
1. Expanded _DOMAIN_CORPUS  — 6 rich documents instead of 3; covers more
   healthcare, data-science, and cross-domain vocabulary so TF-IDF builds a
   much wider feature space.

2. Synonym / alias expansion  — _SYNONYM_MAP normalises common paraphrases
   ("predictive modelling" → adds "prediction forecasting model") before
   embedding so lexically-different-but-semantically-identical phrases can
   match.

3. section_is_empty() helper — callers (matcher) can detect genuinely
   missing sections and handle their weight differently instead of letting
   a zero-vector silently crush the score.

4. embed_resume() section enrichment — when education or certifications
   are present as strings, they are used normally; when empty the section
   text falls back to the full-document context so the vector is not a
   hard zero (avoids the zero-cosine penalty for unrelated-but-real text).

5. Improved embed_jd() — maps more JD field names; adds preferred_skills
   from "skills_preferred" / "nice_to_have" keys used in many real JD JSONs.

6. Increased max_features to 4000 and added sublinear_tf=True for better
   IDF weighting on long documents.
"""

import hashlib
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

# ── Domain corpus for TF-IDF fitting ──────────────────────────────────────────
# Six rich documents: DA, SE, Healthcare-DA, Marketing, MechEng, Cross-domain.
# More documents = richer IDF distribution = better discrimination.
_DOMAIN_CORPUS = [
    # Data Analytics / Data Science
    "Python SQL Tableau Power BI data analytics business intelligence ETL pipeline "
    "Pandas NumPy Matplotlib Seaborn statistical analysis data cleaning data wrangling "
    "data visualisation reporting dashboards KPIs OKRs machine learning AI deep learning "
    "NLP natural language processing data science forecasting regression classification "
    "clustering A/B testing Google Analytics Excel pivot tables scikit-learn XGBoost "
    "random forest logistic regression decision tree feature engineering model training "
    "model evaluation cross-validation hyperparameter tuning data pipeline automation "
    "big data Spark Hadoop data lake data warehouse Snowflake Redshift dbt Airflow "
    "Looker Metabase prediction forecast churn retention segmentation cohort analysis",

    # Software Engineering / Backend
    "Python Java Spring Boot REST API microservices Docker Kubernetes AWS GCP Azure "
    "CI/CD Jenkins Git GitHub Actions Agile Scrum PostgreSQL Redis MongoDB event-driven "
    "software engineering backend cloud infrastructure DevOps distributed systems "
    "Kafka RabbitMQ gRPC GraphQL TypeScript Node.js React Vue Angular Flutter "
    "unit testing integration testing TDD BDD pytest JUnit code review pull request "
    "system design scalability reliability SLA SLO observability logging monitoring "
    "Prometheus Grafana Terraform Ansible Helm microservice architecture API gateway",

    # Healthcare Data Analytics (primary target domain)
    "SQL Python R Tableau Epic Cerner EHR ICD-10 ICD-9 CPT coding HIPAA compliance "
    "clinical data health informatics health information management patient outcomes "
    "readmission quality improvement population health SAS SPSS biostatistics "
    "public health healthcare analytics nursing pharmacy billing coding "
    "medical records electronic health records clinical decision support "
    "predictive modelling patient risk stratification disease management "
    "care management outcomes research real-world evidence clinical trials "
    "epidemiology chronic disease prevention health equity SDOH social determinants "
    "HL7 FHIR interoperability data governance data privacy de-identification "
    "claims data revenue cycle insurance reimbursement DRG procedure codes "
    "hospital administration clinical informatics radiology pharmacy lab results "
    "vital signs diagnosis treatment plan medication administration nursing notes "
    "discharge summary emergency department ICU inpatient outpatient telehealth "
    "patient satisfaction HCAHPS quality metrics HEDIS CMS reporting",

    # Marketing / Business
    "digital marketing SEO SEM Google Ads Meta Ads Facebook Instagram content strategy "
    "email marketing HubSpot Salesforce CRM brand management market research "
    "campaign analytics social media marketing A/B testing copywriting influencer "
    "ROI ROAS conversion funnel lead generation demand generation growth marketing "
    "customer acquisition retention churn product marketing go-to-market strategy "
    "competitive analysis market segmentation customer journey persona B2B B2C",

    # Mechanical Engineering / Manufacturing
    "SolidWorks AutoCAD ANSYS FEA GD&T CNC machining product design FMEA "
    "manufacturing processes BOM management materials science thermodynamics "
    "fluid mechanics structural analysis fatigue analysis tolerance stack-up "
    "design for manufacturability DFM DFMA prototype testing validation "
    "injection moulding sheet metal welding casting forging surface finish "
    "quality control ISO 9001 PPAP APQP lean manufacturing Six Sigma",

    # Cross-domain / General professional
    "project management stakeholder communication Agile Scrum Kanban "
    "leadership teamwork collaboration cross-functional problem solving "
    "data-driven decision making presentation skills written communication "
    "Microsoft Office Excel PowerPoint Word critical thinking analytical skills "
    "time management continuous improvement process optimisation documentation "
    "training mentoring certification professional development",
]

# ── Synonym / alias expansion map ─────────────────────────────────────────────
# Adds synonymous tokens alongside existing text so TF-IDF can match
# semantically-identical phrases that share no surface tokens.
_SYNONYM_MAP = {
    r"\bpredictive modell\w*":        "prediction forecasting model inference",
    r"\bpatient outcome\w*":          "clinical outcomes health results treatment effectiveness",
    r"\breadmission\w*":              "hospital readmission 30-day readmit re-hospitalisation",
    r"\bhealth informatics\b":        "clinical informatics medical informatics health IT",
    r"\behr\b":                       "electronic health records EHR Epic Cerner",
    r"\bhipaa\b":                     "HIPAA data privacy patient confidentiality protected health information",
    r"\bicd-10\b":                    "ICD-10 diagnosis coding medical coding clinical coding",
    r"\bdata visuali[sz]ation\b":     "dashboards charts graphs reporting visualisation",
    r"\bstatistical analysis\b":      "statistics data analysis quantitative analysis modelling",
    r"\bmachine learning\b":          "ML predictive models AI algorithms scikit-learn model training",
    r"\betl\b":                       "ETL extract transform load data pipeline ingestion",
    r"\bsql\b":                       "SQL database query relational database data extraction",
    r"\bpython\b":                    "Python programming scripting automation pandas numpy",
    r"\br\b":                         "R statistical programming ggplot dplyr tidyverse",
    r"\bscikit.learn\b":              "scikit-learn machine learning sklearn Python ML",
    r"\bclinical data\b":             "clinical dataset medical data patient data healthcare records",
    r"\bdata cleaning\b":             "data quality data wrangling preprocessing data validation",
    r"\bbiostatistics\b":             "biostatistics statistics epidemiology clinical research methods",
    r"\bpopulation health\b":         "population health management public health community health",
    r"\brevenue cycle\b":             "revenue cycle management RCM billing coding reimbursement",
    r"\bdata governance\b":           "data governance data quality data stewardship master data",
}


def _apply_synonyms(text: str) -> str:
    """Expand synonyms in-place by appending alias tokens after each match."""
    for pattern, expansion in _SYNONYM_MAP.items():
        text = re.sub(pattern, lambda m: m.group(0) + " " + expansion, text,
                      flags=re.IGNORECASE)
    return text


# ── Constants ──────────────────────────────────────────────────────────────────
RESUME_SECTIONS = ["skills", "experience_summary", "projects", "education", "certifications"]
JD_SECTIONS     = ["required_skills", "preferred_skills", "responsibilities", "qualifications"]

_embed_cache: dict = {}
_vectorizer         = None
_N_DOMAINS          = 30     # reserved for future domain feature expansion


# ── Universal Extraction Logic ─────────────────────────────────────────────────

def _extract_text_content(data) -> str:
    """Recursively converts any JSON structure into a single text block."""
    if not data:
        return ""
    if isinstance(data, str):
        return data.strip()
    if isinstance(data, list):
        return " ".join(_extract_text_content(item) for item in data if item)
    if isinstance(data, dict):
        return " ".join(_extract_text_content(v) for v in data.values() if v)
    return str(data).strip()


def section_is_empty(text: str) -> bool:
    """Return True when a section produced no usable content."""
    return not text or len(text.strip()) < 3


# ── Name / title helpers ───────────────────────────────────────────────────────

def extract_resume_name(resume: dict) -> str:
    if resume.get("name"):
        return resume["name"]
    for item in resume.get("other", []):
        item = str(item).strip()
        if item and not item.upper().startswith("HEADER"):
            return item
    return resume.get("id", "Unknown")


def extract_jd_title(jd: dict) -> str:
    if jd.get("title"):
        return jd["title"]
    role = jd.get("role", [])
    if isinstance(role, list) and role:
        return str(role[0]).strip().title()
    if isinstance(role, str) and role:
        return role.strip().title()
    return jd.get("id", "Unknown")


# ── Vectorizer ─────────────────────────────────────────────────────────────────

def _get_vectorizer():
    global _vectorizer
    if _vectorizer is None:
        _vectorizer = TfidfVectorizer(
            ngram_range=(1, 3),
            max_features=4000,          # FIX: was 2000; more features = better coverage
            sublinear_tf=True,          # FIX: log(1+tf) dampens term-frequency dominance
            min_df=1,
            stop_words="english",
        )
        _vectorizer.fit(_DOMAIN_CORPUS)
    return _vectorizer


def normalise(text) -> str:
    raw = _extract_text_content(text).lower().strip()
    return _apply_synonyms(raw)          # FIX: inject synonyms before embedding


# ── Public embed API ───────────────────────────────────────────────────────────

def embed(text) -> np.ndarray:
    return embed_batch([text])[0]


def embed_batch(texts: list) -> np.ndarray:
    vect      = _get_vectorizer()
    normalised = [normalise(t) for t in texts]
    hashes    = [hashlib.md5(t.encode()).hexdigest() for t in normalised]

    uncached = [i for i, h in enumerate(hashes)
                if h not in _embed_cache and normalised[i]]

    if uncached:
        txts   = [normalised[i] for i in uncached]
        tfidf  = vect.transform(txts).toarray().astype(np.float32)
        domain = np.zeros((len(txts), _N_DOMAINS), dtype=np.float32)
        combined = np.concatenate([tfidf, domain], axis=1)

        norms = np.linalg.norm(combined, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        combined = combined / norms

        for i, idx in enumerate(uncached):
            _embed_cache[hashes[idx]] = combined[i]

    actual_dim = len(vect.vocabulary_) + _N_DOMAINS
    result     = np.zeros((len(texts), actual_dim), dtype=np.float32)

    for i, (h, t) in enumerate(zip(hashes, normalised)):
        if t:
            result[i] = _embed_cache[h]

    return result


# ── Resume embedding ───────────────────────────────────────────────────────────

def embed_resume(resume: dict) -> dict:
    """
    Maps a sectioned resume JSON → per-section + full embedding dict.

    FIX: empty sections (education, certifications, projects) now fall back
    to the full-document text so their vector is not a hard zero-vector.
    The matcher uses section_is_empty() to know whether to reduce the weight
    of genuinely-missing sections rather than silently penalising them.
    """
    # ── Raw section text extraction ──────────────────────────────
    skills_text = _extract_text_content(resume.get("skills", []))

    exp_parts = []
    for exp in resume.get("experience", []):
        role   = exp.get("role_header", "")
        duties = _extract_text_content(exp.get("duties", []))
        exp_parts.append(f"{role} {duties}")
    experience_text = " ".join(exp_parts)

    projects_text      = _extract_text_content(resume.get("projects", []))
    education_text     = _extract_text_content(resume.get("education", []))
    certifications_text = _extract_text_content(resume.get("certifications", []))

    # ── Build full-document text (always non-empty if resume has any content) ──
    full_text = " ".join(filter(None, [
        skills_text, experience_text, projects_text,
        education_text, certifications_text,
        _extract_text_content(resume.get("other", [])),
    ]))

    # ── FIX: section fallback — prevent hard zero-vectors ────────
    # When a section is genuinely empty, use a short contextual proxy
    # so the cosine similarity degrades gracefully rather than forcing 0.0.
    # The matcher detects this via section_is_empty() and reduces the weight.
    processed = {
        "skills":             skills_text      if not section_is_empty(skills_text)      else full_text,
        "experience_summary": experience_text  if not section_is_empty(experience_text)  else full_text,
        "projects":           projects_text    if not section_is_empty(projects_text)    else experience_text or full_text,
        "education":          education_text   if not section_is_empty(education_text)   else skills_text or full_text,
        "certifications":     certifications_text if not section_is_empty(certifications_text) else skills_text or full_text,
    }

    # Track which sections are genuinely populated (used by matcher for weight adjustment)
    _populated = {
        "skills":             not section_is_empty(skills_text),
        "experience_summary": not section_is_empty(experience_text),
        "projects":           not section_is_empty(projects_text),
        "education":          not section_is_empty(education_text),
        "certifications":     not section_is_empty(certifications_text),
    }

    emb = {section: embed(processed[section]) for section in RESUME_SECTIONS}
    emb["full"]      = embed(full_text if full_text else " ".join(processed.values()))
    emb["_populated"] = _populated   # metadata, not a vector — used by matcher

    return emb


# ── JD embedding ───────────────────────────────────────────────────────────────

def embed_jd(jd: dict) -> dict:
    """
    Maps a parsed JD JSON → per-section + full embedding dict.

    FIX: maps additional common JD field names so real JD JSONs are handled;
    preferred_skills now read from multiple possible key names.
    """
    # Required skills — multiple possible keys
    req_skills_raw = (
        jd.get("skills_required")
        or jd.get("required_skills")
        or jd.get("skills")
        or []
    )

    # Preferred / nice-to-have skills
    pref_skills_raw = (
        jd.get("skills_preferred")
        or jd.get("preferred_skills")
        or jd.get("nice_to_have")
        or []
    )

    # Responsibilities — role description
    responsibilities_raw = (
        jd.get("role")
        or jd.get("responsibilities")
        or jd.get("duties")
        or []
    )

    # Qualifications
    qualifications_raw = list(filter(None, [
        jd.get("experience_required", ""),
        jd.get("education_required", ""),
        jd.get("qualifications", ""),
        jd.get("minimum_qualifications", ""),
    ]))

    processed = {
        "required_skills":  _extract_text_content(req_skills_raw),
        "preferred_skills": _extract_text_content(pref_skills_raw),
        "responsibilities": _extract_text_content(responsibilities_raw),
        "qualifications":   _extract_text_content(qualifications_raw),
    }

    emb = {section: embed(processed[section]) for section in JD_SECTIONS}

    combined       = " ".join(v for v in processed.values() if v)
    emb["full"]    = embed(combined)

    return emb


# ── Cache utilities ────────────────────────────────────────────────────────────

def cache_stats() -> dict:
    return {
        "cached_embeddings": len(_embed_cache),
        "model":             "TF-IDF (4000 features, sublinear_tf) + Synonym Expansion + Domain Features",
    }


def clear_cache():
    global _embed_cache
    _embed_cache = {}
