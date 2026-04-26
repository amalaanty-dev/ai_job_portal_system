"""
run_ranking_engine.py
---------------
End-to-end Day 14 ranking pipeline.

Flow:
  1. Load all ATS scoring JSON files from ats_results/ats_scores/
       - Single-candidate files            : {final_score, scoring_breakdown, ...}
       - Multi-candidate "ranked_*.json"   : {ranked_candidates: [...]}
  2. Apply hard filters (min experience, required skills)
  3. Score candidates (PASS-THROUGH from Day 13, or RECOMPUTE with --recompute)
  4. Sort candidates by final_score
  5. Bucket into shortlisted / review / rejected zones
  6. Export per-row CSVs + CONSOLIDATED-by-jd_id JSONs:
       - ranked/ranked_candidates.json           (consolidated, jd_id-grouped)
       - ranked/ranked_candidates.csv            (per-row)
       - ranked/ranked_per_jd/<jd>.json          (one per JD, when >1)
       - shortlisted/shortlisted_candidates.{json,csv} + call_queue.json
       - review/review_candidates.{json,csv}
       - rejected/rejected_candidates.{json,csv}
       - reports/summary.json + top_candidates.md

USAGE
    python scripts/run_ranking.py
    python scripts/run_ranking.py --recompute
    python scripts/run_ranking.py --role mern_stack_developer --min-exp 2 \\
        --required-skills react node.js
    python scripts/run_ranking.py --debug-extract
    python scripts/run_ranking.py --no-per-jd        # skip per-JD breakdowns
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path when the script is run directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ranking_engine.config import ranking_config as cfg
from ranking_engine.core.bias_guards import annotate_bias_flags
from ranking_engine.core.explainability import annotate_explanations
from ranking_engine.core.filters import apply_hard_filters
from ranking_engine.core.ranker import rank_candidates
from ranking_engine.core.shortlister import bucket_candidates
from ranking_engine.exporters.call_queue_builder import build_call_queue
from ranking_engine.exporters.consolidated_exporter import write_consolidated
from ranking_engine.exporters.csv_exporter import export_to_csv
from ranking_engine.exporters.report_generator import write_reports
from utils.io_utils import (
    ensure_dirs,
    list_json_files,
    load_json,
)


# ---------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------
def _setup_logging(log_dir: Path, debug: bool = False) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "ranking_engine.log"
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


logger = logging.getLogger("run_ranking")


# ---------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------
def load_candidates(input_dir: Path, parallel: bool = False) -> list[dict]:
    """Load every *.json file in input_dir.

    Supports two Day 13 file shapes:
      A) Single-candidate file:
            { "identifiers": {...}, "final_score": ..., "scoring_breakdown": ... }
      B) Multi-candidate "ranked_*.json" file:
            { "jd_id": "...", "ranked_candidates": [ {...}, {...} ] }

    Non-candidate JSON files (run summaries, manifests) are silently skipped.
    """
    files = list_json_files(input_dir)
    if not files:
        logger.warning("No input JSON files found in %s", input_dir)
        return []

    def _looks_like_candidate(d: dict) -> bool:
        if not isinstance(d, dict):
            return False
        if "ranked_candidates" in d:
            return True  # wrapper file
        if "identifiers" in d or "scoring_breakdown" in d:
            return True
        if "final_score" in d and ("scoring_breakdown" in d or "scores" in d
                                   or "skill_match" in d):
            return True
        return False

    def _normalize(data, source_name: str) -> list[dict]:
        rows: list[dict] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and _looks_like_candidate(item):
                    item.setdefault("_source_file", source_name)
                    rows.append(item)
        elif isinstance(data, dict):
            if isinstance(data.get("ranked_candidates"), list):
                for item in data["ranked_candidates"]:
                    if isinstance(item, dict):
                        item.setdefault("_source_file", source_name)
                        if not item.get("job_role") and data.get("job_role"):
                            item.setdefault("job_role", data["job_role"])
                        rows.append(item)
            elif _looks_like_candidate(data):
                data.setdefault("_source_file", source_name)
                rows.append(data)
            else:
                logger.debug("Skipping %s: does not look like a candidate file", source_name)
        else:
            logger.warning("Skipping %s: unsupported top-level type %s", source_name, type(data))
        return rows

    def _load_one(path: Path) -> list[dict]:
        try:
            data = load_json(path)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to load %s: %s", path, e)
            return []
        return _normalize(data, path.name)

    candidates: list[dict] = []
    if parallel and len(files) > 100:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as ex:
            for batch in ex.map(_load_one, files):
                candidates.extend(batch)
    else:
        for f in files:
            candidates.extend(_load_one(f))

    logger.info("Loaded %d candidate records from %d files", len(candidates), len(files))
    return candidates


def prefilter_candidates(candidates: list[dict], filter_rules: dict) -> list[dict]:
    """Tag candidates that fail hard filters; keep them in list for reporting."""
    for c in candidates:
        passed, reasons = apply_hard_filters(c, filter_rules)
        if not passed:
            c["hard_filter_failed"] = True
            c.setdefault("rejection_reasons", []).extend(reasons)
    failed = sum(1 for c in candidates if c.get("hard_filter_failed"))
    logger.info("Hard-filter failures: %d / %d", failed, len(candidates))
    return candidates


def deduplicate_by_id(candidates: list[dict]) -> list[dict]:
    """Keep the highest-scoring entry per (resume_id, job_role) pair."""
    from ranking_engine.core.ranker import _candidate_id, _candidate_job_role
    best: dict[tuple, dict] = {}
    for c in candidates:
        cid = _candidate_id(c)
        role = _candidate_job_role(c) or ""
        key = (cid, role)
        score = float(c.get("final_score") or 0)
        if key not in best or score > float(best[key].get("final_score") or 0):
            best[key] = c
    deduped = list(best.values())
    if len(deduped) < len(candidates):
        logger.info("Dedup: %d -> %d (kept best score per resume+role)",
                    len(candidates), len(deduped))
    return deduped


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------
def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Day 14 - Ranking & Shortlisting Pipeline")
    p.add_argument("--role", default=None, help="Job role key (e.g. mern_stack_developer)")
    p.add_argument("--input-dir", type=Path, default=cfg.INPUT_DIR)
    p.add_argument("--output-dir", type=Path, default=cfg.OUTPUT_DIR)
    p.add_argument("--top-n", type=int, default=cfg.DEFAULT_TOP_N)
    p.add_argument("--min-exp", type=float, default=0.0,
                   help="Minimum years of experience (hard filter)")
    p.add_argument("--required-skills", nargs="*", default=[],
                   help="Space-separated required skills (hard filter)")
    p.add_argument("--parallel", action="store_true",
                   help="Load JSON files concurrently (useful for large pools)")
    p.add_argument("--recompute", action="store_true",
                   help="Re-weight sub-scores using Day 14 weights "
                        "(default: pass through Day 13's final_score)")
    p.add_argument("--debug-extract", action="store_true",
                   help="Verbose logging of score extraction")
    p.add_argument("--no-dedup", action="store_true",
                   help="Keep duplicate (resume, role) entries")
    p.add_argument("--no-per-jd", action="store_true",
                   help="Skip writing per-JD breakdown subfolders "
                        "(consolidated top-level JSON still written)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    _setup_logging(cfg.LOG_DIR, debug=args.debug_extract)

    output_dir = args.output_dir
    paths = cfg.get_output_paths(output_dir)
    ensure_dirs(paths.values())

    role_cfg = cfg.get_config_for_role(args.role)
    filter_rules = {
        **cfg.HARD_FILTERS,
        "min_experience_years": args.min_exp,
        "required_skills":      args.required_skills,
    }

    logger.info("Role: %s", role_cfg["role_key"])
    logger.info("Mode: %s", "RECOMPUTE" if args.recompute else "PASS-THROUGH (Day 13 final_score)")
    if args.recompute:
        logger.info("Weights: %s", role_cfg["weights"])
    logger.info("Thresholds: %s", role_cfg["thresholds"])
    logger.info("Hard filters: %s", filter_rules)

    # ---- Pipeline ----
    candidates = load_candidates(args.input_dir, parallel=args.parallel)
    if not candidates:
        logger.error("Aborting: no candidates to rank.")
        return 1

    if not args.no_dedup:
        candidates = deduplicate_by_id(candidates)

    candidates = prefilter_candidates(candidates, filter_rules)
    candidates = annotate_bias_flags(candidates)
    ranked = rank_candidates(
        candidates,
        role_cfg["weights"],
        recompute=args.recompute,
        debug=args.debug_extract,
    )
    buckets = bucket_candidates(ranked, role_cfg["thresholds"])
    annotate_explanations(ranked, role_cfg["thresholds"])

    # ---- CSV exports (per-row, kept for spreadsheet review) ----
    export_to_csv(ranked, paths["ranked"] / "ranked_candidates.csv")
    for zone_name in ("shortlisted", "review", "rejected"):
        export_to_csv(buckets.get(zone_name, []),
                      paths[zone_name] / f"{zone_name}_candidates.csv")

    # ---- CONSOLIDATED JSON exports (single jd_id per file) ----
    write_per_jd = not args.no_per_jd
    write_consolidated(ranked, "ranked", paths["ranked"], write_per_jd=write_per_jd)
    for zone_name in ("shortlisted", "review", "rejected"):
        write_consolidated(
            buckets.get(zone_name, []),
            zone_name,
            paths[zone_name],
            write_per_jd=write_per_jd,
        )

    # ---- Phase-3 handoff: call queue manifest ----
    build_call_queue(
        shortlisted=buckets.get("shortlisted", []),
        job_role=role_cfg["role_key"],
        out_path=paths["shortlisted"] / "call_queue.json",
    )

    # ---- Recruiter reports ----
    write_reports(
        ranked=ranked,
        buckets=buckets,
        reports_dir=paths["reports"],
        config_snapshot={
            "weights":      role_cfg["weights"],
            "thresholds":   role_cfg["thresholds"],
            "hard_filters": filter_rules,
            "scoring_mode": "recomputed" if args.recompute else "passthrough",
            "top_n":        args.top_n,
        },
        run_meta={
            "job_role":    role_cfg["role_key"],
            "input_dir":   str(args.input_dir),
            "output_dir":  str(output_dir),
            "input_files": len(list_json_files(args.input_dir)),
        },
        top_n=args.top_n,
    )

    logger.info("Done. Results in: %s", output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())