# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class ManagerSourceMixin(models.AbstractModel):
    """Manager Data Source mixin."""

    _name = "spp.manager.source.mixin"
    _description = "Manager Data Source Mixin"

    @api.model_create_multi
    def create(self, vals_list):
        """Override to update reference to source on the manager.

        Also auto-creates the matching wrapper record when the calling
        action passed `_spp_wrapper_model` in context — used by the
        program form's `+ Add` zero-state buttons (#953). Opening the
        concrete model in create mode means dismissing the dialog with
        `X` leaves nothing in the DB; the wrapper is only created here,
        atomically with the concrete record, when Save is actually
        clicked.
        """
        records = super().create(vals_list)
        wrapper_model = self.env.context.get("_spp_wrapper_model")
        program_id = self.env.context.get("default_program_id")
        if wrapper_model and program_id and wrapper_model in self.env:
            for record in records:
                wrapper = self.env[wrapper_model].create(
                    {
                        "program_id": program_id,
                        "manager_ref_id": f"{record._name},{record.id}",
                    }
                )
                # Compliance is One2many on `spp.program.compliance_manager_ids`
                # and auto-resolves via the wrapper's `program_id` inverse.
                # Payment is Many2many — its program-side field needs an
                # explicit write, otherwise the program never picks up the
                # new wrapper.
                m2m_field = self.env.context.get("_spp_program_m2m_field")
                if m2m_field and "spp.program" in self.env:
                    self.env["spp.program"].browse(program_id).write({m2m_field: [(4, wrapper.id)]})
        return records

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
