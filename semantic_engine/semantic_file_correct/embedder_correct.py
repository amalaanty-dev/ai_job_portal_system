"""
semantic_engine/embedder.py
────────────────────────────
Universal Section Extractor: Handles Strings, Lists, and Nested Dicts.
UPDATED: Supports sectioned resume + parsed JD formats
"""

import hashlib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

# ── Domain corpus for TF-IDF fitting ──────────────────────────
_DOMAIN_CORPUS = [
    "Python SQL Tableau Power BI data analytics business intelligence ETL pandas "
    "NumPy statistical analysis data cleaning data visualisation reporting dashboards "
    "KPIs machine learning AI deep learning NLP data science forecasting regression "
    "classification clustering A/B testing Google Analytics Excel pivot tables",

    "Python Java Spring Boot REST API microservices Docker Kubernetes AWS GCP Azure "
    "CI/CD Jenkins Git Agile Scrum PostgreSQL Redis MongoDB event-driven architecture "
    "software engineering backend cloud infrastructure DevOps distributed systems",

    "SQL Python R Tableau Epic EHR ICD-10 coding HIPAA compliance clinical data "
    "health informatics health information management patient outcomes readmission "
    "quality improvement population health SAS SPSS biostatistics public health "
    "healthcare analytics nursing pharmacy billing coding"
]

# ── Constants ──────────────────────────────────────────────────
RESUME_SECTIONS = ["skills", "experience_summary", "projects", "education", "certifications"]
JD_SECTIONS     = ["required_skills", "preferred_skills", "responsibilities", "qualifications"]

_embed_cache = {}
_vectorizer  = None
_N_DOMAINS   = 30


# ── Universal Extraction Logic ────────────────────────────────

def _extract_text_content(data):
    """Recursively converts any JSON structure into a single text block."""
    if not data:
        return ""
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return " ".join([_extract_text_content(item) for item in data])
    if isinstance(data, dict):
        return " ".join([_extract_text_content(v) for v in data.values()])
    return str(data)


def extract_resume_name(resume: dict) -> str:
    """
    Extract candidate name from sectioned resume JSON.
    Sectioned resumes store name as the first item in the 'other' list.
    Falls back to 'name' key if present (sample_data format).
    """
    # Standard key (sample_data / manually created resumes)
    if resume.get("name"):
        return resume["name"]

    # Sectioned format: name is other[0] — first entry before any HEADER line
    other = resume.get("other", [])
    for item in other:
        item = str(item).strip()
        if item and not item.upper().startswith("HEADER"):
            return item

    # Last fallback: use resume id
    return resume.get("id", "Unknown")


def extract_jd_title(jd: dict) -> str:
    """
    Extract job title from parsed JD JSON.
    Parsed JDs store the role as a list under 'role' key.
    Falls back to 'title' key if present (sample_data format).
    """
    # Standard key (sample_data / manually created JDs)
    if jd.get("title"):
        return jd["title"]

    # Parsed JD format: role is a list, first item is the job title
    role = jd.get("role", [])
    if isinstance(role, list) and role:
        return str(role[0]).strip().title()
    if isinstance(role, str) and role:
        return role.strip().title()

    # Last fallback: use JD id
    return jd.get("id", "Unknown")


def _get_vectorizer():
    global _vectorizer
    if _vectorizer is None:
        _vectorizer = TfidfVectorizer(
            ngram_range=(1, 3),
            max_features=2000,
            stop_words='english'
        )
        _vectorizer.fit(_DOMAIN_CORPUS)
    return _vectorizer


def normalise(text):
    return _extract_text_content(text).lower().strip()


# ── Public API ────────────────────────────────────────────────

def embed(text):
    return embed_batch([text])[0]


def embed_batch(texts):
    vect = _get_vectorizer()
    normalised = [normalise(t) for t in texts]

    hashes = [hashlib.md5(t.encode()).hexdigest() for t in normalised]

    # Find uncached
    uncached = [i for i, h in enumerate(hashes)
                if h not in _embed_cache and normalised[i]]

    if uncached:
        txts = [normalised[i] for i in uncached]

        tfidf = vect.transform(txts).toarray().astype(np.float32)

        # Domain placeholder (future expansion)
        domain = np.zeros((len(txts), _N_DOMAINS), dtype=np.float32)

        combined = np.concatenate([tfidf, domain], axis=1)

        norms = np.linalg.norm(combined, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        combined = combined / norms

        for i, idx in enumerate(uncached):
            _embed_cache[hashes[idx]] = combined[i]

    actual_dim = len(vect.vocabulary_) + _N_DOMAINS
    result = np.zeros((len(texts), actual_dim), dtype=np.float32)

    for i, (h, t) in enumerate(zip(hashes, normalised)):
        if t:
            result[i] = _embed_cache[h]

    return result


# ── UPDATED: Resume Embedding (SECTIONED FORMAT SUPPORT) ──────

def embed_resume(resume):
    """Maps sectioned resume JSON → semantic engine format"""

    # 🔹 Skills
    skills = resume.get("skills", [])

    # 🔹 Experience (list of dicts → text)
    experience_entries = resume.get("experience", [])
    exp_text = []
    for exp in experience_entries:
        role = exp.get("role_header", "")
        duties = exp.get("duties", [])
        exp_text.append(role + " " + _extract_text_content(duties))

    # 🔹 Projects
    projects = resume.get("projects", [])

    # 🔹 Education & Certifications
    education = resume.get("education", [])
    certifications = resume.get("certifications", [])

    processed = {
        "skills": skills,
        "experience_summary": " ".join(exp_text),
        "projects": projects,
        "education": education,
        "certifications": certifications
    }

    # Normalize all sections
    processed = {k: _extract_text_content(v) for k, v in processed.items()}

    # Generate embeddings
    emb = {section: embed(processed.get(section, "")) for section in RESUME_SECTIONS}

    # Full embedding
    emb["full"] = embed(" ".join(processed.values()))

    return emb


# ── UPDATED: JD Embedding (PARSED JD SUPPORT) ─────────────────

def embed_jd(jd):
    """Maps parsed JD JSON → semantic engine format"""

    processed = {
        "required_skills": jd.get("skills_required", []),
        "preferred_skills": [],
        "responsibilities": jd.get("role", []),
        "qualifications": [
            jd.get("experience_required", ""),
            jd.get("education_required", "")
        ]
    }

    processed = {k: _extract_text_content(v) for k, v in processed.items()}

    emb = {section: embed(processed.get(section, "")) for section in JD_SECTIONS}

    combined = " ".join(processed.values())
    emb["full"] = embed(combined)

    return emb


# ── Cache Utilities ───────────────────────────────────────────

def cache_stats():
    return {
        "cached_embeddings": len(_embed_cache),
        "model": "TF-IDF + Domain Features"
    }


def clear_cache():
    global _embed_cache
    _embed_cache = {}