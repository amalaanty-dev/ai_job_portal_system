"""
run_semantic_pipeline.py
─────────────────────────
Day 12 – Semantic Matching Engine  |  Main Entry Point

Modes:
  1. DEMO      — run on built-in sample data, print results
  2. VALIDATE  — run accuracy report against ground-truth labels
  3. TUNE      — calibrate thresholds and show tuning results
  4. BATCH     — process JSON files from data/ directories

Usage:
    python run_semantic_pipeline.py              # DEMO mode
    python run_semantic_pipeline.py --validate   # accuracy report
    python run_semantic_pipeline.py --tune       # threshold tuning
    python run_semantic_pipeline.py --batch      # batch file mode
    python run_semantic_pipeline.py --query "resume_da_001" "jd_da_001"
"""

import os
import sys
import json
import argparse
from datetime import datetime

# ── Path setup ──────────────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  # sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from semantic_engine import (
    SemanticMatcher,
    ThresholdTuner,
    MatchingValidator,
    cache_stats,
    get_thresholds,
)
from data.sample_data import SAMPLE_RESUMES, SAMPLE_JDS, GROUND_TRUTH


# ═══════════════════════════════════════════════════════════════
# PATH CONFIG  (for --batch mode)
# ═══════════════════════════════════════════════════════════════
RESUME_DIR = "data/resumes/sectioned_resumes/"
JD_DIR     = "data/job_descriptions/parsed_jd/"
OUTPUT_DIR = "data/semantic_outputs/"


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _banner(text: str, width: int = 72) -> None:
    print(f"\n{'═'*width}")
    print(f"  {text}")
    print(f"{'═'*width}")


