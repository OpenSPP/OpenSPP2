from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError


class SPPEntitlement(models.Model):
    _inherit = "spp.entitlement"

    state = fields.Selection(
        selection_add=[("reject", "Rejected")],
        ondelete={"reject": "set default"},
    )
    date_rejected = fields.Date()
    rejected_reason = fields.Text(string="Rejected Reason")

    def reject_entitlement(self):
        form_id = self.env.ref("spp_programs.reject_entitlement_wizard").id
        action = {
            "name": _("Reject Entitlement"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "view_id": form_id,
            "view_type": "form",
            "res_model": "spp.reject.entitlement.wizard",
            "target": "new",
            "context": {
                "to_state": "reject",
            },
        }
        return action

    @staticmethod
    def allowed_to_reject_entitlement():
        return ["draft", "pending_validation"]

    def _reject_entitlement(self, to_state="reject", reject_reason=""):
        # Use sudo() so state changes are applied atomically once the wizard
        # has validated the caller's group-based permissions.
        # nosemgrep: odoo-sudo-without-context — called only from reject wizard with ACLs on wizard model
        for rec in self.sudo():
            if rec.state not in self.allowed_to_reject_entitlement():
                continue

            # Update entitlement-specific fields
            rec.write({"rejected_reason": reject_reason, "date_rejected": fields.Date.today()})

            # Use the approval mixin's rejection workflow to update reviews and approval state
            # Note: _do_reject() will update the state (to rejected1 or rejected3)
            # but we override it to the requested to_state afterwards
            rec._do_reject(reason=reject_reason)

            # Override state if different from what _do_reject set
            if rec.state != to_state:
                rec.write({"state": to_state})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Entitlement"),
                "message": "Entitlement Rejected",
                "sticky": False,
                "type": "danger",
                "next": {
                    "type": "ir.actions.act_window_close",
                },
            },
        }

    def approve_entitlement(self):
        # Check approval definition permissions first
        for rec in self:
            definition = rec._get_approval_definition()

            # If no definition exists, we cannot approve
            if not definition:
                raise UserError(
                    _(
                        "No approval definition configured for this entitlement.\n\n"
                        "Please ensure an approval definition is set up in the entitlement manager "
                        "before attempting to approve entitlements."
                    )
                )

            # Compute permissions and check authorization
            rec._compute_approval_permissions()
            if not rec.can_approve:
                # Get the approver group name for a better error message
                group_name = _("Unknown Group")
                if definition.use_multitier:
                    # Multi-tier: get current tier's group
                    active_review = rec.approval_review_ids.filtered(lambda r: r.status == "pending")[:1]
                    if active_review and active_review.level_id and active_review.level_id.group_id:
                        group_name = active_review.level_id.group_id.name
                elif definition.approval_group_id:
                    # Single-tier: show the approver group
                    group_name = definition.approval_group_id.name

                raise UserError(
                    _(
                        "You are not authorized to approve this entitlement.\n\n"
                        "Only users in the following group(s) can approve:\n%(groups)s"
                    )
                    % {
                        "groups": group_name,
                    }
                )

        if self.env.user.has_group("spp_programs.approve_entitlement"):
            # Elevate to sudo() only for users in the approve_entitlement group
            # so approval operations are not blocked by downstream ACLs.
            return super(
                SPPEntitlement,
                self.sudo(),  # nosemgrep: odoo-sudo-without-context
                # Approval restricted to spp_programs.approve_entitlement group.
            ).approve_entitlement()
        return super().approve_entitlement()

    def write(self, vals):
        if self.env.user.has_group("spp_programs.approve_entitlement") or self.env.user.has_group(
            "spp_programs.approve_entitlement"
        ):
            return super(
                SPPEntitlement,
                self.sudo(),  # nosemgrep: odoo-sudo-without-context
                # Elevated write restricted to spp_programs.approve_entitlement group.
            ).write(vals)
        return super().write(vals)

    def reset_to_pending(self):
        form_id = self.env.ref("spp_programs.reset_to_pending_entitlement_wizard").id
        action = {
            "name": _("Reset to Pending Entitlement"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "view_id": form_id,
            "view_type": "form",
            "res_model": "spp.reset.pending.entitlement.wizard",
            "target": "new",
        }
        return action

    def _reset_to_pending(self):
        # Reset to pending as a system operation after wizard has verified
        # permissions and context.
        for rec in self.sudo():  # nosemgrep: odoo-sudo-without-context
            # Reset called via controlled wizard action.
            rec.state = "pending_validation"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Entitlement"),
                "message": "Entitlement Reset to Pending",
                "sticky": False,
                "type": "success",
                "next": {
                    "type": "ir.actions.act_window_close",
                },
            },
        }


class SPPInKindEntitlement(models.Model):
    _inherit = "spp.entitlement.inkind"

    inkind_item_id = fields.Many2one("spp.program.entitlement.manager.inkind.item", "In-Kind Entitlement Condition")

    state = fields.Selection(
        selection_add=[("reject", "Rejected")],
        ondelete={"reject": "set default"},
    )
    date_rejected = fields.Date()
    rejected_reason = fields.Text(string="Rejected Reason")

    def reject_entitlement(self):
        form_id = self.env.ref("spp_programs.reject_inkind_entitlement_wizard").id
        action = {
            "name": _("Reject In-Kind Entitlement"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "view_id": form_id,
            "view_type": "form",
            "res_model": "spp.reject.inkind.entitlement.wizard",
            "target": "new",
            "context": {
                "to_state": "reject",
            },
        }
        return action

    @staticmethod
    def allowed_to_reject_entitlement():
        return ["draft", "pending_validation"]

    def _reject_entitlement(self, to_state="reject", reject_reason=""):
        # Use sudo() so state changes are applied atomically once the wizard
        # has validated the caller's group-based permissions.
        # Called only from reject wizard with ACLs on wizard model.
        # nosemgrep: odoo-sudo-without-context — called only from reject wizard with ACLs on wizard model
        for rec in self.sudo():
            if rec.state not in self.allowed_to_reject_entitlement():
                continue

            # Update entitlement-specific fields
            rec.write({"rejected_reason": reject_reason, "date_rejected": fields.Date.today()})

            # Use the approval mixin's rejection workflow to update reviews and approval state
            # Note: _do_reject() will update the state (to rejected1)
            # but we override it to the requested to_state afterwards
            rec._do_reject(reason=reject_reason)

            # Override state if different from what _do_reject set
            if rec.state != to_state:
                rec.write({"state": to_state})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("In-Kind Entitlement"),
                "message": "In-Kind Entitlement Rejected",
                "sticky": False,
                "type": "danger",
                "next": {
                    "type": "ir.actions.act_window_close",
                },
            },
        }

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        # to bypass the validation in spp_programs/models/entitlement.py
        if not self.env.user.has_group("spp_security.group_spp_admin"):
            other_user = self.env["res.users"].browse(SUPERUSER_ID)
            # Switch to SUPERUSER to render entitlement views when admin group
            # is not present; this only affects view loading, not record writes.
            self = self.with_user(  # nosemgrep: odoo-with-user-unvalidated
                # Internal view rendering override, SUPERUSER_ID is fixed.
                other_user
            )

        arch, view = super()._get_view(view_id, view_type, **options)

        return arch, view
