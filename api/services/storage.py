"""File + metadata persistence layer.

Inputs (raw resumes, JD JSONs) live under `api_data/`.
Outputs (parsed profiles, scores, shortlists) live under `api_data_results/`,
each as a standalone JSON artifact for easy inspection / export.
"""
from __future__ import annotations
import hashlib
import json
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import UploadFile

from api.config import settings
from api.core.exceptions import InvalidInputError, NotFoundError

_LOCK = threading.RLock()


# ---------- helpers ----------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _atomic_write_json(path: Path, payload: Any) -> Path:
    """Write JSON atomically (tmp + rename) so readers never see partial files.

    Uses a unique tmp filename per call (PID + monotonic counter) so concurrent
    writes to the SAME final path don't collide on the tmp file.
    """
    import os, threading
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique tmp suffix → no two concurrent writers ever pick the same tmp file
    uniq = f".{os.getpid()}.{threading.get_ident()}.{_atomic_counter()}.tmp"
    tmp = path.with_suffix(path.suffix + uniq)
    try:
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        # On Windows, os.replace works even if target exists; safer than Path.replace
        os.replace(tmp, path)
    finally:
        # Clean up tmp if rename failed
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
    return path


_ATOMIC_COUNTER = [0]
_ATOMIC_COUNTER_LOCK = threading.Lock()


def _atomic_counter() -> int:
    with _ATOMIC_COUNTER_LOCK:
        _ATOMIC_COUNTER[0] += 1
        return _ATOMIC_COUNTER[0]


def _load_meta() -> dict:
    if not settings.metadata_file.exists():
        return {"resumes": {}, "jds": {}, "scores": {}}
    try:
        return json.loads(settings.metadata_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"resumes": {}, "jds": {}, "scores": {}}


def _save_meta(data: dict) -> None:
    _atomic_write_json(settings.metadata_file, data)


# ---------- Resume input storage ----------

def save_resume(file: UploadFile, candidate_id: str, job_id: Optional[str] = None) -> dict:
    if not file.filename:
        raise InvalidInputError("filename missing")
    ext = Path(file.filename).suffix.lower()
    if ext not in settings.allowed_extensions:
        raise InvalidInputError(
            f"Unsupported file type {ext!r}. Allowed: {settings.allowed_extensions}"
        )

    resume_id = f"R{uuid.uuid4().hex[:10].upper()}"
    safe_name = f"{resume_id}{ext}"
    dest = settings.upload_dir / safe_name

    sha = hashlib.sha256()
    size = 0
    max_bytes = settings.max_upload_mb * 1024 * 1024

    file.file.seek(0)
    with dest.open("wb") as out:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                out.close()
                dest.unlink(missing_ok=True)
                raise InvalidInputError(f"File exceeds {settings.max_upload_mb} MB limit")
            sha.update(chunk)
            out.write(chunk)

    meta = {
        "resume_id": resume_id,
        "candidate_id": candidate_id,
        "job_id": job_id,
        "filename": file.filename,
        "stored_path": str(dest),
        "size_bytes": size,
        "sha256": sha.hexdigest(),
        "uploaded_at": _utc_now(),
    }

    with _LOCK:
        data = _load_meta()
        data["resumes"][resume_id] = meta
        _save_meta(data)
    return meta


def get_resume(resume_id: str) -> dict:
    with _LOCK:
        data = _load_meta()
    meta = data["resumes"].get(resume_id)
    if not meta:
        raise NotFoundError(f"Resume {resume_id} not found")
    return meta


def list_resumes() -> list[dict]:
    with _LOCK:
        return list(_load_meta()["resumes"].values())


# ---------- JD input storage ----------

def save_jd(jd: dict) -> dict:
    job_id = jd.get("job_id") or f"J{uuid.uuid4().hex[:10].upper()}"
    jd["job_id"] = job_id
    jd["uploaded_at"] = _utc_now()
    _atomic_write_json(settings.jd_dir / f"{job_id}.json", jd)
    with _LOCK:
        data = _load_meta()
        data["jds"][job_id] = jd
        _save_meta(data)
    return jd


def get_jd(job_id: str) -> dict:
    with _LOCK:
        data = _load_meta()
    jd = data["jds"].get(job_id)
    if not jd:
        raise NotFoundError(f"Job {job_id} not found")
    return jd


def list_jds() -> list[dict]:
    with _LOCK:
        return list(_load_meta()["jds"].values())


# ---------- Result artifact writers ----------

def save_parsed_result(resume_id: str, candidate_id: str, parsed_profile: dict) -> Path:
    """Persist a parsed resume profile under api_data_results/parsed/."""
    payload = {
        "artifact_type": "parsed_resume",
        "resume_id": resume_id,
        "candidate_id": candidate_id,
        "parsed_profile": parsed_profile,
        "generated_at": _utc_now(),
    }
    return _atomic_write_json(settings.parsed_results_dir / f"{resume_id}.json", payload)


def load_parsed_result(resume_id: str) -> Optional[dict]:
    p = settings.parsed_results_dir / f"{resume_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def save_score_result(score: dict) -> Path:
    """Persist a candidate × job score under api_data_results/scores/.

    Filename: {candidate_id}__{job_id}.json (double underscore = safe separator).
    Also indexed inside metadata.json for fast shortlist queries.
    """
    payload = dict(score)
    payload["artifact_type"] = "score"
    payload["generated_at"] = _utc_now()

    fname = f"{score['candidate_id']}__{score['job_id']}.json"
    out_path = _atomic_write_json(settings.scores_results_dir / fname, payload)

    # Also keep index in metadata.json for fast lookup
    key = f"{score['candidate_id']}::{score['job_id']}"
    with _LOCK:
        data = _load_meta()
        data["scores"][key] = payload
        _save_meta(data)
    return out_path


# Backwards-compat alias used elsewhere in code
save_score = save_score_result


def get_scores_for_job(job_id: str) -> list[dict]:
    with _LOCK:
        data = _load_meta()
    return [s for s in data["scores"].values() if s.get("job_id") == job_id]


def save_shortlist_result(shortlist: dict) -> Path:
    """Persist a shortlist for a job under api_data_results/shortlists/."""
    payload = dict(shortlist)
    payload["artifact_type"] = "shortlist"
    payload["generated_at"] = _utc_now()
    fname = f"{shortlist['job_id']}.json"
    return _atomic_write_json(settings.shortlist_results_dir / fname, payload)


def load_shortlist_result(job_id: str) -> Optional[dict]:
    p = settings.shortlist_results_dir / f"{job_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# ---------- Test helper ----------

def reset_storage() -> None:
    """Test-only: nuke all input + result dirs."""
    with _LOCK:
        for d in (settings.api_data_root, settings.result_dir):
            if d.exists():
                shutil.rmtree(d)
        settings.ensure_dirs()
