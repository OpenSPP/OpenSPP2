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

# Literal, fully parameterized SQL per target table (no identifier
# composition, so SQL scanners can verify there is no injection surface).
_BACKFILL_INCIDENT = """
    UPDATE spp_hazard_incident t
    SET severity_id = c.id
    FROM spp_vocabulary_code c
    JOIN spp_vocabulary v ON c.vocabulary_id = v.id
    WHERE v.namespace_uri = %s
      AND c.code = CASE t.severity
            WHEN %s THEN %s WHEN %s THEN %s WHEN %s THEN %s
            WHEN %s THEN %s WHEN %s THEN %s END
      AND t.severity IS NOT NULL
      AND t.severity_id IS NULL
"""

_UNMAPPED_INCIDENT = """
    SELECT DISTINCT t.severity
    FROM spp_hazard_incident t
    WHERE t.severity IS NOT NULL
      AND t.severity_id IS NULL
"""

_BACKFILL_AREA = """
    UPDATE spp_hazard_incident_area t
    SET severity_override_id = c.id
    FROM spp_vocabulary_code c
    JOIN spp_vocabulary v ON c.vocabulary_id = v.id
    WHERE v.namespace_uri = %s
      AND c.code = CASE t.severity_override
            WHEN %s THEN %s WHEN %s THEN %s WHEN %s THEN %s
            WHEN %s THEN %s WHEN %s THEN %s END
      AND t.severity_override IS NOT NULL
      AND t.severity_override_id IS NULL
"""

_UNMAPPED_AREA = """
    SELECT DISTINCT t.severity_override
    FROM spp_hazard_incident_area t
    WHERE t.severity_override IS NOT NULL
      AND t.severity_override_id IS NULL
"""

# (table, legacy column, new column, backfill query, unmapped query)
TARGETS = [
    ("spp_hazard_incident", "severity", "severity_id", _BACKFILL_INCIDENT, _UNMAPPED_INCIDENT),
    (
        "spp_hazard_incident_area",
        "severity_override",
        "severity_override_id",
        _BACKFILL_AREA,
        _UNMAPPED_AREA,
    ),
]


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
          AND table_schema = current_schema()
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    case_params = [p for pair in LEGACY_SEVERITY_TO_CAP.items() for p in pair]
    for table, legacy_col, new_col, backfill_query, unmapped_query in TARGETS:
        if not _column_exists(cr, table, legacy_col):
            _logger.info("spp_hazard severity migration: %s.%s absent, skipping", table, legacy_col)
            continue

        cr.execute(backfill_query, [CAP_SEVERITY_NS, *case_params])
        _logger.info(
            "spp_hazard severity migration: backfilled %s rows in %s.%s",
            cr.rowcount,
            table,
            new_col,
        )

        cr.execute(unmapped_query)
        unmapped = [row[0] for row in cr.fetchall()]
        if unmapped:
            _logger.warning(
                "spp_hazard severity migration: %s.%s has unmapped legacy values %s; left empty for manual review",
                table,
                legacy_col,
                unmapped,
            )
