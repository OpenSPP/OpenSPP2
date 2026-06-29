"""Exclude DCI-backed variables from the generic external Data API.

DCI-backed variables carry inter-registry data (disability, vital/civil status)
fetched via the DCI protocol. That data has its own consent/provider boundary
(the DCI server path) and must not be retrievable through the generic Data API
push/pull channel, even once eligibility precompute has cached its values.
"""

from odoo import api, models


class CelVariableDCI(models.Model):
    _inherit = "spp.cel.variable"

    def is_data_api_pullable(self):
        # Ordinary external-provider variables remain pullable; DCI-backed ones
        # are not, regardless of the base rule.
        pullable = super().is_data_api_pullable()
        if pullable and self.external_provider_id.is_dci_backed:
            return False
        return pullable

    @api.model
    def _get_data_api_pullable_domain(self):
        # Exclude DCI-backed providers at the DB level so /Data/variables counts
        # and paginates over the same set is_data_api_pullable() would allow.
        return super()._get_data_api_pullable_domain() + [("external_provider_id.is_dci_backed", "=", False)]
