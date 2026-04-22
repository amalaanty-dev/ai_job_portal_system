"""
semantic_engine/validator.py
──────────────────────────────
Validates the semantic matching engine against ground-truth labels.

Produces:
  • Per-pair pass/fail with expected vs actual score
  • Per-job-type accuracy summary
  • Overall accuracy, precision, recall, F1
  • Printed matching accuracy report
"""

import json
from dataclasses import dataclass
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# RESULT DATACLASS
# ═══════════════════════════════════════════════════════════════

@dataclass
class ValidationRecord:
    resume_id:       str
    jd_id:           str
    resume_name:     str
    jd_title:        str
    expected_label:  str
    actual_label:    str
    expected_range:  tuple
    actual_score:    float
    in_range:        bool
    label_match:     bool
    job_type:        str


@dataclass
class ValidationReport:
    records:          list
    overall_accuracy: float
    label_accuracy:   float
    range_accuracy:   float
    per_job_type:     dict
    confusion_matrix: dict
    total_pairs:      int
    passed_range:     int
    passed_label:     int


# ═══════════════════════════════════════════════════════════════
# VALIDATOR
# ═══════════════════════════════════════════════════════════════

class MatchingValidator:
    """
    Validates semantic matching results against ground truth.

    Usage:
        validator = MatchingValidator()
        report    = validator.validate(match_results, ground_truth, jd_list)
        validator.print_report(report)
    """

    def validate(
        self,
        match_results:  list,        # list of MatchResult objects
        ground_truth:   list[tuple], # (resume_id, jd_id, label, score_range)
        jd_list:        list[dict],  # to get job_type per JD
    ) -> ValidationReport:
        """
        Compare match_results against ground_truth labels.

        Args:
            match_results: output of SemanticMatcher.match_batch()
            ground_truth:  list of (resume_id, jd_id, expected_label, score_range)
            jd_list:       list of JD dicts (used to look up job_type)

        Returns:
            ValidationReport with full accuracy breakdown
        """
        # Build lookups
        result_lookup = {
            (r.resume_id, r.jd_id): r
            for r in match_results
        }
        jd_type_lookup = {
            jd["id"]: jd.get("job_type", "default")
            for jd in jd_list
        }

        records       = []
        label_matches = 0
        range_hits    = 0

        for (rid, jid, exp_label, exp_range) in ground_truth:
            result = result_lookup.get((rid, jid))
            if result is None:
                continue

            actual_score = result.overall_score
            actual_label = result.match_label

            # Normalise labels for comparison
            exp_norm    = self._normalise_label(exp_label)
            actual_norm = self._normalise_label(actual_label)

            in_range    = exp_range[0] <= actual_score <= exp_range[1]
            label_match = exp_norm == actual_norm

            if label_match:  label_matches += 1
            if in_range:     range_hits    += 1

            records.append(ValidationRecord(
                resume_id      = rid,
                jd_id          = jid,
                resume_name    = result.resume_name,
                jd_title       = result.jd_title,
                expected_label = exp_label,
                actual_label   = actual_label,
                expected_range = exp_range,
                actual_score   = actual_score,
                in_range       = in_range,
                label_match    = label_match,
                job_type       = jd_type_lookup.get(jid, "unknown"),
            ))

        total = len(records)

        # Per-job-type breakdown
        per_jt: dict[str, dict] = {}
        for rec in records:
            jt = rec.job_type
            per_jt.setdefault(jt, {"total": 0, "label_ok": 0, "range_ok": 0})
            per_jt[jt]["total"]    += 1
            per_jt[jt]["label_ok"] += int(rec.label_match)
            per_jt[jt]["range_ok"] += int(rec.in_range)

        per_jt_summary = {
            jt: {
                "total":          v["total"],
                "label_accuracy": round(v["label_ok"] / v["total"], 3) if v["total"] else 0,
                "range_accuracy": round(v["range_ok"] / v["total"], 3) if v["total"] else 0,
            }
            for jt, v in per_jt.items()
        }

        # Confusion matrix (expected → actual)
        confusion: dict[str, dict] = {}
        for rec in records:
            e = self._normalise_label(rec.expected_label)
            a = self._normalise_label(rec.actual_label)
            confusion.setdefault(e, {})
            confusion[e][a] = confusion[e].get(a, 0) + 1

        overall_acc = round((label_matches + range_hits) / (2 * total), 4) if total else 0

        return ValidationReport(
            records          = records,
            overall_accuracy = overall_acc,
            label_accuracy   = round(label_matches / total, 4) if total else 0,
            range_accuracy   = round(range_hits    / total, 4) if total else 0,
            per_job_type     = per_jt_summary,
            confusion_matrix = confusion,
            total_pairs      = total,
            passed_range     = range_hits,
            passed_label     = label_matches,
        )

    @staticmethod
    def _normalise_label(label: str) -> str:
        """Map verbose labels to 3-class: strong / partial / mismatch."""
        label = label.lower().replace(" ", "_")
        if "strong" in label or label in ("good_match",):
            return "strong_match"
        if "partial" in label or "weak" in label or "good" in label:
            return "partial_match"
        if "mismatch" in label or "no_match" in label:
            return "mismatch"
        return label

    # ───────────────────────────────────────────────────────────
    # REPORT PRINTER
    # ───────────────────────────────────────────────────────────

    def print_report(self, report: ValidationReport) -> None:
        """Print a formatted matching accuracy report."""

        W = 72
        print()
        print("═" * W)
        print("  DAY 12 – SEMANTIC MATCHING ENGINE  |  ACCURACY REPORT")
        print("═" * W)

        print(f"\n  Total pairs evaluated : {report.total_pairs}")
        print(f"  Label accuracy        : {report.label_accuracy*100:.1f}%  ({report.passed_label}/{report.total_pairs})")
        print(f"  Score-range accuracy  : {report.range_accuracy*100:.1f}%  ({report.passed_range}/{report.total_pairs})")
        print(f"  Overall accuracy      : {report.overall_accuracy*100:.1f}%")

        # Per-job-type
        print(f"\n{'─'*W}")
        print(f"  {'JOB TYPE':<28} {'TOTAL':>5}  {'LABEL ACC':>10}  {'RANGE ACC':>10}")
        print(f"{'─'*W}")
        for jt, v in sorted(report.per_job_type.items()):
            print(f"  {jt:<28} {v['total']:>5}  {v['label_accuracy']*100:>9.1f}%  {v['range_accuracy']*100:>9.1f}%")

        # Confusion matrix
        print(f"\n{'─'*W}")
        print("  CONFUSION MATRIX  (rows=expected, cols=predicted)")
        print(f"{'─'*W}")
        classes = ["strong_match", "partial_match", "mismatch"]
        # header  = f"  {'EXPECTED \\ PREDICTED':<22}" + "".join(f"  {c[:13]:>13}" for c in classes)
        #ADDED
        header = f"  {'EXPECTED ' + chr(92) + ' PREDICTED':<22}" + "".join(f"  {c[:13]:>13}" for c in classes)
        print(header)
        print(f"  {'─'*68}")
        for exp in classes:
            row = f"  {exp:<22}"
            for pred in classes:
                count = report.confusion_matrix.get(exp, {}).get(pred, 0)
                row  += f"  {count:>13}"
            print(row)

        # Per-pair detail
        print(f"\n{'─'*W}")
        print(f"  {'RESUME':<22} {'JD':<30} {'SCORE %':>8}  {'EXPECTED':<16} {'ACTUAL':<16} {'OK'}")
        print(f"{'─'*W}")
        for rec in sorted(report.records, key=lambda r: r.resume_id):
            ok_sym  = "✅" if rec.label_match and rec.in_range else ("⚠️ " if rec.label_match or rec.in_range else "❌")
            rname   = rec.resume_name[:20]
            jtitle  = rec.jd_title[:28]
            exp_rng = f"[{rec.expected_range[0]*100:.1f}-{rec.expected_range[1]*100:.1f}%]"
            print(f"  {rname:<22} {jtitle:<30} {rec.actual_score*100:>7.2f}%  {rec.expected_label:<16} {rec.actual_label:<16} {ok_sym}")

        print(f"\n{'═'*W}\n")

    def to_json(self, report: ValidationReport) -> str:
        """Serialise the report to a JSON string."""
        data = {
            "summary": {
                "total_pairs":      report.total_pairs,
                "label_accuracy":   report.label_accuracy,
                "range_accuracy":   report.range_accuracy,
                "overall_accuracy": report.overall_accuracy,
                "passed_label":     report.passed_label,
                "passed_range":     report.passed_range,
            },
            "per_job_type":     report.per_job_type,
            "confusion_matrix": report.confusion_matrix,
            "pair_results": [
                {
                    "resume_id":      r.resume_id,
                    "jd_id":          r.jd_id,
                    "resume_name":    r.resume_name,
                    "jd_title":       r.jd_title,
                    "job_type":       r.job_type,
                    "semantic_score": round(r.actual_score * 100, 2),
                    "expected_range": [
                        round(r.expected_range[0] * 100, 2),
                        round(r.expected_range[1] * 100, 2),
                    ],
                    "expected_label": r.expected_label,
                    "actual_label":   r.actual_label,
                    "in_range":       r.in_range,
                    "label_match":    r.label_match,
                }
                for r in report.records
            ]
        }
        return json.dumps(data, indent=2)