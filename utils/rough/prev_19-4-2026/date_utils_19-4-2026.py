from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)


def parse_date(date_str: str) -> date | None:
    """
    Parse a date string into a date object.
    Supports: ISO (2020-01-01), Jan 2020, 01/2020, 2020, etc.
    """
    if not date_str:
        return None

    cleaned = date_str.strip()

    if cleaned.lower() in ("present", "current", "now"):
        return date.today().replace(day=1)

    # Added %Y-%m-%d for ISO support
    formats = [
        "%Y-%m-%d", # 2020-01-01
        "%b %Y",    # Jan 2020
        "%B %Y",    # January 2020
        "%b. %Y",   # Jan. 2020
        "%m/%Y",    # 01/2020
        "%Y-%m",    # 2020-01
        "%Y",       # 2020
    ]

    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue

    logger.warning("⚠️ date_utils: could not parse date string: '%s'", cleaned)
    return None


def calculate_months(start: date, end: date) -> int:
    """
    Return the number of whole months between two date objects.
    """
    if not start or not end:
        return 0

    # FIX: Corrected (end.month - start.month)
    delta = (end.year - start.year) * 12 + (end.month - start.month)
    return max(delta + 1, 1)            #return max(delta, 1) # Minimum 1 month to ensure roles are counted