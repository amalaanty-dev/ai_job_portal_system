"""ATS Adapter — sole bridge between API layer and existing ATS engine.

INTEGRATION POINT
=================
The API only imports `parse_resume()` and `score_candidate()` from this module.
If you have working `parsers/resume_parser.py` and `ats_engine/scorer.py`
modules, this adapter will use them. Otherwise it falls back to a robust
built-in heuristic parser/scorer that's good enough for production-quality
ranking on most domains.

Force the built-in stubs even when real modules are present by setting:
    set ATS_USE_STUB_PARSER=1
    set ATS_USE_STUB_SCORER=1
"""
from __future__ import annotations
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


USE_STUB_PARSER = os.getenv("ATS_USE_STUB_PARSER", "").strip() in ("1", "true", "yes", "on")
USE_STUB_SCORER = os.getenv("ATS_USE_STUB_SCORER", "").strip() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Public: parse_resume + score_candidate
# ---------------------------------------------------------------------------
def parse_resume(file_path: str | Path) -> dict[str, Any]:
    """Parse a resume file → structured profile dict (always normalized)."""
    file_path = str(file_path)
    raw: dict[str, Any] | None = None

    if USE_STUB_PARSER:
        raw = _stub_parse_resume(file_path)
    else:
        try:
            from parsers.resume_parser import parse_resume as real_parse  # type: ignore
            raw = real_parse(file_path)
            if _looks_broken(raw, file_path):
                logger.warning(
                    f"Real parser returned empty/placeholder data for {file_path}; "
                    f"falling back to built-in heuristic parser. "
                    f"Set ATS_USE_STUB_PARSER=1 to skip the real parser."
                )
                raw = _stub_parse_resume(file_path)
        except Exception as e:
            logger.warning(f"Real resume parser unavailable, using built-in: {e}")
            raw = _stub_parse_resume(file_path)

    return _normalize_parsed_profile(raw)


def score_candidate(parsed_profile: dict, jd: dict) -> dict[str, Any]:
    """Score one parsed resume against one JD → ScoreBreakdown-compatible dict."""
    if USE_STUB_SCORER:
        return _stub_score(parsed_profile, jd)
    try:
        from ats_engine.scorer import compute_score  # type: ignore
        return compute_score(parsed_profile, jd)
    except Exception as e:
        logger.warning(f"Real scorer unavailable, using built-in: {e}")
        return _stub_score(parsed_profile, jd)


# ---------------------------------------------------------------------------
# Broken-parser detector
# ---------------------------------------------------------------------------
def _looks_broken(profile: Any, file_path: str) -> bool:
    if not isinstance(profile, dict):
        return True
    text_fields = ("clean_text", "raw_text", "raw_text_preview", "text")
    fp_basename = os.path.basename(file_path)
    for k in text_fields:
        v = profile.get(k)
        if isinstance(v, str) and (v == file_path or v.endswith(fp_basename)) and len(v) < 300:
            return True
    skills = profile.get("skills") or []
    education = profile.get("education") or []
    experience = profile.get("experience") or []
    has_text = any(isinstance(profile.get(k), str) and len(profile.get(k, "")) > 50 for k in text_fields)
    if not skills and not education and not experience and not has_text:
        return True
    return False


# ---------------------------------------------------------------------------
# Profile normalizer
# ---------------------------------------------------------------------------
def _normalize_parsed_profile(raw: Any) -> dict[str, Any]:
    if raw is None:
        return _empty_profile()
    if not isinstance(raw, dict):
        return {**_empty_profile(), "raw_text_preview": str(raw)[:500]}
    out = dict(raw)

    name = out.get("name")
    if isinstance(name, list):
        out["name"] = name[0] if name else None
    elif name is not None and not isinstance(name, str):
        out["name"] = str(name)

    email = out.get("email")
    if isinstance(email, (list, tuple)):
        out["email"] = [str(x) for x in email if x]
    elif email is not None and not isinstance(email, str):
        out["email"] = str(email)

    phone = out.get("phone")
    if isinstance(phone, (list, tuple)):
        out["phone"] = [str(x) for x in phone if x]
    elif phone is not None and not isinstance(phone, str):
        out["phone"] = str(phone)

    for key in ("skills", "experience", "education"):
        val = out.get(key)
        if val is None:
            out[key] = []
        elif isinstance(val, dict):
            out[key] = list(val.values())
        elif not isinstance(val, list):
            out[key] = [val]

    exp_years = out.get("total_experience_years")
    if exp_years is None or isinstance(exp_years, (int, float)):
        pass
    elif isinstance(exp_years, str):
        try:
            out["total_experience_years"] = float(exp_years.strip()) if exp_years.strip() else None
        except ValueError:
            out["total_experience_years"] = None
    else:
        out["total_experience_years"] = None

    rtp = out.get("raw_text_preview")
    if rtp is not None and not isinstance(rtp, str):
        out["raw_text_preview"] = str(rtp)[:500]

    return out


