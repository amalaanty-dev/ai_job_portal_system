"""
utils/backlog_generator.py
==========================
Auto-generates an Improvement Backlog by analyzing AI vs HR mismatches.

CORRECTED for Day 17:
- Handles records where matched_skills/missing_skills/experience are missing
  (your scoring pipeline doesn't always populate these — the backlog still
   produces meaningful priority items based on category accuracy alone)

Day: 17 (corrected)
"""

from typing import List, Dict, Any
from collections import Counter


# --- Mismatch type classifiers --------------------------------------------------
KEYWORD_VARIANTS = {
    "js": "javascript",
    "ts": "typescript",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "k8s": "kubernetes",
    "py": "python",
    "ds": "data science",
}


def _detect_keyword_mismatch(record: Dict[str, Any]) -> bool:
    """Detect 'JS' vs 'JavaScript' style abbreviation mismatches in missing_skills."""
    missing_raw = record.get("missing_skills") or []
    matched_raw = record.get("matched_skills") or []

    # Be defensive: these might be lists of dicts, lists of strings, or empty
    if not isinstance(missing_raw, list) or not isinstance(matched_raw, list):
        return False

    missing = []
    for s in missing_raw:
        if isinstance(s, str):
            missing.append(s.lower().strip())
        elif isinstance(s, dict) and "skill" in s:
            missing.append(str(s["skill"]).lower().strip())

    matched = []
    for s in matched_raw:
        if isinstance(s, str):
            matched.append(s.lower().strip())
        elif isinstance(s, dict) and "skill" in s:
            matched.append(str(s["skill"]).lower().strip())

    for short, full in KEYWORD_VARIANTS.items():
        if short in missing and full in matched:
            return True
        if full in missing and short in matched:
            return True
    return False


def _detect_role_misclassification(record: Dict[str, Any]) -> bool:
    """E.g., 'Analyst' vs 'Business Analyst' — partial role-name confusion."""
    role = (record.get("identifiers", {}) or {}).get("job_role") or ""
    role = role.lower()
    expected_role = (record.get("hr_expected_role") or "").lower()
    if not expected_role or not role:
        return False
    role_tokens = set(role.split())
    expected_tokens = set(expected_role.split())
    if role_tokens and expected_tokens and role_tokens != expected_tokens:
        if role_tokens & expected_tokens:  # partial overlap
            return True
    return False


def _detect_experience_misinterpretation(record: Dict[str, Any]) -> bool:
    """Internships counted as full-time, or large delta between candidate & required years."""
    exp = record.get("experience") or {}
    if not isinstance(exp, dict):
        return False

    candidate_years = exp.get("candidate_years", 0) or 0
    required_years = exp.get("required_years", 0) or 0
    try:
        candidate_years = float(candidate_years)
        required_years = float(required_years)
    except (TypeError, ValueError):
        return False

    hr_decision = (record.get("hr_decision") or "").lower()
    ai_decision = (record.get("ai_decision") or "").lower()
    category = (record.get("category") or "").lower()

    # Flag if candidate has >0 years but HR considers them a fresher
    if candidate_years >= 1 and "fresher" in category:
        if ai_decision == "shortlisted" and hr_decision == "rejected":
            return True
    if abs(candidate_years - required_years) > 3 and ai_decision != hr_decision:
        return True
    return False


def _detect_soft_skill_miss(record: Dict[str, Any]) -> bool:
    """Non-tech roles often need soft skills; flag if score is low + role is non-tech."""
    cat = (record.get("category") or "").lower()
    score = record.get("final_score") or 0
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = 0
    if cat == "non_tech" and score < 60:
        return True
    return False


