"""DCI Integration bridge for spp.data.provider.

Links a CEL data provider to a DCI Data Source (spp.dci.data.source). When a
provider is linked, it becomes "DCI-backed": its variable values are fetched
via the DCI protocol using the linked Data Source's connection and
credentials, and the provider's own Base URL / Authentication are ignored at
runtime. The runtime fetch itself is implemented separately; this module
provides the configuration link and the is_dci_backed flag.
"""

from odoo import api, fields, models


class DataProviderDCI(models.Model):
    _inherit = "spp.data.provider"

    dci_data_source_id = fields.Many2one(
        comodel_name="spp.dci.data.source",
        string="DCI Data Source",
        ondelete="set null",
        help="Link this provider to a DCI Data Source. When set, variable values "
        "are fetched via the DCI protocol using that Data Source's connection and "
        "credentials; this provider's own Base URL and Authentication are ignored "
        "at runtime.",
    )
    is_dci_backed = fields.Boolean(
        string="DCI-Backed",
        compute="_compute_is_dci_backed",
        store=True,
        help="True when a DCI Data Source is linked; value routing uses the DCI protocol.",
    )

    @api.depends("dci_data_source_id")
    def _compute_is_dci_backed(self):
        for provider in self:
            provider.is_dci_backed = bool(provider.dci_data_source_id)
