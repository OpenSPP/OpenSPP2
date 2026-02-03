# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pagination utilities for consent-filtered search results."""

import logging

_logger = logging.getLogger(__name__)


def fetch_with_consent(
    search_function,
    consent_filter_function,
    count,
    offset,
):
    """
    Fetch records with consent filtering, over-fetching to fill pages.

    When consent filtering removes records from a page, this function
    fetches additional records to fill the requested page size. This
    prevents clients from seeing short pages due to consent denials.

    To prevent leaking the count of denied records, the total is
    suppressed when any consent filtering occurs.

    Args:
        search_function: callable(offset, limit) -> (records, total)
            Returns a list of records and the total unfiltered count.
        consent_filter_function: callable(record) -> filtered_data or None
            Returns the filtered data dict, or None if consent was denied.
        count: Number of consented records to collect.
        offset: Starting offset in the database.

    Returns:
        tuple of (collected_records, database_offset_consumed, raw_total, consent_was_applied)
    """
    collected = []
    current_offset = offset
    raw_total = 0
    consent_was_applied = False
    # Safety limit: don't fetch more than 3x the requested count to avoid runaway queries
    max_overfetch = count * 3
    fetched_so_far = 0

    while len(collected) < count and fetched_so_far < max_overfetch:
        batch_size = min(count * 2, max_overfetch - fetched_so_far)
        records, raw_total = search_function(offset=current_offset, limit=batch_size)
        if not records:
            break
        for record in records:
            filtered = consent_filter_function(record)
            if filtered is not None:
                collected.append(filtered)
                if len(collected) >= count:
                    break
            else:
                consent_was_applied = True
        fetched_so_far += len(records)
        current_offset += len(records)
        if len(records) < batch_size:
            break  # No more records in DB

    return collected[:count], current_offset, raw_total, consent_was_applied
