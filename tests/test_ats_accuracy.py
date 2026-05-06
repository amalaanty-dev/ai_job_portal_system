"""
tests/test_ats_accuracy.py
==========================
Pytest: validates that the ATS overall accuracy/precision/recall/F1
meet the targets defined in datasets/ats_test_config.json.

Run:
    pytest tests/test_ats_accuracy.py -v

Day: 17
"""

import json
import sys
from pathlib import Path

import pytest

# Make project root importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.score_loader import load_all_scores, get_resume_jd_pair_key, extract_decision
from utils.metrics_calculator import evaluate, ConfusionMatrix, compute_metrics


# ----------------------------- Fixtures ---------------------------------------
@pytest.fixture(scope="module")
def config():
    cfg_path = ROOT / "ats_engine" / "ats_test_config.json"
    if not cfg_path.exists():
        pytest.skip(f"Config missing: {cfg_path}")
    with open(cfg_path) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def hr_evaluations(config):
    hr_path = ROOT / config["paths"]["hr_evaluations"]
    if not hr_path.exists():
        pytest.skip(f"HR evaluations missing: {hr_path}")
    with open(hr_path) as f:
        return json.load(f).get("evaluations", {})


@pytest.fixture(scope="module")
def joined_records(config, hr_evaluations):
    """Load AI scores and join them with HR ground truth."""
    scores_dir = ROOT / config["paths"]["scores_dir"]
    ai_records = load_all_scores(scores_dir)

    # Filter out the example placeholder entries
    real_hr = {k: v for k, v in hr_evaluations.items() if not k.startswith("EXAMPLE_")}

    if not ai_records:
        pytest.skip(
            f"No AI score JSONs found in {scores_dir}. "
            "Run your scoring pipeline first to populate this folder."
        )
    if not real_hr:
        pytest.skip(
            "HR evaluations only contain EXAMPLE_ entries. "
            "Populate datasets/hr_manual_evaluations.json with real entries."
        )

    threshold = config["decision_thresholds"]["shortlist"]
    joined = []
    for rec in ai_records:
        key = get_resume_jd_pair_key(rec)
        hr = real_hr.get(key)
        if hr is None:
            continue  # No HR evaluation for this pair — skip
        joined.append({
            "key": key,
            "ai_decision": extract_decision(rec, threshold=threshold),
            "hr_decision": hr["hr_decision"],
            "category": hr.get("category", "uncategorized"),
            "final_score": rec.get("final_score"),
            "identifiers": rec.get("identifiers", {}),
        })

    if not joined:
        pytest.skip(
            "No overlap between AI scores and HR evaluations. "
            "Ensure resume_id + jd_id values match between score JSONs and HR file."
        )
    return joined


# ----------------------------- Tests ------------------------------------------
def test_dataset_size(joined_records):
    """Sanity: at least 1 record joined."""
    assert len(joined_records) > 0, "No joined AI/HR records to evaluate"


def test_precision_meets_target(joined_records, config):
    targets = config["target_metrics"]
    ai = [r["ai_decision"] for r in joined_records]
    hr = [r["hr_decision"] for r in joined_records]
    m = evaluate(ai, hr)
    assert m.precision >= targets["min_precision"], (
        f"Precision {m.precision:.3f} below target {targets['min_precision']}"
    )


def test_recall_meets_target(joined_records, config):
    targets = config["target_metrics"]
    ai = [r["ai_decision"] for r in joined_records]
    hr = [r["hr_decision"] for r in joined_records]
    m = evaluate(ai, hr)
    assert m.recall >= targets["min_recall"], (
        f"Recall {m.recall:.3f} below target {targets['min_recall']}"
    )


def test_accuracy_meets_target(joined_records, config):
    targets = config["target_metrics"]
    ai = [r["ai_decision"] for r in joined_records]
    hr = [r["hr_decision"] for r in joined_records]
    m = evaluate(ai, hr)
    assert m.accuracy >= targets["min_accuracy"], (
        f"Accuracy {m.accuracy:.3f} below target {targets['min_accuracy']}"
    )


def test_f1_meets_target(joined_records, config):
    targets = config["target_metrics"]
    ai = [r["ai_decision"] for r in joined_records]
    hr = [r["hr_decision"] for r in joined_records]
    m = evaluate(ai, hr)
    assert m.f1_score >= targets["min_f1"], (
        f"F1 {m.f1_score:.3f} below target {targets['min_f1']}"
    )


# ----------------------------- Pure unit tests --------------------------------
def test_confusion_matrix_prd_sample():
    """PRD sample: TP=28 FP=3 FN=4 TN=5 → ~82.5% accuracy, 90.3% precision."""
    cm = ConfusionMatrix(tp=28, fp=3, fn=4, tn=5)
    m = compute_metrics(cm)
    assert round(m.precision * 100, 1) == 90.3
    assert round(m.recall * 100, 1) == 87.5
    assert round(m.accuracy * 100, 1) == 82.5
    assert round(m.f1_score * 100, 1) == 88.9 or round(m.f1_score * 100, 1) == 88.8
