"""ATS Adapter — sole bridge between API layer and existing ATS engine.

Force built-in parser/scorer:
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
# Public API
# ---------------------------------------------------------------------------
def parse_resume(file_path: str | Path) -> dict[str, Any]:
    file_path = str(file_path)
    raw = None
    if USE_STUB_PARSER:
        raw = _stub_parse_resume(file_path)
    else:
        try:
            from parsers.resume_parser import parse_resume as real_parse  # type: ignore
            raw = real_parse(file_path)
            if _looks_broken(raw, file_path):
                raw = _stub_parse_resume(file_path)
        except Exception as e:
            logger.warning(f"Real parser unavailable: {e}")
            raw = _stub_parse_resume(file_path)
    return _normalize_parsed_profile(raw)


def score_candidate(parsed_profile: dict, jd: dict) -> dict[str, Any]:
    if USE_STUB_SCORER:
        return _stub_score(parsed_profile, jd)
    try:
        from ats_engine.scorer import compute_score  # type: ignore
        return compute_score(parsed_profile, jd)
    except Exception as e:
        logger.warning(f"Real scorer unavailable: {e}")
        return _stub_score(parsed_profile, jd)


# ---------------------------------------------------------------------------
# Broken-parser detector
# ---------------------------------------------------------------------------
def _looks_broken(profile: Any, file_path: str) -> bool:
    if not isinstance(profile, dict):
        return True
    fp_basename = os.path.basename(file_path)
    for k in ("clean_text", "raw_text", "raw_text_preview", "text"):
        v = profile.get(k)
        if isinstance(v, str) and (v == file_path or v.endswith(fp_basename)) and len(v) < 300:
            return True
    if not any([profile.get("skills"), profile.get("education"),
                profile.get("experience"),
                any(isinstance(profile.get(k), str) and len(profile.get(k, "")) > 50
                    for k in ("clean_text", "raw_text", "raw_text_preview", "text"))]):
        return True
    return False


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------
def _normalize_parsed_profile(raw: Any) -> dict[str, Any]:
    if raw is None:
        return _empty_profile()
    if not isinstance(raw, dict):
        return {**_empty_profile(), "raw_text_preview": str(raw)[:500]}
    out = dict(raw)
    for field in ("name",):
        v = out.get(field)
        if isinstance(v, list):
            out[field] = v[0] if v else None
        elif v is not None and not isinstance(v, str):
            out[field] = str(v)
    for field in ("email", "phone"):
        v = out.get(field)
        if isinstance(v, (list, tuple)):
            out[field] = [str(x) for x in v if x]
        elif v is not None and not isinstance(v, str):
            out[field] = str(v)
    for key in ("skills", "experience", "education", "certifications", "projects"):
        v = out.get(key)
        if v is None:
            out[key] = []
        elif isinstance(v, dict):
            out[key] = list(v.values())
        elif not isinstance(v, list):
            out[key] = [v]
    exp = out.get("total_experience_years")
    if exp is not None and not isinstance(exp, (int, float)):
        try:
            out["total_experience_years"] = float(str(exp).strip()) or None
        except ValueError:
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
# Skills dictionary
# ---------------------------------------------------------------------------
_SKILLS_DICT: tuple[str, ...] = (
    "healthcare reporting", "health informatics", "clinical data", "medical coding",
    "icd-10", "icd10", "cpt", "hl7", "fhir", "epic systems", "cerner", "meditech",
    "ehr", "emr", "hipaa", "patient outcomes", "claims data", "revenue cycle",
    "kpi monitoring", "dashboard development", "report automation",
    "population health", "hedis", "quality reporting", "clinical workflow",
    "data analysis", "data analytics", "business intelligence", "data visualization",
    "data modeling", "data engineering", "etl", "elt", "data warehousing",
    "tableau", "power bi", "looker", "qlikview", "qlik sense", "google data studio",
    "excel", "advanced excel", "vba", "macros", "pivot tables", "data wrangling",
    "data cleaning", "eda", "streamlit",
    "python", "r programming", "java", "javascript", "typescript", "scala",
    "kotlin", "swift", "go", "rust", "c++", "c#", "ruby", "php", "regex",
    "sql", "mysql", "postgresql", "postgres", "oracle", "sql server", "mssql",
    "mongodb", "cassandra", "redis", "snowflake", "bigquery", "redshift",
    "databricks", "dynamodb",
    "machine learning", "deep learning", "nlp", "computer vision",
    "tensorflow", "pytorch", "scikit-learn", "keras", "xgboost", "lightgbm",
    "transformers", "huggingface", "openai", "langchain",
    "statistical analysis", "statistics", "regression", "classification",
    "clustering", "pca", "feature engineering", "hyperparameter tuning",
    "ann", "cnn", "rnn", "intent classification", "ner", "dialog management",
    "sentiment analysis", "chatbot", "llm",
    "django", "flask", "fastapi", "spring boot", "nodejs", "node.js",
    "express", "react", "vue", "angular", "next.js",
    "rest api", "graphql", "grpc", "microservices",
    "aws", "azure", "gcp", "google cloud", "kubernetes", "docker",
    "terraform", "ansible", "jenkins", "github actions", "gitlab ci", "ci/cd",
    "git", "jira", "confluence", "linux", "bash", "powershell", "postman",
    "project management", "agile", "scrum", "stakeholder management",
    "communication", "leadership", "problem solving",
    "numpy", "pandas", "matplotlib", "seaborn",
)


# ---------------------------------------------------------------------------
# Section splitter — handles ALL-CAPS, Title Case, multi-word headers
# ---------------------------------------------------------------------------

# All known section header variants
_SECTION_HEADER_RE = re.compile(
    r"^[\s\-=_*#]*"
    r"(professional summary|summary|objective|profile|about me|"
    r"professional experience|work experience|employment history|"
    r"experience|work history|career history|employment|"
    r"machine learning projects|key projects|personal projects|"
    r"academic projects|projects|"
    r"core technical skills|technical skills|core skills|key skills|"
    r"skills summary|skills|"
    r"certifications?\s*(?:&|and)?\s*(?:licenses?|achievements?|awards?)?|"
    r"certificates?|licenses?|achievements?|awards?|key achievements?|"
    r"education|academic background|qualifications?|"
    r"tools?\s*(?:&|and)?\s*technologies?|tools?|technologies?|"
    r"languages?|soft skills?|hobbies?|interests?|"
    r"publications?|research|volunteer|references?)"
    r"[\s\-=_*#:]*$",
    re.I | re.M,
)

# Section headers that are NOT experience/projects/certs/education
_NON_CONTENT_SECTIONS = re.compile(
    r"^(summary|objective|profile|about|skills|tools|technologies|"
    r"languages|soft skills|hobbies|interests|publications|research|"
    r"volunteer|references|core technical skills|technical skills|"
    r"core skills|key skills|skills summary|tools\s*&\s*technologies|"
    r"soft\s*skills)\s*$",
    re.I,
)


def _split_sections(text: str) -> dict[str, str]:
    """Split resume into named sections, normalizing header names."""
    CANON = {
        "professional experience": "experience",
        "work experience": "experience",
        "employment history": "experience",
        "work history": "experience",
        "career history": "experience",
        "employment": "experience",
        "machine learning projects": "projects",
        "key projects": "projects",
        "personal projects": "projects",
        "academic projects": "projects",
        "core technical skills": "skills",
        "technical skills": "skills",
        "core skills": "skills",
        "key skills": "skills",
        "skills summary": "skills",
        "professional summary": "summary",
        "about me": "summary",
        "certifications & licenses": "certifications",
        "certifications and licenses": "certifications",
        "certificates": "certifications",
        "licenses": "certifications",
        "key achievements": "achievements",
        "academic background": "education",
        "qualifications": "education",
        "tools & technologies": "tools",
        "tools and technologies": "tools",
        "soft skills": "soft_skills",
    }

    sections: dict[str, str] = {}
    matches = list(_SECTION_HEADER_RE.finditer(text))
    for i, m in enumerate(matches):
        raw_header = re.sub(r"\s+", " ", m.group(1).strip().lower())
        header = CANON.get(raw_header, raw_header)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            sections[header] = content
    return sections


# ---------------------------------------------------------------------------
# Text cleaner
# ---------------------------------------------------------------------------
def _clean(text: str) -> str:
    """Remove PDF artifacts like (cid:N), normalize whitespace."""
    text = re.sub(r"\(cid:\d+\)", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _clean_line(line: str) -> str:
    line = re.sub(r"\(cid:\d+\)", "", line)
    line = re.sub(r"^[\s\-•·*>|]+", "", line)
    return line.strip()


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------
def _stub_parse_resume(file_path: str) -> dict[str, Any]:
    raw_text = _extract_text(file_path)
    if not raw_text:
        return _empty_profile()

    text = _clean(raw_text)
    sections = _split_sections(text)

    return {
        "name": _extract_name(text),
        "email": _extract_email(text),
        "phone": _extract_phone(text),
        "skills": _extract_skills(text),
        "experience": _extract_experience(text, sections),
        "education": _extract_education(text, sections),
        "certifications": _extract_certifications(text, sections),
        "projects": _extract_projects(text, sections),
        "total_experience_years": _extract_total_experience_years(text),
        "raw_text_preview": text[:500],
    }


def _extract_text(file_path: str) -> str:
    p = Path(file_path)
    try:
        if p.suffix.lower() == ".pdf":
            try:
                import pdfplumber
                with pdfplumber.open(p) as pdf:
                    return "\n".join((page.extract_text() or "") for page in pdf.pages)
            except ImportError:
                logger.warning("pdfplumber not installed: pip install pdfplumber")
        elif p.suffix.lower() == ".docx":
            try:
                from docx import Document
                return "\n".join(par.text for par in Document(p).paragraphs)
            except ImportError:
                logger.warning("python-docx not installed: pip install python-docx")
    except Exception as e:
        logger.warning(f"Text extraction failed for {file_path}: {e}")
    return ""


# ---------------------------------------------------------------------------
# Field extractors
# ---------------------------------------------------------------------------
def _extract_email(text: str) -> str | None:
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    return m.group(0) if m else None


def _extract_phone(text: str) -> str | None:
    for pat in [
        r"\+\d{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}",
        r"\+91[\s\-]?\d{10}",
        r"\(\d{3}\)\s?\d{3}[\-]\d{4}",
        r"\b\d{10}\b",
    ]:
        m = re.search(pat, text)
        if m:
            return m.group(0).strip()
    return None


def _extract_name(text: str) -> str | None:
    """
    Extract name from first few lines.
    Handles:
      - 'AMALA P ANTY' (ALL CAPS, 3 tokens)
      - 'Chloe Park' (Title Case, 2 tokens)
    Skips lines with: email, digits, bullets, pipes, job titles, locations.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    SKIP_WORDS = {
        "resume", "curriculum vitae", "cv", "profile", "objective", "summary",
        "page", "address", "linkedin", "github", "portfolio", "www",
    }
    TITLE_RE = re.compile(
        r"\b(engineer|analyst|developer|manager|specialist|consultant|scientist|"
        r"designer|director|intern|associate|coordinator|executive|officer|lead|"
        r"data|nlp|ai|ml|banker|deputy|operations)\b", re.I
    )
    LOCATION_RE = re.compile(r"\b(india|usa|remote|bangalore|mumbai|delhi|oregon|"
                              r"portland|new york|london|city|state)\b", re.I)

    for ln in lines[:10]:
        low = ln.lower()
        # Skip known non-name content
        if any(h in low for h in SKIP_WORDS):
            continue
        # Skip lines with email, digits, bullets, pipes, dots (location separators)
        if "@" in ln or re.search(r"[\d|•·/\\]", ln):
            continue
        # Skip job title lines
        if TITLE_RE.search(ln):
            continue
        # Skip location lines
        if LOCATION_RE.search(ln):
            continue
        # Clean and tokenize
        clean = re.sub(r"[,.]", "", ln).strip()
        tokens = clean.split()
        if 2 <= len(tokens) <= 5:
            if all(re.match(r"^[A-Za-z][A-Za-z'\-]*$", t) for t in tokens):
                if tokens[0][0].isupper():
                    return " ".join(t.capitalize() for t in tokens)
    return None


