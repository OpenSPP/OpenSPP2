# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Backfill the disabled_count aggregate filter typo.

Earlier seed data for `var_disabled_count` referenced a non-existent
`res.partner.is_person_with_disability` field. The actual field added by
`spp_disability_registry` is `has_disability`. This migration rewrites the
already-loaded record so users who upgrade do not have to manually re-seed.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        UPDATE spp_cel_variable
           SET aggregate_filter = 'm.has_disability'
         WHERE cel_accessor = 'disabled_count'
           AND aggregate_filter = 'm.is_person_with_disability'
        """
    )
    if cr.rowcount:
        _logger.info("Fixed disabled_count.aggregate_filter on %s record(s)", cr.rowcount)
