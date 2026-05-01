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

    for key in ("skills", "experience", "education", "certifications", "projects"):
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
        "certifications": [], "projects": [],
        "total_experience_years": None, "raw_text_preview": None,
    }


# ---------------------------------------------------------------------------
# Built-in heuristic parser
# ---------------------------------------------------------------------------

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

# Section header keywords to detect resume sections
_SECTION_HEADERS = re.compile(
    r"^\s*(experience|work experience|employment|professional experience|"
    r"education|academic|qualification|"
    r"skills|technical skills|core skills|"
    r"projects?|personal projects?|academic projects?|"
    r"certifications?|certificates?|licenses?|achievements?|"
    r"summary|objective|profile)\s*$",
    re.I | re.M,
)


def _split_sections(text: str) -> dict[str, str]:
    """Split resume text into named sections."""
    sections: dict[str, str] = {}
    matches = list(_SECTION_HEADERS.finditer(text))
    for i, m in enumerate(matches):
        header = m.group(1).strip().lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[header] = text[start:end].strip()
    return sections


def _stub_parse_resume(file_path: str) -> dict[str, Any]:
    """Heuristic parser. Extracts text + name + email + phone + skills +
    experience years + education + certifications + projects from PDF/DOCX."""
    text = _extract_text(file_path)
    if not text:
        return {
            "name": None, "email": None, "phone": None,
            "skills": [], "experience": [], "education": [],
            "certifications": [], "projects": [],
            "total_experience_years": None, "raw_text_preview": None,
        }

    sections = _split_sections(text)

    return {
        "name": _extract_name(text),
        "email": _extract_email(text),
        "phone": _extract_phone(text),
        "skills": _extract_skills(text),
        "experience": _extract_experience_entries(text, sections),
        "education": _extract_education(text),
        "certifications": _extract_certifications(text, sections),
        "projects": _extract_projects(text, sections),
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
    Handles 2-5 tokens, skips headers, emails, digits, and location lines."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    SKIP = {"resume", "curriculum vitae", "cv", "profile", "objective", "summary",
            "page", "address", "linkedin", "github", "portfolio"}
    for ln in lines[:10]:
        low = ln.lower()
        # Skip known header words
        if any(h in low for h in SKIP):
            continue
        # Skip lines with email, URLs, digits, pipes, bullets
        if "@" in ln or re.search(r"[\d|•·/\\]", ln):
            continue
        # Skip lines that look like job titles (contain common title words)
        if re.search(r"\b(engineer|analyst|developer|manager|specialist|consultant|"
                     r"scientist|designer|director|intern|associate)\b", low):
            continue
        tokens = ln.split()
        # Name: 2-5 words, each 2-30 chars, first word capitalized
        if 2 <= len(tokens) <= 5 and all(2 <= len(t) <= 30 for t in tokens):
            if tokens[0][:1].isupper():
                # Allow names like "AMALA P ANTY" (all caps also valid)
                if all(re.match(r"^[A-Za-z][A-Za-z'-]*\.?$", t) for t in tokens):
                    # Title-case the result for consistency
                    return " ".join(t.capitalize() for t in tokens)
    return None


def _extract_skills(text: str) -> list[str]:
    """Match skills via case-insensitive substring. Longer phrases first."""
    found: dict[str, str] = {}
    lower = text.lower()
    for skill in sorted(_SKILLS_DICT, key=len, reverse=True):
        token = skill.strip().lower()
        if not token:
            continue
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(token) + r"(?![a-zA-Z0-9])"
        if re.search(pattern, lower):
            display = skill.strip().title()
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

    # Date-range fallback
    years = [int(y) for y in re.findall(r"\b(19[89]\d|20[0-2]\d)\b", text)]
    if years:
        from datetime import datetime
        earliest = min(years)
        diff = datetime.now().year - earliest
        if 0 < diff <= 50:
            return float(diff)
    return None