def _extract_skills(text: str) -> list[str]:
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
                        "EHR", "EMR", "HIPAA", "HL7", "FHIR", "KPI", "VBA",
                        "ANN", "CNN", "RNN", "NER", "LLM", "PCA", "EDA"):
                display = re.sub(r"(?i)\b" + acr + r"\b", acr, display)
            found[token] = display
    return sorted(set(found.values()))


def _extract_total_experience_years(text: str) -> float | None:
    candidates = []
    for m in re.finditer(
        r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)?",
        text, re.I,
    ):
        try:
            candidates.append(float(m.group(1)))
        except ValueError:
            pass
    if candidates:
        return max(candidates)
    years = [int(y) for y in re.findall(r"\b(19[89]\d|20[0-2]\d)\b", text)]
    if years:
        from datetime import datetime
        diff = datetime.now().year - min(years)
        if 0 < diff <= 40:
            return float(diff)
    return None


# ---------------------------------------------------------------------------
# Experience extractor
# ---------------------------------------------------------------------------
_DATE_RE = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4})"
    r"\s*[-\u2013\u2014/]+\s*"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}"
    r"|\d{4}|Present|Current|Till\s+Date|Now)",
    re.I,
)

# Words that indicate a line is a section header, not a role/company
_SECTION_NOISE = re.compile(
    r"^(professional experience|work experience|employment|education|"
    r"technical skills|core skills|skills|certifications?|projects?|summary|"
    r"tools?\s*(?:&|and)?\s*technologies?|soft\s*skills?|languages?|"
    r"key achievements?|achievements?|references?|clients?)\s*[:\-]?\s*$",
    re.I,
)


