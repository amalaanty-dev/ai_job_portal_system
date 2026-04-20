from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)


def parse_date(date_str: str) -> date | None:
    """
    Parse a date string into a date object.
    Supports: ISO (2020-01-01), Jan 2020, January 2020, Jan. 2020,
              01/2020, 2020-01, 2020 (year-only → Jan 1 of that year).
    """
    if not date_str:
        return None

    cleaned = date_str.strip()

    if cleaned.lower() in ("present", "current", "now"):
        return date.today().replace(day=1)

    formats = [
        ("%Y-%m-%d", False),   # 2020-01-01
        ("%b %Y",    False),   # Jan 2020
        ("%B %Y",    False),   # January 2020
        ("%b. %Y",   False),   # Jan. 2020
        ("%m/%Y",    False),   # 01/2020
        ("%Y-%m",    False),   # 2020-01
        ("%Y",       True),    # 2020 — year-only, less precise
    ]

    for fmt, year_only in formats:
        try:
            parsed = datetime.strptime(cleaned, fmt).date()
            if year_only:
                logger.debug(
                    "date_utils: year-only date '%s' → %s "
                    "(gap/overlap precision may be reduced)",
                    cleaned, parsed,
                )
            return parsed
        except ValueError:
            continue

    logger.warning("⚠️ date_utils: could not parse date string: '%s'", cleaned)
    return None


def calculate_months(start: date, end: date) -> int:
    """
    Return the number of whole calendar months between two date objects.

    Formula: (end.year - start.year) * 12 + (end.month - start.month)

    Examples:
        Jan 2020 → Jan 2020  =  0  (same month, no full month elapsed)
        Jan 2020 → Feb 2020  =  1
        Jan 2020 → Dec 2020  = 11
        Jul 2021 → Dec 2024  = 41

    Returns 0 if either argument is None or if end < start.
    """
    if not start or not end:
        return 0

    delta = (end.year - start.year) * 12 + (end.month - start.month)
    return max(delta, 0)