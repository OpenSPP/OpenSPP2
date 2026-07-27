# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Migrate legacy boolean disaggregation flags to dimension_ids.

Replaces the post_init_hook version, which only ran on fresh installs (where
there is nothing to migrate) and hardcoded the m2m relation table name. As a
post-migration script this runs on upgrade, and the relation/column names are
derived from the field so they cannot drift from Odoo's canonical naming.
"""

import logging

from psycopg2 import sql

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Mapping: old boolean field name -> dimension technical name
_BOOL_TO_DIMENSION = {
    "disaggregate_by_gender": "gender",
    "disaggregate_by_age": "age_group",
    "disaggregate_by_disability": "disability_status",
}


def migrate(cr, version):
    """Link reports that had legacy boolean flags set to the matching dimensions.

    ``version`` is the previously-installed module version, or a falsy value on
    a fresh install (nothing to migrate). Logs a warning (does not crash) if a
    dimension record is not found.
    """
    if not version:
        # Fresh install: the legacy boolean columns never existed.
        return

    # Only columns that still physically exist in the table can be read. After
    # removing the boolean fields, Odoo leaves the obsolete columns in place, so
    # they are still readable here on the first upgrade.
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'spp_gis_report'
          AND column_name IN ('disaggregate_by_gender', 'disaggregate_by_age', 'disaggregate_by_disability')
        """
    )
    existing_columns = {row[0] for row in cr.fetchall()}
    if not existing_columns:
        _logger.info("No legacy boolean disaggregation columns found, skipping migration")
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    Dimension = env["spp.demographic.dimension"]

    # Derive the m2m relation/column names from the field so this migration
    # cannot drift from Odoo's canonical (alphabetically sorted) table naming.
    m2m = env["spp.gis.report"]._fields["dimension_ids"]
    insert_stmt = sql.SQL("INSERT INTO {rel} ({col_report}, {col_dim}) VALUES (%s, %s) ON CONFLICT DO NOTHING").format(
        rel=sql.Identifier(m2m.relation),
        col_report=sql.Identifier(m2m.column1),
        col_dim=sql.Identifier(m2m.column2),
    )

    for bool_field, dim_name in _BOOL_TO_DIMENSION.items():
        if bool_field not in existing_columns:
            continue

        # bool_field is a trusted column name from _BOOL_TO_DIMENSION; quote it
        # safely via psycopg2.sql.
        query = sql.SQL("SELECT id FROM spp_gis_report WHERE {col} = true").format(col=sql.Identifier(bool_field))
        cr.execute(query)
        report_ids = [row[0] for row in cr.fetchall()]
        if not report_ids:
            continue

        dimension = Dimension.search([("name", "=", dim_name)], limit=1)
        if not dimension:
            _logger.warning(
                "Dimension '%s' not found, cannot migrate %d reports with %s=True",
                dim_name,
                len(report_ids),
                bool_field,
            )
            continue

        for report_id in report_ids:
            cr.execute(insert_stmt, (report_id, dimension.id))

        _logger.info(
            "Migrated %d reports from %s=True to dimension '%s'",
            len(report_ids),
            bool_field,
            dim_name,
        )