def _is_noise_line(line: str) -> bool:
    """Return True if line is a section header or junk, not role/company."""
    line = line.strip()
    if not line or len(line) < 2:
        return True
    if _SECTION_NOISE.match(line):
        return True
    # Lines that are just bullets or separators
    if re.match(r"^[\-=_•·*|#\s]+$", line):
        return True
    return False


def _extract_experience(text: str, sections: dict[str, str]) -> list[dict[str, str]]:
    """
    Extract work experience entries.

    Handles two common formats:
    Format A (Amala): Role | Company | Date  (all on one line)
      e.g. "Data Engineer II | Gupshup Technologies India Pvt. Ltd.|Jul 2021 – Dec 2024"

    Format B (Chloe): Role on line N, Company · Date on line N+1
      e.g. "Health Informatics Analyst"
           "OHSU (Oregon Health & Science University) · Aug 2021 – Present"
    """
    # Use experience section if available
    search_text = text
    for key in ("experience", "professional experience", "work experience",
                "employment history", "employment"):
        if key in sections and len(sections[key]) > 30:
            search_text = sections[key]
            break

    lines = [_clean(ln) for ln in search_text.splitlines()]
    entries: list[dict[str, str]] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line or _is_noise_line(line):
            i += 1
            continue

        dm = _DATE_RE.search(line)

        if dm:
            duration = dm.group(0).strip()
            before_date = line[:dm.start()].strip()
            before_date = re.sub(r"[\|\-·•,]+$", "", before_date).strip()

            role = ""
            company = ""

            if before_date and not _is_noise_line(before_date):
                # Format A: everything before date contains role and/or company
                # Split on | or · to separate role from company
                parts = [p.strip() for p in re.split(r"\s*[\|·•]\s*", before_date) if p.strip()]
                parts = [p for p in parts if not _is_noise_line(p)]
                if len(parts) >= 2:
                    role = parts[0]
                    company = parts[1]
                elif len(parts) == 1:
                    # Could be just company — check previous line for role
                    role = parts[0]
                    # Look back for a preceding role line
                    for j in range(i - 1, max(i - 4, -1), -1):
                        prev = lines[j].strip()
                        if prev and not _is_noise_line(prev) and not _DATE_RE.search(prev):
                            company = role
                            role = prev
                            break
            else:
                # Format B: date on its own line or after company
                # Role is on a previous line, company may be on another
                prev_lines = []
                for j in range(i - 1, max(i - 5, -1), -1):
                    prev = lines[j].strip()
                    if prev and not _is_noise_line(prev) and not _DATE_RE.search(prev):
                        prev_lines.insert(0, prev)
                    elif _DATE_RE.search(prev if prev else ""):
                        break

                # company·date may be on same line
                # e.g. "OHSU (Oregon Health & Science University) · Aug 2021 – Present"
                company_part = before_date
                if company_part and not _is_noise_line(company_part):
                    company = company_part
                    role = prev_lines[-1] if prev_lines else ""
                elif prev_lines:
                    role = prev_lines[-1]
                    company = prev_lines[-2] if len(prev_lines) >= 2 else ""

            # Clean up
            role = re.sub(r"\s+", " ", role).strip()[:120]
            company = re.sub(r"\s+", " ", company).strip()[:120]

            # Skip if role looks like description text (starts lowercase, too long)
            if not role or len(role) < 3:
                i += 1
                continue
            if role[0].islower() and len(role) > 50:
                i += 1
                continue
            # Skip if role is a section header
            if _is_noise_line(role):
                i += 1
                continue

            entries.append({"role": role, "company": company, "duration": duration})

        i += 1

    # Deduplicate
    seen: set[tuple] = set()
    dedup: list[dict[str, str]] = []
    for e in entries:
        key = (e["role"][:30].lower(), e["duration"][:15].lower())
        if key not in seen:
            seen.add(key)
            dedup.append(e)

    return dedup[:10]


