import logging

from odoo import models

_logger = logging.getLogger(__name__)


class DataCacheManager(models.AbstractModel):
    """Route DCI-backed external CEL variables through the DCI dispatcher.

    The parent implementation (spp_cel_domain) treats source_type='external'
    as a push-only path: it returns {} and logs that values must be pushed
    via API. This override fills that gap by calling the dispatcher for
    variables whose external_provider_id is linked to a DCI data source.

    Non-DCI external variables continue to fall through to the parent
    implementation unchanged.
    """

    _inherit = "spp.data.cache.manager"

    def _compute_variable_values(self, variable, subject_ids, period_key, program_id):
        if (
            variable.source_type == "external"
            and variable.external_provider_id
            and variable.external_provider_id.is_dci_backed
        ):
            return self._compute_dci_values(
                variable, subject_ids, period_key, program_id
            )
        return super()._compute_variable_values(
            variable, subject_ids, period_key, program_id
        )

    def _compute_dci_values(self, variable, subject_ids, period_key, program_id):
        """Fetch DCI-backed external values via the dispatcher.

        v1: failure policy is implicitly 'null' — exceptions and missing
        subjects produce no entry in the result dict; the cache manager
        records the absence. Step 6 will add explicit policy handling
        for 'last_known' and 'fail'.
        """
        dispatcher = self.env["spp.cel.dci.dispatcher"]
        try:
            return dispatcher.fetch_values_for_variable(
                variable, subject_ids, period_key
            )
        except Exception as e:
            _logger.error(
                "DCI fetch failed for variable %s: %s",
                variable.name,
                e,
                exc_info=True,
            )
            return {}
