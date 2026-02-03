import logging

from psycopg2 import sql as psycopg2_sql

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ApprovalMixin(models.AbstractModel):
    """Mixin to add standardized approval workflow to any model.

    IMPORTANT: This mixin requires the model to inherit from mail.thread and
    mail.activity.mixin. If your model doesn't already have these, add them:

    Usage::

        class MyModel(models.Model):
            _name = "my.model"
            _inherit = ["mail.thread", "mail.activity.mixin", "spp.approval.mixin"]

            def _on_approve(self):
                # Custom logic after approval
                pass

    Or for extending an existing model:

        class MyModel(models.Model):
            _name = "my.model"
            _inherit = ["my.model", "spp.approval.mixin"]
            # Only if my.model doesn't already have mail.thread:
            # _inherit = ["my.model", "mail.thread", "mail.activity.mixin", "spp.approval.mixin"]
    """

    _name = "spp.approval.mixin"
    _description = "Approval Workflow Mixin"

    # === Fields ===
    approval_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Pending Approval"),
            ("revision", "Revision Requested"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="Approval Status",
        default="draft",
        tracking=True,
        copy=False,
        index=True,
    )

    approval_review_ids = fields.One2many(
        "spp.approval.review",
        "res_id",
        string="Approval Reviews",
        domain=lambda self: [("model", "=", self._name)],
    )

    # Audit fields
    submitted_by_id = fields.Many2one(
        "res.users",
        string="Submitted By",
        readonly=True,
        copy=False,
    )
    submitted_date = fields.Datetime(
        string="Submitted Date",
        readonly=True,
        copy=False,
    )
    approved_by_id = fields.Many2one(
        "res.users",
        string="Approved By",
        readonly=True,
        copy=False,
    )
    approved_date = fields.Datetime(
        string="Approved Date",
        readonly=True,
        copy=False,
    )
    rejected_by_id = fields.Many2one(
        "res.users",
        string="Rejected By",
        readonly=True,
        copy=False,
    )
    rejected_date = fields.Datetime(
        string="Rejected Date",
        readonly=True,
        copy=False,
    )
    rejection_reason = fields.Text(
        string="Rejection Reason",
        readonly=True,
        copy=False,
    )

    # Revision tracking fields
    revision_requested_by_id = fields.Many2one(
        "res.users",
        string="Revision Requested By",
        readonly=True,
        copy=False,
    )
    revision_requested_date = fields.Datetime(
        string="Revision Requested Date",
        readonly=True,
        copy=False,
    )
    revision_notes = fields.Text(
        string="Revision Notes",
        readonly=True,
        copy=False,
        help="Notes explaining what needs to be revised",
    )

    # Computed fields
    can_submit = fields.Boolean(
        compute="_compute_approval_permissions",
    )
    can_approve = fields.Boolean(
        compute="_compute_approval_permissions",
    )
    can_reject = fields.Boolean(
        compute="_compute_approval_permissions",
    )

    # Optimistic locking
    approval_version = fields.Integer(default=1, copy=False)

    # Denormalized for search performance
    pending_since = fields.Datetime(
        compute="_compute_pending_since",
        store=True,
    )

    # === Helper Methods for Field Storage ===
    def _is_approval_state_stored(self):
        """Check if approval_state is stored in the database.

        Returns:
            bool: True if approval_state is a stored field, False if computed/non-stored
        """
        approval_state_field = self._fields.get("approval_state")
        return approval_state_field and approval_state_field.store

    def _write_approval_fields(self, vals):
        """Write approval-related fields, handling both stored and computed approval_state.

        This method allows the mixin to work with models that:
        1. Use the standard stored approval_state field (e.g., change requests)
        2. Override approval_state as a computed field (e.g., entitlements)

        For case 2, the model typically:
        - Maps approval_state to its own state field (e.g., state="pending_validation")
        - Handles state transitions in its action_approve/reject/etc. methods
        - Lets the computed approval_state field reflect the current state

        Args:
            vals: Dictionary of field values to write

        Example:
            Entitlement model computes approval_state from its state field:
            - state="draft" -> approval_state="draft"
            - state="pending_validation" -> approval_state="pending"
            - state="approved" -> approval_state="approved"
        """
        if not self._is_approval_state_stored() and "approval_state" in vals:
            # Remove approval_state from write - let computed field handle it
            vals = vals.copy()
            vals.pop("approval_state")

        if vals:  # Only write if there are remaining fields
            self.write(vals)

    # === Computed Methods ===
    @api.depends("approval_state", "submitted_date")
    def _compute_pending_since(self):
        for record in self:
            if record.approval_state == "pending":
                record.pending_since = record.submitted_date
            else:
                record.pending_since = False

    def _compute_approval_permissions(self):
        """Compute whether current user can submit/approve/reject."""
        for record in self:
            record.can_submit = record.approval_state == "draft"
            record.can_approve = False
            record.can_reject = False
            _logger.warning(
                "Computing approval permissions for %s %s, state=%s", record._name, record.id, record.approval_state
            )

            if record.approval_state == "pending":
                # Check if user can approve using record-specific definition
                definition = record._resolve_approval_definition()
                _logger.warning(
                    "Approval definition for %s %s: %s (use_multitier=%s)",
                    record._name,
                    record.id,
                    definition,
                    definition.use_multitier if definition else False,
                )
                if definition:
                    if definition.use_multitier:
                        # Multi-tier: check current tier approvers
                        active_review = record.approval_review_ids.filtered(lambda r: r.status == "pending")[:1]
                        _logger.warning(
                            "Multi-tier: active_review found for %s %s: %s (total reviews: %s)",
                            record._name,
                            record.id,
                            bool(active_review),
                            len(record.approval_review_ids),
                        )
                        if active_review:
                            approvers = active_review.get_current_tier_approvers()
                            _logger.warning(
                                "Multi-tier approval check for %s %s: current_tier=%s, "
                                "approvers=%s, user=%s in approvers=%s",
                                record._name,
                                record.id,
                                active_review.current_tier_name,
                                approvers.mapped("name"),
                                self.env.user.name,
                                self.env.user in approvers,
                            )
                        else:
                            approvers = self.env["res.users"]
                            _logger.error("No active review found for multi-tier record %s %s", record._name, record.id)
                    else:
                        # Single-tier: use definition approvers
                        approvers = definition.get_approvers(record)
                        _logger.warning(
                            "Single-tier approval check for %s %s: approvers=%s, user=%s in approvers=%s",
                            record._name,
                            record.id,
                            approvers.mapped("name"),
                            self.env.user.name,
                            self.env.user in approvers,
                        )
                    if self.env.user in approvers:
                        record.can_approve = True
                        record.can_reject = True
                        _logger.warning(
                            "User ID %s can approve/reject %s %s", self.env.user.id, record._name, record.id
                        )
                    else:
                        _logger.warning(
                            "User ID %s cannot approve/reject %s %s - not in approvers list",
                            self.env.user.id,
                            record._name,
                            record.id,
                        )

    # === Action Methods ===
    def action_submit_for_approval(self):
        """Submit the record for approval."""
        for record in self:
            record._check_can_submit()
            record._on_submit()

            # Find applicable definition using record-specific method if available
            definition = record._resolve_approval_definition()

            if not definition:
                raise UserError(_("No approval workflow configured for this record type."))

            # Check system freeze
            if definition.is_respect_system_freeze:
                freeze_status = self.env["spp.approval.freeze"].is_frozen(
                    model_name=record._name,
                    company_id=record.company_id.id if hasattr(record, "company_id") else None,
                )
                if freeze_status["frozen"]:
                    raise UserError(_("Approvals are currently frozen: %s") % freeze_status["reason"])

            # Check auto-approve
            if definition.auto_approve_same_user:
                approvers = definition.get_approvers(record)
                if self.env.user in approvers:
                    record._do_approve(auto=True)
                    return

            # Create review record (sudo because it's system-managed)
            review = (
                self.env["spp.approval.review"]
                .sudo()
                .create(
                    {
                        "model": record._name,
                        "res_id": record.id,
                        "definition_id": definition.id,
                        "requested_by_id": self.env.user.id,
                        "requested_date": fields.Datetime.now(),
                    }
                )
            )

            # Update record state
            record._write_approval_fields(
                {
                    "approval_state": "pending",
                    "submitted_by_id": self.env.user.id,
                    "submitted_date": fields.Datetime.now(),
                }
            )

            # Create activity for approvers
            if definition.notify_on_submit:
                record._create_approval_activity(definition, review)

            record._after_submit()

    def action_approve(self, comment=None):
        """Approve the record."""
        for record in self:
            record._check_can_approve()
            record._do_approve(comment=comment)

    def _do_approve(self, comment=None, auto=False):
        """Internal method to perform approval."""
        self.ensure_one()

        # Check if approval_state is stored in the database
        is_stored = self._is_approval_state_stored()

        # Optimistic locking with savepoint
        current_version = self.approval_version

        if is_stored:
            # SQL approach for stored approval_state (with optimistic locking)
            with self.env.cr.savepoint():
                # Use psycopg2.sql for safe table name handling
                query = psycopg2_sql.SQL("""
                    UPDATE {}
                    SET approval_state = 'approved',
                        approved_by_id = %s,
                        approved_date = NOW(),
                        approval_version = approval_version + 1
                    WHERE id = %s
                      AND approval_state = 'pending'
                      AND approval_version = %s
                    RETURNING id
                """).format(psycopg2_sql.Identifier(self._table))
                self.env.cr.execute(
                    query,
                    (self.env.user.id, self.id, current_version),
                )

                if not self.env.cr.fetchone():
                    raise UserError(_("This record was modified by another user. " "Please refresh and try again."))
        else:
            # ORM approach for computed/non-stored approval_state
            # Verify the record is in pending state (via computed field)
            if self.approval_state != "pending":
                raise UserError(_("Only pending records can be approved."))

            # Only update audit fields and version; let subclass handle state transition
            with self.env.cr.savepoint():
                query = psycopg2_sql.SQL("""
                    UPDATE {}
                    SET approved_by_id = %s,
                        approved_date = NOW(),
                        approval_version = approval_version + 1
                    WHERE id = %s
                      AND approval_version = %s
                    RETURNING id
                """).format(psycopg2_sql.Identifier(self._table))
                self.env.cr.execute(
                    query,
                    (self.env.user.id, self.id, current_version),
                )

                if not self.env.cr.fetchone():
                    raise UserError(_("This record was modified by another user. " "Please refresh and try again."))

        # Invalidate cache
        self.invalidate_recordset()

        # Update pending reviews
        pending_reviews = self.approval_review_ids.filtered(lambda r: r.status == "pending")
        pending_reviews.action_approve(comment=comment)

        # Complete activity
        self.activity_feedback(
            ["spp_approval.mail_activity_approval_required"],
            feedback=comment or _("Approved%s") % (" (auto)" if auto else ""),
        )

        # Hook for custom logic
        self._on_approve()

        # Notify submitter
        if not auto:
            self._notify_approval_result("approved")

    def action_reject(self):
        """Open rejection wizard."""
        self.ensure_one()
        self._check_can_reject()

        return {
            "name": _("Reject"),
            "type": "ir.actions.act_window",
            "res_model": "spp.approval.rejection.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_res_model": self._name,
                "default_res_id": self.id,
            },
        }

    def _do_reject(self, reason):
        """Internal method to perform rejection."""
        self.ensure_one()

        self._write_approval_fields(
            {
                "approval_state": "rejected",
                "rejected_by_id": self.env.user.id,
                "rejected_date": fields.Datetime.now(),
                "rejection_reason": reason,
            }
        )

        # Update pending reviews
        pending_reviews = self.approval_review_ids.filtered(lambda r: r.status == "pending")
        pending_reviews.action_reject(comment=reason)

        # Complete activity
        self.activity_feedback(
            ["spp_approval.mail_activity_approval_required"],
            feedback=reason or _("Rejected"),
        )

        # Hook for custom logic
        self._on_reject(reason)

        # Notify submitter
        self._notify_approval_result("rejected", reason)

    def action_reset_to_draft(self):
        """Reset rejected or revision-requested record to draft."""
        for record in self:
            if record.approval_state not in ("rejected", "revision"):
                raise UserError(_("Only rejected or revision-requested records can be reset to draft."))

            record._write_approval_fields(
                {
                    "approval_state": "draft",
                    "rejected_by_id": False,
                    "rejected_date": False,
                    "rejection_reason": False,
                    "revision_requested_by_id": False,
                    "revision_requested_date": False,
                    "revision_notes": False,
                }
            )

            record._on_reset_to_draft()

    def action_request_revision(self):
        """Open revision request wizard."""
        self.ensure_one()
        self._check_can_reject()  # Same permissions as rejection

        return {
            "name": _("Request Revision"),
            "type": "ir.actions.act_window",
            "res_model": "spp.approval.revision.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_res_model": self._name,
                "default_res_id": self.id,
            },
        }

    def _do_request_revision(self, notes):
        """Internal method to request revision."""
        self.ensure_one()

        # Check permissions (same as rejection)
        self._check_can_reject()

        self._write_approval_fields(
            {
                "approval_state": "revision",
                "revision_requested_by_id": self.env.user.id,
                "revision_requested_date": fields.Datetime.now(),
                "revision_notes": notes,
            }
        )

        # Update pending reviews - mark as rejected since revision is requested
        pending_reviews = self.approval_review_ids.filtered(lambda r: r.status == "pending")
        if pending_reviews:
            pending_reviews.write({"status": "rejected"})

        # Complete activity
        self.activity_feedback(
            ["spp_approval.mail_activity_approval_required"],
            feedback=_("Revision requested: %s") % (notes or ""),
        )

        # Hook for custom logic
        self._on_request_revision(notes)

        # Notify submitter
        self._notify_approval_result("revision", notes)

    # === Validation Methods ===
    def _check_can_submit(self):
        """Check if current user can submit."""
        self.ensure_one()
        if self.approval_state != "draft":
            raise UserError(_("Only draft records can be submitted for approval."))

    def _check_can_approve(self):
        """Check if current user can approve."""
        self.ensure_one()
        _logger.warning(
            "_check_can_approve called for %s %s by user %s, state=%s",
            self._name,
            self.id,
            self.env.user.name,
            self.approval_state,
        )
        if self.approval_state != "pending":
            raise UserError(_("Only pending records can be approved."))
        self._compute_approval_permissions()
        _logger.warning("_check_can_approve result for %s %s: can_approve=%s", self._name, self.id, self.can_approve)

        # Check for data consistency
        pending_reviews = self.approval_review_ids.filtered(lambda r: r.status == "pending")
        if self.approval_state == "pending" and not pending_reviews:
            # Gather diagnostic info
            all_reviews = self.approval_review_ids
            review_info = (
                ", ".join(f"Review {r.id}: status={r.status}" for r in all_reviews)
                if all_reviews
                else "No reviews found"
            )

            _logger.error(
                "Data inconsistency detected: %s %s (name=%s) has approval_state='pending' "
                "but no pending approval reviews. Total reviews: %d. Reviews: [%s]",
                self._name,
                self.id,
                getattr(self, "name", "N/A"),
                len(all_reviews),
                review_info,
            )
            raise UserError(
                _(
                    "This record has inconsistent approval data.\n\n"
                    "Details:\n"
                    "- Record: %(model)s #%(id)s (%(name)s)\n"
                    "- State: %(state)s\n"
                    "- Reviews found: %(review_count)d\n"
                    "- Review details: %(review_info)s\n\n"
                    "Please reset to draft and re-submit for approval, "
                    "or contact your administrator."
                )
                % {
                    "model": self._name,
                    "id": self.id,
                    "name": getattr(self, "name", "N/A"),
                    "state": self.approval_state,
                    "review_count": len(all_reviews),
                    "review_info": review_info or "None",
                }
            )

        if not self.can_approve:
            # Get the approver group name for a better error message
            definition = self._resolve_approval_definition()
            group_name = _("Unknown Group")

            if definition:
                if definition.use_multitier:
                    # Multi-tier: get current tier's group
                    active_review = self.approval_review_ids.filtered(lambda r: r.status == "pending")[:1]
                    if (
                        active_review
                        and active_review.current_tier_id
                        and active_review.current_tier_id.approval_group_id
                    ):
                        group_name = active_review.current_tier_id.approval_group_id.name
                elif definition.approval_group_id:
                    # Single-tier: show the approver group
                    group_name = definition.approval_group_id.name

            raise UserError(
                _(
                    "You are not authorized to approve this record.\n\n"
                    "Only users in the following group(s) can approve:\n%(groups)s"
                )
                % {
                    "groups": group_name,
                }
            )

    def _check_can_reject(self):
        """Check if current user can reject."""
        self.ensure_one()
        if self.approval_state != "pending":
            raise UserError(_("Only pending records can be rejected."))
        if not self.can_reject:
            raise UserError(_("You are not authorized to reject this record."))

    # === Hook Methods (Override in subclasses) ===
    def _get_approval_definition(self):
        """Get the approval definition for this record.

        Override this method to provide record-specific approval definitions.
        For example, Change Requests override this to return the definition
        configured on their CR Type.

        Returns:
            spp.approval.definition record or None
        """
        return None

    def _resolve_approval_definition(self):
        """Resolve which approval definition applies to this record.

        First checks if the model provides a specific definition via
        _get_approval_definition(). If not, falls back to model-based lookup.

        Returns:
            spp.approval.definition record or None
        """
        self.ensure_one()

        # First, try record-specific definition (e.g., CR Type's definition)
        definition = self._get_approval_definition()  # pylint: disable=assignment-from-none
        if definition:
            return definition

        # Fall back to model-based lookup
        definitions = self.env["spp.approval.definition"].get_definitions_for_model(
            self._name, self.company_id.id if hasattr(self, "company_id") else None
        )

        for d in definitions:
            if d.matches_record(self):
                return d

        return None

    def _on_submit(self):
        """Called before submitting for approval. Override for validation."""
        pass

    def _after_submit(self):
        """Called after successful submission. Override for post-submit logic."""
        pass

    def _on_approve(self):
        """Called after approval. Override for post-approval logic."""
        pass

    def _on_reject(self, reason):
        """Called after rejection. Override for post-rejection logic."""
        pass

    def _on_request_revision(self, notes):
        """Called after revision request. Override for custom handling."""
        pass

    def _on_reset_to_draft(self):
        """Called after resetting to draft. Override for cleanup logic."""
        pass

    # === Helper Methods ===
    def _create_approval_activity(self, definition, review):
        """Create mail activity for approvers."""
        self.ensure_one()

        approvers = definition.get_approvers(self)
        if not approvers:
            return

        activity_type = self.env.ref(
            "spp_approval.mail_activity_approval_required",
            raise_if_not_found=False,
        )
        if not activity_type:
            return

        for user in approvers:
            deadline = fields.Date.today()
            if definition.sla_days:
                deadline = fields.Date.add(deadline, days=definition.sla_days)

            self.activity_schedule(
                "spp_approval.mail_activity_approval_required",
                user_id=user.id,
                date_deadline=deadline,
                summary=_("Approval Required: %s") % self.display_name,
            )

    def _notify_approval_result(self, result, reason=None):
        """Notify submitter of approval result."""
        self.ensure_one()

        if not self.submitted_by_id:
            return

        if result == "approved":
            subject = _("Approved: %s") % self.display_name
            body = _("Your request has been approved by %s.") % self.env.user.name
        else:
            subject = _("Rejected: %s") % self.display_name
            body = _("Your request has been rejected by %s.") % self.env.user.name
            if reason:
                body += _("\n\nReason: %s") % reason

        self.message_notify(
            partner_ids=self.submitted_by_id.partner_id.ids,
            subject=subject,
            body=body,
        )

    # === Batch Operations ===
    @api.model
    def action_approve_batch(self, record_ids, comment=None):
        """Approve multiple records at once.

        Args:
            record_ids: List of record IDs to approve
            comment: Optional approval comment

        Returns:
            dict with approved_count
        """
        records = self.browse(record_ids).exists()
        approved_count = 0

        for record in records:
            try:
                if record.can_approve:
                    record._do_approve(comment=comment)
                    approved_count += 1
            except UserError:
                continue

        return {"approved_count": approved_count}
