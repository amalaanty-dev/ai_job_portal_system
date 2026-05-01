# ATS API Integration Flow — Zecpath

## Folder Layout

```
ai_job_portal_system/
├── api_data/                 ← INPUT
│   ├── raw_resumes/          ← uploaded resumes (PDF / DOCX)
│   ├── jds/                  ← {job_id}.json
│   └── metadata.json         ← internal index
│
├── api_data_results/         ← OUTPUT (one file per artifact)
│   ├── parsed/               ← {resume_id}.json
│   ├── scores/               ← {candidate_id}__{job_id}.json
│   └── shortlists/           ← {job_id}.json
│
└── logs/ats_api.log          ← rotated structured JSON
```

## High-Level Sequence

```
┌──────────┐   ┌─────────┐   ┌───────────┐   ┌──────────────┐   ┌──────────┐
│ Frontend │──▶│ Backend │──▶│  ATS API  │──▶│  Job Queue   │──▶│  Engine  │
│ (Next.js)│   │ (Node)  │   │ (FastAPI) │   │ (in-memory)  │   │ Modules  │
└──────────┘   └─────────┘   └───────────┘   └──────────────┘   └──────────┘
                                  │                                   │
                                  ▼                                   ▼
                            api_data/                            parsers/
                            api_data_results/                    ats_engine/
                                                                 semantic_engine/
```

## Step-by-Step Flow

```
1. Recruiter posts a JD          → POST /v1/jd/upload
                                   (writes api_data/jds/{job_id}.json)

2. Candidates upload resumes     → POST /v1/resume/upload (or /upload/batch)
                                   (writes api_data/raw_resumes/{resume_id}.pdf)

3. Backend triggers parsing      → POST /v1/resume/parse/batch
                                   (writes api_data_results/parsed/{resume_id}.json)

4. Backend triggers scoring      → POST /v1/ats/score/batch         (sync, ≤ 50 pairs)
                                   POST /v1/jobs/start               (async, > 50 pairs)
                                   (writes api_data_results/scores/{candidate}__{job}.json)

5. Backend polls async job       → GET /v1/jobs/status/{job_id}

6. Backend fetches shortlist     → POST /v1/ats/shortlist
                                   (writes api_data_results/shortlists/{job_id}.json)

7. Frontend renders results      → table on recruiter dashboard
```

## Sync vs Async Decision

| Pairs (N × M) | Recommended |
|---|---|
| ≤ 50 | `/v1/ats/score/batch` (returns inline) |
| 50 – 5000 | `/v1/jobs/start` + polling |
| > 5000 | Future: webhook callback (`POST {callback_url}`) on job completion |

## Backend ↔ AI Communication

- **Sync REST**: lightweight calls (single resume parse, single score, JD upload).
- **Async queue**: heavy N×M scoring batches → submitted to in-memory queue with bounded concurrency (default 4 workers, configurable via `ATS_MAX_CONCURRENT_WORKERS`).
- **Webhooks (future)**: HMAC-signed POST to a recruiter-supplied URL when a long job finishes.

## Data Flow Summary

```
PDF/DOCX  ──▶  api_data/raw_resumes/R{id}.pdf
JSON JD   ──▶  api_data/jds/J{id}.json
                       │
                       ▼
              parse → api_data_results/parsed/R{id}.json
                       │
                       ▼
              score → api_data_results/scores/C{id}__J{id}.json
                       │
                       ▼
              shortlist → api_data_results/shortlists/J{id}.json
```

Every result file contains `artifact_type` and `generated_at` so consumers can detect staleness and verify provenance.

## Error Propagation

```
Existing engine raises Exception
        │
        ▼
ats_adapter catches & re-raises ProcessingError
        │
        ▼
Route handler lets ATSException bubble up
        │
        ▼
Global exception handler → PRD-formatted JSON error → client
```

## Observability

- **Request correlation**: `X-Request-ID` injected by `RequestIDMiddleware`, included in every log line and echoed in response headers.
- **Log location**: `logs/ats_api.log` (rotated at 10 MB, 5 backups).
- **Levels**: `DEBUG` (verbose dev), `INFO` (default), `WARNING`, `ERROR`.

## Failure Modes & Retries (recommended for production)

| Failure | Where | Strategy |
|---|---|---|
| Bad PDF | parse_resume | Return `PROCESSING_ERR`; do not retry |
| Engine timeout | score_candidate | Wrap in `asyncio.wait_for`; retry 1× with backoff |
| File system full | save_resume | Surface `SERVER_ERROR`; alert ops |
| Queue saturated | job_queue | Reject with 503 + `Retry-After` header |

## Security Checklist

- [x] File type & size validation
- [x] Request ID for trace correlation
- [x] Structured error responses (no stack traces leaked)
- [x] Atomic JSON writes (tmp + rename — no half-written artifacts)
- [ ] **TODO before prod**: Auth (JWT / API key), rate limiting, HMAC webhook signing, virus scanning on uploads
