"""All-in-one diagnostic for the empty-scores / empty-shortlists problem.

Run this AFTER bulk_load.py has finished. It will:
  1. Count files in api_data and api_data_results
  2. Print one parsed file, one score file (if any), one shortlist file
  3. Pick the first candidate + first job from metadata.json and try
     a single /v1/ats/score call directly — capturing the FULL response
     including any error from the server
  4. If scoring works, run /v1/ats/shortlist for that job and show result

Usage:
    py scripts/diagnose.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("[!] pip install httpx", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
META = ROOT / "api_data" / "metadata.json"
RESULTS = ROOT / "api_data_results"
API = "http://localhost:8000"


def banner(s):
    print()
    print("=" * 70)
    print(f"  {s}")
    print("=" * 70)


# 1. File counts
banner("1. File counts")
for sub, name in [
    ("api_data/raw_resumes", "raw resumes"),
    ("api_data/jds", "JDs"),
    ("api_data_results/parsed", "parsed artifacts"),
    ("api_data_results/scores", "score artifacts"),
    ("api_data_results/shortlists", "shortlist artifacts"),
]:
    p = ROOT / sub
    n = len(list(p.glob("*.*"))) if p.exists() else 0
    print(f"  {name:25s}: {n:5d}  ({p})")


# 2. Sample artifacts
banner("2. Sample artifacts")
for sub, label in [
    ("api_data_results/parsed", "PARSED"),
    ("api_data_results/scores", "SCORE"),
    ("api_data_results/shortlists", "SHORTLIST"),
]:
    p = ROOT / sub
    files = sorted(p.glob("*.json")) if p.exists() else []
    if files:
        print(f"\n  -- One {label} file ({files[0].name}) --")
        try:
            data = json.loads(files[0].read_text(encoding="utf-8"))
            print(json.dumps(data, indent=2)[:1000])
        except Exception as e:
            print(f"  [!] read error: {e}")
    else:
        print(f"\n  -- No {label} files in {sub} --")


# 3. Live scoring test
banner("3. Live scoring test (single pair)")
if not META.exists():
    print("[!] metadata.json missing — was the server ever run?")
    sys.exit(1)

meta = json.loads(META.read_text(encoding="utf-8"))
resumes = list(meta.get("resumes", {}).values())
jds = list(meta.get("jds", {}).values())

if not resumes or not jds:
    print(f"[!] No resumes ({len(resumes)}) or JDs ({len(jds)}) in metadata.")
    sys.exit(1)

cand_id = resumes[0]["candidate_id"]
job_id = jds[0]["job_id"]
print(f"  Trying: candidate_id={cand_id}  job_id={job_id}")

try:
    r = httpx.get(f"{API}/v1/health", timeout=5)
    r.raise_for_status()
except Exception as e:
    print(f"[!] API not reachable at {API}: {e}")
    print("    Start the server first: uvicorn api.main:app --reload")
    sys.exit(1)

print()
print("  --- POST /v1/ats/score ---")
r = httpx.post(
    f"{API}/v1/ats/score",
    json={"candidate_id": cand_id, "job_id": job_id},
    timeout=60,
)
print(f"  HTTP {r.status_code}")
print(f"  Response body:")
try:
    print("    " + json.dumps(r.json(), indent=2).replace("\n", "\n    "))
except Exception:
    print("    " + r.text[:1000])


# 4. Shortlist for that job
print()
print("  --- POST /v1/ats/shortlist ---")
r = httpx.post(
    f"{API}/v1/ats/shortlist",
    json={"job_id": job_id, "threshold": 0},
    timeout=30,
)
print(f"  HTTP {r.status_code}")
try:
    body = r.json()
    print(f"    total_candidates: {body.get('total_candidates')}")
    print(f"    shortlisted:      {body.get('shortlisted')}")
    print(f"    candidates:       {body.get('candidates', [])[:3]}{'...' if len(body.get('candidates', [])) > 3 else ''}")
except Exception:
    print(f"    {r.text[:1000]}")


# 5. Check stored scores
banner("4. Stored scores in metadata.json")
scores = meta.get("scores", {})
print(f"  Total stored: {len(scores)}")
if scores:
    print(f"  First key: {list(scores.keys())[0]}")
    print(f"  First value: {json.dumps(list(scores.values())[0], indent=2)[:400]}")


print()
print("=" * 70)
print("  SUMMARY")
print("=" * 70)
print(f"  - {len(resumes)} resumes registered")
print(f"  - {len(jds)} JDs registered")
print(f"  - {len(scores)} scores in metadata")
print(f"  - {len(list((ROOT/'api_data_results/scores').glob('*.json')))} score files on disk")
print(f"  - {len(list((ROOT/'api_data_results/shortlists').glob('*.json')))} shortlist files on disk")
