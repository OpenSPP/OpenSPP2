# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging
import random
from uuid import uuid4

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

# Odoo 19: Import Procurement from stock.rule instead of procurement.group
try:
    from odoo.addons.stock.models.stock_rule import Procurement
except ImportError:
    # Fallback for older Odoo versions
    Procurement = None

from . import constants

_logger = logging.getLogger(__name__)


class SPPEntitlement(models.Model):
    _name = "spp.entitlement"
    _inherit = ["mail.thread", "mail.activity.mixin", "spp.approval.mixin"]
    _description = "Entitlement"
    _order = "partner_id asc,id desc"
    _check_company_auto = True

    # Cached model ID for performance (class-level cache)
    _entitlement_model_id_cache = None

    @api.model
    def _generate_code(self):
        return str(uuid4())[4:-8][3:]

    name = fields.Char(compute="_compute_name")
    code = fields.Char(default=lambda x: x._generate_code(), required=True, readonly=True, copy=False)

    ern = fields.Char(
        compute="_compute_generate_ern",
        string="ERN",
        # required=True,
        readonly=True,
        copy=False,
        store=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        "Registrant",
        help="A beneficiary",
        required=True,
        domain=[("is_registrant", "=", True)],
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    cycle_id = fields.Many2one("spp.cycle", required=True)
    program_id = fields.Many2one("spp.program", related="cycle_id.program_id")

    valid_from = fields.Date(required=False)
    valid_until = fields.Date(default=lambda self: fields.Date.add(fields.Date.today(), years=1))

    is_cash_entitlement = fields.Boolean("Cash Entitlement", default=False)
    currency_id = fields.Many2one("res.currency", readonly=True, related="journal_id.currency_id")
    initial_amount = fields.Monetary(required=True, currency_field="currency_id")
    transfer_fee = fields.Monetary(currency_field="currency_id", default=0.0)
    balance = fields.Monetary(compute="_compute_balance")  # in company currency
    # TODO: implement transactions against this entitlement

    journal_id = fields.Many2one(
        "account.journal",
        "Disbursement Journal",
        store=True,
        compute="_compute_journal_id",
    )
    disbursement_id = fields.Many2one("account.payment", "Disbursement Journal Entry")
    service_fee_disbursement_id = fields.Many2one("account.payment", "Service Fee Journal Entry")

    date_approved = fields.Date()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending_validation", "Pending Approval"),
            ("approved", "Approved"),
            ("trans2FSP", "Transferred to FSP"),
            ("rdpd2ben", "Redeemed/Paid to Beneficiary"),
            ("rejected1", "Rejected: Beneficiary didn't want the entitlement"),
            ("rejected2", "Rejected: Beneficiary account does not exist"),
            ("rejected3", "Rejected: Other reason"),
            ("cancelled", "Cancelled"),
            ("expired", "Expired"),
        ],
        "Status",
        default="draft",
        copy=False,
    )

    # Override approval mixin fields to map to existing entitlement fields
    approval_state = fields.Selection(
        related=None,  # Override related
        compute="_compute_approval_state",
        store=False,  # Computed from state field
    )

    # Link to approval definition
    entitlement_approval_definition_id = fields.Many2one(
        "spp.approval.definition",
        string="Approval Definition",
        compute="_compute_entitlement_approval_definition",
        store=False,
    )

    # Approval waiting message fields
    show_approval_waiting_message = fields.Boolean(
        compute="_compute_approval_waiting_message",
        store=False,
    )
    approval_waiting_message = fields.Html(
        compute="_compute_approval_waiting_message",
        store=False,
        sanitize=False,
    )

    show_fund_availability_message = fields.Boolean(
        compute="_compute_approval_waiting_message",
        store=False,
    )
    fund_availability_message = fields.Html(
        compute="_compute_approval_waiting_message",
        store=False,
        sanitize=False,
    )
    has_insufficient_funds = fields.Boolean(
        compute="_compute_approval_waiting_message",
        store=False,
    )

    payment_ids = fields.One2many("spp.payment", "entitlement_id", string="Payments")
    payment_status = fields.Selection([("paid", "Paid"), ("notpaid", "Not Paid")], compute="_compute_payment_status")
    payment_date = fields.Date(compute="_compute_payment_status")

    @api.constrains("code")
    def _check_unique_code(self):
        for record in self:
            if record.code:
                existing = self.search(
                    [
                        ("code", "=", record.code),
                        ("id", "!=", record.id),
                    ],
                    limit=1,
                )
                if existing:
                    raise ValidationError(_("The entitlement code must be unique."))

    @api.constrains("valid_from", "valid_until")
    def _check_valid_dates(self):
        for record in self:
            if record.valid_until and record.valid_from and record.valid_until < record.valid_from:
                raise ValidationError(_('The "Valid Until" date cannot be earlier than the "Valid From" date.'))

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)

        group_spp_admin = self.env.user.has_group("spp_security.group_spp_admin")
        if not group_spp_admin:
            if view_type != "search":
                group_spp_registrar = self.env.user.has_group("spp_registry.group_registry_officer")
                spp_program_validator = self.env.user.has_group("spp_programs.group_programs_validator")
                spp_program_manager = self.env.user.has_group("spp_programs.group_programs_manager")
                spp_program_cycle_approver = self.env.user.has_group("spp_programs.group_programs_cycle_approver")

                if not (
                    group_spp_registrar or spp_program_validator or spp_program_manager or spp_program_cycle_approver
                ):
                    raise ValidationError(_("You have no access in the Entitlement List View"))

        return arch, view

    def _compute_name(self):
        # Prefetch currency_id to avoid N+1 queries in loop
        self.mapped("currency_id")

        for record in self:
            name = _("Entitlement")
            initial_amount = f"{record.initial_amount:,.2f}"
            if record.is_cash_entitlement:
                name += " Cash [" + str(record.currency_id.symbol) + " " + initial_amount + "]"
            else:
                name += " (" + str(record.code) + ")"
            record.name = name

    @api.depends("initial_amount")
    def _compute_balance(self):
        for record in self:
            record.balance = record.initial_amount

    @api.depends("cycle_id.program_id.journal_id")
    def _compute_journal_id(self):
        for record in self:
            record.journal_id = (
                record.cycle_id
                and record.cycle_id.program_id
                and record.cycle_id.program_id.journal_id
                and record.cycle_id.program_id.journal_id.id
                or None
            )

    def _compute_payment_status(self):
        # Prefetch payment_ids and their status to avoid N+1 queries in loop
        self.mapped("payment_ids.status")
        self.mapped("payment_ids.payment_datetime")

        for rec in self:
            paid_payment = None
            for payment in rec.payment_ids:
                if payment.status == "paid":
                    rec.payment_status = "paid"
                    paid_payment = payment
                    break
            if not paid_payment:
                rec.payment_status = "notpaid"
                rec.payment_date = None
            if paid_payment:
                rec.payment_date = paid_payment.payment_datetime

    @api.depends("state")
    def _compute_generate_ern(self):
        for rec in self:
            if rec.state == "approved":
                random_number = str(random.randint(1, 10**10 - 1)).zfill(10)
                rec.ern = random_number
            else:
                rec.ern = False

    # === Approval Workflow Methods ===

    @api.model
    def _get_entitlement_model_id(self):
        """Get cached ir.model ID for spp.entitlement."""
        if SPPEntitlement._entitlement_model_id_cache is None:
            model = self.env["ir.model"].search([("model", "=", "spp.entitlement")], limit=1)
            SPPEntitlement._entitlement_model_id_cache = model.id if model else False
        return SPPEntitlement._entitlement_model_id_cache

    @api.depends("program_id")
    def _compute_entitlement_approval_definition(self):
        """Get the approval definition for entitlements."""
        for record in self:
            manager = record.program_id.get_manager(constants.MANAGER_ENTITLEMENT) if record.program_id else False
            record.entitlement_approval_definition_id = manager.approval_definition_id if manager else False

    def _compute_approval_waiting_message(self):
        """Compute approval waiting message visibility and content."""
        for record in self:
            # Check if user is in the approval group
            current_user = self.env.user
            definition = record.entitlement_approval_definition_id
            user_in_approval_group = False

            if definition:
                if definition.approval_type == "group" and definition.approval_group_id:
                    user_in_approval_group = current_user.id in definition.approval_group_id.user_ids.ids
                elif definition.approval_type == "user" and definition.approval_user_ids:
                    user_in_approval_group = current_user.id in definition.approval_user_ids.ids

            # Show fund availability message if user is in approval group and pending
            if user_in_approval_group and record.state == "pending_validation":
                # Check fund availability for cash entitlements
                from ..models import constants

                entitlement_manager = (
                    record.cycle_id.program_id.get_manager(constants.MANAGER_ENTITLEMENT)
                    if record.cycle_id and record.cycle_id.program_id
                    else None
                )
                if entitlement_manager and entitlement_manager.IS_CASH_ENTITLEMENT:
                    try:
                        available_funds = entitlement_manager.check_fund_balance(record.cycle_id.program_id.id)
                        required_amount = record.initial_amount

                        if available_funds < required_amount:
                            record.show_fund_availability_message = True
                            record.has_insufficient_funds = True
                            record.fund_availability_message = _(
                                "⚠️ <b>Insufficient Funds</b><br/>"
                                "Required: <b>%s %.2f</b> | "
                                "Available: <b>%s %.2f</b> | "
                                "Shortage: <b>%s %.2f</b>"
                            ) % (
                                record.currency_id.symbol,
                                required_amount,
                                record.currency_id.symbol,
                                available_funds,
                                record.currency_id.symbol,
                                required_amount - available_funds,
                            )
                        else:
                            record.show_fund_availability_message = True
                            record.has_insufficient_funds = False
                            record.fund_availability_message = _(
                                "✓ <b>Sufficient Funds Available</b><br/>"
                                "Required: <b>%s %.2f</b> | "
                                "Available: <b>%s %.2f</b>"
                            ) % (
                                record.currency_id.symbol,
                                required_amount,
                                record.currency_id.symbol,
                                available_funds,
                            )
                    except Exception:
                        # If fund check fails, don't show the message
                        record.show_fund_availability_message = False
                        record.fund_availability_message = False
                        record.has_insufficient_funds = False
                else:
                    record.show_fund_availability_message = False
                    record.fund_availability_message = False
                    record.has_insufficient_funds = False
            else:
                record.show_fund_availability_message = False
                record.fund_availability_message = False
                record.has_insufficient_funds = False

            # Show waiting message only if pending and user cannot approve or reject
            if record.state == "pending_validation" and not record.can_approve and not record.can_reject:
                record.show_approval_waiting_message = True

                # Build the message based on approval definition
                if definition:
                    if definition.approval_type == "group" and definition.approval_group_id:
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

    @api.depends("state")
    def _compute_approval_state(self):
        """Map entitlement state to approval mixin state."""
        state_map = {
            "draft": "draft",
            "pending_validation": "pending",
            "approved": "approved",
            "trans2FSP": "approved",
            "rdpd2ben": "approved",
            "reject": "rejected",  # Multi-rejection wizard state
            "rejected1": "rejected",
            "rejected2": "rejected",
            "rejected3": "rejected",
            "cancelled": "rejected",
            "expired": "approved",
        }
        for record in self:
            record.approval_state = state_map.get(record.state, "draft")

    def _compute_approval_permissions(self):
        """Override to include admin users in approval permissions."""
        super()._compute_approval_permissions()

        # Admins can always approve/reject pending entitlements
        if self.env.user.has_group("spp_security.group_spp_admin"):
            for record in self:
                if record.approval_state == "pending":
                    record.can_approve = True
                    record.can_reject = True

    def _get_approval_definition(self):
        """Override to return the entitlement's approval definition."""
        self.ensure_one()
        return self.entitlement_approval_definition_id

    def action_submit_for_approval(self):
        """Submit entitlement for approval using standardized workflow."""
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only draft entitlements can be submitted for approval."))

            # Use mixin submission logic if approval definition exists
            definition = record._get_approval_definition()
            if definition:
                super(SPPEntitlement, record).action_submit_for_approval()

            # Transition to pending_validation state
            record.write(
                {
                    "state": "pending_validation",
                    "submitted_by_id": self.env.user.id,
                    "submitted_date": fields.Datetime.now(),
                }
            )

    def action_approve(self, comment=None):
        """Approve entitlement using standardized workflow."""
        for record in self:
            if record.state != "pending_validation":
                raise UserError(_("Only entitlements pending approval can be approved."))

            # Get approval definition - if none exists, we cannot approve
            definition = record._get_approval_definition()
            if not definition:
                raise UserError(
                    _(
                        "No approval definition configured for this entitlement.\n\n"
                        "Please ensure an approval definition is set up in the entitlement manager "
                        "before attempting to approve entitlements."
                    )
                )

            # Check permissions using the approval mixin
            # This will raise an error if the user is not authorized
            record._check_can_approve()

            # Check if there are sufficient funds before approving
            from ..models import constants

            entitlement_manager = record.cycle_id.program_id.get_manager(constants.MANAGER_ENTITLEMENT)
            if entitlement_manager and entitlement_manager.IS_CASH_ENTITLEMENT:
                available_funds = entitlement_manager.check_fund_balance(record.cycle_id.program_id.id)
                if available_funds < record.initial_amount:
                    raise UserError(
                        _(
                            "Insufficient funds to approve this entitlement!\n\n"
                            "Entitlement Code: %(code)s\n"
                            "Beneficiary: %(beneficiary)s\n"
                            "Required Amount: %(required).2f\n"
                            "Available Funds: %(available).2f\n"
                            "Shortage: %(shortage).2f\n\n"
                            "Please ensure sufficient funds are available before approving."
                        )
                        % {
                            "code": record.code or "N/A",
                            "beneficiary": record.partner_id.name,
                            "required": record.initial_amount,
                            "available": available_funds,
                            "shortage": record.initial_amount - available_funds,
                        }
                    )

            # Call mixin's approval logic to handle reviews and audit fields
            super(SPPEntitlement, record).action_approve(comment=comment)

            # Transition to approved state
            record.write(
                {
                    "state": "approved",
                    "date_approved": fields.Date.today(),
                }
            )

    def action_reject(self):
        """Reject entitlement using standardized workflow."""
        self.ensure_one()

        if self.state != "pending_validation":
            raise UserError(_("Only entitlements pending approval can be rejected."))

        # Use mixin rejection logic (opens wizard)
        return super().action_reject()

    def _do_reject(self, reason):
        """Execute rejection after wizard confirmation."""
        self.ensure_one()

        # Update state to rejected first (so approval_state compute maps correctly)
        self.write({"state": "rejected3"})

        # Call parent mixin logic (handles audit fields)
        super()._do_reject(reason)

        # Explicitly update pending reviews (multitier mixin doesn't do this for single-tier)
        pending_reviews = self.approval_review_ids.filtered(lambda r: r.status == "pending")
        if pending_reviews:
            pending_reviews.action_reject(comment=reason)

    def action_reset_to_draft(self):
        """Reset entitlement to draft state."""
        for record in self:
            valid_reset_states = (
                "pending_validation",
                "cancelled",
                "reject",
                "rejected1",
                "rejected2",
                "rejected3",
            )
            if record.state not in valid_reset_states:
                raise UserError(_("Only entitlements pending approval, cancelled, or rejected can be reset to draft."))

            # Use mixin reset logic if in rejected approval_state
            if record.approval_state == "rejected":
                super(SPPEntitlement, record).action_reset_to_draft()

            # Check if existing approval reviews are present
            if record.approval_review_ids:
                pending_review = record.approval_review_ids.filtered(lambda r: r.status == "pending")
                pending_review.unlink()
                approval_review = record.approval_review_ids.filtered(lambda r: r.status == "approved")
                if approval_review:
                    raise UserError(
                        _(
                            "The entitlement has existing approved approval reviews. Please reset to "
                            "draft from the approval review."
                        )
                    )

            # Transition to draft state
            record.write({"state": "draft"})

            # Force recompute of approval_state
            record._compute_approval_state()

    def batch_approve(self):
        """Approve multiple entitlements at once."""
        eligible = self.filtered(lambda e: e.state == "pending_validation")
        if not eligible:
            raise UserError(_("No entitlements are pending approval."))

        approved_count = 0
        failed_records = []

        for record in eligible:
            try:
                record.action_approve()
                approved_count += 1
            except UserError as e:
                _logger.warning("Failed to approve entitlement ID %s: %s", record.id, str(e))
                failed_records.append(
                    {
                        "id": record.id,
                        "name": record.name or record.code,
                        "error": str(e),
                    }
                )

        if failed_records:
            error_details = "\n".join([f"- {r['name']} (ID {r['id']}): {r['error']}" for r in failed_records[:10]])
            if len(failed_records) > 10:
                error_details += f"\n... and {len(failed_records) - 10} more"

            raise UserError(
                _("Approved %(approved)d entitlement(s), but %(failed)d failed:\n\n%(details)s")
                % {
                    "approved": approved_count,
                    "failed": len(failed_records),
                    "details": error_details,
                }
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Batch Approval Complete"),
                "message": _("Successfully approved %d entitlement(s).") % approved_count,
                "type": "success",
                "sticky": False,
            },
        }

    @api.autovacuum
    def _gc_mark_expired_entitlement(self):
        self.env["spp.entitlement"].search(
            ["&", ("state", "=", "approved"), ("valid_until", "<", fields.Date.today())]
        ).write({"state": "expired"})

    def can_be_used(self):
        # expired state are computed once a day, so can be not synchro
        return self.state == "approved" and self.valid_until >= fields.Date.today()

    def unlink(self):
        if self:
            to_delete = self.filtered(lambda x: x.state == "draft")
            if to_delete:
                # TODO: Need to add the logic if any one entitlements within the cycle have been approved
                # to restrict the delete records even in the draft state.
                return super(SPPEntitlement, to_delete).unlink()
            else:
                raise ValidationError(_("Only draft entitlements are allowed to be deleted"))

    def approve_entitlement(self):
        ent_program_list = []
        for rec in self:
            if rec.program_id not in ent_program_list:
                ent_program_list.append(rec.program_id)
        # TODO: To be remove in case of multiple managers are enabled.
        if len(ent_program_list) > 1:
            raise ValidationError(
                _("You can approve any number of entitlement cycles only from a specific program at a time")
            )
        ent_manager = self.program_id.get_manager(constants.MANAGER_ENTITLEMENT)

        if ent_manager:
            state_err, message = ent_manager.approve_entitlements(self)

            if state_err > 0:
                kind = "danger"
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Entitlement"),
                        "message": message,
                        "sticky": False,
                        "type": kind,
                        "next": {
                            "type": "ir.actions.act_window_close",
                        },
                    },
                }

        else:
            raise UserError(_("No Entitlement Manager defined."))

    def open_entitlement_form(self):
        return self.program_id.get_manager(constants.MANAGER_ENTITLEMENT).open_entitlement_form(self)

    def open_disb_form(self):
        # Prefetch disbursement_id and service_fee_disbursement_id to avoid N+1 queries in loop
        self.mapped("disbursement_id")
        self.mapped("service_fee_disbursement_id")

        for rec in self:
            if rec.disbursement_id:
                res_ids = [rec.disbursement_id.id]
                view_mode = "form"
                view_id = self.env.ref("account.view_account_payment_form").id
                if rec.service_fee_disbursement_id:
                    res_ids.append(rec.service_fee_disbursement_id.id)
                    view_mode = "list"
                    view_id = self.env.ref("account.view_account_payment_tree").id
                domain = [("id", "in", res_ids)]
                return {
                    "name": "Disbursement",
                    "view_mode": view_mode,
                    "res_model": "account.payment",
                    # "res_id": res_id,
                    "view_id": view_id,
                    "type": "ir.actions.act_window",
                    "domain": domain,
                    "target": "current",
                }


