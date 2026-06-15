# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Replace placeholder `name = "Default"` on default-manager records with
their method-specific labels — see #941 round 2 / item 3.

Existing programs upgraded from a prior version still carry rows whose
`name` literally reads "Default" (the value used by
`SPPProgram.create_default_managers` before the cleanup). New rows are
fine because each concrete model now seeds its own meaningful name via
`default_get`. This migration backfills the historical rows so the Edit
form shows e.g. "CEL Eligibility Criteria" instead of "Default".
"""

import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)


# (table_name, label) pairs. Tables are derived from the concrete-manager
# `_name` (dots replaced by underscores).
_DEFAULT_NAME_RENAMES = (
    ("spp_program_membership_manager_default", "CEL Eligibility Criteria"),
    ("spp_program_entitlement_manager_default", "Basic Cash"),
    ("spp_program_entitlement_manager_cash", "Cash Entitlement"),
    ("spp_program_entitlement_manager_inkind", "In-kind Entitlement"),
    ("spp_cycle_manager_default", "Default Cycle Schedule"),
    ("spp_compliance_manager_default", "CEL Compliance Criteria"),
    ("spp_program_payment_manager_default", "Default Payment"),
    ("spp_program_manager_default", "Default Program Manager"),
    ("spp_deduplication_manager_default", "Default Deduplication"),
)


def migrate(cr, version):
    if not version:
        return
    for table, label in _DEFAULT_NAME_RENAMES:
        # Skip tables that don't exist (modules not installed in this DB).
        cr.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
            (table,),
        )
        if not cr.fetchone():
            continue
        cr.execute(
            sql.SQL("UPDATE {tbl} SET name = %s WHERE name = 'Default'").format(
                tbl=sql.Identifier(table),
            ),
            (label,),
        )
        if cr.rowcount:
            _logger.info(
                "Renamed %d %s rows from 'Default' to %r",
                cr.rowcount,
                table,
                label,
            )
