# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Migrate spp.statistic.category to spp.metric.category."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Migrate spp.statistic.category to spp.metric.category.

    Renames the table and sequence if they exist. This allows existing
    statistic categories to be used as metric categories without data loss.
    """
    _logger.info("Starting migration: spp.statistic.category -> spp.metric.category")

    # Check if old table exists
    cr.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'spp_statistic_category'
        )
    """
    )
    table_exists = cr.fetchone()[0]

    if table_exists:
        _logger.info("Found spp_statistic_category table, renaming to spp_metric_category")

        # Rename table
        cr.execute(
            """
            ALTER TABLE spp_statistic_category
            RENAME TO spp_metric_category
        """
        )

        # Check if old sequence exists
        cr.execute(
            """
            SELECT EXISTS (
                SELECT FROM pg_class
                WHERE relname = 'spp_statistic_category_id_seq'
                AND relkind = 'S'
            )
        """
        )
        seq_exists = cr.fetchone()[0]

        if seq_exists:
            _logger.info("Found spp_statistic_category_id_seq sequence, renaming to spp_metric_category_id_seq")

            # Rename sequence
            cr.execute(
                """
                ALTER SEQUENCE spp_statistic_category_id_seq
                RENAME TO spp_metric_category_id_seq
            """
            )

        _logger.info("Successfully migrated spp.statistic.category to spp.metric.category")
    else:
        _logger.info("No spp_statistic_category table found, skipping migration")
