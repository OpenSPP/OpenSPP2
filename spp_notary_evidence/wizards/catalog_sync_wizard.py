# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Wizard for syncing Notary claim catalog metadata."""

from odoo import fields, models


class NotaryCatalogSyncWizard(models.TransientModel):
    """Run catalog-only sync for a Notary data provider."""

    _name = "spp.notary.catalog.sync.wizard"
    _description = "Sync Notary Claim Catalog"

    provider_id = fields.Many2one(
        comodel_name="spp.data.provider",
        string="Notary Provider",
        required=True,
        domain=[("provider_kind", "=", "notary")],
    )

    def action_sync_catalog(self):
        self.ensure_one()
        return self.provider_id.action_sync_notary_claim_catalog()