def _load_json_dir(directory: str) -> list[dict]:
    from semantic_engine.embedder import extract_resume_name, extract_jd_title

    items = []
    if not os.path.isdir(directory):
        return items
    for fname in sorted(os.listdir(directory)):
        if fname.endswith(".json"):
            path = os.path.join(directory, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                    data.setdefault("id", fname.replace(".json", ""))

                    # ── Inject name / title if not already present ──
                    # Resumes: extract from other[0]; JDs: extract from role[0]
                    if "skills" in data or "experience" in data:
                        # Looks like a resume
                        data.setdefault("name", extract_resume_name(data))
                    elif "role" in data or "skills_required" in data:
                        # Looks like a JD
                        data.setdefault("title", extract_jd_title(data))

                    items.append(data)
            except Exception as e:
                print(f"⚠️  Skipping {fname}: {e}")
    return items


# ═══════════════════════════════════════════════════════════════
# MODE 1 — DEMO
# ═══════════════════════════════════════════════════════════════

def run_demo() -> None:
    _banner("DAY 12 – SEMANTIC MATCHING ENGINE  |  DEMO MODE")

    matcher = SemanticMatcher()

    # ── Warm up model ──
    print("\n  Loading embedding model (first run downloads ~80 MB)…")
    from semantic_engine.embedder import get_model
    get_model()
    print("  ✅ Model ready.\n")

    # ── Match each resume against its ideal JD ──
    ideal_pairs = [
        ("resume_da_001",  "jd_da_001",  "Data Analyst match"),
        ("resume_se_001",  "jd_se_001",  "Software Engineer match"),
        ("resume_hda_001", "jd_hda_001", "Healthcare DA match"),
        ("resume_mm_001",  "jd_mm_001",  "Marketing Manager match"),
        ("resume_me_001",  "jd_me_001",  "Mechanical Engineer match"),
        # Cross-domain
        ("resume_da_001",  "jd_hda_001", "DA resume → Healthcare JD"),
        ("resume_mismatch_001", "jd_se_001", "Hospitality resume → SE JD"),
    ]

    resume_map = {r["id"]: r for r in SAMPLE_RESUMES}
    jd_map     = {j["id"]: j for j in SAMPLE_JDS}

    W = 72
    print(f"  {'SCENARIO':<38} {'SCORE':>6}  {'LABEL'}")
    print(f"  {'─'*W}")

    for rid, jid, label in ideal_pairs:
        resume = resume_map[rid]
        jd     = jd_map[jid]
        result = matcher.match(resume, jd)
        print(f"  {label:<38} {result.overall_score:>6.3f}  {result.match_label}")

    # ── Detailed breakdown for one pair ──
    _banner("DETAILED SECTION BREAKDOWN  |  Data Analyst ↔ DA JD")
    result = matcher.match(resume_map["resume_da_001"], jd_map["jd_da_001"])
    ss     = result.to_dict()["section_scores"]
    print(f"\n  Resume : {result.resume_name}")
    print(f"  JD     : {result.jd_title}")
    print(f"  Overall: {result.overall_score:.3f}  —  {result.match_label}\n")
    print(f"  {'SECTION':<24} {'SCORE':>6}")
    print(f"  {'─'*35}")
    for sec, sc in ss.items():
        bar = "█" * int(sc * 20)
        print(f"  {sec:<24} {sc:>6.3f}  {bar}")

    if result.gaps:
        print(f"\n  ⚠️  Gaps identified:")
        for gap in result.gaps:
            print(f"     • {gap['section']:<22} score={gap['score']:.3f}  severity={gap['gap_severity']}")

    # ── Best JD for one resume ──
    _banner(f"BEST JD RANKING  |  Resume: {resume_map['resume_hda_001']['name']}")
    best, all_r = matcher.best_jd_for_resume(resume_map["resume_hda_001"], SAMPLE_JDS)
    print(f"\n  {'RANK':<5} {'JD':<38} {'SCORE':>6}  {'LABEL'}")
    print(f"  {'─'*W}")
    for i, r in enumerate(all_r, 1):
        print(f"  {i:<5} {r.jd_title:<38} {r.overall_score:>6.3f}  {r.match_label}")

    # ── Cache stats ──
    stats = cache_stats()
    print(f"\n  📊 Embeddings cached: {stats['cached_embeddings']}  |  Model: {stats['model']}")


# ═══════════════════════════════════════════════════════════════
# MODE 2 — VALIDATE
# ═══════════════════════════════════════════════════════════════

def run_validate() -> None:
    _banner("DAY 12 – SEMANTIC MATCHING ENGINE  |  VALIDATION MODE")

    matcher   = SemanticMatcher()
    validator = MatchingValidator()

    print("\n  Running all ground-truth pairs…\n")

    resume_map = {r["id"]: r for r in SAMPLE_RESUMES}
    jd_map     = {j["id"]: j for j in SAMPLE_JDS}

    # Build result list for all GT pairs
    results = []
    for (rid, jid, label, score_range) in GROUND_TRUTH:
        resume = resume_map.get(rid)
        jd     = jd_map.get(jid)
        if resume and jd:
            result = matcher.match(resume, jd)
            results.append(result)

    report = validator.validate(results, GROUND_TRUTH, SAMPLE_JDS)
    validator.print_report(report)

    # Save JSON report
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(OUTPUT_DIR, f"validation_report_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(validator.to_json(report))
    print(f"  📄 Report saved: {out_path}\n")


# ═══════════════════════════════════════════════════════════════
# MODE 3 — TUNE
# ═══════════════════════════════════════════════════════════════

def run_tune() -> None:
    _banner("DAY 12 – SEMANTIC MATCHING ENGINE  |  THRESHOLD TUNING")

    matcher = SemanticMatcher()
    tuner   = ThresholdTuner(steps=15)

    print("\n  Computing scores for ground-truth pairs…\n")

    resume_map = {r["id"]: r for r in SAMPLE_RESUMES}
    jd_map     = {j["id"]: j for j in SAMPLE_JDS}

    scored_pairs = []
    for (rid, jid, label, score_range) in GROUND_TRUTH:
        resume = resume_map.get(rid)
        jd     = jd_map.get(jid)
        if resume and jd:
            result = matcher.match(resume, jd)
            scored_pairs.append({
                "resume_id":    rid,
                "jd_id":        jid,
                "overall_score": result.overall_score,
                "job_type":     jd.get("job_type", "default"),
            })

    tuning_results = tuner.tune(scored_pairs, GROUND_TRUTH)

    print(f"\n  {'JOB TYPE':<28} {'N':>4}  {'F1':>6}  {'STRONG_T':>9}  {'PARTIAL_T':>10}")
    print(f"  {'─'*65}")
    for row in tuner.summary():
        print(f"  {row['job_type']:<28} {row['n_samples']:>4}  {row['f1_score']:>6.3f}"
              f"  {row['strong_thresh']:>9.3f}  {row['partial_thresh']:>10.3f}")

    print()
    for jt, res in tuning_results.items():
        print(f"\n  [{jt}]  best thresholds:")
        for k, v in res.best_thresholds.items():
            print(f"     {k:<18} = {v:.3f}")


# ═══════════════════════════════════════════════════════════════
# MODE 4 — BATCH (file-based)
# ═══════════════════════════════════════════════════════════════

def run_batch() -> None:
    _banner("DAY 12 – SEMANTIC MATCHING ENGINE  |  BATCH MODE")

    resumes = _load_json_dir(RESUME_DIR)
    jds     = _load_json_dir(JD_DIR)

    if not resumes:
        print(f"  ⚠️  No resume JSON files found in {RESUME_DIR}")
        print(f"  ℹ️  Falling back to built-in sample data.\n")
        resumes = SAMPLE_RESUMES

    if not jds:
        print(f"  ⚠️  No JD JSON files found in {JD_DIR}")
        print(f"  ℹ️  Falling back to built-in sample JDs.\n")
        jds = SAMPLE_JDS

    matcher = SemanticMatcher()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"\n  Resumes: {len(resumes)}   JDs: {len(jds)}\n")

    for resume in resumes:
        best, all_results = matcher.best_jd_for_resume(resume, jds)

        output = {
            "resume_id":    resume.get("id", "unknown"),
            "resume_name":  resume.get("name", ""),
            "best_match": {
                "jd_id":       best.jd_id,
                "jd_title":    best.jd_title,
                "score":       best.overall_score,
                "label":       best.match_label,
            },
            "all_matches": [
                {
                    "jd_id":    r.jd_id,
                    "jd_title": r.jd_title,
                    "score":    r.overall_score,
                    "label":    r.match_label,
                }
                for r in all_results
            ],
            "section_scores": best.to_dict()["section_scores"],
            "gaps":           best.gaps,
        }

        fname    = f"{resume.get('id', 'resume')}_semantic.json"
        out_path = os.path.join(OUTPUT_DIR, fname)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4)

        print(f"  📄 {resume.get('name','?'):<20} → best: {best.jd_title:<30}  {best.overall_score:.3f}  ✅ saved")

    print(f"\n  Outputs written to {OUTPUT_DIR}\n")


