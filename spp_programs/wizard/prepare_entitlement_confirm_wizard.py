# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models


class PrepareEntitlementConfirmWizard(models.TransientModel):
    """Confirmation wizard for preparing entitlements without compliance criteria applied."""

    _name = "spp.prepare.entitlement.confirm.wizard"
    _description = "Prepare Entitlement Confirmation Wizard"

    cycle_id = fields.Many2one("spp.cycle", string="Cycle", required=True)
    message = fields.Text(string="Message", readonly=True)

    def action_apply_and_prepare(self):
        """Apply compliance criteria first, then prepare entitlements."""
        self.ensure_one()
        # Apply compliance criteria
        self.cycle_id.action_filter_beneficiaries_by_compliance_criteria()
        # Then prepare entitlements
        return self.cycle_id.prepare_entitlement()

    def action_confirm(self):
        """Proceed with preparing entitlements without applying compliance."""
        self.ensure_one()
        return self.cycle_id.prepare_entitlement()

    def action_cancel(self):
        """Cancel and close the wizard."""
        return {"type": "ir.actions.act_window_close"}
