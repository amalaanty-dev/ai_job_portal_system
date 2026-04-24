"""
Missing Data Handler — Day 13
Zecpath AI Job Portal

Handles absent resume sections gracefully by redistributing weights
among the available sections, ensuring final score remains meaningful.

Redistribution strategies:
  proportional  — missing weight shared proportionally among present sections
  equal         — missing weight split equally among present sections
  skills_first  — missing weight added to skills first, then experience
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

REDISTRIBUTION_STRATEGY = "proportional"  # Default global strategy


class MissingDataHandler:
    """
    Adjusts weight distribution when one or more resume sections are absent.
    Always ensures final weights sum to 100.
    """

    def handle(
        self,
        weights: dict,
        missing_sections: list[str],
        strategy: str = REDISTRIBUTION_STRATEGY,
    ) -> tuple[dict, bool, Optional[str]]:
        """
        Parameters
        ----------
        weights         : Original weights dict (skills, experience, education, semantic)
        missing_sections: List of section keys that are absent
        strategy        : Redistribution method

        Returns
        -------
        (adjusted_weights, was_redistributed, strategy_name_or_None)
        """
        if not missing_sections:
            return weights, False, None

        present = [k for k in weights if k not in missing_sections]
        missing = [k for k in weights if k in missing_sections]

        if not present:
            # All sections missing — return equal weights
            equal = 100 // len(weights)
            return {k: equal for k in weights}, True, "all_missing_equal"

        lost_weight = sum(weights[k] for k in missing)
        adjusted = {k: weights[k] for k in weights}

        if strategy == "proportional":
            adjusted = self._proportional(adjusted, present, missing, lost_weight)
        elif strategy == "equal":
            adjusted = self._equal(adjusted, present, missing, lost_weight)
        elif strategy == "skills_first":
            adjusted = self._skills_first(adjusted, present, missing, lost_weight)
        else:
            adjusted = self._proportional(adjusted, present, missing, lost_weight)
            strategy = "proportional"

        # Zero out missing sections
        for k in missing:
            adjusted[k] = 0

        # Ensure exact sum of 100
        adjusted = self._normalise(adjusted, present)

        logger.info(
            "Weight redistribution (%s): lost %.0f from %s → %s",
            strategy, lost_weight, missing, adjusted,
        )

        return adjusted, True, strategy

    # ------------------------------------------------------------------
    # Redistribution strategies
    # ------------------------------------------------------------------

    def _proportional(self, weights, present, missing, lost_weight):
        """Distribute lost weight proportionally to present sections."""
        present_total = sum(weights[k] for k in present)
        if present_total == 0:
            return weights
        for k in present:
            weights[k] += round(lost_weight * (weights[k] / present_total))
        return weights

    def _equal(self, weights, present, missing, lost_weight):
        """Distribute lost weight equally among present sections."""
        share = lost_weight / len(present)
        for k in present:
            weights[k] += share
        return weights

    def _skills_first(self, weights, present, missing, lost_weight):
        """Add lost weight to skills first, then experience, then others."""
        priority = ["skills", "experience", "semantic", "education"]
        remaining = lost_weight
        for key in priority:
            if key in present and remaining > 0:
                cap = 100 - weights[key]
                add = min(remaining, cap)
                weights[key] += add
                remaining -= add
        return weights

    def _normalise(self, weights, present):
        """Force integer weights that sum exactly to 100."""
        total = sum(weights[k] for k in present)
        if total == 0:
            return weights

        # Scale to 100
        scale = 100 / total
        adjusted = {k: round(weights[k] * scale) for k in weights}

        # Fix rounding drift
        diff = 100 - sum(adjusted.values())
        if diff != 0 and present:
            # Add/subtract from the highest-weight present section
            top = max(present, key=lambda k: adjusted[k])
            adjusted[top] += diff

        return adjusted
