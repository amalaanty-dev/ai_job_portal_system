"""ATS Adapter — sole bridge between API layer and existing ATS engine.

⭐ INTEGRATION POINT:
This is the ONLY file that imports from `parsers/`, `ats_engine/`,
`semantic_engine/`, `skill_engine/`, etc.

If your existing modules expose different function names, change them HERE
and nowhere else. The fallback stubs below let the API run end-to-end even
before integration is complete (useful for testing & frontend dev).

Real-world parsers return inconsistent shapes (lists vs dicts, ints vs
strings). `_normalize_parsed_profile()` coerces the output into a shape
that `ParsedProfile` is happy with.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Resume parsing
# ---------------------------------------------------------------------------
def parse_resume(file_path: str | Path) -> dict[str, Any]:
    """Parse a resume file → structured profile dict (always normalized)."""
    file_path = str(file_path)
    raw: dict[str, Any]
    try:
        # INTEGRATION POINT — replace with your real parser
        from parsers.resume_parser import parse_resume as real_parse  # type: ignore
        raw = real_parse(file_path)
    except Exception as e:
        logger.warning(f"Real resume parser unavailable, using stub: {e}")
        raw = _stub_parse_resume(file_path)
    return _normalize_parsed_profile(raw)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def score_candidate(parsed_profile: dict, jd: dict) -> dict[str, Any]:
    """Score one parsed resume against one JD → ScoreBreakdown-compatible dict."""
    try:
        # INTEGRATION POINT — replace with your real scorer
        from ats_engine.scorer import compute_score  # type: ignore
        return compute_score(parsed_profile, jd)
    except Exception as e:
        logger.warning(f"Real scorer unavailable, using stub: {e}")
        return _stub_score(parsed_profile, jd)


# ---------------------------------------------------------------------------
# Profile normalizer — defensive coercion
# ---------------------------------------------------------------------------
def _normalize_parsed_profile(raw: Any) -> dict[str, Any]:
    """Coerce arbitrary parser output into a dict that ParsedProfile accepts.

    Handles common parser quirks:
      - Top-level not a dict → wrap into {"raw_text_preview": str(raw)}
      - email/phone returned as list → keep first item OR keep list (schema OK)
      - skills as dict → use values
      - experience_years as string → coerce to float
      - missing keys → defaults
      - extra keys → preserved (schema config allows extras)
    """
    if raw is None:
        return _empty_profile()
    if not isinstance(raw, dict):
        return {**_empty_profile(), "raw_text_preview": str(raw)[:500]}

    out = dict(raw)  # preserve unknown keys for ParsedProfile.extra='allow'

    # name
    name = out.get("name")
    if isinstance(name, list):
        out["name"] = name[0] if name else None
    elif name is not None and not isinstance(name, str):
        out["name"] = str(name)

    # email — may be str or list[str]; both OK with the lenient schema
    email = out.get("email")
    if isinstance(email, (list, tuple)):
        out["email"] = [str(x) for x in email if x]
    elif email is not None and not isinstance(email, str):
        out["email"] = str(email)

    # phone
    phone = out.get("phone")
    if isinstance(phone, (list, tuple)):
        out["phone"] = [str(x) for x in phone if x]
    elif phone is not None and not isinstance(phone, str):
        out["phone"] = str(phone)

    # list-shaped fields — coerce dicts/scalars to lists
    for key in ("skills", "experience", "education"):
        val = out.get(key)
        if val is None:
            out[key] = []
        elif isinstance(val, dict):
            # turn {"py": "...", "django": "..."} into list of values
            out[key] = list(val.values())
        elif not isinstance(val, list):
            out[key] = [val]

    # total_experience_years — float | int | numeric str | None
    exp_years = out.get("total_experience_years")
    if exp_years is None or isinstance(exp_years, (int, float)):
        pass  # already fine
    elif isinstance(exp_years, str):
        try:
            out["total_experience_years"] = float(exp_years.strip()) if exp_years.strip() else None
        except ValueError:
            out["total_experience_years"] = None
    else:
        out["total_experience_years"] = None

    # raw_text_preview must be str | None
    rtp = out.get("raw_text_preview")
    if rtp is not None and not isinstance(rtp, str):
        out["raw_text_preview"] = str(rtp)[:500]

    return out


def _empty_profile() -> dict[str, Any]:
    return {
        "name": None,
        "email": None,
        "phone": None,
        "skills": [],
        "experience": [],
        "education": [],
        "total_experience_years": None,
        "raw_text_preview": None,
    }


# ---------------------------------------------------------------------------
# Stubs (deterministic, sufficient for API contract validation)
# ---------------------------------------------------------------------------
def _stub_parse_resume(file_path: str) -> dict[str, Any]:
    """Minimal stub — extracts text if possible, else returns empty profile.

    Tries pdfplumber / python-docx if present; degrades gracefully.
    """
    text = ""
    p = Path(file_path)
    try:
        if p.suffix.lower() == ".pdf":
            try:
                import pdfplumber
                with pdfplumber.open(p) as pdf:
                    text = "\n".join((page.extract_text() or "") for page in pdf.pages)
            except ImportError:
                pass
        elif p.suffix.lower() in (".docx",):
            try:
                from docx import Document
                doc = Document(p)
                text = "\n".join(par.text for par in doc.paragraphs)
            except ImportError:
                pass
    except Exception as e:
        logger.warning(f"Stub parser text extraction failed: {e}")

    SKILLS = ["python", "django", "flask", "fastapi", "react", "node", "java", "sql",
              "aws", "docker", "kubernetes", "mongodb", "postgresql", "javascript",
              "typescript", "ml", "nlp", "tensorflow", "pytorch"]
    lower = text.lower()
    found = sorted({s for s in SKILLS if s in lower})

    return {
        "name": None,
        "email": _extract_email(text),
        "phone": None,
        "skills": [s.title() for s in found],
        "experience": [],
        "education": [],
        "total_experience_years": None,
        "raw_text_preview": text[:500] if text else None,
    }


def _extract_email(text: str) -> str | None:
    import re
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    return m.group(0) if m else None


def _stub_score(parsed_profile: dict, jd: dict) -> dict[str, Any]:
    """Deterministic skill-overlap score so API can be exercised end-to-end."""
    raw_skills = parsed_profile.get("skills", [])
    cand_skills: set[str] = set()
    for s in raw_skills:
        if isinstance(s, str):
            cand_skills.add(s.lower())
        elif isinstance(s, dict):
            name = s.get("name") or s.get("skill") or s.get("value")
            if isinstance(name, str):
                cand_skills.add(name.lower())

    req = {s.lower() for s in jd.get("required_skills", []) if isinstance(s, str)}
    pref = {s.lower() for s in jd.get("preferred_skills", []) if isinstance(s, str)}

    if not req and not pref:
        skill_score = 0.0
    else:
        matched_req = len(cand_skills & req)
        matched_pref = len(cand_skills & pref)
        denom = max(len(req), 1)
        skill_score = min(100.0, (matched_req / denom) * 80 + matched_pref * 5)

    try:
        cand_exp = float(parsed_profile.get("total_experience_years") or 0)
    except (TypeError, ValueError):
        cand_exp = 0.0
    try:
        req_exp = float(jd.get("experience_required") or 0)
    except (TypeError, ValueError):
        req_exp = 0.0

    if req_exp <= 0:
        exp_score = 70.0
    elif cand_exp >= req_exp:
        exp_score = min(100.0, 70 + (cand_exp - req_exp) * 5)
    else:
        exp_score = max(0.0, (cand_exp / req_exp) * 70)

    education_score = 75.0
    semantic_score = (skill_score + exp_score) / 2

    final = round(
        skill_score * 0.45 + exp_score * 0.25 + education_score * 0.10 + semantic_score * 0.20,
        2,
    )
    return {
        "skills": round(skill_score, 2),
        "experience": round(exp_score, 2),
        "education": round(education_score, 2),
        "semantic": round(semantic_score, 2),
        "final_score": final,
    }
