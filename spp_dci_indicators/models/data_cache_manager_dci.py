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
        if self._is_dci_backed_variable(variable):
            return self.env["spp.dci.cel.fetcher"].fetch_values(variable, subject_ids)
        return super()._compute_variable_values(variable, subject_ids, period_key, program_id)

    def _cache_computed_values(self, variable, computed, period_key):
        """Cache DCI values under the variable's cel_accessor.

        The base method keys the cache on variable.name, but the CEL resolver
        emits metric('<the token the author typed>', me) - i.e. the cel_accessor
        (e.g. crvs.dci.is_alive), which differs from the name (dci.crvs.is_alive)
        for DCI variables. Keying on cel_accessor keeps the written value
        readable by the compiled metric() subquery.
        """
        if computed and self._is_dci_backed_variable(variable) and variable.cache_strategy in ("ttl", "manual"):
            self.env["spp.data.value"].upsert_values(
                [
                    {
                        "variable_name": variable.cel_accessor,
                        "subject_model": variable.source_model or "res.partner",
                        "subject_id": subject_id,
                        "period_key": period_key or "current",
                        # Store booleans as 1/0: the metric comparison SQL casts
                        # the cached value to numeric, which rejects JSON booleans.
                        "value_json": {"value": int(value) if isinstance(value, bool) else value},
                        "value_type": variable.value_type or "boolean",
                        "source_type": "external",
                        "ttl_seconds": variable.cache_ttl_seconds if variable.cache_strategy == "ttl" else None,
                    }
                    for subject_id, value in computed.items()
                ]
            )
            return
        return super()._cache_computed_values(variable, computed, period_key)

    @staticmethod
    def _is_dci_backed_variable(variable):
        return bool(
            variable.source_type == "external"
            and variable.external_provider_id
            and variable.external_provider_id.is_dci_backed
        )