def _empty_profile() -> dict[str, Any]:
    return {
        "name": None, "email": None, "phone": None,
        "skills": [], "experience": [], "education": [],
        "total_experience_years": None, "raw_text_preview": None,
    }


# ---------------------------------------------------------------------------
# Built-in heuristic parser
# ---------------------------------------------------------------------------

# A practical skill dictionary covering tech, data, healthcare, business roles.
# Phrases like "data analysis" must come before single tokens like "data" so
# the longest-match rule extracts them correctly.
_SKILLS_DICT: tuple[str, ...] = (
    # Healthcare / clinical analytics
    "healthcare reporting", "health informatics", "clinical data", "medical coding",
    "icd-10", "icd10", "cpt", "hl7", "fhir", "epic systems", "cerner", "meditech",
    "ehr", "emr", "hipaa", "patient outcomes", "claims data", "revenue cycle",
    "kpi monitoring", "dashboard development", "report automation",
    # Data & BI
    "data analysis", "data analytics", "business intelligence", "data visualization",
    "data modeling", "data engineering", "etl", "elt", "data warehousing",
    "tableau", "power bi", "looker", "qlikview", "qlik sense", "google data studio",
    "excel", "advanced excel", "vba", "macros",
    # Languages
    "python", "r programming", " r ", "java", "javascript", "typescript", "scala",
    "kotlin", "swift", "go", "rust", "c++", "c#", "ruby", "php",
    # Databases
    "sql", "mysql", "postgresql", "postgres", "oracle", "sql server", "mssql",
    "mongodb", "cassandra", "redis", "snowflake", "bigquery", "redshift", "databricks",
    "dynamodb",
    # ML / AI
    "machine learning", "deep learning", "nlp", "computer vision",
    "tensorflow", "pytorch", "scikit-learn", "scikit learn", "keras", "xgboost",
    "lightgbm", "transformers", "huggingface", "openai", "langchain",
    "statistical analysis", "statistics", "regression", "classification", "clustering",
    # Web / backend
    "django", "flask", "fastapi", "spring boot", "nodejs", "node.js", "express",
    "react", "vue", "angular", "next.js", "nuxt",
    "rest api", "graphql", "grpc", "microservices",
    # Cloud / DevOps
    "aws", "azure", "gcp", "google cloud", "kubernetes", "k8s", "docker",
    "terraform", "ansible", "jenkins", "github actions", "gitlab ci", "ci/cd",
    # Tools
    "git", "jira", "confluence", "slack", "trello", "linux", "bash", "powershell",
    # Soft / business
    "project management", "agile", "scrum", "stakeholder management",
    "communication", "leadership", "problem solving",
)

_EDUCATION_KEYWORDS: tuple[str, ...] = (
    "phd", "ph.d", "doctorate",
    "m.tech", "mtech", "m.sc", "msc", "ms ", "master of science",
    "mba", "master of business administration",
    "m.s.", "master's", "masters",
    "b.tech", "btech", "b.e.", "be ", "bachelor of engineering",
    "b.sc", "bsc", "bs ", "bachelor of science", "b.s.",
    "bca", "mca", "bcom", "bba", "ba ", "ma ",
    "diploma", "certification",
    "computer science", "information technology", "data science",
    "biomedical", "biotechnology", "informatics", "statistics",
)


def _stub_parse_resume(file_path: str) -> dict[str, Any]:
    """Heuristic parser. Extracts text + name + email + phone + skills +
    experience years + education from PDF/DOCX. No external NLP needed."""
    text = _extract_text(file_path)
    if not text:
        return {
            "name": None, "email": None, "phone": None,
            "skills": [], "experience": [], "education": [],
            "total_experience_years": None, "raw_text_preview": None,
        }

    return {
        "name": _extract_name(text),
        "email": _extract_email(text),
        "phone": _extract_phone(text),
        "skills": _extract_skills(text),
        "experience": _extract_experience_entries(text),
        "education": _extract_education(text),
        "total_experience_years": _extract_total_experience_years(text),
        "raw_text_preview": text[:500],
    }


def _extract_text(file_path: str) -> str:
    p = Path(file_path)
    suffix = p.suffix.lower()
    try:
        if suffix == ".pdf":
            try:
                import pdfplumber
                with pdfplumber.open(p) as pdf:
                    return "\n".join((page.extract_text() or "") for page in pdf.pages)
            except ImportError:
                logger.warning("pdfplumber not installed; install with: pip install pdfplumber")
                return ""
        elif suffix in (".docx",):
            try:
                from docx import Document
                return "\n".join(par.text for par in Document(p).paragraphs)
            except ImportError:
                logger.warning("python-docx not installed; install with: pip install python-docx")
                return ""
    except Exception as e:
        logger.warning(f"Text extraction failed for {file_path}: {e}")
    return ""