# ---------------------------------------------------------------------------
# Education extractor
# ---------------------------------------------------------------------------
def _extract_education(text: str, sections: dict[str, str]) -> list[str]:
    """
    Extract education entries.
    Prefers education section lines; falls back to degree pattern matching.
    """
    results: list[str] = []

    # Use education section if available
    edu_text = sections.get("education", "")
    if edu_text:
        for line in edu_text.splitlines():
            clean = _clean_line(line)
            if not clean or len(clean) < 4:
                continue
            # Skip lines that are just years or percentages
            if re.match(r"^[\d\s%\|·\-]+$", clean):
                continue
            # Skip institution-only lines (very long with no degree keyword)
            results.append(clean)

    # If section gave nothing, fall back to degree regex on full text
    if not results:
        DEGREE_PATTERNS = [
            (r"\bph\.?d\.?\b|\bdoctorate\b", "PhD"),
            (r"\bm\.?tech\b", "M.Tech"),
            (r"\bmba\b", "MBA"),
            (r"\bmaster[s']?\s+of\s+\w+", "Masters"),
            (r"\bm\.?s\.?\b(?!\w)", "MS"),
            (r"\bm\.?sc\.?\b", "MSc"),
            (r"\bb\.?tech\b|\bbachelor\s+of\s+(?:engineering|technology)\b", "B.Tech"),
            (r"\bb\.?e\.?\b(?!\w)", "BE"),
            (r"\bb\.?sc\.?\b|\bbachelor\s+of\s+science\b", "BSc"),
            (r"\bbba\b", "BBA"),
            (r"\bbca\b", "BCA"),
            (r"\bmca\b", "MCA"),
            (r"\bdiploma\b", "Diploma"),
            (r"\bcomputer\s+science\b", "Computer Science"),
            (r"\binformation\s+technology\b", "Information Technology"),
            (r"\bdata\s+science\b", "Data Science"),
            (r"\binformatics\b", "Informatics"),
            (r"\bstatistics\b", "Statistics"),
        ]
        lower = text.lower()
        seen: set[str] = set()
        for pattern, label in DEGREE_PATTERNS:
            if re.search(pattern, lower) and label not in seen:
                seen.add(label)
                results.append(label)

    # Deduplicate preserving order
    seen2: set[str] = set()
    dedup: list[str] = []
    for r in results:
        k = r.lower()[:40]
        if k not in seen2:
            seen2.add(k)
            dedup.append(r)
    return dedup