def _extract_experience_entries(text: str, sections: dict[str, str] | None = None) -> list[dict[str, str]]:
    """Extract work experience entries. Uses section text if available, falls back to full text."""
    # Use experience section text if detected
    search_text = text
    if sections:
        for key in ("experience", "work experience", "employment", "professional experience"):
            if key in sections and sections[key]:
                search_text = sections[key]
                break

    entries = []

    # Pattern 1: "Role at/@ Company · Jan 2020 - Present"
    pattern1 = re.compile(
        r"^(.{3,60})\s+(?:at|@|-)\s+([A-Z][A-Za-z0-9 .,&'-]{2,60})\s*[\u00b7|\-:]+\s*"
        r"((?:\w+\s*\d{4}|\d{4})\s*[-\u2013to]+\s*(?:Present|\w+\s*\d{4}|\d{4}))",
        re.M,
    )
    for m in pattern1.finditer(search_text):
        entries.append({
            "role": m.group(1).strip(),
            "company": m.group(2).strip(),
            "duration": m.group(3).strip(),
        })

    # Pattern 2: Lines with date ranges like "Jan 2020 – Dec 2022" or "2019 - Present"
    # preceded by a company/role line
    if not entries:
        date_pattern = re.compile(
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4})"
            r"\s*[-\u2013\u2014to]+\s*"
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4}|Present|present|Current|current)",
            re.I,
        )
        lines = search_text.splitlines()
        for i, line in enumerate(lines):
            if date_pattern.search(line):
                duration = date_pattern.search(line).group(0).strip()
                # Look at surrounding lines for role/company
                context_lines = [l.strip() for l in lines[max(0, i-2):i] if l.strip()]
                role = context_lines[-1] if context_lines else line.strip()
                company = context_lines[-2] if len(context_lines) >= 2 else ""
                if role and len(role) > 3:
                    entries.append({
                        "role": role[:80],
                        "company": company[:80],
                        "duration": duration,
                    })

    # Deduplicate
    seen, dedup = set(), []
    for e in entries:
        key = (e["role"][:30], e["duration"][:20])
        if key not in seen:
            seen.add(key)
            dedup.append(e)

    return dedup[:10]


def _extract_education(text: str) -> list[str]:
    found = []
    lower = text.lower()
    for kw in _EDUCATION_KEYWORDS:
        if kw.strip() in lower:
            found.append(kw.strip().upper().replace(".", "").strip())
    seen, dedup = set(), []
    for e in found:
        if e not in seen:
            seen.add(e); dedup.append(e)
    return dedup


def _extract_certifications(text: str, sections: dict[str, str] | None = None) -> list[str]:
    """Extract certifications from dedicated section or inline mentions."""
    certs = []

    # Use certifications section if available
    search_text = ""
    if sections:
        for key in ("certifications", "certification", "certificates", "licenses", "achievements"):
            if key in sections and sections[key]:
                search_text = sections[key]
                break

    # Known cert patterns to find anywhere in text
    cert_patterns = [
        r"AWS\s+(?:Certified\s+)?[\w\s]+(?:Associate|Professional|Specialty|Practitioner)",
        r"Google\s+(?:Cloud\s+)?(?:Certified\s+)?[\w\s]+",
        r"Microsoft\s+(?:Certified\s+)?[\w\s]+(?:Associate|Expert|Fundamentals)",
        r"(?:PMP|CISSP|CISA|CISM|CEH|OSCP|CPA|CFA|FRM|SHRM|PHR|SPHR)",
        r"Certified\s+[\w\s]{3,50}(?:Professional|Engineer|Analyst|Developer|Architect|Associate)",
        r"(?:Coursera|Udemy|edX|LinkedIn Learning|Pluralsight|DataCamp)\s*[-–:]\s*[\w\s,]+",
        r"(?:Scrum Master|Product Owner|Six Sigma|Lean|ITIL|Prince2|ISO\s*\d+)",
    ]

    # Search in section text first, then full text for known patterns
    for pat in cert_patterns:
        for m in re.finditer(pat, text, re.I):
            cert = m.group(0).strip()
            if len(cert) > 5:
                certs.append(cert)

    # Also extract bullet lines from certifications section
    if search_text:
        for line in search_text.splitlines():
            line = re.sub(r"^[\s\-•·*>]+", "", line).strip()
            if 5 < len(line) < 120 and not re.match(r"^\d+$", line):
                certs.append(line)

    # Deduplicate preserving order
    seen, dedup = set(), []
    for c in certs:
        key = c.lower()[:40]
        if key not in seen:
            seen.add(key)
            dedup.append(c)
    return dedup[:15]


