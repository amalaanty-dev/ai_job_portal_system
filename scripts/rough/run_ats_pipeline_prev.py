#!/usr/bin/env python3
"""
scripts/run_ats_pipeline.py
Day 13 – ATS Scoring Pipeline

OUTPUT FOLDER : ats_results/ats_scores/

Auto-discovery searches these folders (in order) for candidate JSON files:
    ats_results/          skill_engine/       semantic_engine/
    experience_engine/    education_engine/   resume_sections/
    data/                 data/parsed/        parsers/

Usage
-----
# Auto-discover all candidates across known engine output folders:
    python scripts/run_ats_pipeline.py

# Specify a single folder to scan:
    python scripts/run_ats_pipeline.py --auto-dir ats_results/

# Explicit single candidate:
    python scripts/run_ats_pipeline.py ^
        --skills     ats_results/Amala_Resume_DS_DA_2026__skills.json ^
        --education  ats_results/Amala_Resume_DS_DA_2026__sections.json ^
        --experience ats_results/Amala_Resume_DS_DA_2026__vs_ai_specialist_parsed_jd_experience.json ^
        --semantic   ats_results/Amala_Resume_DS_DA_2026__sections_semantic.json ^
        --role       healthcare_analytics

# Batch via manifest:
    python scripts/run_ats_pipeline.py --batch-manifest scripts/batch_manifest_example.json

# List role presets:
    python scripts/run_ats_pipeline.py --list-roles
"""

import argparse
import json
import os
import sys
import glob
import re
from pathlib import Path

# ── Allow running from project root ──────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ats_engine.ats_scorer import score_candidate
from ats_engine.weight_config import WeightConfig


# ── Default output folder ─────────────────────────────────────────────────────
DEFAULT_OUTPUT = os.path.join("ats_results", "ats_scores")

# ── Folders to search when auto-discovering candidate files ───────────────────
# These match the engine output folders visible in the project screenshot
SEARCH_DIRS = [
    "ats_results",
    "skill_engine",
    "semantic_engine",
    "experience_engine",
    "education_engine",
    "resume_sections",
    "data",
    os.path.join("data", "parsed"),
    "parsers",
]


# ─── Argument parsing ─────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="ATS Scoring Pipeline – Day 13  |  Output → ats_results/ats_scores/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--skills",      help="Path to *_skills.json")
    p.add_argument("--education",   help="Path to *_sections.json")
    p.add_argument("--experience",  help="Path to *_vs_*_experience.json")
    p.add_argument("--semantic",    help="Path to *_sections_semantic.json")
    p.add_argument("--role",        default="generic",
                   help="Role type preset (default: generic). Use --list-roles to see all.")
    p.add_argument("--output",      default=DEFAULT_OUTPUT,
                   help=f"Output directory (default: {DEFAULT_OUTPUT})")
    p.add_argument("--auto-dir",    dest="auto_dir",
                   help="Single folder to scan for *_skills.json files.")
    p.add_argument("--list-roles",  action="store_true",
                   help="Print all available role presets and exit")
    p.add_argument("--candidate-name",
                   help="Override candidate display name")
    p.add_argument("--jd-title",
                   help="Override JD title")
    p.add_argument("--batch-manifest",
                   help="Path to JSON manifest listing multiple candidates")
    return p.parse_args()


# ─── File discovery ───────────────────────────────────────────────────────────

def _glob_dir(directory: str, pattern: str) -> list:
    """Return sorted glob matches; empty list if directory missing."""
    if not os.path.isdir(directory):
        return []
    return sorted(glob.glob(os.path.join(directory, pattern)))


def find_skills_files(search_dirs: list) -> list:
    """Find all *_skills.json files across multiple directories (deduped)."""
    found = []
    seen  = set()
    for d in search_dirs:
        for f in _glob_dir(d, "*_skills.json"):
            key = os.path.abspath(f)
            if key not in seen:
                seen.add(key)
                found.append(f)
    return found


def find_sibling(skills_path: str, search_dirs: list, suffix: str) -> str | None:
    """
    Find a sibling file: replace _skills.json with suffix.
    Checks same directory first, then all search_dirs.
    """
    base   = os.path.basename(skills_path)
    prefix = re.sub(r"_skills\.json$", "", base)
    target = prefix + suffix

    # 1) Same folder as skills file
    candidate = os.path.join(os.path.dirname(skills_path), target)
    if os.path.exists(candidate):
        return candidate

    # 2) All search directories
    for d in search_dirs:
        candidate = os.path.join(d, target)
        if os.path.exists(candidate):
            return candidate

    return None


