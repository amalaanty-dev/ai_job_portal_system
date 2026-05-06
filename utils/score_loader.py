"""
utils/score_loader.py
=====================
Loads ATS score JSON files from `ats_results/ats_test_resumes_scores/`.

CORRECTED for Day 17:
- Flexible schema: only identifiers + final_score are required
- Decision derived from multiple fallback fields (decision, decision_logic.result,
  score_interpretation.rating, or threshold-based on final_score)
- Handles your actual scoring pipeline output format

Day: 17 (corrected)
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Strict requirements: file is rejected if these are missing
REQUIRED_KEYS = {
    "identifiers",
    "final_score",
}

# Soft requirements: file is accepted but DEBUG-logged if missing
RECOMMENDED_KEYS = {
    "scoring_breakdown",
    "score_interpretation",
}

# Required sub-keys inside identifiers
REQUIRED_IDENTIFIER_KEYS = {"resume_id", "jd_id"}


def _validate_score_schema(data: Dict[str, Any], filepath: Path) -> bool:
    """Validate that score JSON has the minimum schema. Returns True if valid.

    Strict checks:
      - 'identifiers' (with 'resume_id' + 'jd_id') must exist
      - 'final_score' must exist (numeric)
    Soft checks:
      - 'decision' or 'score_interpretation.rating' will be used for classification
        (derived if missing)
    """
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        logger.warning(f"[{filepath.name}] Missing required keys: {missing}")
        return False

    identifiers = data.get("identifiers")
    if not isinstance(identifiers, dict):
        logger.warning(f"[{filepath.name}] 'identifiers' is not a dict")
        return False

    missing_ids = REQUIRED_IDENTIFIER_KEYS - identifiers.keys()
    if missing_ids:
        logger.warning(f"[{filepath.name}] Missing identifier keys: {missing_ids}")
        return False

    # final_score must be numeric
    score = data.get("final_score")
    try:
        float(score)
    except (TypeError, ValueError):
        logger.warning(f"[{filepath.name}] 'final_score' is not numeric: {score}")
        return False

    # Soft warnings
    soft_missing = RECOMMENDED_KEYS - data.keys()
    if soft_missing:
        logger.debug(f"[{filepath.name}] Missing recommended keys: {soft_missing}")

    return True


def load_single_score(filepath: Path) -> Optional[Dict[str, Any]]:
    """Load and validate a single score JSON file. Returns None on failure."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        logger.error(f"Failed to load {filepath}: {e}")
        return None

    if not _validate_score_schema(data, filepath):
        return None

    return data


def load_all_scores(scores_dir) -> List[Dict[str, Any]]:
    """
    Load all score JSONs from the given directory.

    Args:
        scores_dir: Path to ats_results/ats_test_resumes_scores/

    Returns:
        List of validated score records (one per resume x JD pair).
    """
    scores_dir = Path(scores_dir)
    if not scores_dir.exists():
        logger.error(f"Scores directory does not exist: {scores_dir}")
        return []

    json_files = sorted(scores_dir.glob("*.json"))
    if not json_files:
        logger.warning(f"No JSON files found in {scores_dir}")
        return []

    records = []
    rejected_count = 0
    for fp in json_files:
        record = load_single_score(fp)
        if record is not None:
            record["_source_file"] = fp.name  # debug aid
            records.append(record)
        else:
            rejected_count += 1

    logger.info(
        f"Loaded {len(records)}/{len(json_files)} valid score files from {scores_dir}"
    )
    if rejected_count > 0:
        logger.warning(
            f"{rejected_count} files were rejected. "
            f"Run 'python scripts/diagnose_scores.py' for details."
        )
    return records


def extract_decision(record: Dict[str, Any], threshold: int = 70) -> str:
    """
    Extract a normalized decision from a score record.

    Priority:
      1. record['decision']                          (top-level field)
      2. record['decision_logic']['result']          (nested, your full schema)
      3. record['score_interpretation']['rating']    (mapped from rating string)
      4. Threshold-based on final_score              (computed fallback)

    Returns one of: 'Shortlisted', 'Manual Review', 'Rejected'
    """
    valid = {"Shortlisted", "Manual Review", "Rejected"}

    # Priority 1: top-level decision
    decision = record.get("decision")
    if decision in valid:
        return decision

    # Priority 2: decision_logic.result
    dl = record.get("decision_logic") or {}
    if isinstance(dl, dict) and dl.get("result") in valid:
        return dl["result"]

    # Priority 3: score_interpretation.rating mapped
    si = record.get("score_interpretation") or {}
    rating = (si.get("rating") or "").lower() if isinstance(si, dict) else ""
    if "strong fit" in rating or "good fit" in rating:
        return "Shortlisted"
    if "partial fit" in rating:
        return "Manual Review"
    if "weak fit" in rating or "poor fit" in rating:
        return "Rejected"

    # Priority 4: threshold-based on numeric score
    score = record.get("final_score")
    if score is None:
        score = record.get("overall_ats_score", 0)
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = 0.0

    if score >= threshold:
        return "Shortlisted"
    elif score >= 50:
        return "Manual Review"
    else:
        return "Rejected"


def get_resume_jd_pair_key(record: Dict[str, Any]) -> str:
    """Build a stable key like 'resume_id::jd_id' for joining with HR ground truth."""
    ids = record.get("identifiers", {})
    return f"{ids.get('resume_id', 'UNKNOWN')}::{ids.get('jd_id', 'UNKNOWN')}"


if __name__ == "__main__":
    # Quick smoke test
    logging.basicConfig(level=logging.INFO)
    import sys
    folder = sys.argv[1] if len(sys.argv) > 1 else "ats_results/ats_test_resumes_scores"
    scores = load_all_scores(folder)
    print(f"Loaded {len(scores)} score records")
    for s in scores[:3]:
        print(f"  - {get_resume_jd_pair_key(s)} -> {extract_decision(s)} (score={s.get('final_score')})")