def _extract_projects(text: str, sections: dict[str, str] | None = None) -> list[dict[str, str]]:
    """Extract project entries from dedicated section or inline mentions."""
    projects = []

    search_text = ""
    if sections:
        for key in ("projects", "project", "personal projects", "academic projects"):
            if key in sections and sections[key]:
                search_text = sections[key]
                break

    if search_text:
        # Each non-empty line that looks like a project title/description
        lines = [l.strip() for l in search_text.splitlines() if l.strip()]
        current: dict[str, str] = {}
        for line in lines:
            # Remove bullet characters
            clean = re.sub(r"^[\s\-•·*>|]+", "", line).strip()
            if not clean or len(clean) < 4:
                continue
            # Heuristic: short lines (< 80 chars) with no common sentence endings = title
            if len(clean) <= 80 and not re.search(r"[.!?]$", clean) and not current.get("title"):
                if current:
                    projects.append(current)
                current = {"title": clean, "description": ""}
            else:
                # Append to description
                if current:
                    current["description"] = (current.get("description", "") + " " + clean).strip()
                else:
                    current = {"title": clean, "description": ""}
        if current:
            projects.append(current)

    # Fallback: look for "Project:" or "• ProjectName –" patterns in full text
    if not projects:
        for m in re.finditer(
            r"(?:Project\s*[:\-]\s*|•\s*)([A-Z][A-Za-z0-9 \-_]{3,60})"
            r"(?:\s*[-–:]\s*([\w\s,./]{5,120}))?",
            text,
        ):
            title = m.group(1).strip()
            desc = (m.group(2) or "").strip()
            if title:
                projects.append({"title": title, "description": desc})

    # Deduplicate
    seen, dedup = set(), []
    for p in projects:
        key = p.get("title", "")[:30].lower()
        if key not in seen:
            seen.add(key)
            dedup.append(p)
    return dedup[:10]


# ---------------------------------------------------------------------------
# Built-in heuristic scorer
# ---------------------------------------------------------------------------
def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _skill_match_score(cand_skills: list[Any], req_skills: list[str], pref_skills: list[str]) -> float:
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
            if req_n == c or req_n in c or c in req_n:
                return True
        return False

    matched_req = sum(1 for r in req_skills if matches(r))
    matched_pref = sum(1 for r in pref_skills if matches(r))

    if req_skills:
        score = (matched_req / len(req_skills)) * 100.0
    else:
        score = 70.0

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
        return min(100.0, 50.0 + cand * 10)
    if cand >= req:
        return min(100.0, 70 + (cand - req) * 5)
    return max(0.0, (cand / req) * 70)


def _education_score(cand_edu: list[Any], req_edu: list[str]) -> float:
    if not req_edu:
        return 75.0
    cand_text = " ".join(_norm(e) for e in cand_edu)
    if not cand_text:
        return 30.0
    matched = 0
    for req in req_edu:
        rn = _norm(req)
        if not rn:
            continue
        if rn in cand_text or any(rn in _norm(e) for e in cand_edu):
            matched += 1
    return min(100.0, 60.0 + (matched / max(len(req_edu), 1)) * 40)


def _semantic_score(text: str, jd: dict) -> float:
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
    return round(min(100.0, jaccard * 200.0), 2)


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