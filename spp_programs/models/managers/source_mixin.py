# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class ManagerSourceMixin(models.AbstractModel):
    """Manager Data Source mixin."""

    _name = "spp.manager.source.mixin"
    _description = "Manager Data Source Mixin"

    @api.model
    def create(self, vals):
        """Override to update reference to source on the manager."""
        res = super().create(vals)
        # TODO: Seems not required but this causes error when called from the create program wizard.
        # Disable for now
        # if self.env.context.get("active_model"):
        #    # update reference on manager
        #    self.env[self.env.context["active_model"]].browse(
        #        self.env.context["active_id"]
        #    ).manager_id = res.id
        return res

    def unlink(self):
        for rec in self:
            managers = self.get_managers_for_unlink(f"{rec._name},{rec.id}")
            if managers:
                managers.unlink()
        return super().unlink()

    @api.model
    def get_managers_for_unlink(self, manager_ref):
        managers = self.env["spp.eligibility.manager"].search([("manager_ref_id", "=", manager_ref)])
        if managers:
            return managers
        managers = self.env["spp.deduplication.manager"].search([("manager_ref_id", "=", manager_ref)])
        if managers:
            return managers
        managers = self.env["spp.program.notification.manager"].search([("manager_ref_id", "=", manager_ref)])
        if managers:
            return managers
        managers = self.env["spp.program.manager"].search([("manager_ref_id", "=", manager_ref)])
        if managers:
            return managers
        managers = self.env["spp.cycle.manager"].search([("manager_ref_id", "=", manager_ref)])
        if managers:
            return managers
        managers = self.env["spp.program.entitlement.manager"].search([("manager_ref_id", "=", manager_ref)])
        if managers:
            return managers
        managers = self.env["spp.program.payment.manager"].search([("manager_ref_id", "=", manager_ref)])
        if managers:
            return managers

    def get_manager_view_id(self):
        """Retrieve form view."""
        return self.env["ir.ui.view"].search([("model", "=", self._name), ("type", "=", "form")], limit=1).id
