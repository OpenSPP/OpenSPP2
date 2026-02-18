import logging
from datetime import timedelta
from email.utils import parseaddr

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPGRMTicket(models.Model):
    """Enhanced Grievance Redress Mechanism Ticket model.

    This model manages tickets/complaints in the GRM system with enhanced
    features for SLA tracking, escalation, appeals, and decision management.
    """

    _name = "spp.grm.ticket"
    _description = "Grievance Redress Mechanism Ticket"
    _rec_name = "number"
    _rec_names_search = ["number", "name"]
    _order = "priority desc, sequence, number desc, id desc"
    _mail_post_access = "read"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """Create a new ticket from an inbound email"""
        _logger.debug("Creating new ticket from email")
        # Extract values from the email
        subject = msg_dict.get("subject") or "No Subject"
        body = msg_dict.get("body") or "No Content"
        email_from = msg_dict.get("email_from")
        email_address = parseaddr(email_from)[1]
        # TODO: What to do if the registrant is a group?
        partner = self.env["res.partner"].search([("email", "=", email_address)], limit=1)
        if not partner:
            self._send_custom_error_notification(email_address, subject, email_from)
            _logger.warning("No matching registrant found for email. Email processed but a ticket is not created.")

        # Prepare default values for the new ticket
        vals = {
            "name": subject,
            "description": body,
            "partner_id": partner.id if partner else False,
            "partner_email": email_from,
            "channel_id": self.env.ref("spp_grm.grm_ticket_channel_email").id,
            "priority": "1",  # Default priority
        }

        if custom_values:
            vals.update(custom_values)

        # Create the new GRM ticket
        ticket = super().message_new(msg_dict, custom_values=vals)
        if ticket:
            _logger.info("New ticket created from email: %s", ticket.number)
        else:
            _logger.info("No ticket was created from email.")
        return ticket

    def message_update(self, msg_dict, update_vals=None):
        """Update an existing ticket from an inbound email reply"""
        res = super().message_update(msg_dict, update_vals=update_vals)
        _logger.info("Ticket %s updated from email", self.number)
        return res

    def _send_custom_error_notification(self, email_address, subject, email_from):
        """Send a custom email notification to the sender of the email if no registrant is found.
        :param email_address: The email address of the sender
        :param subject: The subject of the email
        :param email_from: The email address of the recipient
        """
        mail_values = {
            "subject": subject,
            "body_html": f"""
                <p>Dear Sender,</p>
                <p>We could not process your request because your email address <strong>{email_address}</strong> is not
                in our record of registrants.</p>
                <p>Kind Regards</p>
            """,
            "email_to": email_address,
            "email_from": email_from,
        }

        # Send the email
        mail = self.env["mail.mail"].create(mail_values)
        mail.send()

    def _default_stage_id(self):
        stages = self.env["spp.grm.ticket.stage"].search([])
        if stages:
            return stages[0].id
        return None

    # Basic Information
    number = fields.Char(string="Ticket number", default="/", readonly=True)
    name = fields.Char(string="Title", required=True)
    description = fields.Html(required=True, sanitize_style=True)
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Assigned user",
        tracking=True,
        index=True,
        compute="_compute_user_id",
        store=True,
        readonly=False,
    )
    stage_id = fields.Many2one(
        comodel_name="spp.grm.ticket.stage",
        string="Stage",
        default=_default_stage_id,
        store=True,
        readonly=False,
        ondelete="restrict",
        tracking=True,
        group_expand="_read_group_stage_ids",
        copy=False,
        index=True,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Contact",
        required=True,
        domain="[('is_registrant', '=', True)]",
    )
    partner_email = fields.Char(string="Email", related="partner_id.email", store=True)
    last_stage_update = fields.Datetime(default=fields.Datetime.now)
    assigned_date = fields.Datetime()
    closed_date = fields.Datetime(tracking=True)
    closed_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Closed By",
        help="User who closed this ticket",
    )
    is_closed = fields.Boolean(
        string="Is Closed",
        compute="_compute_is_closed",
        store=True,
        help="Computed field indicating if ticket is in a closed stage",
    )
    unattended = fields.Boolean(related="stage_id.unattended", store=True)
    tag_ids = fields.Many2many(comodel_name="spp.grm.ticket.tag", string="Tags")
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    channel_id = fields.Many2one(comodel_name="spp.grm.ticket.channel", string="Channel")

    # Intake Information (per spec Section 4.1)
    intake_date = fields.Datetime(
        string="Intake Date",
        default=fields.Datetime.now,
        help="Date and time when the complaint was received",
    )
    intake_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Intake User",
        default=lambda self: self.env.user,
        help="Staff member who recorded the complaint during intake",
    )
    desired_resolution = fields.Text(
        string="Desired Resolution",
        help="What outcome the complainant is seeking",
    )

    category_id = fields.Many2one(
        comodel_name="spp.grm.ticket.category",
        string="Category",
    )
    subcategory_id = fields.Many2one(
        comodel_name="spp.grm.ticket.subcategory",
        string="Subcategory",
        domain="[('category_id', '=', category_id)]",
        help="Second level of categorization under the main category",
    )
    priority = fields.Selection(
        selection=[
            ("0", "Low"),
            ("1", "Medium"),
            ("2", "High"),
            ("3", "Very High"),
        ],
        default="1",
    )
    attachment_ids = fields.One2many(
        comodel_name="ir.attachment",
        inverse_name="res_id",
        domain=[("res_model", "=", "spp.grm.ticket")],
        string="Media Attachments",
    )
    color = fields.Integer(string="Color Index")
    kanban_state = fields.Selection(
        selection=[
            ("normal", "Default"),
            ("done", "Ready for next stage"),
            ("blocked", "Blocked"),
        ],
    )
    sequence = fields.Integer(
        index=True,
        default=10,
        help="Gives the sequence order when displaying a list of tickets.",
    )
    active = fields.Boolean(default=True)

    # Enhanced Classification Fields
    severity = fields.Selection(
        selection=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        string="Severity",
        default="medium",
        required=True,
        tracking=True,
        help="Severity level of the complaint/grievance",
    )
    sensitivity = fields.Selection(
        selection=[
            ("standard", "Standard"),
            ("sensitive", "Sensitive"),
            ("highly_sensitive", "Highly Sensitive"),
        ],
        string="Sensitivity",
        default="standard",
        tracking=True,
        help="Data sensitivity classification for handling requirements",
    )
    complainant_type = fields.Selection(
        selection=[
            ("beneficiary", "Beneficiary"),
            ("non_beneficiary", "Non-Beneficiary"),
            ("staff", "Staff"),
            ("anonymous", "Anonymous"),
            ("other", "Other"),
        ],
        string="Complainant Type",
        default="beneficiary",
        tracking=True,
        help="Type of person submitting the complaint",
    )

    # Anonymous Complaint Contact Fields
    contact_name = fields.Char(
        string="Contact Name",
        help="Contact name for anonymous complaints (when partner_id is not set)",
    )
    contact_phone = fields.Char(
        string="Contact Phone",
        help="Contact phone for anonymous complaints",
    )
    contact_email = fields.Char(
        string="Contact Email",
        help="Contact email for anonymous complaints",
    )

    # SLA Fields
    sla_deadline = fields.Datetime(
        string="SLA Deadline",
        compute="_compute_sla_deadline",
        store=True,
        tracking=True,
        help="Computed deadline based on SLA rules",
    )
    sla_status = fields.Selection(
        selection=[
            ("on_track", "On Track"),
            ("at_risk", "At Risk"),
            ("breached", "Breached"),
        ],
        string="SLA Status",
        compute="_compute_sla_status",
        store=True,
        help="Current SLA compliance status",
    )

    # Decision and Resolution Fields
    decision = fields.Selection(
        selection=[
            ("upheld", "Upheld"),
            ("partially_upheld", "Partially Upheld"),
            ("rejected", "Rejected"),
            ("withdrawn", "Withdrawn"),
            ("redirected", "Redirected"),
            ("referred_to_case", "Referred to Case"),
        ],
        string="Decision",
        tracking=True,
        help="Final decision on the complaint",
    )
    resolution_summary = fields.Html(
        string="Resolution Summary",
        sanitize_style=True,
        help="Detailed summary of the resolution",
    )

    # Escalation Fields
    is_escalated = fields.Boolean(
        string="Is Escalated",
        default=False,
        tracking=True,
        help="Indicates if this ticket has been escalated",
    )
    escalated_to_id = fields.Many2one(
        comodel_name="res.users",
        string="Escalated To",
        tracking=True,
        help="User to whom this ticket was escalated",
    )
    escalation_date = fields.Datetime(
        string="Escalation Date",
        help="Date when the ticket was escalated",
    )
    escalation_reason = fields.Text(
        string="Escalation Reason",
        help="Reason for escalating the ticket",
    )

    # Appeal Fields
    is_appeal = fields.Boolean(
        string="Is Appeal",
        default=False,
        help="Indicates if this ticket is an appeal of another ticket",
    )
    original_ticket_id = fields.Many2one(
        comodel_name="spp.grm.ticket",
        string="Original Ticket",
        help="Reference to the original ticket if this is an appeal",
        ondelete="restrict",
    )
    appeal_ticket_ids = fields.One2many(
        comodel_name="spp.grm.ticket",
        inverse_name="original_ticket_id",
        string="Appeal Tickets",
        help="Tickets that are appeals of this ticket",
    )

    # Team Assignment
    team_id = fields.Many2one(
        comodel_name="spp.grm.team",
        string="Team",
        tracking=True,
        help="Team responsible for handling this ticket",
    )

    # Computed Metrics
    days_open = fields.Integer(
        string="Days Open",
        compute="_compute_days_open",
        store=True,
        help="Number of days the ticket has been open",
    )

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, rec.number + " - " + rec.name))
        return res

    def _creation_subtype(self):
        return self.env.ref("spp_grm.grm_tck_created")

    @api.model_create_multi
    def create(self, vals_list):
        """Create tickets with auto-generated numbers and assigned dates."""
        for vals in vals_list:
            # Generate ticket number if not provided
            if vals.get("number", "/") == "/":
                vals["number"] = self._prepare_ticket_number()
            _logger.debug("Creating ticket %s", vals.get("number", "NEW"))
            # Set assigned date if user is assigned
            if vals.get("user_id") and not vals.get("assigned_date"):
                vals["assigned_date"] = fields.Datetime.now()
        return super().create(vals_list)

    def copy(self, default=None):
        self.ensure_one()
        if default is None:
            default = {}
        if "number" not in default:
            default["number"] = self._prepare_ticket_number()
        res = super().copy(default)
        return res

    def write(self, vals):
        # Check stage transition requirements
        if "stage_id" in vals:
            new_stage = self.env["spp.grm.ticket.stage"].browse(vals["stage_id"])

            for ticket in self:
                # Check if moving to a stage that requires approval
                if new_stage.is_requires_approval:
                    # For now, only supervisors/managers can move to approval-required stages
                    if not self.env.user.has_group("spp_grm.group_grm_supervisor"):
                        raise UserError(
                            _("Stage '%s' requires supervisor approval. Please request approval from your supervisor.")
                            % new_stage.name
                        )

                # Check if closing without decision
                if new_stage.is_closed and new_stage.is_requires_decision:
                    # Check if decision is being set in this write or already exists
                    decision_value = vals.get("decision") or ticket.decision
                    if not decision_value:
                        raise UserError(
                            _(
                                "A decision must be recorded before closing this ticket. "
                                "Please select a decision (Upheld, Rejected, etc.)."
                            )
                        )

                # Check allowed groups for stage
                if new_stage.allowed_group_ids:
                    user_groups = self.env.user.group_ids
                    if not (user_groups & new_stage.allowed_group_ids):
                        raise UserError(_("You don't have permission to move tickets to stage '%s'.") % new_stage.name)

        # Handle existing logic for stage updates and assignments
        for _ticket in self:
            now = fields.Datetime.now()
            if vals.get("stage_id"):
                stage = self.env["spp.grm.ticket.stage"].browse([vals["stage_id"]])
                vals["last_stage_update"] = now
                if stage.is_closed:
                    vals["closed_date"] = now
                    if not vals.get("closed_by_id"):
                        vals["closed_by_id"] = self.env.user.id
            if vals.get("user_id"):
                vals["assigned_date"] = now
        return super().write(vals)

    @api.depends("team_id", "category_id")
    def _compute_user_id(self):
        """Compute assigned user based on team or category defaults.

        This provides a suggested assignment but can be overridden manually.
        """
        for ticket in self:
            # Skip if already assigned
            if ticket.user_id:
                continue

            # Try to assign from team manager
            if ticket.team_id and ticket.team_id.manager_id:
                ticket.user_id = ticket.team_id.manager_id
            else:
                ticket.user_id = False

    @api.depends("stage_id", "stage_id.is_closed")
    def _compute_is_closed(self):
        """Compute if ticket is in a closed stage."""
        for ticket in self:
            ticket.is_closed = ticket.stage_id.is_closed if ticket.stage_id else False

    @api.depends("create_date")
    def _compute_days_open(self):
        """Compute number of days the ticket has been open."""
        for ticket in self:
            if ticket.create_date:
                if ticket.closed_date:
                    delta = ticket.closed_date - ticket.create_date
                else:
                    delta = fields.Datetime.now() - ticket.create_date
                ticket.days_open = delta.days
            else:
                ticket.days_open = 0

    @api.depends(
        "category_id",
        "subcategory_id",
        "severity",
        "create_date",
        "category_id.default_sla_hours",
        "subcategory_id.default_sla_hours",
    )
    def _compute_sla_deadline(self):
        """Compute SLA deadline based on category settings and SLA rules.

        This is a simplified implementation. In production, this should
        check spp.grm.sla.rule records for matching conditions.
        Subcategory SLA hours override category SLA hours when set.
        """
        for ticket in self:
            if not ticket.create_date:
                ticket.sla_deadline = False
                continue

            # Default to 72 hours if no category or SLA hours defined
            sla_hours = 72

            # Category SLA hours
            if ticket.category_id and ticket.category_id.default_sla_hours:
                sla_hours = ticket.category_id.default_sla_hours

            # Subcategory SLA hours override category SLA
            if ticket.subcategory_id and ticket.subcategory_id.default_sla_hours:
                sla_hours = ticket.subcategory_id.default_sla_hours

            # TODO: Check SLA rules for more specific deadlines based on conditions
            # For now, use simple category/subcategory-based SLA
            ticket.sla_deadline = ticket.create_date + timedelta(hours=sla_hours)

    @api.depends("sla_deadline", "is_closed")
    def _compute_sla_status(self):
        """Compute SLA status by comparing deadline with current time.

        Per spec Section 4.1, when sla_status changes to 'breached',
        automatic escalation rules are triggered.
        """
        for ticket in self:
            # Track old status to detect transitions
            old_status = ticket._origin.sla_status if ticket._origin else False

            if not ticket.sla_deadline:
                ticket.sla_status = False
                continue

            if ticket.is_closed:
                # For closed tickets, check if they were closed before deadline
                if ticket.closed_date:
                    if ticket.closed_date <= ticket.sla_deadline:
                        ticket.sla_status = "on_track"
                    else:
                        ticket.sla_status = "breached"
                else:
                    ticket.sla_status = False
                continue

            now = fields.Datetime.now()
            time_remaining = ticket.sla_deadline - now

            # Consider "at risk" if less than 25% of time remains
            if now >= ticket.sla_deadline:
                ticket.sla_status = "breached"
            elif time_remaining.total_seconds() > 0:
                # Calculate percentage of time remaining
                total_time = ticket.sla_deadline - ticket.create_date
                if total_time.total_seconds() > 0:
                    remaining_percent = time_remaining.total_seconds() / total_time.total_seconds()
                    if remaining_percent < 0.25:  # Less than 25% time remaining
                        ticket.sla_status = "at_risk"
                    else:
                        ticket.sla_status = "on_track"
                else:
                    ticket.sla_status = "on_track"
            else:
                ticket.sla_status = "breached"

            # Trigger escalation when status transitions to 'breached'
            # Only trigger if the status actually changed to breached (not already breached)
            if ticket.sla_status == "breached" and old_status != "breached":
                # Use sudo() to call _on_sla_breach in a new environment context
                # to avoid triggering compute dependencies during the compute itself
                ticket.sudo()._on_sla_breach()  # nosemgrep: odoo-sudo-without-context

    def _on_sla_breach(self):
        """Called when ticket SLA status changes to breached.

        Per spec Section 4.1, this method:
        1. Checks if spp_grm_cel module is installed
        2. Applies escalation rules if available
        3. Posts a breach notification to the ticket chatter
        """
        for ticket in self:
            # Skip if already escalated to avoid duplicate escalation
            if ticket.is_escalated:
                _logger.debug(
                    "Ticket %s SLA breached but already escalated, skipping auto-escalation",
                    ticket.number,
                )
                continue

            _logger.info(
                "SLA breach detected for ticket %s, triggering auto-escalation",
                ticket.number,
            )

            # Try to apply escalation rules if spp_grm_cel module is installed
            if "spp.grm.escalation.rule" in self.env:
                try:
                    _logger.debug("Applying escalation rules for ticket %s", ticket.number)
                    self.env["spp.grm.escalation.rule"].apply_escalations(ticket)
                except Exception as e:
                    _logger.error(
                        "Error applying escalation rules for ticket %s: %s",
                        ticket.number,
                        str(e),
                    )
            else:
                _logger.debug(
                    "spp_grm_cel module not installed, skipping escalation rules for ticket %s",
                    ticket.number,
                )

            # Post message about SLA breach to ticket chatter
            try:
                ticket.message_post(
                    body=_("SLA breached! Ticket has exceeded the deadline."),
                    subject=_("SLA Breach Alert"),
                    message_type="notification",
                )
                _logger.debug("SLA breach notification posted for ticket %s", ticket.number)
            except Exception as e:
                _logger.error(
                    "Error posting SLA breach notification for ticket %s: %s",
                    ticket.number,
                    str(e),
                )

    @api.onchange("category_id")
    def _onchange_category_id(self):
        """Auto-populate fields based on category defaults."""
        # Clear subcategory when category changes
        if self.category_id:
            self.subcategory_id = False
            if self.category_id.default_severity and not self.severity:
                self.severity = self.category_id.default_severity
            if self.category_id.default_sensitivity and not self.sensitivity:
                self.sensitivity = self.category_id.default_sensitivity
            if self.category_id.default_team_id and not self.team_id:
                self.team_id = self.category_id.default_team_id
        else:
            self.subcategory_id = False

    @api.onchange("subcategory_id")
    def _onchange_subcategory_id(self):
        """Auto-populate fields based on subcategory defaults.

        Subcategory defaults override category defaults when set.
        """
        if self.subcategory_id:
            if self.subcategory_id.default_severity:
                self.severity = self.subcategory_id.default_severity
            if self.subcategory_id.default_sla_hours:
                # Subcategory SLA overrides category SLA
                pass  # Will be handled in _compute_sla_deadline

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        """Read group method for stage_id field."""
        return stages.search(domain)

    def assign_to_me(self):
        self.write({"user_id": self.env.user.id})

    def _prepare_ticket_number(self):
        # Generate ticket number
        return self.env["ir.sequence"].next_by_code("spp.grm.ticket.sequence")

    def get_portal_url(self):
        """Get the URL for the ticket's portal page."""
        self.ensure_one()
        return f"/my/tickets/{self.id}"

    def send_ticket_confirmation_email(self, ticket):
        """Send the ticket submission confirmation email."""
        template = self.env.ref("spp_grm.ticket_submission_confirmation", raise_if_not_found=False)
        if template:
            template.sudo().send_mail(  # nosemgrep: odoo-sudo-without-context
                ticket.id,
                force_send=True,
                email_values={
                    "email_to": ticket.partner_id.email,
                },
            )
        else:
            _logger.warning("Email template not found: spp_grm.ticket_submission_confirmation")
