from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SPPCRDetailBase(models.AbstractModel):
    """Abstract base for all CR detail models.

    All detail models should inherit from this to ensure consistent
    structure and link to the parent change request.
    """

    _name = "spp.cr.detail.base"
    _description = "Change Request Detail Base"

    @api.depends("change_request_id.name")
    def _compute_display_name(self):
        for rec in self:
            if rec.change_request_id and rec.change_request_id.name:
                rec.display_name = rec.change_request_id.name
            else:
                super(SPPCRDetailBase, rec)._compute_display_name()

    change_request_id = fields.Many2one(
        "spp.change.request",
        string="Change Request",
        required=True,
        ondelete="cascade",
        index=True,
    )

    # Convenience access to CR fields
    registrant_id = fields.Many2one(
        related="change_request_id.registrant_id",
        string="Registrant",
        store=True,
    )
    approval_state = fields.Selection(
        related="change_request_id.approval_state",
        store=True,
    )
    is_applied = fields.Boolean(
        related="change_request_id.is_applied",
    )

    def action_proceed_to_cr(self):
        """Navigate to the parent Change Request form if there are proposed changes."""
        self.ensure_one()
        cr = self.change_request_id
        if not cr.has_proposed_changes:
            raise UserError(_("No proposed changes detected. Please make changes before proceeding."))
        return {
            "type": "ir.actions.act_window",
            "name": cr.name,
            "res_model": "spp.change.request",
            "res_id": cr.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_submit_for_approval(self):
        """Submit the parent CR for approval."""
        self.ensure_one()
        return self.change_request_id.action_submit_for_approval()

    def action_approve(self):
        """Approve the parent CR."""
        self.ensure_one()
        return self.change_request_id.action_approve()

    def action_reject(self):
        """Reject the parent CR."""
        self.ensure_one()
        return self.change_request_id.action_reject()

    def action_request_revision(self):
        """Request revision on the parent CR."""
        self.ensure_one()
        return self.change_request_id.action_request_revision()

    # ══════════════════════════════════════════════════════════════════════════
    # PREFILL FROM REGISTRANT
    # ══════════════════════════════════════════════════════════════════════════

    def _get_prefill_mapping(self):
        """Return the field mapping for pre-filling from registrant.

        Override this in detail models to define field mappings.

        Returns:
            dict: Mapping of detail field names to registrant field names
                  e.g., {"detail_field": "registrant_field"}
        """
        return {}

    def prefill_from_registrant(self):
        """Pre-fill detail fields from registrant.

        This method updates the current record with values from the registrant
        based on the mapping defined in _get_prefill_mapping().

        Override _get_prefill_mapping() in detail models to enable prefilling.
        """
        self.ensure_one()
        if not self.registrant_id:
            return

        mapping = self._get_prefill_mapping()
        if not mapping:
            return

        values = {}
        for detail_field, registrant_field in mapping.items():
            registrant_value = getattr(self.registrant_id, registrant_field, False)
            if registrant_value:
                values[detail_field] = registrant_value

        if values:
            self.write(values)