def find_experience(skills_path: str, search_dirs: list) -> str | None:
    """
    Experience filename has JD embedded: <prefix>_vs_<jd>_experience.json
    Match with wildcard pattern.
    """
    base    = os.path.basename(skills_path)
    prefix  = re.sub(r"_skills\.json$", "", base)
    pattern = prefix + "_vs_*_experience.json"

    # Same directory first
    hits = _glob_dir(os.path.dirname(skills_path), pattern)
    if hits:
        return hits[0]

    # All search directories
    for d in search_dirs:
        hits = _glob_dir(d, pattern)
        if hits:
            return hits[0]

    return None


def auto_discover(search_dirs: list) -> list:
    """
    Discover all candidate file sets.
    Anchored on *_skills.json; siblings located by naming convention.
    """
    skills_files = find_skills_files(search_dirs)
    candidates   = []

    for sf in skills_files:
        # Skip any skills file that lives inside ats_results/ats_scores
        # (those are already processed outputs, not inputs)
        if os.path.normpath(DEFAULT_OUTPUT) in os.path.normpath(sf):
            continue

        candidates.append({
            "skills":     sf,
            "education":  find_sibling(sf, search_dirs, "_sections.json"),
            "experience": find_experience(sf, search_dirs),
            "semantic":   find_sibling(sf, search_dirs, "_sections_semantic.json"),
        })

    return candidates


# ─── Batch manifest ───────────────────────────────────────────────────────────

def score_from_manifest(manifest_path: str, output_dir: str, default_role: str) -> list:
    """
    Score multiple candidates from a manifest JSON file.

    Manifest format:
    [
      {
        "skills":         "path/to/skills.json",
        "education":      "path/to/sections.json",
        "experience":     "path/to/experience.json",
        "semantic":       "path/to/semantic.json",
        "role_type":      "data_scientist",     (optional)
        "candidate_name": "Name Override",      (optional)
        "jd_title":       "JD Override"         (optional)
      }
    ]
    """
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    results = []
    total   = len(manifest)
    for i, entry in enumerate(manifest, 1):
        name = entry.get("candidate_name") or f"Candidate {i}"
        print(f"\n[Pipeline] [{i}/{total}] Scoring {name}…")
        r = score_candidate(
            skills_path     = entry.get("skills"),
            education_path  = entry.get("education"),
            experience_path = entry.get("experience"),
            semantic_path   = entry.get("semantic"),
            role_type       = entry.get("role_type", default_role),
            candidate_name  = entry.get("candidate_name"),
            jd_title        = entry.get("jd_title"),
            output_dir      = output_dir,
        )
        _print_summary(r)
        results.append(_summary_row(r))

    _write_batch_summary(results, output_dir)
    return results


# ─── Display helpers ──────────────────────────────────────────────────────────

def _summary_row(r: dict) -> dict:
    return {
        "candidate":  r["metadata"]["candidate_name"],
        "jd_title":   r["metadata"]["jd_title"],
        "role_type":  r["metadata"]["role_type"],
        "composite":  r["composite_score"],
        "verdict":    r["verdict"]["label"],
        "skill":      r["components"]["skill_match"]["score"],
        "education":  r["components"]["education_alignment"]["score"],
        "experience": r["components"]["experience_relevance"]["score"],
        "semantic":   r["components"]["semantic_similarity"]["score"],
        "gaps":       len(r["gaps"]),
        "json_out":   r.get("_output_json", ""),
        "html_out":   r.get("_output_html", ""),
    }


def _write_batch_summary(results: list, output_dir: str):
    path = os.path.join(output_dir, "batch_summary.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[Pipeline] Batch summary written → {os.path.abspath(path)}")


def _print_summary(r: dict):
    labels = {
        "skill_match":          "Skill Match",
        "education_alignment":  "Education Alignment",
        "experience_relevance": "Experience Relevance",
        "semantic_similarity":  "Semantic Similarity",
    }
    m = r["metadata"]
    print()
    print("─" * 65)
    print(f"  Candidate  : {m['candidate_name']}")
    print(f"  JD         : {m['jd_title']}")
    print(f"  Role Type  : {m['role_type']}")
    print(f"  Composite  : {r['composite_score']}/100  "
          f"{r['verdict']['icon']} {r['verdict']['label']}")
    print()
    print("  Component Scores:")
    for key, comp in r["components"].items():
        avail = "" if comp["data_available"] else "  [no data]"
        print(f"    {labels.get(key, key):<28} {comp['score']:>6.1f} / 100{avail}")
    print()
    if r["gaps"]:
        print("  Gaps Detected:")
        for g in r["gaps"]:
            sev = g["severity"].upper()
            sec = g["section"].replace("_", " ").title()
            rec = g["recommendation"][:58]
            print(f"    [{sev:10}] {sec}: {rec}…")
    print("─" * 65)
    print(f"  JSON  → {r['_output_json']}")
    print(f"  HTML  → {r['_output_html']}")
    print()


