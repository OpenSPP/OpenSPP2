from odoo import api, fields, models


class DataProvider(models.Model):
    _inherit = "spp.data.provider"

    dci_data_source_id = fields.Many2one(
        "spp.dci.data.source",
        string="DCI Data Source",
        ondelete="restrict",
        help=(
            "When set, this provider fetches values via the DCI protocol. "
            "The registry_type on the DCI source determines which DCI "
            "service handles the call."
        ),
    )

    is_dci_backed = fields.Boolean(
        string="DCI-Backed",
        compute="_compute_is_dci_backed",
        store=True,
    )

    @api.depends("dci_data_source_id")
    def _compute_is_dci_backed(self):
        for rec in self:
            rec.is_dci_backed = bool(rec.dci_data_source_id)
