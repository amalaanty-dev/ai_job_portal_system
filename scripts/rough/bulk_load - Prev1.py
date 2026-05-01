"""Bulk loader for the Zecpath ATS API.

Drops all PDFs from a folder and all JD JSONs from another folder into the
running API, then runs the full N x M scoring and shortlist pipeline.

Robust against bad input:
  - JDs are pre-validated locally; malformed ones are skipped (not fatal)
  - On batch upload failure, falls back to one-by-one upload so one bad
    record doesn't kill the run
  - Verbose error reporting: prints the server's actual error message

Usage:
    py scripts/bulk_load.py
    py scripts/bulk_load.py --resumes-dir my_resumes --jds-dir my_jds
    py scripts/bulk_load.py --threshold 60 --top-n 10
    py scripts/bulk_load.py --reset
"""
from __future__ import annotations
import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    print("[!] httpx not installed. Run: pip install httpx", file=sys.stderr)
    sys.exit(1)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESUMES_DIR = PROJECT_ROOT / "sample_inputs" / "resumes"
DEFAULT_JDS_DIR = PROJECT_ROOT / "sample_inputs" / "jds"
ALLOWED_EXTS = {".pdf", ".docx", ".doc"}


def banner(msg: str) -> None:
    print()
    print("=" * 70)
    print(f"  {msg}")
    print("=" * 70)


def _safe_error(resp: httpx.Response) -> str:
    """Pull the server's error message out of a non-2xx response."""
    try:
        body = resp.json()
        if isinstance(body, dict):
            return body.get("message") or body.get("detail") or str(body)
    except Exception:
        pass
    return resp.text[:500]


# ---------- JD upload ----------

# Common field-name aliases. Maps API canonical name → list of aliases the
# parser/source data might use. First match wins.
JD_FIELD_ALIASES: dict[str, list[str]] = {
    "job_title": ["title", "position", "role", "job_role", "job_name", "designation", "name"],
    "required_skills": ["skills", "must_have_skills", "mandatory_skills", "key_skills",
                        "technical_skills", "required_skill", "skills_required"],
    "preferred_skills": ["nice_to_have", "good_to_have", "preferred", "optional_skills",
                          "secondary_skills", "additional_skills"],
    "experience_required": ["experience", "years_of_experience", "yoe", "min_experience",
                             "experience_years", "exp_required", "exp"],
    "education_required": ["education", "qualification", "qualifications", "degree",
                            "education_qualification"],
    "location": ["job_location", "city", "place"],
    "description": ["job_description", "summary", "details", "about_role", "about"],
}


def _coerce_to_str_list(val: Any) -> list[str] | None:
    """Best-effort coercion to list of strings."""
    if val is None:
        return None
    if isinstance(val, list):
        return [str(x).strip() for x in val if x is not None and str(x).strip()]
    if isinstance(val, str):
        # Comma- or semicolon-separated string
        parts = [p.strip() for p in val.replace(";", ",").split(",")]
        return [p for p in parts if p]
    return [str(val)]


def _coerce_to_number(val: Any) -> float | None:
    """Best-effort coercion to a number; pull first int from things like '3 years'."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        import re
        m = re.search(r"\d+(?:\.\d+)?", val)
        return float(m.group()) if m else None
    return None


UNUSABLE_VALUES = {"not specified", "n/a", "na", "none", "null", "tbd", "to be decided", "any", "-"}


def _is_usable(val: Any) -> bool:
    """A value is 'usable' if it's not None, not empty, and not a placeholder string."""
    if val is None or val == "" or val == [] or val == {}:
        return False
    if isinstance(val, str) and val.strip().lower() in UNUSABLE_VALUES:
        return False
    return True


def _remap_jd_fields(data: dict) -> dict:
    """Rewrite a JD dict so the API's canonical field names are present,
    pulling values from common alias names if the canonical key is missing
    or contains placeholder text like 'Not specified'."""
    out = dict(data)  # don't mutate caller's dict
    for canonical, aliases in JD_FIELD_ALIASES.items():
        if _is_usable(out.get(canonical)):
            continue  # canonical key has a real value — leave it
        # canonical missing or placeholder; try aliases
        for alias in aliases:
            if _is_usable(out.get(alias)):
                out[canonical] = out[alias]
                break

    # job_title: accept list (take first), other non-strings -> str()
    title = out.get("job_title")
    if isinstance(title, list):
        out["job_title"] = next((str(x).strip() for x in title if x), None)
    elif title is not None and not isinstance(title, str):
        out["job_title"] = str(title)
    if isinstance(out.get("job_title"), str):
        out["job_title"] = out["job_title"].strip()
    if not out.get("job_title"):
        out.pop("job_title", None)

    # Type coercions on the canonical fields (handles parser quirks)
    for key in ("required_skills", "preferred_skills", "education_required"):
        if key in out:
            coerced = _coerce_to_str_list(out[key])
            if coerced is not None and coerced:
                out[key] = coerced
            else:
                out.pop(key, None)

    if "experience_required" in out:
        n = _coerce_to_number(out["experience_required"])
        if n is not None:
            out["experience_required"] = n
        else:
            out.pop("experience_required", None)

    return out


