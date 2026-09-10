# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Recompute the incident KPIs whose meaning changed in this version (OP#1100).

Three stored computes were redefined rather than added:

* ``drims_total_stock_units`` and ``drims_stock_item_count`` went from
  "everything physically in the warehouse" to "incident-related stock net of
  what has been allocated out".
* ``drims_distributed_value`` is now net of confirmed returns.

Odoo only computes a stored field for existing rows when its column is newly
created, so an upgraded database keeps the old numbers until something happens
to touch a dependency. For a quiet incident that may be never — and closed
incidents are excluded from ``_cron_refresh_drims_kpis``, so nothing would ever
correct them.

The cached ``spp.data.value`` rows behind the value KPIs hold pre-change
numbers for the same reason, and the compute prefers a live cache entry over
recomputing, so they are dropped first.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

STALE_CACHE_VARIABLES = ("drims_distributed_value", "drims_stock_value")

RECOMPUTED_FIELDS = (
    "drims_total_stock_units",
    "drims_stock_item_count",
    "drims_distributed_value",
)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    data_value = env.get("spp.data.value")
    if data_value is not None:
        for variable in STALE_CACHE_VARIABLES:
            data_value.invalidate(variable_name=variable)
        _logger.info("Dropped cached values for %s", ", ".join(STALE_CACHE_VARIABLES))

    # Every incident, not just the open ones: the cron that would otherwise
    # heal these skips closed incidents, which is exactly where a stale number
    # would sit unnoticed.
    incidents = env["spp.hazard.incident"].search([])
    if not incidents:
        return

    for field_name in RECOMPUTED_FIELDS:
        field = incidents._fields.get(field_name)
        if field is not None:
            env.add_to_compute(field, incidents)
    env.flush_all()
    _logger.info("Recomputed %s for %d incident(s)", ", ".join(RECOMPUTED_FIELDS), len(incidents))
