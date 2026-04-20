from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)


def parse_date(date_str: str) -> date | None:
    """
    Parse a date string into a date object.

    Supports:
        "Jan 2020", "January 2020", "Jan. 2020"
        "01/2020", "2020-01", "2020"
        "Present", "Current", "Now"

    Returns:
        date object or None if unparseable
    """
    if not date_str:
        return None

    cleaned = date_str.strip()

    # Present-tokens handled by caller (_resolve_end_date) — but guard here too
    if cleaned.lower() in ("present", "current", "now"):
        return date.today().replace(day=1)

    formats = [
        "%b %Y",    # Jan 2020
        "%B %Y",    # January 2020
        "%b. %Y",   # Jan. 2020
        "%m/%Y",    # 01/2020
        "%Y-%m",    # 2020-01
        "%Y",       # 2020  (fallback — sets month=Jan)
    ]

    for fmt in formats:
        try:
            # Parse into datetime then extract date — avoids T00:00:00 datetime objects
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue

    logger.warning("⚠️ date_utils: could not parse date string: '%s'", cleaned)
    return None


def calculate_months(start: date, end: date) -> int:
    """
    Return the number of whole months between two date objects.

    Args:
        start: Start date
        end:   End date

    Returns:
        Whole months as int, minimum 0 (never negative)
    """
    if not start or not end:
        return 0

    delta = (end.year - start.year) * 12 + (end.month - end.month)
    return max(delta, 0)