"""
Fairness Utility Helpers
Path: ai_job_portal_system/utils/fairness_utils.py

Helper functions used across fairness_engine modules.
"""

import json
import os
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Union

# ---------------------------------------------------------------
# Logger setup
# ---------------------------------------------------------------
def get_logger(name: str = "fairness_engine") -> logging.Logger:
    """Standard logger for fairness module."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        fmt = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
        )
        ch.setFormatter(fmt)
        logger.addHandler(ch)
    return logger


# ---------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------
def load_json(filepath: Union[str, Path]) -> Dict[str, Any]:
    """Safely load JSON file."""
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"JSON file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Dict[str, Any], filepath: Union[str, Path], indent: int = 2) -> None:
    """Safely save JSON file (creates parent dirs)."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, default=str)


# ---------------------------------------------------------------
# String / Text Helpers
# ---------------------------------------------------------------
def clean_text(text: str) -> str:
    """Strip extra whitespace and unicode artifacts."""
    if not text:
        return ""
    text = text.replace("\uf0b7", "").replace("\uf0d8", "").replace("\u2022", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def safe_lower(value: Any) -> str:
    """Convert any value to lowercase string safely."""
    return str(value).lower() if value is not None else ""


def flatten_list(nested: List[Any]) -> List[Any]:
    """Flatten one level of nesting."""
    out = []
    for item in nested:
        if isinstance(item, list):
            out.extend(item)
        else:
            out.append(item)
    return out


# ---------------------------------------------------------------
# Skill / Token Helpers
# ---------------------------------------------------------------
def tokenize_skills(skill_block: List[str]) -> List[str]:
    """
    Take raw skill lines (often pipe/comma/newline separated)
    and return clean tokens.
    """
    tokens = []
    for line in skill_block:
        # split by comma, pipe, semicolon, or multiple spaces
        parts = re.split(r"[,;|]|\s{2,}", line)
        for p in parts:
            p = clean_text(p).strip(":")
            # strip category labels like "Programming & DB"
            if p and len(p) < 60:
                tokens.append(p.lower())
    # de-dupe preserving order
    seen, result = set(), []
    for t in tokens:
        if t not in seen and t:
            seen.add(t)
            result.append(t)
    return result


def normalize_skill_token(token: str, synonyms: Dict[str, List[str]]) -> str:
    """
    Map a skill token to its canonical form using synonym dict.
    Matches case-insensitively. Returns canonical key when token == any variant
    (canonical form included). Otherwise returns the lowercase token unchanged.
    """
    t = token.lower().strip()
    for canonical, variants in synonyms.items():
        # variants list may or may not include canonical itself
        variant_set = {v.lower() for v in variants} | {canonical.lower()}
        if t in variant_set:
            return canonical
    return t


# ---------------------------------------------------------------
# Numeric Helpers
# ---------------------------------------------------------------
def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Avoid ZeroDivisionError."""
    try:
        return numerator / denominator if denominator else default
    except (TypeError, ZeroDivisionError):
        return default


def round_score(value: float, decimals: int = 2) -> float:
    """Round to fixed decimals."""
    try:
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------
# Timestamp
# ---------------------------------------------------------------
def now_iso() -> str:
    """Return current timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------
# File path utilities
# ---------------------------------------------------------------
def ensure_dir(path: Union[str, Path]) -> Path:
    """Create directory if missing."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_resume_id(filepath: Union[str, Path]) -> str:
    """Extract resume_id from filepath."""
    return Path(filepath).stem
