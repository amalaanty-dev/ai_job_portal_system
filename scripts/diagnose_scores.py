"""
scripts/diagnose_scores.py
==========================
Inspect a score JSON folder and report:
  - Total file count
  - Schema variants present
  - Common missing fields
  - Whether files belong to test resumes or dev resumes
  - Sample records

Run:
    python scripts/diagnose_scores.py
    python scripts/diagnose_scores.py path/to/folder

Day: 17
"""

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Resolve project root
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPTS_DIR)


def _list_test_resume_ids():
    """List filename-stems of test resumes for cross-checking."""
    folder = Path(_ROOT) / "data" / "resumes" / "ats_test_resumes"
    if not folder.exists():
        return set()
    ids = set()
    for f in folder.iterdir():
        if f.is_file():
            ids.add(f.stem)
    return ids


def diagnose(folder: Path):
    print(f"\nDiagnosing: {folder}")
    print("=" * 70)

    if not folder.exists():
        print(f"FOLDER DOES NOT EXIST: {folder}")
        return

    json_files = sorted(folder.glob("*.json"))
    print(f"Total .json files: {len(json_files)}")

    if not json_files:
        print("(empty)")
        return

    test_resume_ids = _list_test_resume_ids()
    print(f"Test resumes available: {len(test_resume_ids)}")

    top_keys_counter = Counter()
    schema_variants = defaultdict(list)
    parse_failures = []
    sample_records = []
    test_match_count = 0
    non_test_match_count = 0
    sample_test_match = []
    sample_non_test = []

    for fp in json_files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            parse_failures.append((fp.name, str(e)))
            continue

        if not isinstance(data, dict):
            schema_variants["non_dict"].append(fp.name)
            continue

        keys = frozenset(data.keys())
        top_keys_counter.update(keys)
        schema_variants[keys].append(fp.name)

        # Check if this score belongs to a test resume
        ids = data.get("identifiers", {}) or {}
        rid = ids.get("resume_id", "")
        # Try fuzzy match: test resume stem should appear inside resume_id
        if test_resume_ids and any(tid in rid or rid in tid for tid in test_resume_ids):
            test_match_count += 1
            if len(sample_test_match) < 3:
                sample_test_match.append((fp.name, rid))
        else:
            non_test_match_count += 1
            if len(sample_non_test) < 3:
                sample_non_test.append((fp.name, rid))

        if len(sample_records) < 2:
            sample_records.append((fp.name, data))

    # Report
    print(f"\nParse failures: {len(parse_failures)}")
    for name, err in parse_failures[:5]:
        print(f"  - {name}: {err[:100]}")

    print(f"\n[Test-resume match]")
    print(f"  Files matching test resumes:     {test_match_count}")
    print(f"  Files NOT matching test resumes: {non_test_match_count}")
    if sample_test_match:
        print("  Sample matching:")
        for fn, rid in sample_test_match:
            print(f"    {fn}  (resume_id={rid})")
    if sample_non_test:
        print("  Sample NOT matching:")
        for fn, rid in sample_non_test:
            print(f"    {fn}  (resume_id={rid})")

    print(f"\nDistinct schema variants: {len(schema_variants)}")
    for variant_keys, files in sorted(schema_variants.items(), key=lambda x: -len(x[1]))[:5]:
        print(f"\n  Variant ({len(files)} files):")
        if isinstance(variant_keys, frozenset):
            print(f"    keys: {sorted(variant_keys)}")
        else:
            print(f"    {variant_keys}")
        print(f"    sample file: {files[0]}")

    print("\nTop-level key frequency:")
    for key, count in top_keys_counter.most_common(20):
        print(f"  {key:35s} -> {count} files")

    print("\nSample records:")
    for name, rec in sample_records:
        print(f"\n  >>> {name}:")
        for k, v in rec.items():
            v_str = str(v)
            if len(v_str) > 80:
                v_str = v_str[:80] + "..."
            print(f"      {k}: {v_str}")


def main():
    if len(sys.argv) > 1:
        folder = Path(sys.argv[1])
    else:
        folder = Path(_ROOT) / "ats_results" / "ats_test_resumes_scores"

    diagnose(folder)


if __name__ == "__main__":
    main()