# ═══════════════════════════════════════════════════════════════
# MODE 5 — QUERY (single pair)
# ═══════════════════════════════════════════════════════════════

def run_query(resume_id: str, jd_id: str) -> None:
    _banner(f"QUERY  |  {resume_id}  ↔  {jd_id}")

    resume_map = {r["id"]: r for r in SAMPLE_RESUMES}
    jd_map     = {j["id"]: j for j in SAMPLE_JDS}

    resume = resume_map.get(resume_id)
    jd     = jd_map.get(jd_id)

    if not resume:
        print(f"  ❌ Resume '{resume_id}' not found in sample data.")
        return
    if not jd:
        print(f"  ❌ JD '{jd_id}' not found in sample data.")
        return

    matcher = SemanticMatcher(thresholds=get_thresholds(jd.get("job_type", "default")))
    result  = matcher.match(resume, jd)

    print(f"\n  Resume : {result.resume_name}  ({resume_id})")
    print(f"  JD     : {result.jd_title}  ({jd_id})")
    print(f"  Score  : {result.overall_score:.4f}")
    print(f"  Label  : {result.match_label}\n")

    ss = result.to_dict()["section_scores"]
    print(f"  {'SECTION':<24} {'SCORE':>6}  BAR")
    print(f"  {'─'*55}")
    for sec, sc in ss.items():
        bar = "█" * int(sc * 25)
        print(f"  {sec:<24} {sc:>6.3f}  {bar}")

    if result.gaps:
        print(f"\n  ⚠️  Gaps:")
        for g in result.gaps:
            print(f"     {g['section']:<22}  score={g['score']:.3f}  [{g['gap_severity']}]")
    else:
        print("\n  ✅ No significant gaps found.")

    print()


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Day 12 – Semantic Matching Engine")
    parser.add_argument("--validate", action="store_true", help="Run accuracy validation")
    parser.add_argument("--tune",     action="store_true", help="Run threshold tuning")
    parser.add_argument("--batch",    action="store_true", help="Run batch file processing")
    parser.add_argument("--query",    nargs=2, metavar=("RESUME_ID", "JD_ID"),
                        help="Match a specific resume ↔ JD pair")
    args = parser.parse_args()

    if args.validate:
        run_validate()
    elif args.tune:
        run_tune()
    elif args.batch:
        run_batch()
    elif args.query:
        run_query(args.query[0], args.query[1])
    else:
        run_demo()