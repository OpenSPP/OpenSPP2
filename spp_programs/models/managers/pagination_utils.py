# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Keyset pagination utilities for async job dispatch.

OFFSET-based pagination causes PostgreSQL to scan and discard N rows for
OFFSET N, making later batches progressively slower (O(N) per batch).

This module provides ID-range batching using the NTILE window function,
which pre-computes (min_id, max_id) boundaries in a single query. Each
job then uses WHERE id BETWEEN min_id AND max_id, which is O(1) via the
primary key index regardless of batch position.
"""

import math


def compute_id_ranges(cr, table, where_clause, params, batch_size):
    """Compute ID-range boundaries for parallel job dispatch.

    Uses PostgreSQL's NTILE window function to split matching rows into
    roughly equal-sized buckets, then returns the (min_id, max_id) of each.

    :param cr: Database cursor
    :param table: Table name (e.g. 'spp_program_membership')
    :param where_clause: SQL WHERE clause without 'WHERE' keyword
        (e.g. 'program_id = %s AND state IN %s')
    :param params: Tuple of parameters for the WHERE clause
    :param batch_size: Target number of rows per batch
    :return: List of (min_id, max_id) tuples, ordered by min_id
    """
    # Get total count to calculate number of batches
    cr.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {where_clause}",  # noqa: S608  # nosec B608
        params,
    )
    total = cr.fetchone()[0]
    if total == 0:
        return []

    num_batches = math.ceil(total / batch_size)
    if num_batches <= 1:
        cr.execute(
            f"SELECT MIN(id), MAX(id) FROM {table} WHERE {where_clause}",  # noqa: S608  # nosec B608
            params,
        )
        row = cr.fetchone()
        return [(row[0], row[1])]

    # Use NTILE to split rows into equal-sized buckets, then get
    # the min/max ID of each bucket as the range boundaries.
    cr.execute(
        f"""
        SELECT MIN(id) AS min_id, MAX(id) AS max_id
        FROM (
            SELECT id, NTILE(%s) OVER (ORDER BY id) AS tile
            FROM {table}
            WHERE {where_clause}
        ) sub
        GROUP BY tile
        ORDER BY min_id
        """,  # noqa: S608  # nosec B608
        (num_batches, *params),
    )
    return cr.fetchall()
