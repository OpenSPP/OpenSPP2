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

    is_cr_manager = fields.Boolean(
        compute="_compute_is_cr_manager",
    )

    def _compute_is_cr_manager(self):
        is_manager = self.env.user.has_group("spp_change_request_v2.group_cr_manager")
        for rec in self:
            rec.is_cr_manager = is_manager

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
    stage = fields.Selection(
        related="change_request_id.stage",
    )
    use_dynamic_approval = fields.Boolean(
        related="change_request_id.request_type_id.use_dynamic_approval",
    )
    field_to_modify = fields.Selection(
        selection="_get_field_to_modify_selection",
        string="Field to Modify",
        help="Select which field to update in this change request",
    )

    @api.model
    def _get_field_to_modify_selection(self):
        """Return available field options for field-level change requests.

        Override in concrete detail models to provide the list of modifiable fields.
        Returns a list of (value, label) tuples, e.g.:
            [("poverty_status_id", "Poverty Status"), ("set_group_id", "Set Group")]
        """
        return []

    def write(self, vals):
        result = super().write(vals)
        if "field_to_modify" in vals:
            for rec in self:
                if rec.change_request_id:
                    rec._sync_field_to_modify()
        else:
            for rec in self:
                if rec.field_to_modify and rec.field_to_modify in vals and rec.change_request_id:
                    rec._sync_field_to_modify()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.field_to_modify and rec.change_request_id:
                rec._sync_field_to_modify()
        return records

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

    def action_save_and_go_to_list(self):
        """Save current state and navigate back to the CR list."""
        return self.change_request_id.action_save_and_go_to_list()

    def action_next_documents(self):
        """Save and navigate to the documents stage."""
        self.ensure_one()
        if not self.change_request_id.has_proposed_changes:
            raise UserError(_("No proposed changes detected. Please make changes before proceeding."))
        return self.change_request_id.action_goto_documents()

    def action_skip_to_review(self):
        """Skip documents stage and go directly to review if all required docs are uploaded."""
        self.ensure_one()
        change_req = self.change_request_id
        if not change_req.has_proposed_changes:
            raise UserError(_("No proposed changes detected. Please make changes before proceeding."))
        if not change_req.documents_complete:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Missing Documents"),
                    "message": _("Some required documents are missing. Redirecting to Documents stage."),
                    "type": "warning",
                    "sticky": False,
                    "next": change_req.action_goto_documents(),
                },
            }
        return change_req.action_goto_review()

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
    # DYNAMIC APPROVAL SYNC
    # ══════════════════════════════════════════════════════════════════════════

    def _sync_field_to_modify(self):
        """Sync field_to_modify and its old/new values to the parent CR."""
        self.ensure_one()
        cr = self.change_request_id
        if not cr:
            return
        # Only sync for dynamic-approval CR types
        if not cr.request_type_id.use_dynamic_approval:
            return

        field_name = self.field_to_modify
        cr_vals = {
            "selected_field_name": field_name,
            "selected_field_old_value": False,
            "selected_field_new_value": False,
        }

        if field_name:
            mapping = cr.request_type_id.apply_mapping_ids.filtered(lambda m: m.source_field == field_name)[:1]

            if mapping:
                registrant = cr.registrant_id
                old_raw = getattr(registrant, mapping.target_field, None)
                cr_vals["selected_field_old_value"] = self._format_value_for_display(old_raw)

            new_raw = getattr(self, field_name, None)
            cr_vals["selected_field_new_value"] = self._format_value_for_display(new_raw)

        cr.write(cr_vals)

    def _format_value_for_display(self, value):
        """Format a field value as a human-readable string for audit display."""
        # Boolean check MUST come before the falsy check,
        # otherwise False displays as "" instead of "No"
        if isinstance(value, bool):
            return _("Yes") if value else _("No")
        if value is None or value is False:
            return ""
        if hasattr(value, "display_name"):
            return value.display_name or ""
        return str(value)

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
