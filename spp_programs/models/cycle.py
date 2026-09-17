# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json
import logging

from lxml import etree
from num2words import num2words

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from . import constants

_logger = logging.getLogger(__name__)


class SPPCycle(models.Model):
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "spp.approval.mixin",
        "spp.job.relate.mixin",
        "spp.refreshable.mixin",
        # "disable.edit.mixin",
    ]
    _name = "spp.cycle"
    _description = "Cycle"
    _order = "sequence asc"
    _check_company_auto = True

    STATE_DRAFT = constants.STATE_DRAFT
    STATE_TO_APPROVE = constants.STATE_TO_APPROVE
    STATE_APPROVED = constants.STATE_APPROVED
    STATE_CANCELED = constants.STATE_CANCELLED
    STATE_DISTRIBUTED = constants.STATE_DISTRIBUTED
    STATE_ENDED = constants.STATE_ENDED
    # DISABLE_EDIT_DOMAIN = [("state", "!=", "draft")]

    # Cached model ID for performance (class-level cache)
    _cycle_model_id_cache = None

    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)

        if view_type == "form":
            # FIX: 'hide_cash' context is not set when form is loaded directly
            # via copy+paste URL in browser.
            # Set all payment management components to invisible
            # if the form was loaded directly via URL.
            if "hide_cash" not in self._context:
                doc = arch
                modifiers = json.dumps({"invisible": True})

                # Buttons may be absent in simplified forms; guard each xpath
                prepare_payment_button = doc.xpath("//button[@name='prepare_payment']")
                if prepare_payment_button:
                    prepare_payment_button[0].set("modifiers", modifiers)

                send_payment_button = doc.xpath("//button[@name='send_payment']")
                if send_payment_button:
                    send_payment_button[0].set("modifiers", modifiers)

                open_payments_form_button = doc.xpath("//button[@name='open_payments_form']")
                if open_payments_form_button:
                    open_payments_form_button[0].set("modifiers", modifiers)

                payment_batches_page = doc.xpath("//page[@name='payment_batches']")
                if payment_batches_page:
                    payment_batches_page[0].set("modifiers", modifiers)

                parser = etree.XMLParser(resolve_entities=False, no_network=True)
                arch = etree.fromstring(etree.tostring(doc, encoding="unicode"), parser=parser)  # nosec B320 — internal view XML with restricted parser (no entities, no network)

        return arch, view

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    program_id = fields.Many2one("spp.program", "Program", required=True)
    sequence = fields.Integer(required=True, readonly=True, default=1)
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    state = fields.Selection(
        [
            (STATE_DRAFT, "Draft"),
            (STATE_TO_APPROVE, "To Approve"),
            (STATE_APPROVED, "Approved"),
            (STATE_DISTRIBUTED, "Distributed"),
            (STATE_CANCELED, "Canceled"),
            (STATE_ENDED, "Ended"),
        ],
        default="draft",
    )

    cycle_membership_ids = fields.One2many("spp.cycle.membership", "cycle_id", "Cycle Memberships")
    entitlement_ids = fields.One2many("spp.entitlement", "cycle_id", "Entitlements")
    payment_batch_ids = fields.One2many("spp.payment.batch", "cycle_id", "Payment Batches")

    # In-kind entitlement fields
    inkind_entitlement_ids = fields.One2many("spp.entitlement.inkind", "cycle_id", "In-Kind Entitlements")
    inkind_entitlements_count = fields.Integer(
        string="# In-kind Entitlements",
        readonly=True,
        compute="_compute_inkind_entitlements_count",
        store=False,
    )

    # Stock Management Fields
    picking_ids = fields.One2many("stock.picking", "cycle_id", string="Stock Transfers")
    # Odoo 19: procurement.group replaced with stock.reference for document linking
    procurement_group_id = fields.Many2one("stock.reference", "Stock Reference")

    validate_async_err = fields.Boolean(default=False)

    previous_cycle_id = fields.Many2one("spp.cycle", "Previous Cycle", readonly=True)
    next_cycle_id = fields.Many2one("spp.cycle", "Next Cycle", readonly=True)

    # Get the auto-approve entitlement setting from the cycle manager
    auto_approve_entitlements = fields.Boolean("Auto-approve entitlements")

    # Statistics
    members_count = fields.Integer(string="# Beneficiaries", readonly=True, compute="_compute_members_count")
    entitlements_count = fields.Integer(string="# Entitlements", readonly=True, compute="_compute_entitlements_count")
    total_entitlements_count = fields.Integer(
        string="# Total Entitlements",
        readonly=True,
        compute="_compute_total_entitlements_count",
        store=False,
    )
    payments_count = fields.Integer(string="# Payments", readonly=True, compute="_compute_payments_count")
    all_members_count = fields.Integer(string="# Enrollments", readonly=True, compute="_compute_all_members_count")

    # Compliance criteria
    allow_filter_compliance_criteria = fields.Boolean(compute="_compute_allow_filter_compliance_criteria")
    compliance_criteria_applied = fields.Boolean(
        string="Compliance Criteria Applied",
        default=False,
        help="Indicates whether compliance criteria filtering has been applied to this cycle.",
    )

    # This is used to prevent any issue while some background tasks are happening
    # such as importing beneficiaries
    is_locked = fields.Boolean(default=False)
    locked_reason = fields.Char()

    total_amount = fields.Float(compute="_compute_total_amount")
    total_amount_in_words = fields.Char(compute="_compute_total_amount_in_words")
    currency_id = fields.Many2one("res.currency", related="program_id.currency_id", store=True, readonly=True)

    show_approve_entitlements_button = fields.Boolean(compute="_compute_show_approve_entitlement")
    can_approve_entitlements = fields.Boolean(
        compute="_compute_can_approve_entitlements",
        string="Can Approve Entitlements",
        help="True if the current user can approve entitlements based on the entitlement approval definition",
    )

    # Approval waiting message for cycle (similar to entitlements)
    show_approval_waiting_message = fields.Boolean(
        compute="_compute_approval_waiting_message",
        string="Show Approval Waiting Message",
    )
    approval_waiting_message = fields.Html(
        compute="_compute_approval_waiting_message",
        string="Approval Waiting Message",
    )

    # Payment and distribution visibility
    has_payment_manager = fields.Boolean(
        compute="_compute_has_payment_manager",
        string="Has Payment Manager",
        help="True if the program has a payment manager configured",
    )
    all_entitlements_approved = fields.Boolean(
        compute="_compute_all_entitlements_approved",
        string="All Entitlements Approved",
        help="True if all entitlements have been approved",
    )

    # Entitlement type indicator
    is_cash_entitlement = fields.Boolean(compute="_compute_entitlement_type", string="Is Cash Entitlement", store=False)
    is_inkind_entitlement = fields.Boolean(
        compute="_compute_entitlement_type",
        string="Is In-Kind Entitlement",
        store=False,
    )

    # Fund availability fields for auto-approve cycles
    has_sufficient_funds = fields.Boolean(
        compute="_compute_fund_availability",
        string="Has Sufficient Funds",
    )
    fund_availability_message = fields.Text(
        compute="_compute_fund_availability",
        string="Fund Availability Message",
    )
    available_funds = fields.Monetary(
        compute="_compute_fund_availability",
        currency_field="currency_id",
        string="Available Funds",
    )
    required_funds = fields.Monetary(
        compute="_compute_fund_availability",
        currency_field="currency_id",
        string="Required Funds",
    )

    # Override approval mixin fields to map to existing cycle fields
    approval_state = fields.Selection(
        related=None,  # Override related
        compute="_compute_approval_state",
        store=True,  # Computed from state field
    )

    # Link to approval definition
    cycle_approval_definition_id = fields.Many2one(
        "spp.approval.definition",
        string="Approval Definition",
        compute="_compute_cycle_approval_definition",
        store=False,
    )

    # Keep legacy field names for backward compatibility
    approved_date = fields.Datetime(string="Cycle Approved Date", readonly=True)
    approved_by = fields.Many2one("res.users", string="Cycle Approved By", readonly=True)

    @api.constrains("name", "program_id")
    def _check_unique_name_per_program(self):
        for record in self:
            if record.name and record.program_id:
                existing = self.search(
                    [
                        ("name", "=", record.name),
                        ("program_id", "=", record.program_id.id),
                        ("id", "!=", record.id),
                    ],
                    limit=1,
                )
                if existing:
                    raise ValidationError(_("Cycle with this name already exists. Please choose a different name."))

    @api.depends("entitlement_ids")
    def _compute_total_amount(self):
        if not self.ids:
            for rec in self:
                rec.total_amount = 0
            return
        self.env.cr.execute(
            """
            SELECT cycle_id, COALESCE(SUM(initial_amount), 0)
            FROM spp_entitlement
            WHERE cycle_id IN %s
            GROUP BY cycle_id
            """,
            (tuple(self.ids),),
        )
        totals = dict(self.env.cr.fetchall())
        for rec in self:
            rec.total_amount = totals.get(rec.id, 0)

    @api.depends("total_amount", "currency_id")
    def _compute_total_amount_in_words(self):
        for record in self:
            if record.total_amount and record.currency_id:
                lang_code = (self.env.context.get("lang") or self.env.user.lang or "en_US").split("_")[0]
                try:
                    amount_in_words = num2words(record.total_amount, lang=lang_code).title()
                except NotImplementedError:
                    amount_in_words = num2words(record.total_amount, lang="en").title()
                record.total_amount_in_words = f"{amount_in_words} {record.currency_id.name}"
            else:
                record.total_amount_in_words = ""

    def _compute_members_count(self):
        for rec in self:
            domain = rec._get_beneficiaries_domain(["enrolled"])
            members_count = self.env["spp.cycle.membership"].search_count(domain)
            rec.update({"members_count": members_count})

    def _compute_entitlements_count(self):
        for rec in self:
            entitlements_count = self.env["spp.entitlement"].search_count([("cycle_id", "=", rec.id)])
            rec.entitlements_count = entitlements_count

    def refresh_statistics(self):
        """Refresh all cycle statistics after bulk operations.

        Call this after raw SQL inserts that bypass ORM dependency tracking
        (e.g. bulk_create_memberships with skip_duplicates=True).
        """
        self._compute_members_count()
        self._compute_entitlements_count()
        self._compute_total_entitlements_count()

    @api.depends("entitlement_ids", "inkind_entitlement_ids")
    def _compute_total_entitlements_count(self):
        if not self.ids:
            for rec in self:
                rec.total_entitlements_count = 0
            return
        cycle_ids = tuple(self.ids)
        self.env.cr.execute(
            """
            SELECT cycle_id, COUNT(*)
            FROM spp_entitlement
            WHERE cycle_id IN %s
            GROUP BY cycle_id
            """,
            (cycle_ids,),
        )
        cash_counts = dict(self.env.cr.fetchall())
        self.env.cr.execute(
            """
            SELECT cycle_id, COUNT(*)
            FROM spp_entitlement_inkind
            WHERE cycle_id IN %s
            GROUP BY cycle_id
            """,
            (cycle_ids,),
        )
        inkind_counts = dict(self.env.cr.fetchall())
        for rec in self:
            rec.total_entitlements_count = cash_counts.get(rec.id, 0) + inkind_counts.get(rec.id, 0)

    def _compute_payments_count(self):
        for rec in self:
            payments_count = self.env["spp.payment"].search_count([("cycle_id", "=", rec.id)])
            rec.update({"payments_count": payments_count})

    @api.depends("entitlement_ids.state", "inkind_entitlement_ids.state")
    def _compute_show_approve_entitlement(self):
        """Show the 'Validate Entitlements' button when there are entitlements pending validation."""
        if not self.ids:
            for rec in self:
                rec.show_approve_entitlements_button = False
            return
        cycle_ids = tuple(self.ids)
        self.env.cr.execute(
            """
            SELECT DISTINCT cycle_id FROM spp_entitlement
            WHERE cycle_id IN %s AND state = 'pending_validation'
            UNION
            SELECT DISTINCT cycle_id FROM spp_entitlement_inkind
            WHERE cycle_id IN %s AND state = 'pending_validation'
            """,
            (cycle_ids, cycle_ids),
        )
        pending_cycle_ids = {row[0] for row in self.env.cr.fetchall()}
        for rec in self:
            rec.show_approve_entitlements_button = rec.id in pending_cycle_ids

    @api.depends("program_id", "entitlement_ids.state", "inkind_entitlement_ids.state")
    def _compute_can_approve_entitlements(self):
        """Check if current user can approve entitlements based on the entitlement approval definition."""
        for rec in self:
            rec.can_approve_entitlements = False
            if not rec.program_id:
                continue

            # Get the entitlement manager to find the approval definition
            entitlement_manager = rec.program_id.get_manager(constants.MANAGER_ENTITLEMENT)
            if not entitlement_manager or not entitlement_manager.approval_definition_id:
                # No approval definition means anyone with the right groups can approve
                rec.can_approve_entitlements = True
                continue

            definition = entitlement_manager.approval_definition_id
            user = self.env.user

            # Get pending entitlements (both cash and in-kind)
            pending_entitlements = rec.entitlement_ids.filtered(lambda e: e.state == "pending_validation")
            pending_inkind = rec.inkind_entitlement_ids.filtered(lambda e: e.state == "pending_validation")

            if not pending_entitlements and not pending_inkind:
                # No pending entitlements, nothing to approve
                continue

            # Check if user can approve based on the approval definition
            if definition.use_multitier:
                # For multi-tier, check the current tier from pending entitlements' approval reviews
                all_pending = pending_entitlements | pending_inkind
                for entitlement in all_pending:
                    # Get the pending review for this entitlement
                    pending_review = entitlement.approval_review_ids.filtered(lambda r: r.status == "pending")[:1]
                    if pending_review and pending_review.current_tier_id:
                        # Check if user is in the current tier's approval group
                        current_tier = pending_review.current_tier_id
                        if current_tier.approval_group_id and user in current_tier.approval_group_id.user_ids:
                            rec.can_approve_entitlements = True
                            break
            else:
                # Single-tier: check the main approval group
                if definition.approval_group_id and user in definition.approval_group_id.user_ids:
                    rec.can_approve_entitlements = True

    @api.depends("state", "can_approve", "can_reject", "cycle_approval_definition_id")
    def _compute_approval_waiting_message(self):
        """Compute approval waiting message visibility and content for cycles."""
        for record in self:
            # Show waiting message only if to_approve and user cannot approve or reject
            if record.state == "to_approve" and not record.can_approve and not record.can_reject:
                record.show_approval_waiting_message = True

                # Build the message based on cycle approval definition
                definition = record.cycle_approval_definition_id
                if definition:
                    if definition.use_multitier:
                        # For multi-tier, get the current tier from pending approval review
                        pending_review = record.approval_review_ids.filtered(lambda r: r.status == "pending")[:1]
                        if pending_review and pending_review.current_tier_id:
                            current_tier = pending_review.current_tier_id
                            if current_tier.approval_group_id:
                                record.approval_waiting_message = (
                                    _("Waiting for approval from members of the <b>%s</b> security group.")
                                    % current_tier.approval_group_id.display_name
                                )
                            else:
                                record.approval_waiting_message = _("Waiting for approval from designated approver.")
                        else:
                            record.approval_waiting_message = _("Waiting for approval.")
                    elif definition.approval_type == "group" and definition.approval_group_id:
                        record.approval_waiting_message = (
                            _("Waiting for approval from members of the <b>%s</b> security group.")
                            % definition.approval_group_id.display_name
                        )
                    elif definition.approval_type == "user" and definition.approval_user_ids:
                        user_names = ", ".join(definition.approval_user_ids.mapped("name"))
                        record.approval_waiting_message = (
                            _("Waiting for approval from specific users: <b>%s</b>") % user_names
                        )
                    else:
                        record.approval_waiting_message = _("Waiting for approval from designated approver.")
                else:
                    record.approval_waiting_message = _("Waiting for approval.")
            else:
                record.show_approval_waiting_message = False
                record.approval_waiting_message = False

    @api.depends("program_id")
    def _compute_has_payment_manager(self):
        """Check if the program has a payment manager configured."""
        for rec in self:
            payment_manager = rec.program_id.get_manager(constants.MANAGER_PAYMENT) if rec.program_id else False
            rec.has_payment_manager = bool(payment_manager)

    @api.depends("entitlement_ids.state", "inkind_entitlement_ids.state")
    def _compute_all_entitlements_approved(self):
        """Check if all entitlements have been approved."""
        if not self.ids:
            for rec in self:
                rec.all_entitlements_approved = False
            return
        cycle_ids = tuple(self.ids)
        # Find cycles that have at least one entitlement (cash or inkind)
        self.env.cr.execute(
            """
            SELECT DISTINCT cycle_id FROM spp_entitlement
            WHERE cycle_id IN %s
            UNION
            SELECT DISTINCT cycle_id FROM spp_entitlement_inkind
            WHERE cycle_id IN %s
            """,
            (cycle_ids, cycle_ids),
        )
        cycles_with_entitlements = {row[0] for row in self.env.cr.fetchall()}
        # Find cycles that have any non-approved entitlement
        self.env.cr.execute(
            """
            SELECT DISTINCT cycle_id FROM spp_entitlement
            WHERE cycle_id IN %s AND state IS DISTINCT FROM 'approved'
            UNION
            SELECT DISTINCT cycle_id FROM spp_entitlement_inkind
            WHERE cycle_id IN %s AND state IS DISTINCT FROM 'approved'
            """,
            (cycle_ids, cycle_ids),
        )
        cycles_with_unapproved = {row[0] for row in self.env.cr.fetchall()}
        for rec in self:
            if rec.id not in cycles_with_entitlements:
                rec.all_entitlements_approved = False
            else:
                rec.all_entitlements_approved = rec.id not in cycles_with_unapproved

    @api.depends("program_id")
    def _compute_entitlement_type(self):
        """Determine if program uses cash or in-kind entitlements."""
        for rec in self:
            rec.is_cash_entitlement = False
            rec.is_inkind_entitlement = False

            if rec.program_id:
                entitlement_manager = rec.program_id.get_manager(constants.MANAGER_ENTITLEMENT)
                if entitlement_manager:
                    if entitlement_manager.IS_CASH_ENTITLEMENT:
                        rec.is_cash_entitlement = True
                    else:
                        rec.is_inkind_entitlement = True

    @api.depends(
        "auto_approve_entitlements",
        "entitlement_ids.initial_amount",
        "entitlement_ids.state",
        "state",
        "program_id",
    )
    def _compute_fund_availability(self):
        """Compute fund availability for cycles with pending entitlements."""
        for rec in self:
            # Default values
            rec.has_sufficient_funds = True
            rec.fund_availability_message = ""
            rec.available_funds = 0.0
            rec.required_funds = 0.0

            # Check funds when cycle is in to_approve OR approved state with pending entitlements
            if rec.state not in ("to_approve", "approved"):
                continue

            # Get entitlement manager
            entitlement_manager = rec.program_id.get_manager(constants.MANAGER_ENTITLEMENT)
            if not entitlement_manager or not entitlement_manager.IS_CASH_ENTITLEMENT:
                continue

            # Get pending entitlements
            entitlements = rec.get_entitlements(["draft", "pending_validation"], entitlement_model="spp.entitlement")
            if not entitlements:
                # No entitlements, no message needed
                continue

            # Calculate required funds
            required_funds = sum(entitlements.mapped("initial_amount"))
            rec.required_funds = required_funds

            # Get available funds
            available_funds = entitlement_manager.check_fund_balance(rec.program_id.id)
            rec.available_funds = available_funds

            # Check if sufficient
            if available_funds < required_funds:
                rec.has_sufficient_funds = False
                shortage = required_funds - available_funds
                if rec.auto_approve_entitlements:
                    # Auto-approve enabled: both entitlements and cycle approval blocked
                    rec.fund_availability_message = _(
                        "Insufficient funds to approve entitlements and cycle.\n"
                        "Available: %(available).2f | Required: %(required).2f | Shortage: %(shortage).2f"
                    ) % {
                        "available": available_funds,
                        "required": required_funds,
                        "shortage": shortage,
                    }
                else:
                    # Manual approval: only entitlement approval blocked
                    rec.fund_availability_message = _(
                        "Insufficient funds to approve entitlements.\n"
                        "Available: %(available).2f | Required: %(required).2f | Shortage: %(shortage).2f"
                    ) % {
                        "available": available_funds,
                        "required": required_funds,
                        "shortage": shortage,
                    }
            else:
                rec.has_sufficient_funds = True
                surplus = available_funds - required_funds
                rec.fund_availability_message = _(
                    "Sufficient funds available for approving entitlements.\n"
                    "Available: %(available).2f | Required: %(required).2f | Remaining: %(surplus).2f"
                ) % {
                    "available": available_funds,
                    "required": required_funds,
                    "surplus": surplus,
                }

    @api.model
    def _get_cycle_model_id(self):
        """Get cached ir.model ID for spp.cycle."""
        if SPPCycle._cycle_model_id_cache is None:
            model = self.env["ir.model"].search([("model", "=", "spp.cycle")], limit=1)
            SPPCycle._cycle_model_id_cache = model.id if model else False
        return SPPCycle._cycle_model_id_cache

    @api.depends("program_id")
    def _compute_cycle_approval_definition(self):
        """Get the approval definition for cycles."""
        for record in self:
            manager = record.program_id.get_manager(constants.MANAGER_CYCLE) if record.program_id else False
            record.cycle_approval_definition_id = manager.approval_definition_id if manager else False

    @api.depends("state")
    def _compute_approval_state(self):
        """Map cycle state to approval mixin state."""
        state_map = {
            "draft": "draft",
            "to_approve": "pending",
            "approved": "approved",
            "distributed": "approved",
            "cancelled": "rejected",
            "ended": "approved",
        }
        for record in self:
            record.approval_state = state_map.get(record.state, "draft")

    def _compute_approval_permissions(self):
        """Override to include admin users in approval permissions."""
        super()._compute_approval_permissions()

        # Admins can always approve/reject pending cycles
        if self.env.user.has_group("spp_security.group_spp_admin"):
            for record in self:
                if record.approval_state == "pending":
                    record.can_approve = True
                    record.can_reject = True

    def _get_approval_definition(self):
        """Override to return the cycle's approval definition."""
        self.ensure_one()
        return self.cycle_approval_definition_id

    def _notify_thread_by_email(self, message, recipients_data, **kwargs):
        """Suppress outgoing email when the parent program has email
        notifications disabled. Chatter logging and in-app notifications are
        unaffected — only the email dispatch is short-circuited."""
        self.ensure_one()
        if self.program_id and not self.program_id._should_send_email_notifications():
            return
        return super()._notify_thread_by_email(message, recipients_data, **kwargs)

    def _create_approval_activity(self, definition, review):
        """Gate the approver-email path on the parent program's toggle.

        spp.approval.mixin schedules a mail.activity for each approver on
        submit; the activity dispatch sends email through the assignee's
        notification preferences. Skip the scheduling entirely when the
        program has email notifications turned off."""
        self.ensure_one()
        if self.program_id and not self.program_id._should_send_email_notifications():
            return
        return super()._create_approval_activity(definition, review)

    @api.onchange("start_date")
    def on_start_date_change(self):
        self.program_id.get_manager(constants.MANAGER_CYCLE).on_start_date_change(self)

    @api.onchange("state")
    def on_state_change(self):
        self.program_id.get_manager(constants.MANAGER_CYCLE).on_state_change(self)

    def _get_beneficiaries_domain(self, states=None):
        domain = [("cycle_id", "=", self.id)]
        if states:
            domain.append(("state", "in", states))
        return domain

    @api.model
    def get_beneficiaries(
        self, state, offset=0, limit=None, order=None, count=False, last_id=None, min_id=None, max_id=None
    ):
        """
        Get beneficiaries by state with pagination support.

        :param state: State(s) to filter by
        :param offset: Row offset for pagination (WARNING: causes O(n) scaling issues with large datasets)
        :param limit: Maximum number of records to return
        :param order: Sort order
        :param count: If True, return count instead of records
        :param last_id: For cursor-based pagination - ID of last record from previous batch (more efficient)
        :param min_id: For ID-range pagination - minimum record ID (inclusive)
        :param max_id: For ID-range pagination - maximum record ID (inclusive)
        :return: Recordset or count

        Note: For large datasets, prefer min_id/max_id (ID-range) or last_id (cursor)
        pagination over offset-based pagination.
        """
        if isinstance(state, str):
            state = [state]
        for rec in self:
            domain = rec._get_beneficiaries_domain(state)
            if count:
                return self.env["spp.cycle.membership"].search_count(domain, limit=limit)

            # ID-range pagination (best for parallel job dispatch)
            if min_id is not None and max_id is not None:
                domain = domain + [("id", ">=", min_id), ("id", "<=", max_id)]
                return self.env["spp.cycle.membership"].search(domain, order=order or "id")

            # Cursor-based pagination (good for sequential iteration)
            if last_id is not None:
                domain = domain + [("id", ">", last_id)]
                return self.env["spp.cycle.membership"].search(domain, limit=limit, order=order or "id")

            # Fall back to offset-based pagination (less efficient for large datasets)
            return self.env["spp.cycle.membership"].search(domain, offset=offset, limit=limit, order=order)

    def get_entitlements(
        self,
        state,
        entitlement_model="spp.entitlement",
        offset=0,
        limit=None,
        order=None,
        count=False,
        last_id=None,
    ):
        """
        Query entitlements based on state with pagination support.

        :param state: List of states
        :param entitlement_model: String value of entitlement model to search
        :param offset: Optional integer value for the ORM search offset (WARNING: causes O(n) scaling issues)
        :param limit: Optional integer value for the ORM search limit
        :param order: Optional string value for the ORM search order fields
        :param count: Optional boolean for executing a search-count (if true) or search (if false: default)
        :param last_id: For cursor-based pagination - ID of last record from previous batch (more efficient)
        :return: Recordset or count

        Note: For large datasets, use cursor-based pagination with last_id parameter instead of offset.
        """
        domain = [("cycle_id", "=", self.id)]
        if state:
            if isinstance(state, str):
                state = [state]
            domain += [("state", "in", state)]

        if count:
            return self.env[entitlement_model].search_count(domain, limit=limit)

        # Use cursor-based pagination if last_id is provided (more efficient)
        if last_id is not None:
            domain = domain + [("id", ">", last_id)]
            return self.env[entitlement_model].search(domain, limit=limit, order=order or "id")

        # Fall back to offset-based pagination (less efficient for large datasets)
        return self.env[entitlement_model].search(domain, offset=offset, limit=limit, order=order)

    # @api.model
    def copy_beneficiaries_from_program(self):
        # _logger.debug("Copying beneficiaries from program, cycles: %s", cycles)
        self.ensure_one()
        cycle_manager = self.program_id.get_manager(constants.MANAGER_CYCLE)
        if cycle_manager:
            return cycle_manager.copy_beneficiaries_from_program(self)
        else:
            raise UserError(_("No Cycle Manager defined."))

    def check_eligibility(self, beneficiaries=None):
        cycle_manager = self.program_id.get_manager(constants.MANAGER_CYCLE)

        if cycle_manager:
            cycle_manager.check_eligibility(self, beneficiaries)
        else:
            raise UserError(_("No Cycle Manager defined."))

    # === Standardized Approval Workflow Methods ===

    def action_submit_for_approval(self):
        """Submit cycle for approval using standardized workflow."""
        for rec in self:
            if rec.state != self.STATE_DRAFT:
                raise UserError(_("Only draft cycles can be submitted for approval."))

            if rec.is_locked:
                raise UserError(_("Cycle is locked: %(reason)s") % {"reason": rec.locked_reason})

            # Check for both cash and in-kind entitlements
            if not rec.entitlement_ids and not rec.inkind_entitlement_ids:
                raise UserError(_("Cannot submit cycle without entitlements. Please prepare entitlements first."))

            entitlement_manager = rec.program_id.get_manager(constants.MANAGER_ENTITLEMENT)
            if not entitlement_manager:
                raise UserError(_("No Entitlement Manager defined."))

            # Use mixin submission logic if approval definition exists
            definition = rec._get_approval_definition()
            if definition:
                super(SPPCycle, rec).action_submit_for_approval()

            # Transition to to_approve state
            rec.write(
                {
                    "state": self.STATE_TO_APPROVE,
                    "submitted_by_id": self.env.user.id,
                    "submitted_date": fields.Datetime.now(),
                }
            )

            # Set entitlements to pending validation
            entitlement_manager.set_pending_validation_entitlements(rec)

    # Legacy alias for backward compatibility
    def to_approve(self):
        """Legacy method - redirects to action_submit_for_approval."""
        return self.action_submit_for_approval()

    def action_approve(self, comment=None):
        """Approve cycle using standardized workflow."""
        for rec in self:
            if rec.state != self.STATE_TO_APPROVE:
                raise UserError(_("Only cycles pending approval can be approved."))

            # Check permissions FIRST using the approval mixin
            # This will raise an error if the user is not authorized
            definition = rec._get_approval_definition()
            if definition:
                # The mixin's _check_can_approve now includes group info in error message
                rec._check_can_approve()

            cycle_manager = rec.program_id.get_manager(constants.MANAGER_CYCLE)
            if not cycle_manager:
                raise UserError(_("No Cycle Manager defined."))

            entitlement_manager = rec.program_id.get_manager(constants.MANAGER_ENTITLEMENT)
            if not entitlement_manager:
                raise UserError(_("No Entitlement Manager defined."))

            # Call mixin's approval logic (if definition exists)
            # This updates approval_review_ids and records the approval in history
            if definition:
                super(SPPCycle, rec).action_approve(comment=comment)

            # Approve cycle through manager (includes fund check if auto_approve enabled)
            result = cycle_manager.approve_cycle(
                rec,
                auto_approve=rec.auto_approve_entitlements,
                entitlement_manager=entitlement_manager,
            )

            # Check if it's an ERROR notification (danger type) AND cycle was not approved
            # This only happens when fund check fails before cycle approval
            is_error = (
                result
                and isinstance(result, dict)
                and result.get("type") == "ir.actions.client"
                and result.get("params", {}).get("type") == "danger"
                and rec.state != self.STATE_APPROVED
            )

            if is_error:
                # Rollback: Reset approval review records that were updated by the mixin
                # (Cycle state should still be to_approve since fund check failed before cycle approval)
                if definition:
                    rec.approval_review_ids.filtered(lambda r: r.status == "approved").write(
                        {
                            "status": "pending",
                            "reviewer_id": False,
                            "review_date": False,
                        }
                    )

                return result

            return result

    # Legacy alias for backward compatibility
    def approve(self):
        """Legacy method - redirects to action_approve."""
        return self.action_approve()

    def action_reject(self):
        """Reject cycle using standardized workflow."""
        self.ensure_one()

        if self.state != self.STATE_TO_APPROVE:
            raise UserError(_("Only cycles pending approval can be rejected."))

        # Use mixin rejection logic (opens wizard)
        return super().action_reject()

    def _do_reject(self, reason):
        """Execute rejection after wizard confirmation."""
        self.ensure_one()

        # Call parent mixin logic
        super()._do_reject(reason)

        # Transition to cancelled state
        self.write({"state": self.STATE_CANCELED})

        # Also reject all pending entitlements
        entitlements = self.entitlement_ids.filtered(lambda e: e.state == "pending_validation")
        if entitlements:
            entitlements.write({"state": "cancelled"})

    def action_reset_to_draft(self):
        """Reset cycle to draft state."""
        for rec in self:
            if rec.state not in (self.STATE_TO_APPROVE, self.STATE_CANCELED):
                raise UserError(_("Only cycles pending approval or cancelled can be reset to draft."))

            # Use mixin reset logic if in rejected approval_state
            if rec.approval_state == "rejected":
                super(SPPCycle, rec).action_reset_to_draft()

            # Check if existing approval reviews are present
            if rec.approval_review_ids:
                pending_review = rec.approval_review_ids.filtered(lambda r: r.status == "pending")
                pending_review.unlink()
                approval_review = rec.approval_review_ids.filtered(lambda r: r.status == "approved")
                if approval_review:
                    raise UserError(
                        _(
                            "The cycle has existing approved approval reviews. Please reset to "
                            "draft from the approval review."
                        )
                    )

            # Transition to draft state
            rec.write({"state": self.STATE_DRAFT})

            # Reset entitlements too
            entitlements = rec.entitlement_ids.filtered(lambda e: e.state in ("pending_validation", "cancelled"))
            if entitlements:
                entitlements.action_reset_to_draft()

    # Legacy alias for backward compatibility
    def reset_draft(self):
        """Legacy method - redirects to action_reset_to_draft."""
        return self.action_reset_to_draft()

    def notify_cycle_started(self):
        # 1. Notify the beneficiaries using notification_manager.cycle_started()
        pass

    def action_prepare_entitlement(self):
        """Wrapper method for prepare_entitlement that checks compliance criteria first.

        If compliance criteria are enabled but not yet applied, shows a confirmation
        dialog before proceeding. Otherwise, directly calls prepare_entitlement.
        """
        self.ensure_one()

        # Check if compliance criteria are available but not applied
        if self.allow_filter_compliance_criteria and not self.compliance_criteria_applied:
            # Open confirmation wizard
            return {
                "name": _("Prepare Entitlements Confirmation"),
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "spp.prepare.entitlement.confirm.wizard",
                "view_id": self.env.ref("spp_programs.view_spp_prepare_entitlement_confirm_wizard_form").id,
                "target": "new",
                "context": {
                    "default_cycle_id": self.id,
                },
            }

        # No compliance criteria or already applied - proceed directly
        return self.prepare_entitlement()

    def prepare_entitlement(self):
        # 1. Prepare the entitlement of the beneficiaries using entitlement_manager.prepare_entitlements()
        cycle_manager = self.program_id.get_manager(constants.MANAGER_CYCLE)
        if not cycle_manager:
            raise UserError(_("No Cycle Manager defined."))

        return cycle_manager.prepare_entitlements(self)

    def prepare_payment(self):
        # 1. Issue the payment of the beneficiaries using payment_manager.prepare_payments()
        payment_manager = self.program_id.get_manager(constants.MANAGER_PAYMENT)
        if not payment_manager:
            raise UserError(_("No Payment Manager defined."))

        return payment_manager.prepare_payments(self)

    def send_payment(self):
        # 1. Send the payments using payment_manager.send_payments()
        payment_manager = self.program_id.get_manager(constants.MANAGER_PAYMENT)
        if not payment_manager:
            raise UserError(_("No Payment Manager defined."))

        return payment_manager.send_payments(self.payment_batch_ids)

    def mark_distributed(self):
        # 1. Mark the cycle as distributed using the cycle manager
        self.program_id.get_manager(constants.MANAGER_CYCLE).mark_distributed(self)

    def mark_ended(self):
        # 1. Mark the cycle as ended using the cycle manager
        self.program_id.get_manager(constants.MANAGER_CYCLE).mark_ended(self)

    def mark_cancelled(self):
        # 1. Mark the cycle as cancelled using the cycle manager
        self.program_id.get_manager(constants.MANAGER_CYCLE).mark_cancelled(self)

    def validate_entitlement(self):
        # 1. Make sure the user has the right to do this
        # 2. Validate the entitlement of the beneficiaries using entitlement_manager.validate_entitlements()
        entitlement_manager = self.program_id.get_manager(constants.MANAGER_ENTITLEMENT)
        if not entitlement_manager:
            raise UserError(_("No Entitlement Manager defined."))

        return entitlement_manager.validate_entitlements(self)

    def reject_all_entitlements(self):
        """Open wizard to reject all pending entitlements in the cycle."""
        self.ensure_one()

        # Get pending entitlements
        entitlements = self.entitlement_ids.filtered(lambda e: e.state in ("draft", "pending_validation"))
        inkind_entitlements = self.inkind_entitlement_ids.filtered(lambda e: e.state in ("draft", "pending_validation"))

        if not entitlements and not inkind_entitlements:
            raise UserError(_("No entitlements to reject. All entitlements are already processed."))

        # Open wizard for cash entitlements (primary)
        if entitlements:
            return {
                "name": _("Reject All Entitlements"),
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "spp.reject.entitlement.wizard",
                "view_id": self.env.ref("spp_programs.reject_entitlement_wizard").id,
                "target": "new",
                "context": {
                    "active_ids": entitlements.ids,
                    "to_state": "reject",
                },
            }
        # For in-kind entitlements
        elif inkind_entitlements:
            return {
                "name": _("Reject All In-Kind Entitlements"),
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "spp.reject.inkind.entitlement.wizard",
                "view_id": self.env.ref("spp_programs.reject_inkind_entitlement_wizard").id,
                "target": "new",
                "context": {
                    "active_ids": inkind_entitlements.ids,
                    "to_state": "reject",
                },
            }

    def export_distribution_list(self):
        # Not sure if this should be here.
        # It could be customizable reports based on https://github.com/OCA/reporting-engine
        pass

    def duplicate(self, new_start_date):
        # 1. Make sure the user has the right to do this
        # 2. Copy the cycle using the cycle manager
        pass

    def open_cycle_form(self):
        entitlement_manager = self.program_id.get_manager(constants.MANAGER_ENTITLEMENT)
        payment_manager = self.program_id.get_manager(constants.MANAGER_PAYMENT)
        hide_cash = False if entitlement_manager and entitlement_manager.IS_CASH_ENTITLEMENT else True
        if not payment_manager:
            hide_cash = True

        # Use stored action for proper URL/refresh handling
        action = self.env.ref("spp_programs.action_cycle_list").sudo().read()[0]  # nosemgrep: odoo-sudo-without-context
        action.update(
            {
                "name": self.name,
                "view_mode": "form",
                "views": [[self.env.ref("spp_programs.view_cycle_form").id, "form"]],
                "res_id": self.id,
                "context": {"hide_cash": hide_cash},
                "target": "current",
            }
        )
        return action

    def open_entitlements_form(self):
        entitlement_manager = self.program_id.get_manager(constants.MANAGER_ENTITLEMENT)
        if entitlement_manager:
            return entitlement_manager.open_entitlements_form(self)
        else:
            raise UserError(_("No Entitlement Manager defined."))

    def open_payments_form(self):
        self.ensure_one()

        action = {
            "name": _("Payments"),
            "type": "ir.actions.act_window",
            "res_model": "spp.payment",
            "context": {
                "create": False,
            },
            "view_mode": "list,form",
            "domain": [("entitlement_id", "in", self.entitlement_ids.ids)],
        }
        return action

    def _get_related_job_domain(self):
        jobs = self.env["queue.job"].search([("model_name", "like", self._name)])
        related_jobs = jobs.filtered(lambda r: self in r.args[0])
        return [("id", "in", related_jobs.ids)]

    def _assert_operation_lock_writable(self, vals):
        """Reject out-of-band changes to the operation lock fields.

        ``is_locked`` / ``locked_reason`` form an operation lock protecting
        in-flight async pipelines (entitlement, payment, eligibility). Clearing
        or setting it out of band lets conflicting operations run, so direct
        changes to these fields are restricted to system administrators. The
        pipeline manages the lock through ``_acquire_operation_lock`` /
        ``_release_operation_lock`` (which ``sudo()``), and Force Unlock is the
        admin-only manual override.

        Enforced on create as well as write: a record created already locked
        would otherwise skip the guard entirely, and its creator could not
        clear the lock afterwards without a system administrator.
        """
        if self.env.su:
            return
        if "is_locked" not in vals and "locked_reason" not in vals:
            return
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(
                _(
                    "Changing the operation lock is restricted to system "
                    "administrators. The lock is managed automatically by "
                    "the async pipeline; use Force Unlock only in an emergency."
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._assert_operation_lock_writable(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._assert_operation_lock_writable(vals)
        return super().write(vals)

    # NOTE(#337): these helpers sudo the lock write, so any PUBLIC method that
    # calls them (e.g. the async mark_*_as_done / mark_*_as_failed completion
    # callbacks) is an RPC-reachable lock-clearing path that the write() guard
    # above does not cover. Closing that needs authorization on those
    # callbacks and is tracked separately in issue #337.
    def _acquire_operation_lock(self, reason):
        """Set the async-operation lock. Written via ``sudo()`` because direct
        writes to ``is_locked`` / ``locked_reason`` are restricted to system
        administrators (see ``write``); the pipeline runs as the initiating
        non-admin user and must bypass that guard for the two lock fields only."""
        # nosemgrep: odoo-sudo-without-context - lock fields admin-write-only (see write()); sudo scoped
        self.sudo().write({"is_locked": True, "locked_reason": reason})

    def _release_operation_lock(self):
        """Clear the async-operation lock (see ``_acquire_operation_lock``)."""
        # nosemgrep: odoo-sudo-without-context - lock fields admin-write-only (see write()); sudo scoped
        self.sudo().write({"is_locked": False, "locked_reason": False})

    def action_force_unlock(self):
        """System-administrator-only escape hatch: clear a stuck "Operation
        in progress" lock.

        Use when an async pipeline (entitlement processing, payment prep, etc.)
        died without firing its on_done/on_error callback — for example after
        a hard server restart or before this fix was deployed. Posts an audit
        line to chatter so admins can see who unstuck the cycle.

        The view button is gated to base.group_system, but object methods are
        reachable via RPC regardless of button visibility, so the same
        restriction is enforced here: clearing an active operation lock while
        jobs may still be running is an emergency control reserved for system
        administrators. Trusted server-side sudo() flows are exempt.
        """
        if not self.env.su and not self.env.user.has_group("base.group_system"):
            raise AccessError(
                _(
                    "Force unlock is restricted to system administrators. It is an "
                    "emergency control for clearing a stuck operation lock; ask a "
                    "system administrator to confirm the async job has actually "
                    "stopped before the lock is cleared."
                )
            )
        for rec in self:
            if not rec.is_locked:
                continue
            previous_reason = rec.locked_reason
            rec.write({"is_locked": False, "locked_reason": False})
            rec.message_post(
                body=_(
                    "Lock manually cleared by %(user)s. Previous reason: %(reason)s",
                    user=self.env.user.display_name,
                    reason=previous_reason or _("(none)"),
                )
            )

    def unlink(self):
        # Admin also not able to delete the cycle bcz of beneficiaries mapped
        # So this function common for who are all having delete access.

        # TODO: Need to add the below logic for group based unlink options if necessary
        # user = self.env.user
        # group_spp_admin = user.has_group("spp_security.group_spp_admin")
        # spp_program_manager = user.has_group("spp_programs.group_programs_manager")
        # if group_spp_admin:
        #     return super().unlink()

        if self:
            draft_records = self.filtered(lambda x: x.state == "draft")

            if draft_records:
                if any(record.entitlement_ids.filtered(lambda e: e.state == "approved") for record in draft_records):
                    raise ValidationError(_("A cycle for which entitlements have been approved cannot be deleted."))
                elif all(record.entitlement_ids.filtered(lambda e: e.state == "draft") for record in draft_records):
                    raise ValidationError(_("Cycle cannot be deleted when Entitlements have been added to the cycle."))
                elif draft_records.mapped("cycle_membership_ids"):
                    raise ValidationError(_("Cycle cannot be deleted when beneficiaries are present in the cycle."))

                draft_records.mapped("cycle_membership_ids").unlink()
                return super().unlink()
            else:
                raise ValidationError(_("Once a cycle has been approved, it cannot be deleted."))

        raise ValidationError(_("Delete only draft cycles with no approved entitlements."))

    def generate_summary(self):
        return self.env.ref("spp_programs.action_generate_summary").report_action(self)

    @api.depends("inkind_entitlement_ids")
    def _compute_inkind_entitlements_count(self):
        for rec in self:
            rec.inkind_entitlements_count = len(rec.inkind_entitlement_ids)

    def get_previous_cycle(self):
        self.ensure_one()
        if self.previous_cycle_id:
            return self.previous_cycle_id
        else:
            sorted_cycles = self.program_id.cycle_ids.sorted(key="create_date")
            current_index = sorted_cycles.ids.index(self.id)
            if current_index > 0:
                # Return the previous cycle
                self.previous_cycle_id = sorted_cycles[current_index - 1]
                return sorted_cycles[current_index - 1]
            else:
                # Return None or False if there is no previous cycle
                return None

    def get_next_cycle(self):
        self.ensure_one()
        if self.next_cycle_id:
            return self.next_cycle_id
        else:
            sorted_cycles = self.program_id.cycle_ids.sorted(key="create_date")
            current_index = sorted_cycles.ids.index(self.id)
            if current_index < len(sorted_cycles) - 1:
                # Return the next cycle
                self.next_cycle_id = sorted_cycles[current_index + 1]
                return sorted_cycles[current_index + 1]
            else:
                # Return None or False if there is no next cycle
                return None

    @api.depends("program_id", "program_id.compliance_manager_ids")
    def _compute_allow_filter_compliance_criteria(self):
        for rec in self:
            # Check if program has dedicated compliance managers configured
            rec.allow_filter_compliance_criteria = bool(rec.program_id.compliance_manager_ids)

    def action_filter_beneficiaries_by_compliance_criteria(self):
        self.ensure_one()
        if not self.program_id.compliance_manager_ids:
            raise ValidationError(_("Cycle is not on correct condition to filter by compliance!"))
        if self.state not in ("draft", "to_approve") or not self.cycle_membership_ids:
            return
        if not self.env.user.has_group("spp_programs.group_programs_manager"):
            raise AccessError(
                _(
                    "You do not have permission to filter beneficiaries by compliance criteria. "
                    "This operation is restricted to program managers."
                )
            )
        registrant_satisfied = (
            self.env["res.partner"]  # nosemgrep: odoo-sudo-on-sensitive-models, odoo-sudo-without-context
            .sudo()  # nosemgrep: odoo-sudo-on-sensitive-models
            .search(
                # Cross-program compliance filter restricted to
                # spp_programs.group_programs_manager; domain is built from
                # program-managed compliance criteria.
                self._get_compliance_criteria_domain()
            )
        )
        membership_to_paused = self.cycle_membership_ids.filtered(lambda cm: cm.partner_id not in registrant_satisfied)
        membership_to_paused.state = "non_compliant"
        membership_to_enrolled = self.cycle_membership_ids - membership_to_paused
        membership_to_enrolled.state = "enrolled"

        # Mark compliance criteria as applied
        self.compliance_criteria_applied = True

    def _get_compliance_criteria_domain(self):
        """Build domain from dedicated compliance managers.

        Uses the program's compliance_manager_ids and calls get_compliance_domain()
        on each manager implementation to retrieve the compliance filtering domain.
        """
        from functools import reduce

        from odoo.fields import Domain

        self.ensure_one()
        domains = []
        membership = self.cycle_membership_ids if self.cycle_membership_ids else None

        # Get compliance managers and build domain using get_compliance_domain
        for manager in self.program_id.compliance_manager_ids:
            manager_ref = manager.manager_ref_id
            if manager_ref and hasattr(manager_ref, "get_compliance_domain"):
                compliance_domain = manager_ref.get_compliance_domain(membership)
                if compliance_domain:
                    domains.append(compliance_domain)

        if not domains:
            return []
        return reduce(lambda d1, d2: Domain(d1) | Domain(d2), domains)

    def _compute_all_members_count(self):
        for rec in self:
            domain = rec._get_beneficiaries_domain(None)
            members_count = self.env["spp.cycle.membership"].search_count(domain)
            rec.update({"all_members_count": members_count})

    def open_all_members_form(self):
        self.ensure_one()
        # Use stored action for proper URL/refresh handling
        # nosemgrep: odoo-sudo-without-context
        action = self.env.ref("spp_programs.action_cycle_membership").sudo().read()[0]
        action.update(
            {
                "name": _("Cycle Members - %s", self.name),
                "context": {
                    "create": False,
                    "default_cycle_id": self.id,
                    "search_default_cycle_id": self.id,
                },
                "domain": [("cycle_id", "=", self.id)],
            }
        )
        return action

    def open_members_form(self):  # noqa: F811
        self.ensure_one()
        # Use stored action for proper URL/refresh handling
        # nosemgrep: odoo-sudo-without-context
        action = self.env.ref("spp_programs.action_cycle_membership").sudo().read()[0]
        action.update(
            {
                "name": _("Cycle Beneficiaries - %s", self.name),
                "context": {
                    "create": False,
                    "default_cycle_id": self.id,
                    "search_default_enrolled_state": 1,
                    "search_default_cycle_id": self.id,
                },
                "domain": [("cycle_id", "=", self.id)],
            }
        )
        return action

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for record in self:
            if record.start_date and record.start_date < fields.Date.today():
                raise ValidationError(_('The "Start Date" cannot be earlier than today.'))
            if record.end_date and record.start_date and record.end_date < record.start_date:
                raise ValidationError(_('The "End Date" cannot be earlier than the "Start Date".'))
