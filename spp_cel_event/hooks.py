# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging
import os

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Post-init hook to create database indexes for CEL event data queries."""
    _logger.info("spp_cel_event: Creating database indexes...")

    # Read SQL file
    module_path = os.path.dirname(os.path.abspath(__file__))
    sql_file = os.path.join(module_path, "data", "cel_event_indexes.sql")

    if os.path.exists(sql_file):
        with open(sql_file, encoding="utf-8") as f:
            sql = f.read()

        # Execute SQL
        env.cr.execute(sql)
        _logger.info("spp_cel_event: Database indexes created successfully")
    else:
        _logger.warning("spp_cel_event: Index SQL file not found: %s", sql_file)
