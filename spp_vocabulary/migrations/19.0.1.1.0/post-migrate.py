# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Migration script for OpenSPP Vocabulary 19.0.1.1.0
ADR-016 Phase 1: Populate URIs for existing vocabulary codes
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Populate URI field for existing vocabulary codes.

    ADR-016: Each code needs a globally unique URI in format:
    {vocabulary.namespace_uri}#{code}

    This migration:
    1. Populates URI for all existing codes that don't have one
    2. Uses the computed format: namespace_uri + '#' + code
    3. Handles any potential conflicts by logging warnings
    """
    _logger.info("Starting ADR-016 Phase 1 migration: Populating code URIs")

    # Update all codes that don't have a URI yet
    # Using SQL for performance with large datasets
    cr.execute("""
        UPDATE spp_vocabulary_code c
        SET uri = v.namespace_uri || '#' || c.code
        FROM spp_vocabulary v
        WHERE c.vocabulary_id = v.id
          AND (c.uri IS NULL OR c.uri = '')
    """)

    rows_updated = cr.rowcount
    _logger.info(f"ADR-016 migration: Populated URIs for {rows_updated} vocabulary codes")

    # Check for any potential URI conflicts (shouldn't happen with proper namespace design)
    cr.execute("""
        SELECT uri, COUNT(*) as count
        FROM spp_vocabulary_code
        WHERE uri IS NOT NULL
        GROUP BY uri
        HAVING COUNT(*) > 1
    """)

    conflicts = cr.fetchall()
    if conflicts:
        _logger.warning(
            f"ADR-016 migration: Found {len(conflicts)} URI conflicts. "
            "This may indicate overlapping namespaces. Conflicts: %s",
            conflicts[:10],  # Log first 10 conflicts
        )
    else:
        _logger.info("ADR-016 migration: No URI conflicts detected")

    _logger.info("ADR-016 Phase 1 migration completed successfully")
