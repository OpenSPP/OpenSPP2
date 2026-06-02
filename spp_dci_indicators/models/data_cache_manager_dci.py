"""Route DCI-backed external variables through the DCI fetcher.

The base cache manager returns {} for source_type='external' variables (it
expects values to be pushed in). When the variable's provider is DCI-backed,
fetch the values via the DCI protocol instead, so the existing precompute /
refresh / TTL caching machinery populates spp.data.value for them.
"""

from odoo import models


class DataCacheManagerDCI(models.AbstractModel):
    _inherit = "spp.data.cache.manager"

    def _compute_variable_values(self, variable, subject_ids, period_key, program_id):
        if (
            variable.source_type == "external"
            and variable.external_provider_id
            and variable.external_provider_id.is_dci_backed
        ):
            return self.env["spp.dci.cel.fetcher"].fetch_values(variable, subject_ids)
        return super()._compute_variable_values(variable, subject_ids, period_key, program_id)
