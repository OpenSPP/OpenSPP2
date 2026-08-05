# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Deduplicate spp.cr.type.reason.document before the unique constraint applies.

The (cr_type_id, reason) uniqueness rule was declared with the legacy
``_sql_constraints`` attribute, which Odoo 19 ignores — the constraint was
never created in the database, so duplicate rules could be saved (#394).
19.0.3.1.1 re-declares it as ``models.Constraint``; if duplicates exist when
the upgrade tries to ADD CONSTRAINT, Odoo downgrades the failure to a schema
warning and the constraint stays missing. Deduplicate first: keep the
lowest-id rule per (cr_type_id, reason) — matching the runtime behaviour of
``_get_effective_required_document_ids()``, which only ever used the first
matching rule — and log what is removed.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Upgrades from versions predating the model (< 19.0.3.0.0) run this
    # script before the ORM creates the table.
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'spp_cr_type_reason_document'
        """
    )
    if not cr.fetchone():
        return

    cr.execute(
        """
        SELECT dup.id, dup.cr_type_id, dup.reason
        FROM spp_cr_type_reason_document dup
        JOIN spp_cr_type_reason_document kept
          ON kept.cr_type_id = dup.cr_type_id
         AND kept.reason = dup.reason
         AND kept.id < dup.id
        """
    )
    duplicates = cr.fetchall()
    if not duplicates:
        return

    for dup_id, cr_type_id, reason in duplicates:
        _logger.warning(
            "Removing duplicate reason-document rule id=%s (cr_type_id=%s, reason=%s); the lowest-id rule is kept.",
            dup_id,
            cr_type_id,
            reason,
        )

    cr.execute(
        """
        DELETE FROM spp_cr_type_reason_document dup
        USING spp_cr_type_reason_document kept
        WHERE kept.cr_type_id = dup.cr_type_id
          AND kept.reason = dup.reason
          AND kept.id < dup.id
        """
    )
