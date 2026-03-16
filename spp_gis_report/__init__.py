import logging

from . import controllers
from . import models
from . import wizards

_logger = logging.getLogger(__name__)

# Mapping: old boolean field name -> dimension technical name
_BOOL_TO_DIMENSION = {
    "disaggregate_by_gender": "gender",
    "disaggregate_by_age": "age_group",
    "disaggregate_by_disability": "disability_status",
}


def _migrate_boolean_disaggregation(env):
    """Post-init hook: migrate boolean disaggregation flags to dimension_ids.

    Looks up reports that had boolean flags set and links them to the
    corresponding spp.demographic.dimension records. Logs a warning
    (does not crash) if a dimension record is not found.
    """
    cr = env.cr

    # Check if the old boolean columns still exist
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

    # Get the m2m relation table name
    Dimension = env["spp.demographic.dimension"]

    for bool_field, dim_name in _BOOL_TO_DIMENSION.items():
        if bool_field not in existing_columns:
            continue

        # Find reports with this boolean set
        cr.execute(
            f"SELECT id FROM spp_gis_report WHERE {bool_field} = true"  # nosec B608
        )
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

        # Insert m2m links (skip duplicates)
        for report_id in report_ids:
            cr.execute(
                """
                INSERT INTO spp_gis_report_spp_demographic_dimension_rel
                    (spp_gis_report_id, spp_demographic_dimension_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (report_id, dimension.id),
            )

        _logger.info(
            "Migrated %d reports from %s=True to dimension '%s'",
            len(report_ids),
            bool_field,
            dim_name,
        )
