"""
ats_engine/result_writer.py
────────────────────────────
Writes ATS results to:
  ats_results/ats_scores/{resume_id}__vs_{jd_slug}__ats_score.json
  ats_results/ats_scores/{resume_id}__vs_{jd_slug}__ats_report.md
  ats_results/ats_scores/batch_leaderboard.json
  ats_results/ats_scores/batch_leaderboard.md

Output JSON schema is fully documented below.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ats_engine.ats_scorer import ATSResult, ScoreComponent

log = logging.getLogger(__name__)

ATS_SCORES_DIR = Path("ats_results/ats_scores")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _score_label(score: float) -> str:
    if score >= 85: return "Excellent"
    if score >= 70: return "Good"
    if score >= 55: return "Moderate"
    if score >= 40: return "Below Average"
    return "Poor"

def _bar(score: float, width: int = 30) -> str:
    filled = int(round(score / 100 * width))
    return "█" * filled + "░" * (width - filled)

COMP_DISPLAY = {
    "skill_match":            "Skill Match",
    "experience_relevance":   "Experience Relevance",
    "education_alignment":    "Education Alignment",
    "semantic_similarity":    "Semantic Similarity",
}


# ════════════════════════════════════════════════════════════════
#  JSON OUTPUT  (canonical output format)
# ════════════════════════════════════════════════════════════════

def build_json_payload(result: "ATSResult") -> dict:
    """
    Build the canonical JSON output dictionary.

    Schema
    ──────
    {
      "meta": {
        "generated_at": "ISO timestamp",
        "resume_id":    "Amala_Resume_DS_DA_2026",
        "jd_slug":      "ai_specialist_in_healthcare_analytics_parsed_jd",
        "job_title":    "AI Specialist in Healthcare Analytics",
        "weight_profile": "healthcare_analytics"
      },
      "overall": {
        "final_score":    55.07,
        "grade":          "C",
        "recommendation": "Partial Match – Screen with Caution",
        "score_label":    "Moderate"
      },
      "components": [
        {
          "dimension":        "skill_match",
          "display_name":     "Skill Match",
          "raw_score":        89.6,
          "weight":           0.3,
          "weighted_score":   26.88,
          "confidence":       1.0,
          "penalty_applied":  0.0,
          "missing_data":     false,
          "score_label":      "Excellent",
          "evidence":         [...]
        },
        ...
      ],
      "gap_analysis": [...],
      "strengths":         [...],
      "improvement_areas": [...],
      "scoring_metadata": {
        "effective_weights":        {...},
        "missing_data_components":  [...],
        "target_years":             3.0
      },
      "data_quality": {
        "load_errors": [...]
      }
    }
    """
    return {
        "meta": {
            "generated_at":   datetime.now().isoformat(),
            "resume_id":      result.resume_id,
            "jd_slug":        result.jd_slug,
            "job_title":      result.job_title,
            "weight_profile": result.weight_profile,
        },
        "overall": {
            "final_score":    result.final_score,
            "grade":          result.grade,
            "recommendation": result.recommendation,
            "score_label":    _score_label(result.final_score),
        },
        "components": [
            {
                "dimension":       c.name,
                "display_name":    COMP_DISPLAY.get(c.name, c.name),
                "raw_score":       c.raw_score,
                "weight":          c.weight,
                "weighted_score":  round(c.weighted_score, 4),
                "confidence":      c.confidence,
                "penalty_applied": c.penalty_applied,
                "missing_data":    c.missing_data,
                "score_label":     _score_label(c.raw_score),
                "evidence":        c.evidence,
            }
            for c in result.components
        ],
        "gap_analysis":      result.gap_analysis,
        "strengths":         result.strengths,
        "improvement_areas": result.improvement_areas,
        "scoring_metadata":  result.metadata,
        "data_quality": {
            "load_errors": result.load_errors,
        },
    }


def write_json(result: "ATSResult", out_dir: Path | None = None) -> Path:
    base = out_dir or ATS_SCORES_DIR
    base.mkdir(parents=True, exist_ok=True)

    filename = f"{result.resume_id}__vs_{result.jd_slug}__ats_score.json"
    out_path = base / filename

    payload = build_json_payload(result)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    log.info("JSON score written → %s", out_path)
    return out_path


# ════════════════════════════════════════════════════════════════
#  MARKDOWN REPORT
# ════════════════════════════════════════════════════════════════

def write_markdown(result: "ATSResult", out_dir: Path | None = None) -> Path:
    base = out_dir or ATS_SCORES_DIR
    base.mkdir(parents=True, exist_ok=True)

    filename = f"{result.resume_id}__vs_{result.jd_slug}__ats_report.md"
    out_path = base / filename

    lines: list[str] = []
    a = lines.append

    a("# ATS Scoring Report")
    a("")
    a("| Field | Value |")
    a("|---|---|")
    a(f"| **Candidate** | `{result.resume_id}` |")
    a(f"| **Position** | {result.job_title} |")
    a(f"| **JD Slug** | `{result.jd_slug}` |")
    a(f"| **Weight Profile** | `{result.weight_profile}` |")
    a(f"| **Generated** | {datetime.now().strftime('%Y-%m-%d %H:%M')} |")
    a("")
    a("---")
    a("")
    a(f"## Overall Score: {result.final_score:.2f} / 100")
    a("")
    a(f"**Grade:** `{result.grade}` — {result.recommendation}")
    a("")
    a("```")
    bar_w = int(result.final_score / 100 * 30)
    a(f"{'█'*bar_w}{'░'*(30-bar_w)}  {result.final_score:.2f}%")
    a("```")
    a("")
    a("---")
    a("")
    a("## Component Scores")
    a("")
    a("| Dimension | Raw Score | Weight | Weighted | Confidence | Penalty | Status |")
    a("|---|---:|---:|---:|---:|---:|---|")

    for c in result.components:
        flags = []
        if c.missing_data:    flags.append("⚠ Missing data")
        if c.penalty_applied: flags.append(f"-{c.penalty_applied:.1f} pts")
        a(
            f"| {COMP_DISPLAY.get(c.name, c.name)} "
            f"| {c.raw_score:.2f} "
            f"| {c.weight:.2f} "
            f"| {c.weighted_score:.4f} "
            f"| {c.confidence:.2f} "
            f"| {c.penalty_applied:.1f} "
            f"| {', '.join(flags) or 'OK'} |"
        )

    a("")
    a("### Visual Breakdown")
    a("")
    a("```")
    for c in result.components:
        label = COMP_DISPLAY.get(c.name, c.name)
        a(f"{label:<28} {_bar(c.raw_score)} {c.raw_score:.2f}")
    a("```")
    a("")
    a("---")
    a("")

    if result.strengths:
        a("## Strengths")
        a("")
        for s in result.strengths:
            a(f"- ✅ {s}")
        a("")

    if result.improvement_areas:
        a("## Areas for Improvement")
        a("")
        for s in result.improvement_areas:
            a(f"- ⬆ {s}")
        a("")

    if result.gap_analysis:
        a("## Gap Analysis")
        a("")
        a("| Dimension | Score | Severity | Action |")
        a("|---|---:|---|---|")
        for g in result.gap_analysis:
            icon = "🔴" if g["severity"] == "critical" else "🟡"
            a(
                f"| {g['dimension'].replace('_',' ').title()} "
                f"| {g['score']:.2f} "
                f"| {icon} {g['severity'].upper()} "
                f"| {g['action']} |"
            )
        a("")
        a("---")
        a("")

    a("## Evidence Trail")
    a("")
    for c in result.components:
        a(f"### {COMP_DISPLAY.get(c.name, c.name)}")
        a("")
        for ev in c.evidence:
            a(f"- {ev}")
        a("")

    ew = result.metadata.get("effective_weights", {})
    if ew:
        a("---")
        a("")
        a("## Scoring Weights Used")
        a("")
        a("| Dimension | Effective Weight | Visual |")
        a("|---|---:|---|")
        for k, v in ew.items():
            wbar = int(v * 100 / 5)
            a(f"| {k.replace('_',' ').title()} | {v:.4f} | {'▓'*wbar}{'░'*(20-wbar)} |")
        a("")

    if result.load_errors:
        a("---")
        a("")
        a("## Data Quality Notes")
        a("")
        for e in result.load_errors:
            a(f"- ⚠ {e}")
        a("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Markdown report written → %s", out_path)
    return out_path


# ════════════════════════════════════════════════════════════════
#  BATCH LEADERBOARD
# ════════════════════════════════════════════════════════════════

def write_batch_leaderboard(
    results: list["ATSResult"],
    out_dir: Path | None = None,
) -> tuple[Path, Path]:
    """
    Writes two files:
      batch_leaderboard.json  – machine-readable ranked summary
      batch_leaderboard.md    – human-readable ranked table
    Returns (json_path, md_path).
    """
    base = out_dir or ATS_SCORES_DIR
    base.mkdir(parents=True, exist_ok=True)

    ranked = sorted(results, key=lambda r: r.final_score, reverse=True)

    # ── JSON leaderboard ──────────────────────────────────────────────────────
    lb_json: list[dict] = []
    for rank, r in enumerate(ranked, 1):
        comp_summary = {
            c.name: {
                "raw_score":  c.raw_score,
                "weight":     c.weight,
                "confidence": c.confidence,
            }
            for c in r.components
        }
        lb_json.append({
            "rank":               rank,
            "resume_id":          r.resume_id,
            "jd_slug":            r.jd_slug,
            "job_title":          r.job_title,
            "final_score":        r.final_score,
            "grade":              r.grade,
            "recommendation":     r.recommendation,
            "weight_profile":     r.weight_profile,
            "component_summary":  comp_summary,
            "strengths":          r.strengths,
            "improvement_areas":  r.improvement_areas,
            "gap_count":          len(r.gap_analysis),
        })

    json_path = base / "batch_leaderboard.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "total_candidates": len(ranked),
            "leaderboard": lb_json,
        }, f, indent=2, ensure_ascii=False)

    # ── Markdown leaderboard ──────────────────────────────────────────────────
    lines: list[str] = []
    a = lines.append

    a("# ATS Batch Leaderboard")
    a("")
    a(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  ")
    a(f"Total candidates: **{len(ranked)}**")
    a("")
    a("---")
    a("")
    a("## Ranked Results")
    a("")
    a("| Rank | Candidate | JD | Score | Grade | Recommendation |")
    a("|---|---|---|---:|---|---|")
    for entry in lb_json:
        icon = {"A":"🟢","B":"🔵","C":"🟡","D":"🟠","F":"🔴"}.get(entry["grade"],"⚪")
        a(
            f"| {entry['rank']} "
            f"| `{entry['resume_id']}` "
            f"| {entry['jd_slug'][:40]} "
            f"| {entry['final_score']:.2f} "
            f"| {icon} {entry['grade']} "
            f"| {entry['recommendation']} |"
        )

    a("")
    a("---")
    a("")
    a("## Component Score Matrix")
    a("")
    dims = ["skill_match", "experience_relevance", "education_alignment", "semantic_similarity"]
    headers = "| Candidate | " + " | ".join(COMP_DISPLAY[d] for d in dims) + " | **Total** |"
    sep     = "|---|" + "---:|" * len(dims) + "---:|"
    a(headers)
    a(sep)
    for entry in lb_json:
        cs = entry["component_summary"]
        row = f"| `{entry['resume_id']}` | "
        row += " | ".join(f"{cs.get(d,{}).get('raw_score',0):.1f}" for d in dims)
        row += f" | **{entry['final_score']:.2f}** |"
        a(row)

    a("")
    a("---")
    a("")
    a("## Visual Score Bars")
    a("")
    a("```")
    for entry in lb_json:
        bar = _bar(entry["final_score"], 25)
        a(f"{entry['resume_id']:<45} {bar} {entry['final_score']:.2f} ({entry['grade']})")
    a("```")

    md_path = base / "batch_leaderboard.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    log.info("Batch leaderboard written → %s, %s", json_path, md_path)
    return json_path, md_path


# ════════════════════════════════════════════════════════════════
#  CONSOLE OUTPUT
# ════════════════════════════════════════════════════════════════

BOLD  = "\033[1m"
RESET = "\033[0m"

def _score_color(s: float) -> str:
    if s >= 70: return "\033[92m"
    if s >= 55: return "\033[93m"
    if s >= 40: return "\033[33m"
    return "\033[91m"

def print_score_report(result: "ATSResult", verbose: bool = False) -> None:
    col = _score_color(result.final_score)
    sep = "─" * 68

    print(f"\n{BOLD}{'═'*68}{RESET}")
    print(f"{BOLD}  ATS SCORE REPORT{RESET}")
    print(f"  Candidate  : {BOLD}{result.resume_id}{RESET}")
    print(f"  JD         : {result.jd_slug}")
    print(f"  Position   : {result.job_title}")
    print(f"  Profile    : {result.weight_profile}")
    print(f"{'='*68}")
    print(f"\n  FINAL SCORE : {col}{BOLD}{result.final_score:.2f}{RESET}/100  "
          f"[{_score_label(result.final_score)}]")
    print(f"  {_bar(result.final_score, 32)}")
    print(f"\n  GRADE  : {col}{BOLD}{result.grade}{RESET}")
    print(f"  VERDICT: {col}{result.recommendation}{RESET}\n")
    print(sep)

    print(f"\n  {'DIMENSION':<28} {'SCORE':>6}  {'WT':>5}  {'W.SCORE':>8}  {'CONF':>5}  {'PENALTY':>8}")
    print(f"  {'─'*28} {'─'*6}  {'─'*5}  {'─'*8}  {'─'*5}  {'─'*8}")
    for c in result.components:
        s_col = _score_color(c.raw_score)
        flag  = "  ⚠ MISSING" if c.missing_data else ""
        print(
            f"  {COMP_DISPLAY.get(c.name,c.name):<28} "
            f"{s_col}{c.raw_score:>6.2f}{RESET}  "
            f"{c.weight:>5.2f}  "
            f"{c.weighted_score:>8.4f}  "
            f"{c.confidence:>5.2f}  "
            f"{c.penalty_applied:>8.1f}"
            f"{flag}"
        )

    print(f"\n  VISUAL BREAKDOWN")
    for c in result.components:
        s_col = _score_color(c.raw_score)
        label = COMP_DISPLAY.get(c.name, c.name)
        print(f"  {label:<28} {s_col}{_bar(c.raw_score,25)}{RESET} {c.raw_score:.2f}")

    if result.strengths:
        print(f"\n  ✓ STRENGTHS")
        for s in result.strengths:
            print(f"    • {s}")
    if result.gap_analysis:
        print(f"\n  ✗ GAPS")
        for g in result.gap_analysis:
            gc = "\033[91m" if g["severity"]=="critical" else "\033[93m"
            print(f"    {gc}• {g['dimension'].replace('_',' ').title()} "
                  f"[{g['severity'].upper()}] – {g['action']}{RESET}")
    if result.improvement_areas:
        print(f"\n  ↑ IMPROVEMENT AREAS")
        for a in result.improvement_areas:
            print(f"    • {a}")

    if verbose:
        print(f"\n{sep}")
        print(f"  EVIDENCE TRAIL")
        for c in result.components:
            print(f"\n  ▸ {COMP_DISPLAY.get(c.name,c.name).upper()}")
            for ev in c.evidence:
                print(f"      {ev}")

    if result.load_errors:
        print(f"\n{sep}")
        print(f"  ⚠ DATA QUALITY ISSUES")
        for e in result.load_errors:
            print(f"    {e}")

    ew = result.metadata.get("effective_weights", {})
    if ew:
        print(f"\n{sep}")
        print(f"  EFFECTIVE WEIGHTS")
        for k, v in ew.items():
            print(f"    {k.replace('_',' ').title():<30}: {v:.4f}")

    print(f"\n{'═'*68}\n")


def print_leaderboard(results: list["ATSResult"]) -> None:
    ranked = sorted(results, key=lambda r: r.final_score, reverse=True)
    print(f"\n{'═'*78}")
    print(f"  {'RK':<4} {'CANDIDATE':<38} {'SCORE':>6} {'GR':>3}  RECOMMENDATION")
    print(f"  {'─'*4} {'─'*38} {'─'*6} {'─'*3}  {'─'*28}")
    for i, r in enumerate(ranked, 1):
        col = _score_color(r.final_score)
        print(
            f"  {i:<4} {r.resume_id:<38} "
            f"{col}{r.final_score:>6.2f}{RESET} "
            f"{col}{r.grade:>3}{RESET}  "
            f"{r.recommendation}"
        )
    print(f"{'═'*78}\n")