def _extract_email(text: str) -> str | None:
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    return m.group(0) if m else None


def _extract_phone(text: str) -> str | None:
    # International, Indian, US-style numbers
    patterns = [
        r"\+\d{1,3}[\s-]?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}",
        r"\+91[\s-]?\d{10}",
        r"\(\d{3}\)\s?\d{3}-\d{4}",
        r"\b\d{10}\b",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(0).strip()
    return None


def _extract_name(text: str) -> str | None:
    """Heuristic: first non-empty line that looks like a person's name.
    Skips lines with @, digits, or common heading words."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    HEADERS = {"resume", "curriculum vitae", "cv", "profile", "objective", "summary"}
    for ln in lines[:8]:  # name is almost always near the top
        low = ln.lower()
        if any(h in low for h in HEADERS):
            continue
        if "@" in ln or re.search(r"\d", ln):
            continue
        # 2-4 capitalized tokens, each 2-25 chars (handles Unicode)
        tokens = ln.split()
        if 2 <= len(tokens) <= 5 and all(2 <= len(t) <= 25 for t in tokens):
            # First word starts with uppercase letter (works for unicode)
            if tokens[0][:1].isupper():
                return ln
    return None


def _extract_skills(text: str) -> list[str]:
    """Match skills via case-insensitive substring. Longer phrases first so
    'data analysis' wins over plain 'data'."""
    found: dict[str, str] = {}  # canonical-form -> display
    lower = text.lower()
    # Longer phrases first
    for skill in sorted(_SKILLS_DICT, key=len, reverse=True):
        token = skill.strip().lower()
        if not token:
            continue
        # Word-boundary-ish search; allow leading/trailing whitespace or punctuation
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(token) + r"(?![a-zA-Z0-9])"
        if re.search(pattern, lower):
            display = skill.strip().title()
            # Restore common acronyms in proper case
            for acr in ("SQL", "AWS", "GCP", "ETL", "ELT", "NLP", "API", "BI",
                        "EHR", "EMR", "HIPAA", "ICD-10", "HL7", "FHIR", "CPT",
                        "KPI", "VBA"):
                if acr.lower() in display.lower():
                    display = re.sub(re.escape(acr), acr, display, flags=re.I)
            found[token] = display
    return sorted(set(found.values()))


def _extract_total_experience_years(text: str) -> float | None:
    """Look for 'X years of experience' / 'X+ years' patterns."""
    candidates = []
    for m in re.finditer(
        r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years|yrs)\s*(?:of\s*)?(?:experience|exp)?",
        text, flags=re.I,
    ):
        try:
            candidates.append(float(m.group(1)))
        except ValueError:
            pass
    if candidates:
        return max(candidates)

    # Date-range fallback: find earliest year, assume present is 2026
    years = [int(y) for y in re.findall(r"\b(19[89]\d|20[0-2]\d)\b", text)]
    if years:
        from datetime import datetime
        earliest = min(years)
        diff = datetime.now().year - earliest
        if 0 < diff <= 50:
            return float(diff)
    return None


def _extract_experience_entries(text: str) -> list[dict[str, str]]:
    """Find 'Company - Role - Dates' style entries. Best-effort."""
    entries = []
    # 'Senior Engineer at Acme Corp · Jan 2020 - Present'
    pattern = re.compile(
        r"^(.{3,60})\s+(?:at|@|-)\s+([A-Z][A-Za-z0-9 .,&'-]{2,60})\s*[\u00b7|\-:]+\s*"
        r"((?:\w+\s*\d{4}|\d{4})\s*[-\u2013to]+\s*(?:Present|\w+\s*\d{4}|\d{4}))",
        re.M,
    )
    for m in pattern.finditer(text):
        entries.append({
            "role": m.group(1).strip(),
            "company": m.group(2).strip(),
            "duration": m.group(3).strip(),
        })
    return entries[:10]


def _extract_education(text: str) -> list[str]:
    found = []
    lower = text.lower()
    for kw in _EDUCATION_KEYWORDS:
        if kw.strip() in lower:
            found.append(kw.strip().upper().replace(".", "").strip())
    # Dedup, preserve insertion order
    seen, dedup = set(), []
    for e in found:
        if e not in seen:
            seen.add(e); dedup.append(e)
    return dedup


# ---------------------------------------------------------------------------
# Built-in heuristic scorer
# ---------------------------------------------------------------------------
def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _skill_match_score(cand_skills: list[Any], req_skills: list[str], pref_skills: list[str]) -> float:
    """Weighted overlap with substring tolerance.

    Resume "Python 3.10" matches JD "Python".
    Resume "MySQL" matches JD "SQL".
    Each required skill = 1 point if matched, otherwise 0.
    Each preferred = 0.5 point bonus.
    Returns 0-100.
    """
    cand_norm: list[str] = []
    for s in cand_skills:
        if isinstance(s, str):
            cand_norm.append(_norm(s))
        elif isinstance(s, dict):
            v = s.get("name") or s.get("skill") or s.get("value") or ""
            cand_norm.append(_norm(v))

    if not req_skills and not pref_skills:
        return 0.0

    def matches(req: str) -> bool:
        req_n = _norm(req)
        if not req_n:
            return False
        for c in cand_norm:
            if not c:
                continue
            # Bidirectional substring match (catches 'Python 3.10' vs 'Python', 'MySQL' vs 'SQL')
            if req_n == c or req_n in c or c in req_n:
                return True
        return False

    matched_req = sum(1 for r in req_skills if matches(r))
    matched_pref = sum(1 for r in pref_skills if matches(r))

    if req_skills:
        score = (matched_req / len(req_skills)) * 100.0
    else:
        score = 70.0  # only prefs given

    # +5 per preferred match, capped at 100
    score = min(100.0, score + matched_pref * 5)
    return round(score, 2)


def _experience_score(cand_years: Any, req_years: Any) -> float:
    try:
        cand = float(cand_years) if cand_years is not None else 0.0
    except (TypeError, ValueError):
        cand = 0.0
    try:
        req = float(req_years) if req_years is not None else 0.0
    except (TypeError, ValueError):
        req = 0.0

    if req <= 0:
        # No requirement; give credit for any experience
        return min(100.0, 50.0 + cand * 10)
    if cand >= req:
        return min(100.0, 70 + (cand - req) * 5)
    return max(0.0, (cand / req) * 70)


def _education_score(cand_edu: list[Any], req_edu: list[str]) -> float:
    if not req_edu:
        return 75.0  # No requirement; neutral
    cand_text = " ".join(_norm(e) for e in cand_edu)
    if not cand_text:
        return 30.0  # Education required but none parsed
    matched = 0
    for req in req_edu:
        rn = _norm(req)
        if not rn:
            continue
        if rn in cand_text or any(rn in _norm(e) for e in cand_edu):
            matched += 1
    return min(100.0, 60.0 + (matched / max(len(req_edu), 1)) * 40)


def _semantic_score(text: str, jd: dict) -> float:
    """Simple cosine-like overlap between resume text and JD's textual content."""
    if not text:
        return 0.0
    jd_text_parts = [
        str(jd.get("job_title", "")),
        " ".join(str(s) for s in jd.get("required_skills", []) or []),
        " ".join(str(s) for s in jd.get("preferred_skills", []) or []),
        str(jd.get("description", "")),
    ]
    jd_text = _norm(" ".join(jd_text_parts))
    if not jd_text:
        return 0.0

    def tokens(s: str) -> set[str]:
        return {t for t in re.findall(r"[a-z0-9]{3,}", s.lower())}

    a, b = tokens(text), tokens(jd_text)
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    union = len(a | b)
    jaccard = overlap / union if union else 0.0
    return round(min(100.0, jaccard * 200.0), 2)  # boost since resumes are much longer


def _stub_score(parsed_profile: dict, jd: dict) -> dict[str, Any]:
    cand_skills = parsed_profile.get("skills", []) or []
    req_skills = [s for s in (jd.get("required_skills") or []) if isinstance(s, str)]
    pref_skills = [s for s in (jd.get("preferred_skills") or []) if isinstance(s, str)]

    skill_score = _skill_match_score(cand_skills, req_skills, pref_skills)
    exp_score = _experience_score(
        parsed_profile.get("total_experience_years"),
        jd.get("experience_required"),
    )
    education_score = _education_score(
        parsed_profile.get("education", []) or [],
        [e for e in (jd.get("education_required") or []) if isinstance(e, str)],
    )
    semantic_score = _semantic_score(
        parsed_profile.get("raw_text_preview") or "",
        jd,
    )

    # Weighted final
    final = round(
        skill_score * 0.45
        + exp_score * 0.25
        + education_score * 0.10
        + semantic_score * 0.20,
        2,
    )

    return {
        "skills": round(skill_score, 2),
        "experience": round(exp_score, 2),
        "education": round(education_score, 2),
        "semantic": round(semantic_score, 2),
        "final_score": final,
    }