def _validate_jd(data: Any) -> str | None:
    """Return None if valid, else a short error string."""
    if not isinstance(data, dict):
        return f"top-level must be JSON object, got {type(data).__name__}"
    title = data.get("job_title")
    if not isinstance(title, str) or not title.strip():
        # Hint at what aliases exist in the data
        present = [k for k in data.keys() if k in JD_FIELD_ALIASES["job_title"]]
        hint = f" (saw alias keys: {present})" if present else ""
        return f"missing or empty 'job_title' (must be non-empty string){hint}"
    for key in ("required_skills", "preferred_skills", "education_required"):
        v = data.get(key)
        if v is not None and not isinstance(v, list):
            return f"'{key}' must be a list, got {type(v).__name__}"
        if isinstance(v, list):
            non_str = [i for i, x in enumerate(v) if not isinstance(x, str)]
            if non_str:
                return f"'{key}' must contain only strings (bad at positions {non_str})"
    er = data.get("experience_required")
    if er is not None and not isinstance(er, (int, float)):
        return f"'experience_required' must be a number, got {type(er).__name__}"
    return None


def upload_jds(client: httpx.Client, jds_dir: Path) -> list[str]:
    jd_files = sorted(p for p in jds_dir.iterdir() if p.suffix.lower() == ".json")
    if not jd_files:
        print(f"[!] No JSON files found in {jds_dir}")
        return []

    print(f"[i] Found {len(jd_files)} JD file(s) in {jds_dir}")

    valid_jobs: list[dict] = []
    valid_files: list[Path] = []
    skipped = 0
    remapped = 0
    for p in jd_files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"    [-] Skipping malformed JSON {p.name}: {e}")
            skipped += 1
            continue

        # Try field-name remapping for common parser variants
        if isinstance(data, dict):
            original_title = data.get("job_title")
            data = _remap_jd_fields(data)
            if not original_title and data.get("job_title"):
                remapped += 1

        err = _validate_jd(data)
        if err:
            print(f"    [-] Skipping {p.name}: {err}")
            skipped += 1
            continue
        valid_jobs.append(data)
        valid_files.append(p)

    if remapped:
        print(f"[i] Auto-remapped field names in {remapped} JD file(s)")
    if skipped:
        print(f"[i] Skipped {skipped} invalid JD file(s); proceeding with {len(valid_jobs)}")

    if not valid_jobs:
        print("[!] No valid JDs to upload")
        return []

    # Try batch upload first (fast path)
    job_ids: list[str] = []
    try:
        # API caps batch at 100; chunk if needed
        for i in range(0, len(valid_jobs), 100):
            chunk = valid_jobs[i:i + 100]
            r = client.post("/v1/jd/upload/batch", json={"jobs": chunk}, timeout=120)
            r.raise_for_status()
            job_ids.extend(r.json()["job_ids"])
        print(f"[+] Uploaded {len(job_ids)} JD(s) (batch)")
        return job_ids
    except httpx.HTTPStatusError as e:
        print(f"[!] Batch upload failed: {e.response.status_code} — {_safe_error(e.response)}")
        print("[i] Falling back to one-by-one upload (slower but isolates bad records)")

    # Fallback: one at a time
    for jd, src in zip(valid_jobs, valid_files):
        try:
            r = client.post("/v1/jd/upload", json=jd, timeout=30)
            r.raise_for_status()
            job_ids.append(r.json()["job_id"])
        except httpx.HTTPStatusError as e:
            print(f"    [-] {src.name} rejected: {e.response.status_code} — {_safe_error(e.response)}")
        except Exception as e:
            print(f"    [-] {src.name} failed: {e}")

    print(f"[+] Uploaded {len(job_ids)}/{len(valid_jobs)} JD(s) individually")
    return job_ids


# ---------- Resume upload ----------

