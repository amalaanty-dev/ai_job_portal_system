"""
io_utils.py
------------
Small IO helpers for the Ranking Engine: JSON load/save and directory setup.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)


def ensure_dirs(paths: Iterable[Path]) -> None:
    """Create each path (as a directory) if it doesn't already exist."""
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict:
    """Load a JSON file and return its contents as a dict."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"JSON not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Any, path: Path, indent: int = 2) -> Path:
    """Save `data` as JSON to `path`. Creates parent directories as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
    return path


def list_json_files(directory: Path) -> list[Path]:
    """Return all *.json files in `directory` (non-recursive), sorted."""
    directory = Path(directory)
    if not directory.exists():
        logger.warning("Input directory does not exist: %s", directory)
        return []
    return sorted(directory.glob("*.json"))


def safe_get(d: dict, *keys, default=None):
    """Safely traverse nested dicts: safe_get(d, 'a', 'b', 'c')."""
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur
