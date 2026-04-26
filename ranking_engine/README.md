# Ranking Engine (Day 14)

Candidate Ranking & Shortlisting module for the AI Job Portal.

## What it does

Reads ATS scoring JSON files (Day 13 output) and produces:

1. **Ranked list** — all candidates sorted by composite score
2. **Shortlist zones** — auto-bucketed into shortlisted / review / rejected
3. **Recruiter reports** — summary stats + top-N markdown
4. **Call queue manifest** — Phase-3 ready JSON for the AI Call Trigger Engine
5. **CSV exports** — for every zone, recruiter-friendly spreadsheets

## Folder placement

Drop `ranking_engine/` at the project root, beside `ats_engine/`,
`skill_engine/`, etc.

```
ai_job_portal_system/
├── ats_engine/
├── ats_results/
│   └── ats_scores/                   <- INPUT (Day 13 JSONs)
├── ranking_engine/                   <- NEW (this module)
│   ├── config/
│   │   └── ranking_config.py
│   ├── core/
│   │   ├── bias_guards.py
│   │   ├── explainability.py
│   │   ├── filters.py
│   │   ├── ranker.py
│   │   └── shortlister.py
│   ├── exporters/
│   │   ├── call_queue_builder.py
│   │   ├── csv_exporter.py
│   │   └── report_generator.py
│   └── utils/
│       ├── io_utils.py
│       └── score_utils.py
├── ranking_engine_results/           <- OUTPUT (auto-created)
│   ├── ranked/
│   ├── shortlisted/
│   ├── review/
│   ├── rejected/
│   └── reports/
├── scripts/
│   └── run_ranking.py                <- entrypoint
└── tests/
    └── test_ranking_engine.py
```

## Quick start

```bash
# 1) Install pytest (only needed for tests)
pip install pytest

# 2) Run the tests
python -m pytest tests/test_ranking_engine.py -v

# 3) Run the pipeline (uses ats_results/ats_scores/*.json)
python scripts/run_ranking.py

# 4) With job-role-specific weights + hard filters
python scripts/run_ranking.py \
    --role mern_stack_developer \
    --min-exp 2 \
    --required-skills react node.js
```

## Composite score formula

```
final_score = Σ (weight_i × sub_score_i)
```

where sub-scores come from upstream engines (ATS, Skill, Experience, Education).
Missing sub-scores cause their weight to be redistributed proportionally.
Default weights: `ATS 0.40 | Skill 0.30 | Experience 0.20 | Education 0.10`
(role overrides available in `config/ranking_config.py`).

## Zones

| Zone         | Rule                                                    | Action              |
|--------------|---------------------------------------------------------|---------------------|
| shortlisted  | `final_score >= shortlist_threshold` (default 75)       | Triggers AI call    |
| review       | `review_threshold <= final_score < shortlist_threshold` | Recruiter decides   |
| rejected     | `final_score < review_threshold` OR hard filter failed  | Polite auto-reject  |

## Outputs

| File                                           | Purpose                                    |
|------------------------------------------------|--------------------------------------------|
| `ranked/ranked_candidates.json` (+ .csv)       | Full ranked list                           |
| `shortlisted/shortlisted.json` (+ .csv)        | Shortlisted candidates                     |
| `shortlisted/call_queue.json`                  | **Phase-3 handoff manifest**               |
| `review/review.json` (+ .csv)                  | Manual-review zone                         |
| `rejected/rejected.json` (+ .csv)              | Rejected candidates + reasons              |
| `reports/summary.json`                         | Run stats + config snapshot (audit trail)  |
| `reports/top_candidates.md`                    | Recruiter-friendly top-N list              |

## Design highlights (from code review)

- **Bias guardrails** (`core/bias_guards.py`) — flags PII/demographic signals per PRD Phase 2
- **Explainability** (`core/explainability.py`) — every candidate gets a one-line "why"
- **Config validation** — weights must sum to 1.0; thresholds must be ordered
- **Collision-safe merging** — reserved keys on input are preserved as `_original_<key>`
- **Deterministic tie-breaking** — identical scores resolve via sub-scores then candidate_id
- **Parallel loader** — `--parallel` flag for pools >100 candidates
- **Heterogeneous input shapes** — handles flat, nested-`scores`, and sub-engine key paths
