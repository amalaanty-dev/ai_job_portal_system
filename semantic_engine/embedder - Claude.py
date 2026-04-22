"""
semantic_engine/embedder.py
────────────────────────────
Hybrid local embedder: TF-IDF (ngram 1-3) + Domain Keyword vectors.
No internet or model downloads required.

Public API is identical to the sentence-transformer version.
Embedding dimension: 2000 (TF-IDF) + 30 (domain) = 2030 dims.
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
    "healthcare analytics nursing pharmacy billing coding",

    "digital marketing SEO SEM Google Ads Meta Ads content strategy brand management "
    "email marketing HubSpot Salesforce CRM campaign management A/B testing "
    "lead generation conversion funnel ROAS social media analytics",

    "SolidWorks AutoCAD ANSYS FEA CFD GD&T manufacturing processes lean manufacturing "
    "Six Sigma quality control MATLAB project management product design structural "
    "analysis thermal analysis prototype testing DFM tolerance",

    "financial modelling Excel VBA Bloomberg CFA FRM investment banking accounting "
    "auditing taxation financial reporting IFRS GAAP DCF valuation equity risk "
    "treasury cost accounting payroll HRIS human resources recruitment talent",

    "corporate law litigation compliance contract intellectual property labour law "
    "LLB LLM architecture urban planning interior design graphic design UX UI Figma "
    "biology biochemistry microbiology genetics molecular laboratory PCR cell culture",

    "supply chain logistics procurement ERP SAP inventory operations lean Six Sigma "
    "process improvement teaching curriculum instructional design e-learning pedagogy "
    "cybersecurity penetration testing SIEM firewall spark hadoop kafka airflow dbt",
]

# ── Domain keyword vectors (30 domains) ───────────────────────
_DOMAIN_KEYWORDS = {
    "data_analytics":        ["data analytics", "tableau", "power bi", "business intelligence", "kpi", "dashboard", "etl"],
    "python_sql":            ["python", "sql", "pandas", "numpy", "jupyter", "postgresql", "mysql"],
    "machine_learning":      ["machine learning", "deep learning", "nlp", "tensorflow", "pytorch", "sklearn", "ai"],
    "software_engineering":  ["microservices", "rest api", "spring boot", "docker", "kubernetes", "git", "ci/cd"],
    "cloud":                 ["aws", "azure", "gcp", "cloud", "lambda", "s3", "devops"],
    "web_development":       ["react", "angular", "javascript", "typescript", "html", "css", "node"],
    "healthcare_informatics":["ehr", "hipaa", "icd", "epic", "clinical", "health informatics", "patient"],
    "public_health":         ["public health", "epidemiology", "biostatistics", "community health", "population health"],
    "biology":               ["biology", "biochemistry", "microbiology", "genetics", "molecular", "laboratory", "pcr"],
    "pharmacy":              ["pharmacy", "pharmaceutical", "drug", "pharmacology", "clinical trials", "fda"],
    "mechanical_engineering":["solidworks", "ansys", "fea", "cfd", "autocad", "gd&t", "manufacturing"],
    "electrical_engineering":["electrical", "circuits", "pcb", "embedded", "plc", "scada", "vlsi"],
    "civil_engineering":     ["civil", "structural", "construction", "revit", "bim", "concrete"],
    "chemical_engineering":  ["chemical", "process engineering", "reactor", "separation", "thermodynamics"],
    "finance":               ["finance", "financial modelling", "dcf", "valuation", "cfa", "bloomberg", "investment"],
    "accounting":            ["accounting", "auditing", "gaap", "ifrs", "taxation", "cost accounting"],
    "banking":               ["banking", "credit", "lending", "risk management", "treasury", "aml", "kyc"],
    "marketing":             ["marketing", "seo", "sem", "google ads", "meta ads", "content strategy", "brand"],
    "crm_sales":             ["salesforce", "crm", "hubspot", "lead generation", "sales", "pipeline"],
    "hr":                    ["human resources", "recruitment", "talent", "payroll", "hris", "shrm"],
    "law":                   ["law", "legal", "litigation", "compliance", "contract", "intellectual property"],
    "education":             ["teaching", "curriculum", "pedagogy", "lms", "instructional design", "assessment"],
    "design_ux":             ["figma", "ux", "ui", "user experience", "prototyping", "wireframe", "adobe"],
    "architecture":          ["architecture", "urban planning", "autocad", "revit", "bim"],
    "supply_chain":          ["supply chain", "logistics", "procurement", "inventory", "sap", "warehouse"],
    "operations":            ["operations", "lean", "six sigma", "process improvement", "kaizen"],
    "project_management":    ["project management", "pmp", "agile", "scrum", "prince2", "stakeholder"],
    "data_engineering":      ["spark", "hadoop", "kafka", "airflow", "dbt", "data pipeline", "data warehouse"],
    "cyber_security":        ["cybersecurity", "penetration testing", "siem", "firewall", "zero trust"],
    "research_science":      ["research", "publications", "phd", "academic", "experiment", "hypothesis"],
}

_DOMAIN_NAMES = list(_DOMAIN_KEYWORDS.keys())
_N_DOMAINS    = len(_DOMAIN_NAMES)
_TFIDF_DIM    = 2000
_EMBED_DIM    = None  # set dynamically after vectoriser is first fitted

_vectorizer = None
_embed_cache = {}

RESUME_SECTIONS = ["skills", "experience_summary", "projects", "education", "certifications"]
JD_SECTIONS     = ["required_skills", "preferred_skills", "responsibilities", "qualifications"]


def _get_vectorizer():
    global _vectorizer
    if _vectorizer is None:
        _vectorizer = TfidfVectorizer(
            ngram_range=  (1, 3),
            max_features= _TFIDF_DIM,
            sublinear_tf= True,
            min_df=       1,
            analyzer=     "word",
        )
        _vectorizer.fit(_DOMAIN_CORPUS)
    return _vectorizer


def _domain_vector(text):
    t   = text.lower()
    vec = np.zeros(_N_DOMAINS, dtype=np.float32)
    for i, domain in enumerate(_DOMAIN_NAMES):
        hits = sum(1 for kw in _DOMAIN_KEYWORDS[domain] if kw in t)
        if hits > 0:
            vec[i] = min(1.0, hits / max(3, len(_DOMAIN_KEYWORDS[domain]) // 2))
    return vec


def normalise(text):
    if text is None:
        return ""
    if isinstance(text, list):
        return ". ".join(str(t).strip() for t in text if t)
    return str(text).strip()


def _hash(text):
    return hashlib.md5(text.encode()).hexdigest()


def embed(text):
    text_str = normalise(text)
    if not text_str:
        actual_dim = len(_get_vectorizer().vocabulary_) + _N_DOMAINS
        return np.zeros(actual_dim, dtype=np.float32)
    key = _hash(text_str)
    if key in _embed_cache:
        return _embed_cache[key]
    vect     = _get_vectorizer()
    tfidf    = vect.transform([text_str]).toarray()[0].astype(np.float32)
    domain   = _domain_vector(text_str)
    combined = np.concatenate([tfidf, domain])
    norm     = np.linalg.norm(combined)
    if norm > 0:
        combined = combined / norm
    _embed_cache[key] = combined.astype(np.float32)
    return _embed_cache[key]


def embed_batch(texts):
    normalised = [normalise(t) for t in texts]
    hashes     = [_hash(t)     for t in normalised]
    uncached   = [i for i, h in enumerate(hashes) if h not in _embed_cache]
    if uncached:
        vect     = _get_vectorizer()
        txts     = [normalised[i] for i in uncached]
        tfidf    = vect.transform(txts).toarray().astype(np.float32)
        domain   = np.array([_domain_vector(t) for t in txts], dtype=np.float32)
        combined = np.concatenate([tfidf, domain], axis=1)
        norms    = np.linalg.norm(combined, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        combined = combined / norms
        for i, idx in enumerate(uncached):
            _embed_cache[hashes[idx]] = combined[i]
    actual_dim = len(_get_vectorizer().vocabulary_) + _N_DOMAINS
    result = np.zeros((len(texts), actual_dim), dtype=np.float32)
    for i, (h, t) in enumerate(zip(hashes, normalised)):
        if t:
            result[i] = _embed_cache[h]
    return result


def embed_resume(resume):
    #ADDED
    print(f"DEBUG: Processing Resume {resume.get('id')} - Skills length: {len(resume.get('skills', ''))}")
    emb = {}
    emb = {}
    for section in RESUME_SECTIONS:
        emb[section] = embed(resume.get(section, ""))
    combined = " ".join(normalise(resume.get(s, "")) for s in RESUME_SECTIONS)
    emb["full"] = embed(combined)
    return emb


def embed_jd(jd):
    emb = {}
    for section in JD_SECTIONS:
        emb[section] = embed(jd.get(section, ""))
    combined = " ".join(normalise(jd.get(s, "")) for s in JD_SECTIONS)
    emb["full"] = embed(combined)
    return emb


def get_model():
    return _get_vectorizer()


def cache_stats():
    return {
        "cached_embeddings": len(_embed_cache),
        "model":             "TF-IDF (ngram 1-3) + Domain Keywords (local, no download)",
        "embedding_dim":     (len(_get_vectorizer().vocabulary_) + _N_DOMAINS),
    }