def upload_resumes(client: httpx.Client, resumes_dir: Path) -> list[dict[str, Any]]:
    pdfs = sorted(p for p in resumes_dir.iterdir() if p.suffix.lower() in ALLOWED_EXTS)
    if not pdfs:
        print(f"[!] No PDF/DOCX files found in {resumes_dir}")
        return []

    print(f"[i] Found {len(pdfs)} resume file(s) in {resumes_dir}")
    items: list[dict[str, Any]] = []

    # Batch in chunks of 50 to stay well under any limit
    chunk_size = 50
    for i in range(0, len(pdfs), chunk_size):
        chunk = pdfs[i:i + chunk_size]
        files = [
            ("files", (p.name, p.read_bytes(), "application/pdf"))
            for p in chunk
        ]
        try:
            r = client.post("/v1/resume/upload/batch", files=files, timeout=300)
            r.raise_for_status()
            body = r.json()
            items.extend(body["items"])
            for err in body.get("errors", []):
                print(f"    [-] {err}")
        except httpx.HTTPStatusError as e:
            print(f"[!] Resume batch failed: {e.response.status_code} — {_safe_error(e.response)}")
            print("[i] Falling back to one-by-one resume upload")
            for p in chunk:
                try:
                    r = client.post(
                        "/v1/resume/upload",
                        files={"file": (p.name, p.read_bytes(), "application/pdf")},
                        timeout=60,
                    )
                    r.raise_for_status()
                    body = r.json()
                    items.append({
                        "resume_id": body["resume_id"],
                        "candidate_id": body["candidate_id"],
                        "filename": body["filename"],
                        "size_bytes": body["size_bytes"],
                    })
                except Exception as ex:
                    print(f"    [-] {p.name}: {ex}")

    print(f"[+] Uploaded {len(items)}/{len(pdfs)} resume(s)")
    return items


def parse_resumes(client: httpx.Client, resume_ids: list[str]) -> None:
    if not resume_ids:
        return
    print(f"[i] Parsing {len(resume_ids)} resume(s)")
    parsed_ok = 0
    # Batch in chunks of 100
    for i in range(0, len(resume_ids), 100):
        chunk = resume_ids[i:i + 100]
        try:
            r = client.post(
                "/v1/resume/parse/batch",
                json={"resume_ids": chunk},
                timeout=600,
            )
            r.raise_for_status()
            body = r.json()
            parsed_ok += len(body["parsed"])
            for err in body.get("errors", []):
                print(f"    [-] {err}")
        except httpx.HTTPStatusError as e:
            print(f"[!] Parse batch failed: {e.response.status_code} — {_safe_error(e.response)}")
    print(f"[+] Parsed {parsed_ok}/{len(resume_ids)} resume(s)")


def score_matrix(
    client: httpx.Client,
    candidate_ids: list[str],
    job_ids: list[str],
    threshold: float,
    max_jobs_per_call: int = 50,
    max_candidates_per_call: int = 200,
) -> dict[str, Any]:
    """Score N x M concurrently. Chunks large requests to stay under API caps."""
    total = len(candidate_ids) * len(job_ids)
    print(f"[i] Scoring {len(candidate_ids)} candidate(s) x {len(job_ids)} JD(s) = {total} pair(s)")

    # Decide whether to chunk
    job_chunks = [job_ids[i:i + max_jobs_per_call] for i in range(0, len(job_ids), max_jobs_per_call)]
    cand_chunks = [candidate_ids[i:i + max_candidates_per_call]
                    for i in range(0, len(candidate_ids), max_candidates_per_call)]
    n_calls = len(job_chunks) * len(cand_chunks)
    if n_calls > 1:
        print(f"[i] Splitting into {n_calls} batch call(s) to stay under API limits")

    all_scores: list[dict] = []
    all_errors: list[dict] = []

    for ci, cands in enumerate(cand_chunks, 1):
        for ji, jobs in enumerate(job_chunks, 1):
            if n_calls > 1:
                print(f"    [chunk {(ci-1)*len(job_chunks)+ji}/{n_calls}] "
                      f"{len(cands)} cand x {len(jobs)} jobs = {len(cands)*len(jobs)} pairs")
            try:
                r = client.post(
                    "/v1/ats/score/batch",
                    json={
                        "candidate_ids": cands,
                        "job_ids": jobs,
                        "shortlist_threshold": threshold,
                    },
                    timeout=900,
                )
                r.raise_for_status()
                body = r.json()
                all_scores.extend(body.get("scores", []))
                all_errors.extend(body.get("errors", []))
            except httpx.HTTPStatusError as e:
                msg = _safe_error(e.response)
                print(f"    [-] chunk failed: {e.response.status_code} — {msg}")
                # Add a synthetic error per pair so totals reconcile
                for c in cands:
                    for j in jobs:
                        all_errors.append({"candidate_id": c, "job_id": j,
                                            "error_type": "BatchHTTPError", "error": msg})

    print(f"[+] Scored {len(all_scores)}/{total} pair(s), {len(all_errors)} error(s)")

    if all_errors:
        from collections import Counter
        fingerprint = Counter()
        for err in all_errors:
            key = f"{err.get('error_type', '?')}: {err.get('error', err)}"
            fingerprint[key] += 1
        print(f"[!] Error breakdown:")
        for msg, count in fingerprint.most_common(20):
            print(f"      x{count}  {msg}")
        if not all_scores:
            print()
            print("[!] No scores succeeded. Check server log for tracebacks.")

    return {"total_pairs": total, "scores": all_scores, "errors": all_errors}


