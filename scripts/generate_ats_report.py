"""
scripts/generate_ats_report.py
==============================
Generates the Day 17 ATS Testing Report (Markdown) using the
metrics + backlog produced by `run_ats_testing.py`.

Run AFTER `run_ats_testing.py`:
    python scripts/generate_ats_report.py

Output:
    ats_results/day17_testing_report.md

Day: 17
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Required file missing: {path}\nRun scripts/run_ats_testing.py first.")
    with open(path) as f:
        return json.load(f)


def build_report(metrics: dict, backlog: dict) -> str:
    overall = metrics["overall"]
    cm = overall["confusion_matrix"]
    by_cat = metrics.get("by_category", {})
    items = backlog.get("items", {})
    mismatch = metrics.get("mismatch_analysis", {}).get("counts", {})

    out = []
    out.append("# ATS System Testing Report — Zecpath AI")
    out.append("")
    out.append(f"**Day:** 17  ")
    out.append(f"**Generated:** {datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', '')}Z  ")  #ADDED
    #out.append(f"**Generated:** {datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "")}Z  ")
    out.append(f"**Records evaluated:** {metrics.get('total_records', 0)}")
    out.append("")
    out.append("---")
    out.append("")

    # 1. Objective
    out.append("## 1. Objective")
    out.append("")
    out.append("Evaluate the **accuracy, reliability, and adaptability** of the ATS AI across multiple")
    out.append("job roles and candidate profiles (tech, non-tech, fresher, senior).")
    out.append("")

    # 2. Test Dataset Summary
    out.append("## 2. Test Dataset Summary")
    out.append("")
    out.append("| Category | Count |")
    out.append("|---|---|")
    for cat, m in by_cat.items():
        out.append(f"| {cat} | {m['confusion_matrix']['tp'] + m['confusion_matrix']['fp'] + m['confusion_matrix']['fn'] + m['confusion_matrix']['tn']} |")
    out.append(f"| **Total Tested** | **{metrics.get('total_records', 0)}** |")
    out.append("")

    # 3. Confusion Matrix
    out.append("## 3. Confusion Matrix (Shortlist Decision)")
    out.append("")
    out.append("|              | AI Shortlist | AI Reject |")
    out.append("|---|---|---|")
    out.append(f"| **HR Shortlist** | {cm['tp']} (TP) | {cm['fn']} (FN) |")
    out.append(f"| **HR Reject**    | {cm['fp']} (FP) | {cm['tn']} (TN) |")
    out.append("")

    # 4. Key Metrics
    out.append("## 4. Key Metrics")
    out.append("")
    out.append(f"- **Precision:** {overall['precision_pct']}")
    out.append(f"- **Recall:** {overall['recall_pct']}")
    out.append(f"- **Accuracy:** {overall['accuracy_pct']}")
    out.append(f"- **F1 Score:** {overall['f1_pct']}")
    out.append("")
    out.append("Formulas:")
    out.append("```")
    out.append("Precision = TP / (TP + FP)")
    out.append("Recall    = TP / (TP + FN)")
    out.append("Accuracy  = (TP + TN) / Total")
    out.append("F1        = 2 * (P * R) / (P + R)")
    out.append("```")
    out.append("")

    # 5. Category-wise performance
    out.append("## 5. Category-wise Performance")
    out.append("")
    out.append("| Category | Accuracy | Precision | Recall | F1 | n |")
    out.append("|---|---|---|---|---|---|")
    for cat, m in by_cat.items():
        n = m["confusion_matrix"]["tp"] + m["confusion_matrix"]["fp"] + m["confusion_matrix"]["fn"] + m["confusion_matrix"]["tn"]
        out.append(f"| {cat} | {m['accuracy_pct']} | {m['precision_pct']} | {m['recall_pct']} | {m['f1_pct']} | {n} |")
    out.append("")

    # 6. Mismatch Cases
    out.append("## 6. Mismatch Cases")
    out.append("")
    if mismatch:
        out.append("| Issue Type | Count |")
        out.append("|---|---|")
        for k, v in mismatch.items():
            label = k.replace("_", " ").title()
            out.append(f"| {label} | {v} |")
    else:
        out.append("_No mismatches detected._")
    out.append("")

    # 7. Improvement Backlog
    out.append("## 7. Improvement Backlog")
    out.append("")
    for prio in ["high", "medium", "low"]:
        out.append(f"### {prio.title()} Priority")
        out.append("")
        prio_items = items.get(prio, [])
        if not prio_items:
            out.append("_None_")
            out.append("")
            continue
        for item in prio_items:
            out.append(f"- **[{item['id']}] {item['title']}**")
            out.append(f"  - Evidence: {item['evidence']}")
            out.append(f"  - Suggestion: {item['suggestion']}")
        out.append("")

    # 8. Final Evaluation
    out.append("## 8. Final Evaluation Summary")
    out.append("")
    out.append("**Overall Performance**")
    out.append("")
    out.append(f"- Accuracy: {overall['accuracy_pct']}")
    out.append(f"- Precision: {overall['precision_pct']}")
    out.append(f"- Recall: {overall['recall_pct']}")
    out.append(f"- F1 Score: {overall['f1_pct']}")
    out.append("")
    out.append("**Conclusion**")
    out.append("")
    accuracy = overall["accuracy"]
    if accuracy >= 0.85:
        verdict = "ATS system is **production-ready** for hiring across tested roles."
    elif accuracy >= 0.75:
        verdict = "ATS system is **production-ready for tech hiring**; non-tech roles need improvement."
    else:
        verdict = "ATS system requires **further tuning** before broad production rollout."
    out.append(f"- {verdict}")
    if mismatch.get("soft_skill_miss", 0) > 0:
        out.append("- Soft-skill extraction needs enhancement for non-tech roles.")
    if mismatch.get("keyword_mismatch", 0) > 0:
        out.append("- Keyword normalization (abbreviations) requires attention.")
    out.append("")
    out.append("---")
    out.append("_Auto-generated by `scripts/generate_ats_report.py`_")

    return "\n".join(out)


def main():
    metrics_path = ROOT / "ats_results" / "day17_metrics.json"
    backlog_path = ROOT / "ats_results" / "day17_backlog.json"
    report_path = ROOT / "ats_results" / "day17_testing_report.md"

    metrics = load_json(metrics_path)
    backlog = load_json(backlog_path)
    md = build_report(metrics, backlog)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"✓ Report generated: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
