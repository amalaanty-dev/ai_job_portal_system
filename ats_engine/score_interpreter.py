"""
Score Interpreter — Day 13
Zecpath AI Job Portal

Converts a numeric ATS final score into a human-readable rating,
band description, and actionable recruiter recommendation.

Score Bands:
  90–100 : Excellent Fit
  80–89  : Strong Fit
  70–79  : Good Fit
  60–69  : Moderate Fit
  50–59  : Partial Fit
  <50    : Poor Fit / Not Recommended
"""

import logging

logger = logging.getLogger(__name__)

SCORE_BANDS = [
    {
        "min": 90,
        "max": 100,
        "rating": "Excellent Fit",
        "score_band": "90-100",
        "recommendation": "Shortlist immediately for first interview round",
        "priority": "High Priority",
    },
    {
        "min": 80,
        "max": 90,
        "rating": "Strong Fit",
        "score_band": "80-89",
        "recommendation": "Shortlist for first interview round",
        "priority": "High",
    },
    {
        "min": 70,
        "max": 80,
        "rating": "Good Fit",
        "score_band": "70-79",
        "recommendation": "Proceed to next interview round",
        "priority": "Medium-High",
    },
    {
        "min": 60,
        "max": 70,
        "rating": "Moderate Fit",
        "score_band": "60-69",
        "recommendation": "Consider if strong candidates are limited",
        "priority": "Medium",
    },
    {
        "min": 50,
        "max": 60,
        "rating": "Partial Fit",
        "score_band": "50-59",
        "recommendation": "Review manually before deciding",
        "priority": "Low",
    },
    {
        "min": 0,
        "max": 50,
        "rating": "Poor Fit",
        "score_band": "0-49",
        "recommendation": "Not recommended for this role",
        "priority": "Reject",
    },
]


class ScoreInterpreter:
    """Translates numeric scores into explainable rating objects."""

    def interpret(self, score: float, job_role: str = "") -> dict:
        """
        Return interpretation dict for a given score.

        Parameters
        ----------
        score    : Final ATS score (0–100)
        job_role : Job role string (for future role-specific overrides)

        Returns
        -------
        dict with keys: rating, score_band, recommendation, priority
        """
        score = max(0.0, min(100.0, float(score)))

        for band in SCORE_BANDS:
            # Use half-open intervals [min, max) with special case for top band
            if score >= band["min"] and (score < band["max"] or band["max"] == 100):
                return {
                    "rating": band["rating"],
                    "score_band": band["score_band"],
                    "recommendation": band["recommendation"],
                    "priority": band["priority"],
                }

        # Fallback (should never reach here)
        logger.warning("Score %.1f did not match any band — defaulting to Poor Fit", score)
        return {
            "rating": "Poor Fit",
            "score_band": "0-49",
            "recommendation": "Not recommended for this role",
            "priority": "Reject",
        }

    def bulk_rank(self, results: list[dict]) -> list[dict]:
        """
        Rank a list of ATS result dicts by final_score descending.
        Returns the same list sorted with rank field added.
        """
        sorted_results = sorted(
            results,
            key=lambda r: r.get("final_score", 0),
            reverse=True,
        )
        for rank, result in enumerate(sorted_results, start=1):
            result["rank"] = rank
        return sorted_results

    def summary_table(self, results: list[dict]) -> list[dict]:
        """
        Return a condensed summary table for reporting / dashboard display.
        """
        table = []
        for r in results:
            table.append({
                "resume_id": r["identifiers"]["resume_id"],
                "jd_id": r["identifiers"]["jd_id"],
                "job_role": r["identifiers"]["job_role"],
                "final_score": r["final_score"],
                "rating": r["score_interpretation"]["rating"],
                "recommendation": r["score_interpretation"]["recommendation"],
                "rank": r.get("rank", "-"),
            })
        return table
