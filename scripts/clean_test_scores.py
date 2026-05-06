"""
scripts/clean_test_scores.py
============================
Smart cleanup of `ats_results/ats_test_resumes_scores/`.

Removes any score JSONs whose `identifiers.resume_id` does NOT match any
filename in `data/resumes/ats_test_resumes/`. This is useful when the
folder accidentally got polluted with dev-pipeline outputs (e.g., 528
files from the old 8 resumes x 66 JDs run).

Run:
    python scripts/clean_test_scores.py            # dry-run (lists what WOULD be deleted)
    python scripts/clean_test_scores.py --apply    # actually delete

Day: 17
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Project root
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPTS_DIR)

TEST_RESUMES_DIR = Path(_ROOT) / "data" / "resumes" / "ats_test_resumes"
TEST_SCORES_DIR = Path(_ROOT) / "ats_results" / "ats_test_resumes_scores"


def list_test_resume_ids() -> set:
    """Return filename stems of test resumes (lowercased for fuzzy matching)."""
    if not TEST_RESUMES_DIR.exists():
        return set()
    ids = set()
    for f in TEST_RESUMES_DIR.iterdir():
        if f.is_file():
            ids.add(f.stem)
            ids.add(f.stem.lower())
    return ids


def is_test_score(filepath: Path, test_ids: set) -> bool:
    """Decide whether a given score JSON belongs to a test resume."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        # Malformed file -> treat as non-test (safer to remove)
        return False

    ids = data.get("identifiers", {}) or {}
    rid = (ids.get("resume_id") or "").lower()

    if not rid:
        return False
    if not test_ids:
        # No test resumes available -> can't determine; leave alone
        return True

    # Match if any test ID is a substring of the resume_id (or vice versa)
    for tid in test_ids:
        if not tid:
            continue
        if tid in rid or rid in tid:
            return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Clean ats_test_resumes_scores/ of files not belonging to test resumes",
    )
    parser.add_argument("--apply", action="store_true",
                        help="Actually delete files. Without this, only lists.")
    parser.add_argument("--all", action="store_true",
                        help="Delete ALL files (full reset). Use with --apply.")
    args = parser.parse_args()

    if not TEST_SCORES_DIR.exists():
        print(f"Scores folder does not exist: {TEST_SCORES_DIR}")
        return 1

    json_files = sorted(TEST_SCORES_DIR.glob("*.json"))
    print(f"Folder: {TEST_SCORES_DIR}")
    print(f"Total files: {len(json_files)}")

    if args.all:
        if args.apply:
            for fp in json_files:
                fp.unlink()
            print(f"Deleted ALL {len(json_files)} files (full reset)")
        else:
            print(f"DRY-RUN: would delete ALL {len(json_files)} files")
            print("Add --apply to actually delete.")
        return 0

    test_ids = list_test_resume_ids()
    print(f"Test resumes available: {len(test_ids)} (in {TEST_RESUMES_DIR})")

    if not test_ids:
        print(
            "WARNING: No test resumes found. Cannot identify which scores belong "
            "to test resumes. Use --all if you want to wipe everything."
        )
        return 1

    keep = []
    remove = []
    for fp in json_files:
        if is_test_score(fp, test_ids):
            keep.append(fp.name)
        else:
            remove.append(fp.name)

    print(f"\nKeep:   {len(keep):4d} files (match test resumes)")
    print(f"Remove: {len(remove):4d} files (do NOT match test resumes)")

    if remove[:5]:
        print("\nFirst 5 to remove:")
        for n in remove[:5]:
            print(f"  - {n}")

    if not args.apply:
        print(f"\nDRY-RUN. Add --apply to actually delete the {len(remove)} non-test files.")
        return 0

    deleted = 0
    for name in remove:
        try:
            (TEST_SCORES_DIR / name).unlink()
            deleted += 1
        except Exception as e:
            print(f"  Failed to delete {name}: {e}")

    print(f"\nDeleted {deleted} non-test score files.")
    print(f"Remaining: {len(keep)} test score files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