# ---------------------------------------------------------------------------
# Certifications extractor
# ---------------------------------------------------------------------------
def _extract_certifications(text: str, sections: dict[str, str]) -> list[str]:
    """Section-first extraction. Strict known-cert patterns as fallback."""
    certs: list[str] = []

    # 1. Use certifications section
    cert_text = sections.get("certifications", "")
    if cert_text:
        for line in cert_text.splitlines():
            clean = _clean_line(line)
            if len(clean) < 8:
                continue
            if re.match(r"^\d{4}$", clean):
                continue
            # Skip pure tool names that aren't certifications
            if re.match(
                r"^(Google\s+(?:Translate|Colab|Docs|Sheets|Drive|Meet|Chrome)|"
                r"Microsoft\s+(?:Word|Excel|PowerPoint|Teams|Office)|"
                r"Slack|Zoom|Jira|GitHub|VS\s*Code|Postman)\s*$",
                clean, re.I,
            ):
                continue
            if len(clean) < 150:
                certs.append(clean)

    # 2. Strict patterns fallback
    if not certs:
        CERT_PATTERNS = [
            r"AWS\s+Certified\s+[\w\s]+(?:Associate|Professional|Specialty|Practitioner)",
            r"Google\s+Cloud\s+(?:Certified\s+)?[\w\s]+(?:Associate|Professional|Engineer)",
            r"Microsoft\s+Certified\s*:\s*[\w\s]+(?:Associate|Expert|Fundamentals)",
            r"(?:PMP|CISSP|CISA|CISM|CEH|OSCP|CPA|CFA|FRM|SHRM|PHR|SPHR|CAPM)\b",
            r"Certified\s+(?:Data|Cloud|Security|Scrum|SAFe|Kubernetes)\s+[\w\s]{3,40}",
            r"(?:Coursera|Udemy|edX|DataCamp|Pluralsight)\s*[-–:]\s*[\w\s,]{5,60}",
            r"(?:Scrum\s+Master|Product\s+Owner|Six\s+Sigma\s+[\w]+|ITIL\s+[\w]+|Prince2)",
            r"Epic\s+Certified\s+[\w\s]+",
            r"HL7\s+FHIR\s+[\w\s]+",
            r"AMIA\s+[\w\s]+Certification",
        ]
        for pat in CERT_PATTERNS:
            for m in re.finditer(pat, text, re.I):
                cert = m.group(0).strip()
                if len(cert) > 8:
                    certs.append(cert)

    seen: set[str] = set()
    dedup: list[str] = []
    for c in certs:
        k = c.lower()[:40]
        if k not in seen:
            seen.add(k)
            dedup.append(c)
    return dedup[:15]


