# Zecpath ATS API — Specification (Day 16)

**Version:** 1.0
**Base URL:** `https://api.zecpath.ai/v1/`
**Local dev:** `http://localhost:8000/v1/`

---

## Storage Layout

```
api_data/                       ← INPUT root
├── raw_resumes/                ← uploaded PDFs/DOCX (renamed to {resume_id}.{ext})
├── jds/                        ← {job_id}.json
└── metadata.json               ← internal index (resumes / jds / scores)

api_data_results/               ← OUTPUT root
├── parsed/{resume_id}.json     ← one file per parsed resume
├── scores/{candidate_id}__{job_id}.json
└── shortlists/{job_id}.json    ← one file per job shortlist

logs/ats_api.log                ← rotated structured JSON logs
```

Every result file includes `artifact_type` and `generated_at` for traceability.

---

## Conventions

- All responses include an ISO-8601 `timestamp` in UTC (suffix `Z`).
- All requests get an `X-Request-ID` echoed back in response headers.
- Error responses follow the format in [§ Error Handling](#error-handling).
- File uploads: `multipart/form-data`, max 10 MB, allowed: `.pdf`, `.docx`, `.doc`.

---

## 1. Resume APIs

### 1.1 Upload single resume

`POST /v1/resume/upload` — `multipart/form-data`

| Field | Type | Required | Notes |
|---|---|---|---|
| `file` | file | yes | PDF / DOCX, ≤ 10 MB |
| `job_id` | string | no | Pre-link to a JD |
| `candidate_id` | string | no | Auto-generated if omitted |

**Side effect:** file saved to `api_data/raw_resumes/{resume_id}.{ext}`.

**200 OK**
```json
{
  "status": "success",
  "message": "Resume uploaded successfully",
  "resume_id": "RAB12CD34EF",
  "candidate_id": "CXY78ZW90AB",
  "job_id": "J123",
  "filename": "resume.pdf",
  "size_bytes": 24891,
  "timestamp": "2026-04-28T10:00:00Z"
}
```

### 1.2 Upload multiple resumes (batch)

`POST /v1/resume/upload/batch` — `multipart/form-data`

| Field | Type | Required |
|---|---|---|
| `files` | file[] | yes — repeated |
| `job_id` | string | no |

### 1.3 Parse a resume

`POST /v1/resume/parse` — `application/json`

**Side effect:** writes `api_data_results/parsed/{resume_id}.json`.

```json
{ "resume_id": "RAB12CD34EF" }
```

**200 OK**
```json
{
  "status": "completed",
  "candidate_id": "CXY78ZW90AB",
  "resume_id": "RAB12CD34EF",
  "parsed_profile": {
    "name": "Asha Menon",
    "email": "asha@example.com",
    "skills": ["Python", "Django"],
    "experience": [],
    "education": [],
    "total_experience_years": 3.5
  },
  "timestamp": "..."
}
```

### 1.4 Parse multiple resumes (batch)

`POST /v1/resume/parse/batch` — writes one artifact per resume to `api_data_results/parsed/`.

```json
{ "resume_ids": ["R1", "R2", "R3"] }
```

---

## 2. Job Description APIs

### 2.1 Upload single JD

`POST /v1/jd/upload` — `application/json`

**Side effect:** writes `api_data/jds/{job_id}.json`.

```json
{
  "job_title": "Backend Developer",
  "required_skills": ["Python", "Django"],
  "preferred_skills": ["AWS"],
  "experience_required": 3,
  "education_required": ["B.Tech"],
  "location": "Bengaluru",
  "description": "Build scalable APIs"
}
```

### 2.2 Upload multiple JDs

`POST /v1/jd/upload/batch`

```json
{ "jobs": [ {...}, {...} ] }
```

---

## 3. ATS Scoring APIs

### 3.1 Score one (candidate, JD)

`POST /v1/ats/score`

**Side effect:** writes `api_data_results/scores/{candidate_id}__{job_id}.json`.

```json
{ "candidate_id": "C123", "job_id": "J123" }
```

**200 OK**
```json
{
  "status": "completed",
  "candidate_id": "C123",
  "job_id": "J123",
  "final_score": 86.5,
  "breakdown": { "skills": 90, "experience": 85, "education": 80, "semantic": 88 },
  "matched_status": "Shortlisted",
  "timestamp": "..."
}
```

### 3.2 Batch score (N × M)

`POST /v1/ats/score/batch`

**Side effect:** N×M score files written, one per pair.

```json
{
  "candidate_ids": ["C1", "C2", "C3"],
  "job_ids": ["J1", "J2"],
  "shortlist_threshold": 70
}
```

> ⚠️ **Use the async endpoint (`/v1/jobs/start`) for > 50 pairs** to avoid HTTP timeouts.

### 3.3 Shortlist for a job

`POST /v1/ats/shortlist`

**Side effect:** writes `api_data_results/shortlists/{job_id}.json`.

```json
{ "job_id": "J123", "threshold": 70, "top_n": 20 }
```

**200 OK**
```json
{
  "status": "completed",
  "job_id": "J123",
  "total_candidates": 50,
  "shortlisted": 20,
  "candidates": [
    { "candidate_id": "C123", "score": 88, "status": "Shortlisted", "rank": 1 }
  ],
  "timestamp": "..."
}
```

---

## 4. Async Job APIs

### 4.1 Start

`POST /v1/jobs/start` — kinds: `score_batch`, `shortlist`.

```json
{
  "kind": "score_batch",
  "payload": {
    "candidate_ids": ["C1", "C2"],
    "job_ids": ["J1"],
    "shortlist_threshold": 70
  }
}
```

### 4.2 Status

`GET /v1/jobs/status/{job_id}` → `queued | processing | completed | failed`

### 4.3 Result

`GET /v1/jobs/result/{job_id}` → final result payload once `completed`.

---

## Error Handling

```json
{
  "status": "error",
  "error_code": "INVALID_INPUT",
  "message": "Missing candidate_id",
  "timestamp": "2026-04-28T10:05:00Z",
  "request_id": "..."
}
```

| HTTP | `error_code` | When |
|---|---|---|
| 400 | `INVALID_INPUT` | Missing/invalid field, bad file type, oversized file |
| 404 | `NOT_FOUND` | Unknown `resume_id`, `job_id`, `JOB...` |
| 422 | `PROCESSING_ERR` | Parsing/scoring failed mid-pipeline |
| 500 | `SERVER_ERROR` | Unhandled exception |

---

## Logging Standard

Every log line is single-line JSON:

```json
{
  "timestamp": "2026-04-28T10:10:00Z",
  "service": "ATS Engine",
  "level": "INFO",
  "message": "Candidate scoring completed",
  "candidate_id": "C123",
  "job_id": "J123",
  "request_id": "..."
}
```

Levels: `DEBUG` (dev), `INFO` (default), `WARNING`, `ERROR`.

---

## curl Quickstart

```bash
# 1. Upload JD                           → api_data/jds/J{id}.json
curl -X POST http://localhost:8000/v1/jd/upload \
  -H 'Content-Type: application/json' \
  -d '{"job_title":"Backend Dev","required_skills":["Python","Django"],"experience_required":2}'

# 2. Upload resume                       → api_data/raw_resumes/R{id}.pdf
curl -X POST http://localhost:8000/v1/resume/upload \
  -F "file=@/path/to/resume.pdf" \
  -F "job_id=J123"

# 3. Parse                               → api_data_results/parsed/R{id}.json
curl -X POST http://localhost:8000/v1/resume/parse \
  -H 'Content-Type: application/json' \
  -d '{"resume_id":"R..."}'

# 4. Score                               → api_data_results/scores/C{id}__J{id}.json
curl -X POST http://localhost:8000/v1/ats/score \
  -H 'Content-Type: application/json' \
  -d '{"candidate_id":"C...","job_id":"J..."}'

# 5. Shortlist                           → api_data_results/shortlists/J{id}.json
curl -X POST http://localhost:8000/v1/ats/shortlist \
  -H 'Content-Type: application/json' \
  -d '{"job_id":"J...","threshold":70,"top_n":20}'
```
