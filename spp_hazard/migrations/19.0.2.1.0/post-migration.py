# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Backfill vocabulary-backed severity fields from the legacy 1-5 Selection columns.

Up to v19.0.2.0.x (including release v19.0.2.0.0 "Biliran"), severity was a
Selection stored as varchar '1'..'5'. The fields are now Many2one to
spp.vocabulary.code (CAP v1.2 severity). Odoo leaves the legacy columns in
place when the fields are removed, so this migration maps their values onto
the new columns:

    1 (Minor)        -> minor
    2 (Moderate)     -> moderate
    3 (Significant)  -> severe   (CAP: "Significant threat to life or property")
    4 (Severe)       -> severe
    5 (Catastrophic) -> extreme

Rows whose new column is already set are never overwritten. Legacy columns are
kept as a safety net. Fresh installs have no legacy columns and skip cleanly.
"""

import logging

from psycopg2 import sql

# Fixed name: this file is loaded by Odoo's migration runner (and by tests via
# importlib), where __name__ differs; a stable logger keeps output filterable.
_logger = logging.getLogger("odoo.addons.spp_hazard.migrations.severity")

CAP_SEVERITY_NS = "urn:oasis:names:tc:cap:severity"

LEGACY_SEVERITY_TO_CAP = {
    "1": "minor",
    "2": "moderate",
    "3": "severe",
    "4": "severe",
    "5": "extreme",
}

# (table, legacy column, new column)
TARGETS = [
    ("spp_hazard_incident", "severity", "severity_id"),
    ("spp_hazard_incident_area", "severity_override", "severity_override_id"),
]


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    for table, legacy_col, new_col in TARGETS:
        if not _column_exists(cr, table, legacy_col):
            _logger.info("spp_hazard severity migration: %s.%s absent, skipping", table, legacy_col)
            continue

        ids = {
            "table": sql.Identifier(table),
            "legacy": sql.Identifier(legacy_col),
            "new": sql.Identifier(new_col),
        }
        case_parts = sql.SQL(" ").join(sql.SQL("WHEN %s THEN %s") for _ in LEGACY_SEVERITY_TO_CAP)
        case_params = [p for pair in LEGACY_SEVERITY_TO_CAP.items() for p in pair]
        cr.execute(
            sql.SQL(
                """
                UPDATE {table} t
                SET {new} = c.id
                FROM spp_vocabulary_code c
                JOIN spp_vocabulary v ON c.vocabulary_id = v.id
                WHERE v.namespace_uri = %s
                  AND c.code = CASE t.{legacy} {case_parts} END
                  AND t.{legacy} IS NOT NULL
                  AND t.{new} IS NULL
                """
            ).format(case_parts=case_parts, **ids),
            [CAP_SEVERITY_NS, *case_params],
        )
        _logger.info(
            "spp_hazard severity migration: backfilled %s rows in %s.%s",
            cr.rowcount,
            table,
            new_col,
        )

        cr.execute(
            sql.SQL(
                """
                SELECT DISTINCT t.{legacy}
                FROM {table} t
                WHERE t.{legacy} IS NOT NULL
                  AND t.{new} IS NULL
                """
            ).format(**ids)
        )
        unmapped = [row[0] for row in cr.fetchall()]
        if unmapped:
            _logger.warning(
                "spp_hazard severity migration: %s.%s has unmapped legacy values %s; left empty for manual review",
                table,
                legacy_col,
                unmapped,
            )