def _print_discovered(candidates: list):
    print(f"\n[Pipeline] Discovered {len(candidates)} candidate(s):\n")
    for i, c in enumerate(candidates, 1):
        name = os.path.basename(c["skills"]).replace("_skills.json", "")
        e = "✔" if c["education"]  else "✘"
        x = "✔" if c["experience"] else "✘"
        s = "✔" if c["semantic"]   else "✘"
        print(f"  {i}. {name}")
        print(f"       skills=✔  education={e}  experience={x}  semantic={s}")
    print()


def _print_no_candidates(scan_dirs: list):
    print("\n[Pipeline] ✘ No *_skills.json files found.\n")
    print("  Folders scanned:")
    for d in scan_dirs:
        status = "exists" if os.path.isdir(d) else "not found"
        print(f"    {d}  ({status})")
    print()
    print("  Fix options:")
    print()
    print("  Option 1 – Explicit paths (most reliable):")
    print("    python scripts/run_ats_pipeline.py \\")
    print("      --skills     ats_results/YourName__skills.json \\")
    print("      --education  ats_results/YourName__sections.json \\")
    print("      --experience ats_results/YourName__vs_JD_experience.json \\")
    print("      --semantic   ats_results/YourName__sections_semantic.json \\")
    print("      --role       healthcare_analytics")
    print()
    print("  Option 2 – Point to exact folder containing *_skills.json:")
    print("    python scripts/run_ats_pipeline.py --auto-dir <folder_path>/")
    print()
    print("  Run  dir /s /b *.json | findstr _skills  to locate your files.")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    args       = parse_args()
    output_dir = args.output

    # ── List role presets ─────────────────────────────────────────────────────
    if args.list_roles:
        print("\nAvailable role presets:\n")
        for name in WeightConfig.list_presets():
            w     = WeightConfig.get_weights(name)
            parts = [f"{k.split('_')[0]}={v:.0%}" for k, v in w.items()]
            print(f"  {name:<28} {', '.join(parts)}")
        print()
        sys.exit(0)

    # Ensure output folder exists
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n[Pipeline] Output → {os.path.abspath(output_dir)}")

    # ── Batch manifest ────────────────────────────────────────────────────────
    if args.batch_manifest:
        if not os.path.exists(args.batch_manifest):
            print(f"[Pipeline] ERROR: Manifest not found: {args.batch_manifest}")
            sys.exit(1)
        score_from_manifest(args.batch_manifest, output_dir, args.role)
        return

    # ── Explicit single candidate ─────────────────────────────────────────────
    if any([args.skills, args.education, args.experience, args.semantic]):
        print(f"[Pipeline] Single-candidate mode  |  role={args.role}")
        r = score_candidate(
            skills_path     = args.skills,
            education_path  = args.education,
            experience_path = args.experience,
            semantic_path   = args.semantic,
            role_type       = args.role,
            candidate_name  = args.candidate_name,
            jd_title        = args.jd_title,
            output_dir      = output_dir,
        )
        _print_summary(r)
        return

    # ── Auto-discover mode ────────────────────────────────────────────────────
    if args.auto_dir:
        scan_dirs = [args.auto_dir]
    else:
        # No flags → scan all known engine output folders
        # Both absolute (from ROOT) and relative (from cwd)
        scan_dirs = []
        for d in SEARCH_DIRS:
            scan_dirs.append(d)                        # relative to cwd
            scan_dirs.append(str(ROOT / d))            # absolute

    print(f"[Pipeline] Auto-discover mode  |  role={args.role}")

    candidates = auto_discover(scan_dirs)

    if not candidates:
        _print_no_candidates(list(dict.fromkeys(scan_dirs)))  # dedupe for display
        sys.exit(1)

    _print_discovered(candidates)

    all_results = []
    for i, c in enumerate(candidates, 1):
        print(f"[Pipeline] [{i}/{len(candidates)}] Processing…")
        r = score_candidate(
            skills_path     = c["skills"],
            education_path  = c["education"],
            experience_path = c["experience"],
            semantic_path   = c["semantic"],
            role_type       = args.role,
            output_dir      = output_dir,
        )
        _print_summary(r)
        all_results.append(_summary_row(r))

    if len(all_results) > 1:
        _write_batch_summary(all_results, output_dir)

    print(f"[Pipeline] ✅ Done. {len(all_results)} candidate(s) scored.")
    print(f"[Pipeline] Output → {os.path.abspath(output_dir)}\n")


if __name__ == "__main__":
    main()
