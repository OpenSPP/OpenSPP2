# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Backfill the disability variable typo.

Earlier seed data referenced a non-existent `res.partner.is_person_with_disability`
field. The actual field added by `spp_disability_registry` is `has_disability`.
This migration rewrites already-loaded records so users who upgrade do not have
to manually fix or re-seed the variables.

Touches two records, both in `spp_studio/data/standard_variables.xml`:
- `var_has_disability` — `source_field`
- `var_has_disabled_member` — `cel_expression`
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        UPDATE spp_cel_variable
           SET source_field = 'has_disability'
         WHERE cel_accessor = 'has_disability'
           AND source_field = 'is_person_with_disability'
        """
    )
    if cr.rowcount:
        _logger.info("Fixed has_disability.source_field on %s record(s)", cr.rowcount)

    cr.execute(
        """
        UPDATE spp_cel_variable
           SET cel_expression = 'members.exists(m.has_disability)'
         WHERE cel_accessor = 'has_disabled_member'
           AND cel_expression = 'members.exists(m.is_person_with_disability)'
        """
    )
    if cr.rowcount:
        _logger.info("Fixed has_disabled_member.cel_expression on %s record(s)", cr.rowcount)