# ---------------------------------------------------------------------------
# Projects extractor
# ---------------------------------------------------------------------------
def _extract_projects(text: str, sections: dict[str, str]) -> list[dict[str, str]]:
    """
    Extract projects from dedicated section.
    Handles:
      - 'MACHINE LEARNING PROJECTS' (Amala format)
      - 'PROJECTS' (generic)
      - Inline 'Project: Name' patterns as fallback
    """
    projects: list[dict[str, str]] = []

    proj_text = sections.get("projects", "")
    if not proj_text:
        # Try alternate section names
        for key in sections:
            if "project" in key.lower():
                proj_text = sections[key]
                break

    if proj_text:
        lines = [_clean(ln) for ln in proj_text.splitlines()]
        current: dict[str, str] = {}

        for line in lines:
            clean = re.sub(r"^[\s\-•·*>|]+", "", line).strip()
            if not clean or len(clean) < 3:
                continue

            # Detect project title:
            # - Short line (≤ 100 chars)
            # - Starts with capital letter or is ALL CAPS
            # - Often contains | or — separating title from type
            # - Does NOT end with sentence punctuation
            is_title = (
                len(clean) <= 120
                and not re.search(r"\.$", clean)
                and (clean[0].isupper() or clean.isupper())
                and not re.match(r"^(built|developed|created|designed|implemented|"
                                 r"performed|analyzed|led|managed|conducted)\b", clean, re.I)
            )

            if is_title and not current.get("title"):
                if current and current.get("title"):
                    projects.append(current)
                current = {"title": clean, "description": ""}
            elif is_title and current.get("title"):
                # New project title — save previous
                projects.append(current)
                current = {"title": clean, "description": ""}
            else:
                # Description line
                if current:
                    sep = " " if current["description"] else ""
                    current["description"] = current["description"] + sep + clean
                else:
                    current = {"title": clean, "description": ""}

        if current and current.get("title"):
            projects.append(current)

    # Fallback: scan full text
    if not projects:
        for m in re.finditer(
            r"(?:^|\n)\s*(?:Project\s*[:\-]\s*|➢\s*|▪\s*)([A-Z][A-Za-z0-9 \-_&|]{3,80})"
            r"(?:\s*[-–:]\s*([\w\s,./]{5,120}))?",
            text, re.M,
        ):
            title = m.group(1).strip()
            desc = (m.group(2) or "").strip()
            if title and len(title) > 5:
                projects.append({"title": title, "description": desc})

    # Deduplicate
    seen: set[str] = set()
    dedup: list[dict[str, str]] = []
    for p in projects:
        k = p.get("title", "")[:30].lower()
        if k not in seen:
            seen.add(k)
            dedup.append(p)
    return dedup[:10]


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------
def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _skill_match_score(cand_skills: list[Any], req_skills: list[str], pref_skills: list[str]) -> float:
    cand_norm = []
    for s in cand_skills:
        if isinstance(s, str):
            cand_norm.append(_norm(s))
        elif isinstance(s, dict):
            cand_norm.append(_norm(s.get("name") or s.get("skill") or ""))

    if not req_skills and not pref_skills:
        return 0.0

    def matches(req: str) -> bool:
        rn = _norm(req)
        return any(rn == c or rn in c or c in rn for c in cand_norm if c)

    matched_req = sum(1 for r in req_skills if matches(r))
    matched_pref = sum(1 for r in pref_skills if matches(r))
    score = (matched_req / len(req_skills) * 100.0) if req_skills else 70.0
    return round(min(100.0, score + matched_pref * 5), 2)


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
    matched = sum(
        1 for req in req_edu
        if (rn := _norm(req)) and (rn in cand_text or any(rn in _norm(e) for e in cand_edu))
    )
    return min(100.0, 60.0 + (matched / max(len(req_edu), 1)) * 40)


