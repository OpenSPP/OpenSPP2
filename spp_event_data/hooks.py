# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging
import os
import re

_logger = logging.getLogger(__name__)

# Valid index name pattern (alphanumeric and underscore only)
INDEX_NAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$", re.IGNORECASE)


def post_init_hook(env):
    """Post-init hook to create database indexes for scalability."""
    _logger.info("spp_event_data: Creating database indexes...")

    # Read SQL file
    module_path = os.path.dirname(os.path.abspath(__file__))
    sql_file = os.path.join(module_path, "data", "event_data_indexes.sql")

    if os.path.exists(sql_file):
        with open(sql_file) as f:
            sql = f.read()

        # Execute SQL from static file (no user input involved)
        env.cr.execute(sql)  # nosemgrep: odoo-sql-injection-string-format
        # SQL comes from static module file data/event_data_indexes.sql, not from user input.
        _logger.info("spp_event_data: Database indexes created successfully")
    else:
        _logger.warning("spp_event_data: Index SQL file not found: %s", sql_file)


def uninstall_hook(env):
    """Cleanup hook on module uninstall."""
    _logger.info("spp_event_data: Cleaning up database indexes...")

    # Drop custom indexes
    indexes = [
        "idx_spp_event_data_active_by_type",
        "idx_spp_event_data_collection_date",
        "idx_spp_event_data_expiry",
        "idx_spp_event_data_source_ref",
        "idx_spp_event_data_state",
        "idx_spp_event_type_source",
    ]

    for index in indexes:
        # Validate index name to prevent SQL injection
        if not INDEX_NAME_PATTERN.match(index):
            _logger.warning("Invalid index name pattern, skipping: %s", index)
            continue
        try:
            # Use psycopg2's sql module for safe identifier handling
            from psycopg2 import sql

            env.cr.execute(  # nosemgrep: odoo-sql-injection-string-format
                # Index name is validated by regex and passed as psycopg2 Identifier,
                # not string interpolation.
                sql.SQL("DROP INDEX IF EXISTS {}").format(sql.Identifier(index))
            )
        except Exception as e:
            _logger.warning("Failed to drop index %s: %s", index, e)

    _logger.info("spp_event_data: Cleanup completed")
