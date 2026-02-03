# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""CEL Event Helper Functions.

This module provides utility functions for working with event data in CEL expressions.
Functions are designed to be pure/testable where possible, with Odoo env dependencies
clearly marked.

Categories:
    1. Period parsing - Convert period strings to date ranges
    2. Dynamic period generators - Get current/past period strings
    3. Selection mode resolvers - Determine event selection behavior
    4. Temporal filter helpers - Combine and apply date filters
"""

import logging
import re
from calendar import monthrange
from datetime import date, timedelta
from typing import Any

_logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# PERIOD PARSING
# ══════════════════════════════════════════════════════════════════════════════


def parse_period(period: str) -> tuple[date, date]:
    """Parse a period string to (start_date, end_date).

    Formats supported:
        - 'YYYY' -> Full year (2024 -> 2024-01-01 to 2024-12-31)
        - 'YYYY-QN' -> Quarter (2024-Q1 -> 2024-01-01 to 2024-03-31)
        - 'YYYY-HN' -> Half year (2024-H1 -> 2024-01-01 to 2024-06-30)
        - 'YYYY-MM' -> Month (2024-03 -> 2024-03-01 to 2024-03-31)
        - 'YYYY-WNN' -> ISO week (2024-W01 -> week 1 of 2024)

    Args:
        period: Period string in one of the supported formats

    Returns:
        Tuple of (start_date, end_date) inclusive

    Raises:
        ValueError: If period format is invalid or values are out of range

    Examples:
        >>> parse_period('2024')
        (date(2024, 1, 1), date(2024, 12, 31))

        >>> parse_period('2024-Q2')
        (date(2024, 4, 1), date(2024, 6, 30))

        >>> parse_period('2024-H1')
        (date(2024, 1, 1), date(2024, 6, 30))

        >>> parse_period('2024-03')
        (date(2024, 3, 1), date(2024, 3, 31))

        >>> parse_period('2024-W15')
        (date(2024, 4, 8), date(2024, 4, 14))
    """
    if not period or not isinstance(period, str):
        raise ValueError(f"Invalid period: {period!r}")

    period = period.strip()

    # Year: YYYY
    if re.match(r"^\d{4}$", period):
        year = int(period)
        return date(year, 1, 1), date(year, 12, 31)

    # Quarter: YYYY-QN
    match = re.match(r"^(\d{4})-Q([1-4])$", period)
    if match:
        year = int(match.group(1))
        quarter = int(match.group(2))
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2
        start_date = date(year, start_month, 1)
        end_date = date(year, end_month, monthrange(year, end_month)[1])
        return start_date, end_date

    # Half year: YYYY-HN
    match = re.match(r"^(\d{4})-H([1-2])$", period)
    if match:
        year = int(match.group(1))
        half = int(match.group(2))
        if half == 1:
            return date(year, 1, 1), date(year, 6, 30)
        else:  # half == 2
            return date(year, 7, 1), date(year, 12, 31)

    # Month: YYYY-MM
    match = re.match(r"^(\d{4})-(\d{2})$", period)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        if not (1 <= month <= 12):
            raise ValueError(f"Invalid month in period: {period}")
        start_date = date(year, month, 1)
        end_date = date(year, month, monthrange(year, month)[1])
        return start_date, end_date

    # ISO Week: YYYY-WNN
    match = re.match(r"^(\d{4})-W(\d{2})$", period)
    if match:
        year = int(match.group(1))
        week = int(match.group(2))
        if not (1 <= week <= 53):
            raise ValueError(f"Invalid week number in period: {period}")

        # ISO week date: find the Monday of the given week
        # ISO 8601: Week 1 is the week with the first Thursday of the year
        jan4 = date(year, 1, 4)  # Jan 4 is always in week 1
        week1_monday = jan4 - timedelta(days=jan4.weekday())
        start_date = week1_monday + timedelta(weeks=week - 1)
        end_date = start_date + timedelta(days=6)

        return start_date, end_date

    raise ValueError(f"Invalid period format: {period}. " f"Expected: YYYY, YYYY-QN, YYYY-HN, YYYY-MM, or YYYY-WNN")


# ══════════════════════════════════════════════════════════════════════════════
# DYNAMIC PERIOD GENERATORS
# ══════════════════════════════════════════════════════════════════════════════


def this_year(base_date: date | None = None) -> str:
    """Get current year as period string.

    Args:
        base_date: Reference date (defaults to today)

    Returns:
        Year string (e.g., '2024')

    Examples:
        >>> this_year(date(2024, 6, 15))
        '2024'
    """
    if base_date is None:
        base_date = date.today()
    return str(base_date.year)


def last_year(base_date: date | None = None) -> str:
    """Get previous year as period string.

    Args:
        base_date: Reference date (defaults to today)

    Returns:
        Year string (e.g., '2023')

    Examples:
        >>> last_year(date(2024, 6, 15))
        '2023'
    """
    if base_date is None:
        base_date = date.today()
    return str(base_date.year - 1)


def this_quarter(base_date: date | None = None) -> str:
    """Get current quarter as period string.

    Args:
        base_date: Reference date (defaults to today)

    Returns:
        Quarter string (e.g., '2024-Q2')

    Examples:
        >>> this_quarter(date(2024, 6, 15))
        '2024-Q2'
    """
    if base_date is None:
        base_date = date.today()
    quarter = (base_date.month - 1) // 3 + 1
    return f"{base_date.year}-Q{quarter}"


def last_quarter(base_date: date | None = None) -> str:
    """Get previous quarter as period string.

    Args:
        base_date: Reference date (defaults to today)

    Returns:
        Quarter string (e.g., '2024-Q1')

    Examples:
        >>> last_quarter(date(2024, 4, 15))
        '2024-Q1'
    """
    if base_date is None:
        base_date = date.today()

    current_quarter = (base_date.month - 1) // 3 + 1
    if current_quarter == 1:
        # Previous quarter is Q4 of last year
        return f"{base_date.year - 1}-Q4"
    else:
        return f"{base_date.year}-Q{current_quarter - 1}"


def this_month(base_date: date | None = None) -> str:
    """Get current month as period string.

    Args:
        base_date: Reference date (defaults to today)

    Returns:
        Month string (e.g., '2024-06')

    Examples:
        >>> this_month(date(2024, 6, 15))
        '2024-06'
    """
    if base_date is None:
        base_date = date.today()
    return f"{base_date.year}-{base_date.month:02d}"


def last_month(base_date: date | None = None) -> str:
    """Get previous month as period string.

    Args:
        base_date: Reference date (defaults to today)

    Returns:
        Month string (e.g., '2024-05')

    Examples:
        >>> last_month(date(2024, 6, 15))
        '2024-05'
    """
    if base_date is None:
        base_date = date.today()

    if base_date.month == 1:
        # Previous month is December of last year
        return f"{base_date.year - 1}-12"
    else:
        return f"{base_date.year}-{base_date.month - 1:02d}"


def quarters_ago(n: int, base_date: date | None = None) -> str:
    """Get quarter N quarters ago as period string.

    Args:
        n: Number of quarters to go back
        base_date: Reference date (defaults to today)

    Returns:
        Quarter string (e.g., '2023-Q4')

    Examples:
        >>> quarters_ago(2, date(2024, 6, 15))
        '2023-Q4'
    """
    if base_date is None:
        base_date = date.today()

    current_quarter = (base_date.month - 1) // 3 + 1
    target_quarter = current_quarter - n

    year = base_date.year
    while target_quarter <= 0:
        target_quarter += 4
        year -= 1

    return f"{year}-Q{target_quarter}"


def months_ago(n: int, base_date: date | None = None) -> str:
    """Get month N months ago as period string.

    Args:
        n: Number of months to go back
        base_date: Reference date (defaults to today)

    Returns:
        Month string (e.g., '2024-04')

    Examples:
        >>> months_ago(2, date(2024, 6, 15))
        '2024-04'
    """
    if base_date is None:
        base_date = date.today()

    target_month = base_date.month - n
    year = base_date.year

    while target_month <= 0:
        target_month += 12
        year -= 1

    return f"{year}-{target_month:02d}"


def year_start(base_date: date | None = None) -> date:
    """Get start date of current year.

    Args:
        base_date: Reference date (defaults to today)

    Returns:
        First day of the year

    Examples:
        >>> year_start(date(2024, 6, 15))
        date(2024, 1, 1)
    """
    if base_date is None:
        base_date = date.today()
    return date(base_date.year, 1, 1)


def quarter_start(base_date: date | None = None) -> date:
    """Get start date of current quarter.

    Args:
        base_date: Reference date (defaults to today)

    Returns:
        First day of the quarter

    Examples:
        >>> quarter_start(date(2024, 6, 15))
        date(2024, 4, 1)
    """
    if base_date is None:
        base_date = date.today()

    quarter = (base_date.month - 1) // 3 + 1
    start_month = (quarter - 1) * 3 + 1
    return date(base_date.year, start_month, 1)


def month_start(base_date: date | None = None) -> date:
    """Get start date of current month.

    Args:
        base_date: Reference date (defaults to today)

    Returns:
        First day of the month

    Examples:
        >>> month_start(date(2024, 6, 15))
        date(2024, 6, 1)
    """
    if base_date is None:
        base_date = date.today()
    return date(base_date.year, base_date.month, 1)


# ══════════════════════════════════════════════════════════════════════════════
# SELECTION MODE RESOLVERS
# ══════════════════════════════════════════════════════════════════════════════


def get_default_select_mode(env: Any, event_type_code: str) -> str:
    """Determine default selection mode for event type.

    Returns 'active' if event type has is_one_active_per_registrant=True,
    otherwise returns 'latest'.

    Args:
        env: Odoo environment
        event_type_code: Event type code to look up

    Returns:
        Selection mode: 'active' or 'latest'

    Examples:
        In CEL context with env available:
        >>> get_default_select_mode(env, 'household_survey')
        'active'
    """
    try:
        event_type = env["spp.event.type"].search([("code", "=", event_type_code)], limit=1)
        if event_type and event_type.is_one_active_per_registrant:
            return "active"
    except Exception as e:
        _logger.warning(f"Failed to determine select mode for event type {event_type_code!r}: {e}")

    return "latest"


def get_states_for_select_mode(select: str) -> list[str]:
    """Get default states list for a selection mode.

    Selection mode behaviors:
        - 'active': Only active events -> ['active']
        - 'latest': Most recent event regardless of state -> ['active', 'superseded', 'expired']
        - 'latest_active': Most recent active event -> ['active']
        - 'first': Oldest event regardless of state -> ['active', 'superseded', 'expired']
        - 'any': Any matching event -> ['active']

    Args:
        select: Selection mode string

    Returns:
        List of state strings to include

    Examples:
        >>> get_states_for_select_mode('active')
        ['active']

        >>> get_states_for_select_mode('latest')
        ['active', 'superseded', 'expired']

        >>> get_states_for_select_mode('latest_active')
        ['active']
    """
    if select in ("active", "latest_active", "any"):
        return ["active"]
    elif select in ("latest", "first"):
        # Include historical states for latest/first selection
        return ["active", "superseded", "expired"]
    else:
        # Default to active only for unknown modes
        _logger.warning(f"Unknown select mode: {select!r}, defaulting to ['active']")
        return ["active"]


# ══════════════════════════════════════════════════════════════════════════════
# TEMPORAL FILTER HELPERS
# ══════════════════════════════════════════════════════════════════════════════


def apply_temporal_filters(
    base_date: date | None = None,
    after: date | str | None = None,
    before: date | str | None = None,
    within_days: int | None = None,
    within_months: int | None = None,
    period: str | None = None,
) -> tuple[date | None, date | None]:
    """Resolve temporal filters to (start_date, end_date).

    Combines all filter types, returning the intersection (most restrictive range).
    All filters are optional. If no filters provided, returns (None, None).

    Filter types:
        - after: Events on or after this date
        - before: Events on or before this date
        - within_days: Events within last N days from base_date
        - within_months: Events within last N months from base_date
        - period: Named period (e.g., '2024', '2024-Q1', '2024-03')

    Args:
        base_date: Reference date for relative filters (defaults to today)
        after: Start date (date object or period string)
        before: End date (date object or period string)
        within_days: Number of days back from base_date
        within_months: Number of months back from base_date
        period: Period string to parse

    Returns:
        Tuple of (start_date, end_date) or (None, None) if no filters

    Raises:
        ValueError: If period string is invalid

    Examples:
        >>> apply_temporal_filters(within_days=30)
        (date(2024, 11, 3), date(2024, 12, 3))

        >>> apply_temporal_filters(period='2024-Q1')
        (date(2024, 1, 1), date(2024, 3, 31))

        >>> apply_temporal_filters(after=date(2024, 1, 1), before=date(2024, 6, 30))
        (date(2024, 1, 1), date(2024, 6, 30))

        >>> apply_temporal_filters(period='2024', after=date(2024, 6, 1))
        (date(2024, 6, 1), date(2024, 12, 31))
    """
    if base_date is None:
        base_date = date.today()

    start_date = None
    end_date = None

    # Parse 'after' filter
    if after is not None:
        if isinstance(after, str):
            # Parse as period and take start date
            period_start, _ = parse_period(after)
            after = period_start
        if start_date is None or after > start_date:
            start_date = after

    # Parse 'before' filter
    if before is not None:
        if isinstance(before, str):
            # Parse as period and take end date
            _, period_end = parse_period(before)
            before = period_end
        if end_date is None or before < end_date:
            end_date = before

    # Apply within_days filter
    if within_days is not None:
        days_start = base_date - timedelta(days=within_days)
        if start_date is None or days_start > start_date:
            start_date = days_start
        if end_date is None or base_date < end_date:
            end_date = base_date

    # Apply within_months filter
    if within_months is not None:
        # Calculate months back
        target_month = base_date.month - within_months
        year = base_date.year
        while target_month <= 0:
            target_month += 12
            year -= 1

        # Use same day of month, or last day if not valid
        day = min(base_date.day, monthrange(year, target_month)[1])
        months_start = date(year, target_month, day)

        if start_date is None or months_start > start_date:
            start_date = months_start
        if end_date is None or base_date < end_date:
            end_date = base_date

    # Apply period filter
    if period is not None:
        period_start, period_end = parse_period(period)
        if start_date is None or period_start > start_date:
            start_date = period_start
        if end_date is None or period_end < end_date:
            end_date = period_end

    return start_date, end_date


def validate_temporal_range(start_date: date | None, end_date: date | None) -> tuple[date | None, date | None]:
    """Validate and normalize a temporal range.

    Ensures start_date <= end_date. Returns (None, None) if range is invalid.

    Args:
        start_date: Range start date
        end_date: Range end date

    Returns:
        Validated (start_date, end_date) or (None, None) if invalid

    Examples:
        >>> validate_temporal_range(date(2024, 1, 1), date(2024, 12, 31))
        (date(2024, 1, 1), date(2024, 12, 31))

        >>> validate_temporal_range(date(2024, 12, 31), date(2024, 1, 1))
        (None, None)
    """
    if start_date is not None and end_date is not None:
        if start_date > end_date:
            _logger.warning(f"Invalid temporal range: start_date {start_date} > end_date {end_date}")
            return None, None

    return start_date, end_date


# ══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════


def days_between(start: date, end: date) -> int:
    """Calculate number of days between two dates.

    Args:
        start: Start date
        end: End date

    Returns:
        Number of days (can be negative if end < start)

    Examples:
        >>> days_between(date(2024, 1, 1), date(2024, 1, 31))
        30
    """
    return (end - start).days


def is_within_range(check_date: date, start: date | None = None, end: date | None = None) -> bool:
    """Check if a date falls within a range.

    Args:
        check_date: Date to check
        start: Range start (None means no lower bound)
        end: Range end (None means no upper bound)

    Returns:
        True if date is within range

    Examples:
        >>> is_within_range(date(2024, 6, 15), date(2024, 1, 1), date(2024, 12, 31))
        True

        >>> is_within_range(date(2024, 6, 15), start=date(2024, 1, 1))
        True

        >>> is_within_range(date(2024, 6, 15), end=date(2024, 5, 31))
        False
    """
    if start is not None and check_date < start:
        return False
    if end is not None and check_date > end:
        return False
    return True