def generate_shortlists(
    client: httpx.Client,
    job_ids: list[str],
    threshold: float,
    top_n: int | None,
) -> None:
    print(f"[i] Generating shortlists (threshold={threshold}, top_n={top_n or 'all'})")
    for jid in job_ids:
        payload: dict[str, Any] = {"job_id": jid, "threshold": threshold}
        if top_n is not None:
            payload["top_n"] = top_n
        try:
            r = client.post("/v1/ats/shortlist", json=payload, timeout=60)
            r.raise_for_status()
            body = r.json()
            print(f"    [+] {jid}: {body['shortlisted']}/{body['total_candidates']} shortlisted")
        except httpx.HTTPStatusError as e:
            print(f"    [-] {jid}: {e.response.status_code} — {_safe_error(e.response)}")


def reset_storage() -> None:
    for p in (PROJECT_ROOT / "api_data", PROJECT_ROOT / "api_data_results"):
        if p.exists():
            shutil.rmtree(p)
            print(f"[i] Removed {p}")
    # Recreate the directory skeleton so the API can write into them.
    for sub in (
        "api_data/raw_resumes",
        "api_data/jds",
        "api_data_results/parsed",
        "api_data_results/scores",
        "api_data_results/shortlists",
    ):
        (PROJECT_ROOT / sub).mkdir(parents=True, exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk-load resumes & JDs into the ATS API")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--resumes-dir", type=Path, default=DEFAULT_RESUMES_DIR)
    parser.add_argument("--jds-dir", type=Path, default=DEFAULT_JDS_DIR)
    parser.add_argument("--threshold", type=float, default=70.0)
    parser.add_argument("--top-n", type=int, default=None)
    parser.add_argument("--reset", action="store_true", help="Wipe api_data/ and api_data_results/ first")
    parser.add_argument("--skip-scoring", action="store_true", help="Only upload, no scoring")
    args = parser.parse_args()

    if args.reset:
        banner("Step 0: Reset storage")
        reset_storage()

    if not args.resumes_dir.exists():
        print(f"[!] Resumes folder not found: {args.resumes_dir}")
        return 1
    if not args.jds_dir.exists():
        print(f"[!] JDs folder not found: {args.jds_dir}")
        return 1

    client = httpx.Client(base_url=args.api_url)

    # Health check
    try:
        r = client.get("/v1/health", timeout=5)
        r.raise_for_status()
    except Exception as e:
        print(f"[!] Cannot reach API at {args.api_url} — is the server running?")
        print(f"    Start it with: uvicorn api.main:app --reload")
        print(f"    Error: {e}")
        return 1

    started = time.time()

    banner("Step 1: Upload JDs")
    job_ids = upload_jds(client, args.jds_dir)
    if not job_ids:
        print("[!] No JDs uploaded — aborting")
        return 1

    banner("Step 2: Upload resumes")
    resume_items = upload_resumes(client, args.resumes_dir)
    candidate_ids = [item["candidate_id"] for item in resume_items]
    resume_ids = [item["resume_id"] for item in resume_items]
    if not candidate_ids:
        print("[!] No resumes uploaded — aborting")
        return 1

    if args.skip_scoring:
        print("[i] Skipping scoring (--skip-scoring set)")
        return 0

    banner("Step 3: Parse resumes")
    parse_resumes(client, resume_ids)

    banner("Step 4: Score N x M matrix")
    score_matrix(client, candidate_ids, job_ids, args.threshold)

    banner("Step 5: Generate shortlists")
    generate_shortlists(client, job_ids, args.threshold, args.top_n)

    banner("Done!")
    elapsed = time.time() - started
    print(f"[i] Total time: {elapsed:.1f}s")
    print()
    print("Inspect outputs:")
    print(f"  {PROJECT_ROOT / 'api_data_results' / 'parsed'}     ({len(resume_ids)} files expected)")
    print(f"  {PROJECT_ROOT / 'api_data_results' / 'scores'}     ({len(candidate_ids)*len(job_ids)} files expected)")
    print(f"  {PROJECT_ROOT / 'api_data_results' / 'shortlists'} ({len(job_ids)} files expected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
