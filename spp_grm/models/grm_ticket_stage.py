from odoo import api, fields, models


class SPPGRMTicketStage(models.Model):
    """Enhanced Ticket Stage model with workflow and SLA features.

    Stages represent different states in the ticket lifecycle with
    enhanced capabilities for access control, SLA tracking, and workflow rules.
    """

    _name = "spp.grm.ticket.stage"
    _description = "Grievance Redress Mechanism Ticket Stage"
    _order = "sequence, id"

    name = fields.Char(string="Stage Name", required=True, translate=True)
    description = fields.Html(translate=True, sanitize_style=True)
    sequence = fields.Integer(default=1)
    active = fields.Boolean(default=True)
    unattended = fields.Boolean(
        help="Tickets in this stage are considered unattended",
    )
    is_closed = fields.Boolean(
        default=False,
        help="Indicates this is a closed/final stage",
    )
    mail_template_id = fields.Many2one(
        comodel_name="mail.template",
        string="Email Template",
        domain=[("model", "=", "spp.grm.ticket")],
        help="If set an email will be sent to the customer when the ticket reaches this step.",
    )
    fold = fields.Boolean(
        string="Folded in Kanban",
        help="This stage is folded in the kanban view when there are no records in that stage to display.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    # Enhanced Stage Classification
    stage_type = fields.Selection(
        selection=[
            ("new", "New"),
            ("in_progress", "In Progress"),
            ("waiting", "Waiting"),
            ("escalated", "Escalated"),
            ("resolved", "Resolved"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        help="Categorization of the stage for workflow logic",
    )

    # Workflow Control Fields
    is_requires_approval = fields.Boolean(
        string="Requires Approval",
        default=False,
        help="Tickets in this stage require approval before proceeding",
    )
    is_requires_decision = fields.Boolean(
        string="Requires Decision",
        default=False,
        help="A decision must be recorded before closing tickets in this stage",
    )

    # SLA Configuration
    sla_hours = fields.Integer(
        string="SLA Hours",
        help="Maximum hours a ticket should remain in this stage before escalation",
    )

    # Access Control
    allowed_group_ids = fields.Many2many(
        comodel_name="res.groups",
        relation="grm_ticket_stage_group_rel",
        column1="stage_id",
        column2="group_id",
        string="Allowed Groups",
        help="Only users in these groups can move tickets to this stage",
    )

    @api.onchange("is_closed")
    def _onchange_is_closed(self):
        """Set stage_type to closed when is_closed is True."""
        if self.is_closed:
            if not self.stage_type:
                self.stage_type = "closed"
