# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pure parsing helpers for DCI v1.0.0 Disability Registry records.

All functions are stateless and require no Odoo env, making them
independently testable and easy to reuse.
"""

import logging
from datetime import date, datetime

_logger = logging.getLogger(__name__)

# Status values that indicate the person is registered as disabled.
# The SP DCI v1.0.0 spec does not declare an enum; these are the
# spec-aligned workflow tokens. Empty / missing / other values trigger
# the impairment-list fallback in extract_disability_data.
_APPROVED_STATUSES = {"approved", "registered"}

# Status values that explicitly reject disability registration.
_REJECTED_STATUSES = {"rejected", "denied"}


def _coerce_date(value) -> date | None:
    """Coerce a DCI date/datetime value into a ``date`` object.

    Accepts ISO date strings (``YYYY-MM-DD``), ISO datetime strings with an
    optional trailing ``Z`` (``YYYY-MM-DDTHH:MM:SSZ``), naive/aware datetimes,
    and date objects. Returns ``None`` for empty input or unparseable values
    (with a WARNING logged).

    For tz-aware inputs, the local wall-clock date is returned;
    no UTC normalization is applied.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).removesuffix("Z")).date()
    except ValueError:
        _logger.warning("Could not parse date from value: %r", value)
        return None


def unwrap_search_data(data) -> list:
    """Extract the reg_records list from a DCI v1.0.0 search response data envelope.

    Args:
        data: The value of ``search_response[*].data`` from the API response.
              Expected to be a dict with a ``reg_records`` key per the spec.

    Returns:
        list: The contents of ``data["reg_records"]``, or an empty list when
              the envelope is absent, empty, or malformed.
    """
    if data is None:
        return []

    if not isinstance(data, dict):
        _logger.warning(
            "Unexpected type for search response data envelope: %s; expected dict",
            type(data).__name__,
        )
        return []

    if not data:
        return []

    records = data.get("reg_records")
    if records is None:
        return []
    if not isinstance(records, list):
        _logger.warning(
            "Unexpected type for reg_records: %s; expected list",
            type(records).__name__,
        )
        return []
    return records


def extract_disability_data(record: dict) -> dict:
    """Extract structured disability information from a DCI v1.0.0 record.

    Args:
        record: A single record dict from ``reg_records``.

    Returns:
        dict with keys:
            - ``has_disability`` (bool)
            - ``disability_types`` (list[str])
            - ``functional_scores`` (dict, always ``{}``: spec has no numeric scores)
            - ``assessment_date`` (``date`` | None)
            - ``source_registry`` (str | None)
            - ``raw_data`` (the input record, unchanged)
    """
    # Extract impairment types from disability_details.
    # Use `or []` so an explicit null on the wire does not crash the loop.
    details = record.get("disability_details") or []
    disability_types = [d["impairment_type"] for d in details if isinstance(d, dict) and d.get("impairment_type")]

    # Resolve has_disability from the disability_status string
    status_str = str(record.get("disability_status", "")).strip().lower()

    if status_str in _APPROVED_STATUSES:
        has_disability = True
    elif status_str in _REJECTED_STATUSES:
        has_disability = False
    elif status_str == "":
        # No explicit status: fall back to impairment list presence
        has_disability = bool(disability_types)
    else:
        _logger.warning(
            "Unknown disability_status value: %s; falling back to impairment list",
            record.get("disability_status"),
        )
        has_disability = bool(disability_types)

    # Assessment date: prefer last_updated, fall back to registration_date.
    # The spec uses ISO datetime strings; coerce to a date for the ORM.
    assessment_date = _coerce_date(record.get("last_updated") or record.get("registration_date"))

    # Source registry: prefer source_registry, fall back to registry_name
    source_registry = record.get("source_registry") or record.get("registry_name")

    return {
        "has_disability": has_disability,
        "disability_types": disability_types,
        "functional_scores": {},
        "assessment_date": assessment_date,
        "source_registry": source_registry,
        "raw_data": record,
    }


def extract_functional_scores(record: dict) -> dict:
    """Return functional assessment scores from a DCI v1.0.0 record.

    The DCI v1.0.0 spec does not define numeric functional scores.
    ``impairment_level`` is a free-text string, not a number.
    This function always returns ``{}`` and exists as a hook for future
    spec versions that may introduce numeric scoring.

    Args:
        record: A single record dict from ``reg_records``.

    Returns:
        dict: Always ``{}``.
    """
    return {}
