# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Add source tracking to existing registrants.

    This migration sets default source tracking values for existing
    registrants that were created before the source tracking module
    was installed.
    """
    _logger.info("Starting source tracking migration for existing registrants...")

    # Update existing registrants with migration source tracking
    cr.execute(
        """
        UPDATE res_partner
        SET source_system = 'v1-migration',
            collection_method = 'migration',
            collection_date = create_date
        WHERE source_system IS NULL
          AND is_registrant = TRUE
    """
    )
    registrant_count = cr.rowcount
    _logger.info(
        "Updated %s existing registrants with migration source tracking",
        registrant_count,
    )

    # Update existing registry IDs
    cr.execute(
        """
        UPDATE spp_registry_id
        SET source_system = 'v1-migration',
            collection_method = 'migration',
            collection_date = create_date
        WHERE source_system IS NULL
    """
    )
    reg_id_count = cr.rowcount
    _logger.info("Updated %s existing registry IDs with migration source tracking", reg_id_count)

    # Update existing program memberships — only when the programs stack is
    # installed (the source-tracking extension now lives in
    # spp_source_tracking_programs; the table may be absent otherwise).
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'spp_program_membership'"
    )
    if cr.fetchone():
        cr.execute(
            """
            UPDATE spp_program_membership
            SET source_system = 'v1-migration',
                collection_method = 'migration',
                collection_date = create_date
            WHERE source_system IS NULL
        """
        )
        membership_count = cr.rowcount
        _logger.info(
            "Updated %s existing program memberships with migration source tracking",
            membership_count,
        )

    _logger.info("Source tracking migration completed successfully")
