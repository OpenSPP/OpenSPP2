# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pagination utilities for consent-filtered search results."""

import logging

_logger = logging.getLogger(__name__)

# The search services return at most this many rows per query, so a batch
# must not ask for more: a short batch is read as the end of the data
MAX_ROWS_PER_QUERY = 100

# Largest _offset PostgreSQL accepts (bigint); larger values are rejected as
# request validation errors instead of reaching the database
MAX_OFFSET = 2**63 - 1


def page_total_and_next(returned, count, offset, db_offset_consumed, raw_total, consent_filtered):
    """
    Return the (total, next_offset) to publish for a search page.

    For a client subject to consent filtering the total is the number of
    records returned, whether or not this page met a hidden record: the raw
    total counts records the client may not see, and a page past the end
    would otherwise reveal whether a hidden match exists. The next page
    starts after the last row examined and is given while rows remain, even
    when the page came back short.

    next_offset is None on the last page.
    """
    if consent_filtered:
        next_offset = db_offset_consumed if db_offset_consumed < raw_total else None
        return returned, next_offset
    next_offset = offset + count if returned >= count else None
    return raw_total, next_offset


def fetch_with_consent(
    search_function,
    consent_filter_function,
    count,
    offset,
):
    """
    Fetch records with consent filtering, over-fetching to fill pages.

    When consent filtering removes records from a page, this function
    fetches additional records to fill the requested page size, up to a
    safety limit of 3x the page size. A page can therefore still come back
    short, or empty, while rows remain: clients follow `next` until it is
    null (see page_total_and_next for the total and next offset to publish).

    Args:
        search_function: callable(offset, limit) -> (records, total)
            Returns a list of records and the total unfiltered count.
        consent_filter_function: callable(record) -> filtered_data or None
            Returns the filtered data dict, or None if consent was denied.
        count: Number of consented records to collect.
        offset: Starting offset in the database.

    Returns:
        tuple of (collected_records, database_offset_consumed, raw_total, consent_was_applied)

        database_offset_consumed is the offset just after the last row
        examined, so the next page starts at the first row not yet seen.
    """
    collected = []
    current_offset = offset
    raw_total = 0
    consent_was_applied = False
    # Safety limit: don't fetch more than 3x the requested count to avoid runaway queries
    max_overfetch = count * 3
    fetched_so_far = 0

    while len(collected) < count and fetched_so_far < max_overfetch:
        batch_size = min(count * 2, max_overfetch - fetched_so_far, MAX_ROWS_PER_QUERY)
        records, raw_total = search_function(offset=current_offset, limit=batch_size)
        if not records:
            break
        examined = 0
        for record in records:
            examined += 1
            filtered = consent_filter_function(record)
            if filtered is not None:
                collected.append(filtered)
                if len(collected) >= count:
                    break
            else:
                consent_was_applied = True
        # Rows after the one that filled the page were not examined: the next
        # page must start at them, not skip them
        fetched_so_far += examined
        current_offset += examined
        if len(records) < batch_size:
            break  # No more records in DB

    return collected[:count], current_offset, raw_total, consent_was_applied
