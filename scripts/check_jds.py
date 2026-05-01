"""JD validator + field-name diagnostic.

For each JD JSON, reports:
  - whether it's valid JSON
  - whether it has 'job_title' (or which alias keys it uses)
  - whether the loader's auto-remapping would fix it

Usage:
    py scripts/check_jds.py
    py scripts/check_jds.py path/to/jds_folder
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JDS_DIR = ROOT / "sample_inputs" / "jds"

JD_ALIASES = {
    "job_title": ["title", "position", "role", "job_role", "job_name", "designation", "name"],
    "required_skills": ["skills", "must_have_skills", "mandatory_skills", "key_skills",
                        "technical_skills", "required_skill", "skills_required"],
    "preferred_skills": ["nice_to_have", "good_to_have", "preferred", "optional_skills",
                          "secondary_skills", "additional_skills"],
    "experience_required": ["experience", "years_of_experience", "yoe", "min_experience",
                             "experience_years", "exp_required", "exp"],
    "education_required": ["education", "qualification", "qualifications", "degree",
                            "education_qualification"],
}

UNUSABLE = {"not specified", "n/a", "na", "none", "null", "tbd", "to be decided", "any", "-"}


def _usable_str_from(val) -> str | None:
    """Extract a usable non-empty string from val (which may be str or list)."""
    if val is None:
        return None
    if isinstance(val, list):
        for x in val:
            s = _usable_str_from(x)
            if s:
                return s
        return None
    if isinstance(val, str):
        s = val.strip()
        if not s or s.lower() in UNUSABLE:
            return None
        return s
    return str(val).strip() or None


if len(sys.argv) > 1:
    JDS_DIR = Path(sys.argv[1])

if not JDS_DIR.exists():
    print(f"[!] Folder not found: {JDS_DIR}")
    sys.exit(1)

ok = remappable = bad = 0
for p in sorted(JDS_DIR.glob("*.json")):
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[BAD JSON]  {p.name}: {e}")
        bad += 1
        continue

    if not isinstance(data, dict):
        print(f"[NOT DICT]  {p.name}: top-level must be JSON object, got {type(data).__name__}")
        bad += 1
        continue

    title = _usable_str_from(data.get("job_title"))
    if title:
        ok += 1
        continue

    # Look for alias keys the auto-remap would use
    found_alias = None
    found_value = None
    for alias in JD_ALIASES["job_title"]:
        v = _usable_str_from(data.get(alias))
        if v:
            found_alias = alias
            found_value = v
            break

    if found_alias:
        print(f"[REMAP OK]  {p.name}: '{found_alias}' = {found_value!r} -> auto-remap will fix this")
        remappable += 1
    else:
        keys = list(data.keys())[:8]
        print(f"[BAD]       {p.name}: no 'job_title' and no usable alias. Top-level keys: {keys}")
        bad += 1

print()
print(f"Summary: {ok} valid as-is, {remappable} auto-remappable, {bad} unfixable")
print(f"         Total: {ok + remappable + bad}")
print()
if remappable:
    print(f"-> Loader will auto-fix {remappable} files. Just run: py scripts/bulk_load.py --reset --threshold 60")
if bad:
    print(f"-> {bad} files need manual fixing — open them and add a 'job_title' field, or rename")
    print("   one of: title, position, role, designation, name, etc.")

sys.exit(0 if bad == 0 else 1)