# --- Backlog assembly ----------------------------------------------------------
def analyze_mismatches(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Walks every test record and tallies mismatch categories.

    Each record should contain at minimum:
      - ai_decision, hr_decision
      - identifiers
      - category (tech/non_tech/fresher/senior)
    Optional fields enrich detection: matched_skills, missing_skills, experience.
    """
    mismatch_counter = Counter()
    examples: Dict[str, List[Dict[str, Any]]] = {
        "keyword_mismatch": [],
        "role_misclassification": [],
        "experience_misinterpretation": [],
        "soft_skill_miss": [],
    }

    for r in records:
        ai = (r.get("ai_decision") or "").strip().lower()
        hr = (r.get("hr_decision") or "").strip().lower()
        if ai == hr:
            continue  # not a mismatch

        ids = r.get("identifiers", {}) or {}
        ex = {
            "resume_id": ids.get("resume_id"),
            "jd_id": ids.get("jd_id"),
            "ai_decision": r.get("ai_decision"),
            "hr_decision": r.get("hr_decision"),
            "final_score": r.get("final_score"),
        }

        if _detect_keyword_mismatch(r):
            mismatch_counter["keyword_mismatch"] += 1
            examples["keyword_mismatch"].append(ex)
        if _detect_role_misclassification(r):
            mismatch_counter["role_misclassification"] += 1
            examples["role_misclassification"].append(ex)
        if _detect_experience_misinterpretation(r):
            mismatch_counter["experience_misinterpretation"] += 1
            examples["experience_misinterpretation"].append(ex)
        if _detect_soft_skill_miss(r):
            mismatch_counter["soft_skill_miss"] += 1
            examples["soft_skill_miss"].append(ex)

    return {"counts": dict(mismatch_counter), "examples": examples}


def generate_backlog(
    records: List[Dict[str, Any]],
    category_metrics: Dict[str, Any],
) -> Dict[str, List[Dict[str, str]]]:
    """
    Build a prioritized backlog using mismatch analysis + category metrics.

    Returns:
        {"high": [...], "medium": [...], "low": [...]}
    """
    analysis = analyze_mismatches(records)
    counts = analysis["counts"]

    backlog: Dict[str, List[Dict[str, str]]] = {"high": [], "medium": [], "low": []}

    # ---- HIGH PRIORITY -----------------------------------------------------
    non_tech_acc = _safe_get_acc(category_metrics, "non_tech")
    if non_tech_acc is not None and non_tech_acc < 0.85:
        backlog["high"].append({
            "id": "BL-H-01",
            "title": "Improve non-tech role understanding",
            "evidence": f"Non-tech accuracy: {non_tech_acc * 100:.1f}% (target ≥85%)",
            "suggestion": "Add domain-specific embeddings for sales/marketing/HR roles.",
        })
    if counts.get("soft_skill_miss", 0) > 0:
        backlog["high"].append({
            "id": "BL-H-02",
            "title": "Enhance soft skill extraction",
            "evidence": f"{counts['soft_skill_miss']} non-tech candidates scored <60",
            "suggestion": "Train soft-skill NER on communication/leadership/teamwork tokens.",
        })
    if counts.get("role_misclassification", 0) > 0:
        backlog["high"].append({
            "id": "BL-H-03",
            "title": "Refine role similarity mapping",
            "evidence": f"{counts['role_misclassification']} role misclassification cases",
            "suggestion": "Use role-taxonomy embeddings to disambiguate Analyst vs Business Analyst.",
        })

    # ---- MEDIUM PRIORITY ---------------------------------------------------
    if counts.get("experience_misinterpretation", 0) > 0:
        backlog["medium"].append({
            "id": "BL-M-01",
            "title": "Better experience parsing (internships vs full-time)",
            "evidence": f"{counts['experience_misinterpretation']} experience misinterpretation cases",
            "suggestion": "Add 'employment_type' field detection (intern/full-time/contract) in parser.",
        })
    if counts.get("keyword_mismatch", 0) > 0:
        backlog["medium"].append({
            "id": "BL-M-02",
            "title": "Improve keyword normalization",
            "evidence": f"{counts['keyword_mismatch']} JS↔JavaScript style mismatches",
            "suggestion": "Maintain a curated synonym/abbreviation dictionary in skill_engine.",
        })
    fresher_acc = _safe_get_acc(category_metrics, "fresher")
    if fresher_acc is not None and fresher_acc < 0.85:
        backlog["medium"].append({
            "id": "BL-M-03",
            "title": "Improve education relevance logic",
            "evidence": f"Fresher accuracy: {fresher_acc * 100:.1f}% (target ≥85%)",
            "suggestion": "Weight education higher and projects/certifications for freshers.",
        })

    # ---- LOW PRIORITY ------------------------------------------------------
    backlog["low"].append({
        "id": "BL-L-01",
        "title": "UI improvements for recruiter dashboard",
        "evidence": "Standard UX backlog item",
        "suggestion": "Add filterable mismatch view in recruiter dashboard.",
    })
    backlog["low"].append({
        "id": "BL-L-02",
        "title": "Faster API response times",
        "evidence": "Performance backlog",
        "suggestion": "Profile scoring pipeline; consider caching parsed JDs.",
    })
    backlog["low"].append({
        "id": "BL-L-03",
        "title": "Logging enhancements",
        "evidence": "Currently no per-mismatch trace logging",
        "suggestion": "Add structured logging for every score decision.",
    })

    return backlog


def _safe_get_acc(category_metrics: Dict[str, Any], cat: str):
    """Helper: extract accuracy for a category if present."""
    if cat not in category_metrics:
        return None
    m = category_metrics[cat]
    if hasattr(m, "accuracy"):
        return m.accuracy
    if isinstance(m, dict):
        return m.get("accuracy")
    return None


if __name__ == "__main__":
    fake = [
        {"ai_decision": "Shortlisted", "hr_decision": "Rejected",
         "category": "non_tech", "final_score": 55,
         "identifiers": {"resume_id": "R1", "jd_id": "JD1", "job_role": "Marketing"}},
    ]
    from utils.metrics_calculator import ConfusionMatrix, compute_metrics
    cat_metrics = {"non_tech": compute_metrics(ConfusionMatrix(tp=5, fp=2, fn=3, tn=0))}
    print(generate_backlog(fake, cat_metrics))