def _semantic_score(text: str, jd: dict) -> float:
    if not text:
        return 0.0
    jd_text = _norm(" ".join([
        str(jd.get("job_title", "")),
        " ".join(str(s) for s in (jd.get("required_skills") or [])),
        " ".join(str(s) for s in (jd.get("preferred_skills") or [])),
        str(jd.get("description", "")),
    ]))
    if not jd_text:
        return 0.0

    def tokens(s: str) -> set[str]:
        return {t for t in re.findall(r"[a-z0-9]{3,}", s.lower())}

    a, b = tokens(text), tokens(jd_text)
    if not a or not b:
        return 0.0
    return round(min(100.0, len(a & b) / len(a | b) * 200.0), 2)


def _stub_score(parsed_profile: dict, jd: dict) -> dict[str, Any]:
    cand_skills = parsed_profile.get("skills", []) or []
    req_skills = [s for s in (jd.get("required_skills") or []) if isinstance(s, str)]
    pref_skills = [s for s in (jd.get("preferred_skills") or []) if isinstance(s, str)]

    skill_score = _skill_match_score(cand_skills, req_skills, pref_skills)
    exp_score = _experience_score(
        parsed_profile.get("total_experience_years"),
        jd.get("experience_required"),
    )
    edu_score = _education_score(
        parsed_profile.get("education", []) or [],
        [e for e in (jd.get("education_required") or []) if isinstance(e, str)],
    )
    sem_score = _semantic_score(parsed_profile.get("raw_text_preview") or "", jd)

    final = round(skill_score * 0.45 + exp_score * 0.25 + edu_score * 0.10 + sem_score * 0.20, 2)
    return {
        "skills": round(skill_score, 2),
        "experience": round(exp_score, 2),
        "education": round(edu_score, 2),
        "semantic": round(sem_score, 2),
        "final_score": final,
    }