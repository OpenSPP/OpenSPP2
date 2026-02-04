"""Integrate spp.logic with standardized approval framework."""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class LogicApproval(models.Model):
    """Extend spp.cel.expression with standardized approval workflow.

    This bridges the logic publishing workflow with the standardized
    spp_approval framework, making approval optional via configuration.

    State Mapping:
        - draft -> draft (approval mixin)
        - pending -> pending (approval mixin)
        - published -> approved (approval mixin)
        - archived -> (no mixin equivalent)

    Configuration:
        Set system parameter 'spp_studio.require_approval' to 'True'
        to enforce approval workflow. When False, direct publishing is allowed.
    """

    _name = "spp.cel.expression"
    _inherit = ["spp.cel.expression", "spp.approval.mixin"]

    # Link to approval definition for logic
    logic_approval_definition_id = fields.Many2one(
        "spp.approval.definition",
        string="Logic Approval Definition",
        compute="_compute_logic_approval_definition",
        store=False,
    )

    # Override approval mixin fields to map to existing logic fields
    approval_state = fields.Selection(
        related=None,  # Override related
        compute="_compute_approval_state",
        store=False,  # Computed from state field
    )

    # Track if using standardized approval
    use_approval_workflow = fields.Boolean(
        compute="_compute_use_approval_workflow",
        store=False,
        help="Whether this logic requires approval before publishing",
    )

    # Cached model ID for performance
    _logic_model_id_cache = None

    @api.model
    def _get_logic_model_id(self):
        """Get cached ir.model ID for spp.cel.expression.

        Returns:
            int: Model ID or False if not found
        """
        if LogicApproval._logic_model_id_cache is None:
            model = self.env["ir.model"].search([("model", "=", "spp.cel.expression")], limit=1)
            LogicApproval._logic_model_id_cache = model.id if model else False
        return LogicApproval._logic_model_id_cache

    def _compute_logic_approval_definition(self):
        """Get the approval definition for logic.

        Looks for active approval definitions configured for spp.cel.expression.
        """
        # Get model ID once (cached)
        logic_model_id = self._get_logic_model_id()

        if not logic_model_id:
            for record in self:
                record.logic_approval_definition_id = False
            return

        # Fetch all active definitions for logic ONCE
        definitions = self.env["spp.approval.definition"].search(
            [
                ("model_id", "=", logic_model_id),
                ("active", "=", True),
            ]
        )

        # Use first matching definition for all records
        definition = definitions[0] if definitions else False

        for record in self:
            record.logic_approval_definition_id = definition

    def _compute_use_approval_workflow(self):
        """Check if approval workflow should be enforced.

        Approval is required when:
        1. System parameter 'spp_studio.require_approval' is True, AND
        2. An approval definition exists for the logic model
        """
        ICPSudo = self.env["ir.config_parameter"].sudo()
        require_approval = ICPSudo.get_param("spp_studio.require_approval", default="False")

        for record in self:
            if require_approval == "True" and record.logic_approval_definition_id:
                record.use_approval_workflow = True
            else:
                record.use_approval_workflow = False

    @api.depends("state")
    def _compute_approval_state(self):
        """Map logic state to approval mixin state."""
        state_map = {
            "draft": "draft",
            "pending": "pending",
            "published": "approved",
            "archived": "approved",  # Keep as approved
        }
        for record in self:
            record.approval_state = state_map.get(record.state, "draft")

    def _get_approval_definition(self):
        """Override to return the logic's approval definition.

        Returns:
            spp.approval.definition: Approval definition or None
        """
        self.ensure_one()
        return self.logic_approval_definition_id

    # ═══════════════════════════════════════════════════════════════════════
    # OVERRIDE APPROVAL MIXIN ACTIONS
    # ═══════════════════════════════════════════════════════════════════════

    def action_submit_for_approval(self):
        """Submit logic for approval using standardized workflow.

        This is called when the user clicks "Submit for Approval" button.
        It validates the logic and transitions it to pending state.
        """
        self.ensure_one()

        if not self.use_approval_workflow:
            # If approval not required, fall back to direct publish
            return self.action_publish()

        # Check preconditions
        if self.state != "draft":
            raise UserError(_("Only draft logic can be submitted for approval."))

        # Validate before submission (same checks as publishing)
        try:
            self._check_can_publish()
        except ValidationError as e:
            raise UserError(_("Cannot submit logic for approval:\n%s") % str(e)) from e

        # Update compiled expression before submission
        self._update_compiled_expression()

        # Use mixin submission logic
        result = super().action_submit_for_approval()

        # Transition to pending state
        self.write({"state": "pending"})

        _logger.info(
            "Logic %s submitted for approval by user %s",
            self.name,
            self.env.user.name,
        )

        return result

    def action_approve(self, comment=None):
        """Approve logic and publish it.

        This is called when an approver clicks "Approve".
        It calls action_publish() to freeze the expression and create a version.
        """
        self.ensure_one()

        if not self.use_approval_workflow:
            # If approval not required, this shouldn't be called
            raise UserError(_("Approval workflow is not enabled for this logic."))

        # Check preconditions
        if self.state != "pending":
            raise UserError(_("Only pending logic can be approved."))

        # Use mixin approval logic
        result = super().action_approve(comment=comment)

        # Publish the logic (freeze expression, create version)
        # Note: action_publish() will set state to 'published' and update audit fields
        self.action_publish()

        _logger.info(
            "Logic %s approved and published by user %s",
            self.name,
            self.env.user.name,
        )

        return result

    def action_reject(self):
        """Reject logic using standardized workflow.

        Opens a wizard for the approver to provide a rejection reason.
        """
        self.ensure_one()

        if not self.use_approval_workflow:
            raise UserError(_("Approval workflow is not enabled for this logic."))

        # Check preconditions
        if self.state != "pending":
            raise UserError(_("Only pending logic can be rejected."))

        # Use mixin rejection logic (opens wizard)
        return super().action_reject()

    def _do_reject(self, reason):
        """Execute rejection after wizard confirmation.

        Args:
            reason (str): Rejection reason provided by approver
        """
        self.ensure_one()

        # Call parent mixin logic
        super()._do_reject(reason)

        # Transition back to draft state
        self.write({"state": "draft"})

        _logger.info(
            "Logic %s rejected by user %s: %s",
            self.name,
            self.env.user.name,
            reason,
        )

    def action_request_revision(self):
        """Request revision using standardized workflow.

        Opens a wizard for the approver to provide revision notes.
        """
        self.ensure_one()

        if not self.use_approval_workflow:
            raise UserError(_("Approval workflow is not enabled for this logic."))

        # Check preconditions
        if self.state != "pending":
            raise UserError(_("Only pending logic can have revision requested."))

        # Use mixin revision request logic (opens wizard)
        return super().action_request_revision()

    def _do_request_revision(self, notes):
        """Execute revision request after wizard confirmation.

        Args:
            notes (str): Revision notes provided by approver
        """
        self.ensure_one()

        # Call parent mixin logic
        super()._do_request_revision(notes)

        # Transition back to draft state
        self.write({"state": "draft"})

        _logger.info(
            "Revision requested for logic %s by user %s: %s",
            self.name,
            self.env.user.name,
            notes,
        )

    def action_reset_to_draft(self):
        """Reset logic to draft state.

        This is available for rejected or revision-requested logic.
        """
        self.ensure_one()

        if self.state not in ("pending", "draft"):
            raise UserError(_("Only pending or draft logic can be reset."))

        # Use mixin reset logic only if in rejected approval_state
        if self.approval_state in ("rejected", "revision"):
            super().action_reset_to_draft()

        # Transition to draft state
        self.write({"state": "draft"})

        _logger.info("Logic ID %s reset to draft", self.id)

    # ═══════════════════════════════════════════════════════════════════════
    # APPROVAL HOOKS
    # ═══════════════════════════════════════════════════════════════════════

    def _on_submit(self):
        """Called before submitting for approval.

        Validates that:
        - Logic has an expression (simple conditions or CEL expression)
        - All tests pass
        - No missing variables
        """
        super()._on_submit()

        # Use the same validation as publishing
        self._check_can_publish()

        _logger.debug("Logic ID %s passed validation for submission", self.id)

    def _on_approve(self):
        """Called after approval.

        The actual publishing happens in action_approve() which calls
        action_publish(). This hook is for any additional post-approval logic.
        """
        super()._on_approve()
        # Additional post-approval logic can go here if needed

    def _on_reject(self, reason):
        """Called after rejection.

        Args:
            reason (str): Rejection reason
        """
        super()._on_reject(reason)

        # Post a message to the chatter
        self.message_post(
            body=_("Logic rejected: %s") % reason,
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )

    def _on_request_revision(self, notes):
        """Called after revision request.

        Args:
            notes (str): Revision notes
        """
        super()._on_request_revision(notes)

        # Post a message to the chatter
        self.message_post(
            body=_("Revision requested: %s") % notes,
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # COMPUTED PERMISSIONS
    # ═══════════════════════════════════════════════════════════════════════

    @api.depends("state", "logic_approval_definition_id")
    def _compute_can_submit(self):
        """Compute if current user can submit for approval."""
        for record in self:
            if record.use_approval_workflow:
                record.can_submit = record.state == "draft"
            else:
                record.can_submit = False

    @api.depends("state", "logic_approval_definition_id")
    def _compute_can_approve(self):
        """Compute if current user can approve."""
        for record in self:
            if record.use_approval_workflow and record.state == "pending":
                # Check if user is in approvers
                record.can_approve = record._is_approver()
            else:
                record.can_approve = False

    @api.depends("state", "logic_approval_definition_id")
    def _compute_can_reject(self):
        """Compute if current user can reject."""
        for record in self:
            if record.use_approval_workflow and record.state == "pending":
                record.can_reject = record._is_approver()
            else:
                record.can_reject = False

    def _is_approver(self):
        """Check if current user is an approver for this logic.

        Returns:
            bool: True if user can approve, False otherwise
        """
        self.ensure_one()
        definition = self._get_approval_definition()
        if not definition:
            return True  # No definition = anyone can approve

        approvers = definition.get_approvers(self)
        return self.env.user in approvers