class InKindEntitlement(models.Model):
    _name = "spp.entitlement.inkind"
    _inherit = ["mail.thread", "mail.activity.mixin", "spp.approval.mixin"]
    _description = "Entitlement"
    _order = "id desc"
    _check_company_auto = True

    @api.model
    def _generate_code(self):
        return str(uuid4())[4:-8][3:]

    name = fields.Char(compute="_compute_name")
    code = fields.Char(default=lambda x: x._generate_code(), required=True, readonly=True, copy=False)

    partner_id = fields.Many2one(
        "res.partner",
        "Registrant",
        help="A beneficiary",
        required=True,
        ondelete="cascade",
        domain=[("is_registrant", "=", True)],
        index=True,
    )
    id_number = fields.Char()

    service_point_id = fields.Many2one("spp.service.point", "Service Point")

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    cycle_id = fields.Many2one("spp.cycle", required=True)
    program_id = fields.Many2one("spp.program", related="cycle_id.program_id")

    # Approval definition field
    entitlement_approval_definition_id = fields.Many2one(
        "spp.approval.definition",
        string="Approval Definition",
        compute="_compute_entitlement_approval_definition",
        store=False,
    )

    # Approval waiting message fields
    show_approval_waiting_message = fields.Boolean(
        compute="_compute_approval_waiting_message",
        store=False,
    )
    approval_waiting_message = fields.Html(
        compute="_compute_approval_waiting_message",
        store=False,
        sanitize=False,
    )

    show_fund_availability_message = fields.Boolean(
        compute="_compute_approval_waiting_message",
        store=False,
    )
    fund_availability_message = fields.Html(
        compute="_compute_approval_waiting_message",
        store=False,
        sanitize=False,
    )
    has_insufficient_funds = fields.Boolean(
        compute="_compute_approval_waiting_message",
        store=False,
    )

    # Product Fields
    product_id = fields.Many2one("product.product", "Product", domain=[("type", "=", "product")])
    quantity = fields.Integer("Quantity", default=1)
    unit_price = fields.Monetary(string="Value/Unit", currency_field="currency_id")
    uom_id = fields.Many2one("uom.uom", "Unit of Measure")

    # Inventory integration fields
    manage_inventory = fields.Boolean(default=False)
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
    )
    route_id = fields.Many2one("stock.route", string="Route", ondelete="restrict", check_company=True)
    move_ids = fields.One2many("stock.move", "entitlement_id", string="Stock Moves")

    # Accounting Fields
    currency_id = fields.Many2one("res.currency", readonly=True, related="journal_id.currency_id")
    total_amount = fields.Monetary(string="Total Value", currency_field="currency_id")
    journal_id = fields.Many2one(
        "account.journal",
        "Journal",
        store=True,
        compute="_compute_journal_id",
    )

    valid_from = fields.Date(required=False)
    valid_until = fields.Date(default=lambda self: fields.Date.add(fields.Date.today(), years=1))

    date_approved = fields.Date()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending_validation", "Pending Validation"),
            ("approved", "Approved"),
            ("trans2FSP", "Transferred to FSP"),
            ("rdpd2ben", "Redeemed/Paid to Beneficiary"),
            ("rejected1", "Rejected: Beneficiary didn't want the entitlement"),
            ("rejected2", "Rejected: Beneficiary account does not exist"),
            ("rejected3", "Rejected: Other reason"),
            ("cancelled", "Cancelled"),
            ("expired", "Expired"),
        ],
        "Status",
        default="draft",
        copy=False,
    )

    _unique_entitlement_code = models.Constraint("UNIQUE(code)", "The entitlement code must be unique.")

    def _get_view(self, view_id=None, view_type="list", **options):
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)

        group_spp_admin = self.env.user.has_group("spp_security.group_spp_admin")
        if not group_spp_admin:
            if view_type != "search":
                group_spp_registrar = self.env.user.has_group("spp_registry.group_registry_officer")
                spp_program_validator = self.env.user.has_group("spp_programs.group_programs_validator")
                spp_program_manager = self.env.user.has_group("spp_programs.group_programs_manager")
                spp_program_cycle_approver = self.env.user.has_group("spp_programs.group_programs_cycle_approver")

                if not (
                    group_spp_registrar or spp_program_validator or spp_program_manager or spp_program_cycle_approver
                ):
                    raise ValidationError(_("You have no access in the Entitlement List View"))

        return arch, view

    @api.depends("cycle_id.program_id.journal_id")
    def _compute_journal_id(self):
        # Prefetch related fields to avoid N+1 queries
        self.mapped("cycle_id.program_id.journal_id")

        for record in self:
            record.journal_id = (
                record.cycle_id
                and record.cycle_id.program_id
                and record.cycle_id.program_id.journal_id
                and record.cycle_id.program_id.journal_id.id
                or None
            )

    def _compute_name(self):
        # Prefetch product_id to avoid N+1 queries in loop
        self.mapped("product_id.name")

        for record in self:
            name = _("Entitlement: (%s)", record.product_id.name)
            record.name = name

    @api.depends("program_id")
    def _compute_entitlement_approval_definition(self):
        """Get the approval definition for in-kind entitlements."""
        for record in self:
            manager = record.program_id.get_manager(constants.MANAGER_ENTITLEMENT) if record.program_id else False
            record.entitlement_approval_definition_id = manager.approval_definition_id if manager else False

    def _compute_approval_waiting_message(self):
        """Compute approval waiting message visibility and content."""
        for record in self:
            # In-kind entitlements don't check funds, so no fund availability message
            record.show_fund_availability_message = False
            record.fund_availability_message = False
            record.has_insufficient_funds = False

            # Show waiting message only if pending and user cannot approve or reject
            if record.state == "pending_validation" and not record.can_approve and not record.can_reject:
                record.show_approval_waiting_message = True

                # Build the message based on approval definition
                definition = record.entitlement_approval_definition_id
                if definition:
                    if definition.approval_type == "group" and definition.approval_group_id:
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

    @api.depends("state")
    def _compute_approval_state(self):
        """Map in-kind entitlement state to approval mixin state."""
        state_map = {
            "draft": "draft",
            "pending_validation": "pending",
            "approved": "approved",
            "trans2FSP": "approved",
            "rdpd2ben": "approved",
            "reject": "rejected",  # Multi-rejection wizard state (for consistency)
            "rejected1": "rejected",
            "rejected2": "rejected",
            "rejected3": "rejected",
            "cancelled": "rejected",
            "expired": "approved",
        }
        for record in self:
            record.approval_state = state_map.get(record.state, "draft")

    def _get_approval_definition(self):
        """Override to return the in-kind entitlement's approval definition."""
        self.ensure_one()
        return self.entitlement_approval_definition_id

    def _resolve_approval_definition(self):
        """Resolve approval definition for the mixin."""
        self.ensure_one()
        return self._get_approval_definition()

    def action_submit_for_approval(self):
        """Submit in-kind entitlement for approval using standardized workflow."""
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only draft entitlements can be submitted for approval."))

            definition = record._get_approval_definition()
            if not definition:
                raise UserError(_("No approval workflow configured for this record type."))

            # Use the mixin's submit method
            super(InKindEntitlement, record).action_submit_for_approval()

            # Update state to pending_validation
            record.state = "pending_validation"

    def action_approve(self, comment=None):
        """Approve in-kind entitlement(s) using approval mixin."""
        # First validate all records before approving any
        for record in self:
            if record.state != "pending_validation":
                raise UserError(_("Only entitlements pending validation can be approved."))

            # Get approval definition - if none exists, we cannot approve
            definition = record._get_approval_definition()
            if not definition:
                raise UserError(
                    _(
                        "No approval definition configured for this in-kind entitlement.\n\n"
                        "Please ensure an approval definition is set up in the in-kind entitlement manager "
                        "before attempting to approve entitlements."
                    )
                )

            # Check permissions using the approval mixin
            # This will raise an error if the user is not authorized
            record._check_can_approve()

        # Call approve_entitlement on all records at once (method handles multiple records)
        return self.approve_entitlement()

    def action_reject(self):
        """Reject in-kind entitlement using standardized workflow."""
        self.ensure_one()

        if self.state != "pending_validation":
            raise UserError(_("Only entitlements pending approval can be rejected."))

        # Use mixin rejection logic (opens wizard)
        return super().action_reject()

    def _do_reject(self, reason):
        """Execute rejection after wizard confirmation."""
        self.ensure_one()

        # Update state to rejected first (so approval_state compute maps correctly)
        self.write({"state": "rejected1"})

        # Call parent mixin logic (handles audit fields)
        super()._do_reject(reason)

        # Explicitly update pending reviews (multitier mixin doesn't do this for single-tier)
        pending_reviews = self.approval_review_ids.filtered(lambda r: r.status == "pending")
        if pending_reviews:
            pending_reviews.action_reject(comment=reason)

    def action_reset_to_draft(self):
        """Reset in-kind entitlement to draft."""
        for record in self:
            if record.state not in (
                "pending_validation",
                "reject",
                "rejected1",
                "rejected2",
                "rejected3",
                "cancelled",
            ):
                raise UserError(
                    _("Only entitlements pending validation, rejected, or cancelled can be reset to draft.")
                )

            # Use the mixin's reset method if applicable
            if record.approval_state == "rejected":
                super(InKindEntitlement, record).action_reset_to_draft()

            # Check if existing approval reviews are present
            if record.approval_review_ids:
                pending_review = record.approval_review_ids.filtered(lambda r: r.status == "pending")
                pending_review.unlink()  # Delete pending reviews like cash entitlements
                approval_review = record.approval_review_ids.filtered(lambda r: r.status == "approved")
                if approval_review:
                    raise UserError(
                        _(
                            "The entitlement has existing approved approval reviews. Please reset to "
                            "draft from the approval review."
                        )
                    )

            # Transition to draft state
            record.write({"state": "draft"})

            # Force recompute of approval_state
            record._compute_approval_state()

    @api.autovacuum
    def _gc_mark_expired_entitlement(self):
        self.env["spp.entitlement"].search(
            ["&", ("state", "=", "approved"), ("valid_until", "<", fields.Date.today())]
        ).write({"state": "expired"})

    def unlink(self):
        for rec in self:
            if rec.state == "draft":
                return super().unlink()
            else:
                raise ValidationError(_("Only draft entitlements are allowed to be deleted"))

    def approve_entitlement(self):
        """Approve in-kind entitlement(s) using approval mixin."""
        ent_program_list = []
        for rec in self:
            if rec.program_id not in ent_program_list:
                ent_program_list.append(rec.program_id)
        if len(ent_program_list) > 1:
            raise ValidationError(
                _("You can approve any number of entitlement cycles only from a specific program at a time")
            )

        ent_manager = self.program_id.get_manager(constants.MANAGER_ENTITLEMENT)
        if not ent_manager:
            raise UserError(_("No Entitlement Manager defined."))

        original_states = {rec.id: rec.state for rec in self}

        for rec in self:
            _logger.debug("In-Kind Entitlement %s - State: %s", rec.id, rec.state)
            if rec.state in ("draft", "pending_validation"):
                definition = rec._get_approval_definition()
                if definition:
                    if rec.state == "draft":
                        rec.action_submit_for_approval()
                        self.env.cr.flush()  # Ensure approval reviews are committed
                        rec.invalidate_cache(["approval_review_ids"])  # Invalidate cache to reload reviews

                    pending_reviews = rec.approval_review_ids.filtered(lambda r: r.status == "pending")
                    _logger.debug(
                        "In-Kind Entitlement %s - Found %d pending reviews to approve",
                        rec.id,
                        len(pending_reviews),
                    )
                    if pending_reviews:
                        pending_reviews.write(
                            {
                                "status": "approved",
                                "reviewer_id": self.env.user.id,
                                "review_date": fields.Datetime.now(),
                            }
                        )
                        _logger.debug(
                            "In-Kind Entitlement %s - Updated approval reviews to approved",
                            rec.id,
                        )

        state_err, message = ent_manager.approve_entitlements(self)

        if state_err > 0:
            for rec in self:
                original_state = original_states.get(rec.id)
                if original_state in ("draft", "pending_validation"):
                    definition = rec._get_approval_definition()
                    if definition:
                        rec.approval_review_ids.filtered(lambda r: r.status == "approved").write(
                            {
                                "status": "pending",
                                "reviewer_id": False,
                                "review_date": False,
                            }
                        )
                        if original_state == "draft" and rec.state == "pending_validation":
                            rec.write({"state": "draft"})

            kind = "danger"
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Entitlement"),
                    "message": message,
                    "sticky": False,
                    "type": kind,
                    "next": {
                        "type": "ir.actions.act_window_close",
                    },
                },
            }
        return None  # Return None on success

    def open_entitlement_form(self):
        return self.program_id.get_manager(constants.MANAGER_ENTITLEMENT).open_entitlement_form(self)

    # Inventory functions
    def _prepare_procurement_values(self, group_id=False):
        """Prepare specific key for moves or other components that will be created from a stock rule
        comming from an entitlement.
        """
        self.ensure_one()
        # Use the delivery date if there is else use date_order and lead time
        # TODO: @edwin Shouldn't this be the start date cause the delivery need to be done by the time the cycle start?
        date_deadline = self.cycle_id.end_date
        date_planned = self.cycle_id.start_date
        values = {
            "group_id": group_id,
            "entitlement_id": self.id,
            "date_planned": date_planned,
            "date_deadline": date_deadline,
            "route_ids": self.route_id,
            "warehouse_id": self.warehouse_id or False,
            "partner_id": self.partner_id.id,
            "product_description_variants": self.product_id.name,
            "company_id": self.company_id,
            # 'product_packaging_id': self.product_packaging_id,
        }
        return values

    def _get_qty_procurement(self):
        self.ensure_one()
        quantity = 0.0
        outgoing_moves, incoming_moves = self._get_outgoing_incoming_moves()
        for move in outgoing_moves:
            quantity += move.product_uom._compute_quantity(move.product_uom_qty, self.uom_id, rounding_method="HALF-UP")
        for move in incoming_moves:
            quantity -= move.product_uom._compute_quantity(move.product_uom_qty, self.uom_id, rounding_method="HALF-UP")
        return quantity

    def _get_outgoing_incoming_moves(self):
        outgoing_moves = self.env["stock.move"]
        incoming_moves = self.env["stock.move"]

        moves = self.move_ids.filtered(
            lambda r: (
                r.state != "cancel"
                and not getattr(r, "scrapped", False)
                and not r.scrap_id
                and self.product_id == r.product_id
            )
        )

        # Prefetch location_dest_id to avoid N+1 queries in loop
        moves.mapped("location_dest_id.usage")
        moves.mapped("origin_returned_move_id")

        for move in moves:
            if move.location_dest_id.usage == "customer":
                if not move.origin_returned_move_id or (move.origin_returned_move_id and move.to_refund):
                    outgoing_moves |= move
            elif move.location_dest_id.usage != "customer" and move.to_refund:
                incoming_moves |= move

        return outgoing_moves, incoming_moves

    def _get_procurement_group(self):
        return self.cycle_id.procurement_group_id

    def _prepare_procurement_group_vals(self):
        # Odoo 19: procurement.group replaced with stock.reference
        # stock.reference only has 'name' field, not move_type/partner_id
        return {
            "name": self.cycle_id.name,
            "cycle_id": self.cycle_id.id,
        }

    def _action_launch_stock_rule(self):
        """
        Launch procurement group run method with required/custom fields generated by an
        entitlement. procurement group will launch '_run_pull', '_run_buy' or '_run_manufacture'
        depending on the entitlement product rule.
        """
        if self._context.get("skip_procurement"):
            return True
        precision = self.env["decimal.precision"].precision_get("Product Unit of Measure")

        # Prefetch related fields to avoid N+1 queries in loop
        self.mapped("company_id")
        self.mapped("product_id.type")
        self.mapped("product_id.uom_id")
        self.mapped("cycle_id.procurement_group_id")
        self.mapped("partner_id.property_stock_customer")

        procurements = []
        for row in self:
            row = row.with_company(row.company_id)
            if row.product_id.type not in ("consu", "product"):
                continue
            quantity = row._get_qty_procurement()
            if float_compare(quantity, float(row.quantity), precision_digits=precision) == 0:
                continue

            # Odoo 19: procurement.group replaced with stock.reference
            group_id = row._get_procurement_group()
            if not group_id:
                group_id = self.env["stock.reference"].create(row._prepare_procurement_group_vals())
                row.cycle_id.procurement_group_id = group_id
            # Note: stock.reference doesn't have partner_id or move_type fields
            # Those are now handled differently in Odoo 19

            values = row._prepare_procurement_values(group_id=group_id)
            product_qty = float(row.quantity) - quantity

            row_uom = row.uom_id
            quant_uom = row.product_id.uom_id
            product_qty, procurement_uom = row_uom._adjust_uom_quantities(product_qty, quant_uom)

            # Odoo 19: Use Procurement namedtuple from stock.rule
            if Procurement:  # Check if import succeeded
                procurements.append(
                    Procurement(
                        product_id=row.product_id,
                        product_qty=product_qty,
                        product_uom=procurement_uom,
                        location_id=row.partner_id.property_stock_customer,
                        name=row.name,
                        origin=row.cycle_id.name,
                        company_id=row.company_id,
                        values=values,
                    )
                )
        if procurements:
            # Odoo 19: run() method moved to stock.rule
            self.env["stock.rule"].run(procurements)

        # This next block is currently needed only because the scheduler trigger is done by picking confirmation
        # rather than stock.move confirmation
        cycles = self.mapped("cycle_id")

        # Prefetch picking_ids and their state to avoid N+1 queries in loop
        cycles.mapped("picking_ids.state")

        for cycle in cycles:
            pickings_to_confirm = cycle.picking_ids.filtered(lambda p: p.state not in ["cancel", "done"])
            if pickings_to_confirm:
                # Trigger the Scheduler for Pickings
                pickings_to_confirm.action_confirm()
        return True
