"""
tests/test_ats_role_adaptability.py
===================================
Pytest: validates per-category accuracy
(tech / non_tech / fresher / senior).

Run:
    pytest tests/test_ats_role_adaptability.py -v

Day: 17
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.score_loader import load_all_scores, get_resume_jd_pair_key, extract_decision
from utils.metrics_calculator import evaluate_by_category


@pytest.fixture(scope="module")
def config():
    with open(ROOT / "ats_engine" / "ats_test_config.json") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def joined_records(config):
    hr_path = ROOT / config["paths"]["hr_evaluations"]
    scores_dir = ROOT / config["paths"]["scores_dir"]

    if not hr_path.exists():
        pytest.skip(f"HR evaluations missing: {hr_path}")

    with open(hr_path) as f:
        real_hr = {
            k: v for k, v in json.load(f).get("evaluations", {}).items()
            if not k.startswith("EXAMPLE_")
        }

    ai_records = load_all_scores(scores_dir)
    if not ai_records or not real_hr:
        pytest.skip("No AI scores or HR evaluations available.")

    threshold = config["decision_thresholds"]["shortlist"]
    joined = []
    for rec in ai_records:
        key = get_resume_jd_pair_key(rec)
        hr = real_hr.get(key)
        if hr is None:
            continue
        joined.append({
            "key": key,
            "ai_decision": extract_decision(rec, threshold=threshold),
            "hr_decision": hr["hr_decision"],
            "category": hr.get("category", "uncategorized"),
        })
    if not joined:
        pytest.skip("No overlap between AI scores and HR evaluations.")
    return joined


@pytest.fixture(scope="module")
def category_metrics(joined_records):
    return evaluate_by_category(joined_records, category_field="category")


# Parametrized test — runs once per category
@pytest.mark.parametrize("category", ["tech", "non_tech", "fresher", "senior"])
def test_category_accuracy(category_metrics, config, category):
    targets = config["category_targets"]
    target = targets.get(category, {}).get("min_accuracy", 0.7)

    if category not in category_metrics:
        pytest.skip(f"No records for category '{category}' in HR evaluations.")

    m = category_metrics[category]
    assert m.accuracy >= target, (
        f"[{category}] accuracy {m.accuracy:.3f} below target {target}"
    )


def test_at_least_two_categories_present(category_metrics):
    """Make sure HR evals span multiple categories — not single-category dataset."""
    assert len(category_metrics) >= 2, (
        f"Only {len(category_metrics)} category present; "
        "Day 17 PRD requires tech, non_tech, fresher, senior."
    )
