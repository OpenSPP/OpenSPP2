# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EscalateToCaseWizard(models.TransientModel):
    """Wizard to escalate GRM ticket to case management case."""

    _name = "spp.grm.escalate.wizard"
    _description = "Escalate GRM Ticket to Case"

    ticket_id = fields.Many2one(
        "spp.grm.ticket",
        string="Ticket",
        required=True,
        ondelete="cascade",
    )
    ticket_number = fields.Char(
        related="ticket_id.number",
        string="Ticket Number",
        readonly=True,
    )
    ticket_description = fields.Text(
        related="ticket_id.description",
        string="Ticket Description",
        readonly=True,
    )
    partner_id = fields.Many2one(
        related="ticket_id.partner_id",
        string="Registrant",
        readonly=True,
    )

    # Case creation fields
    case_type_id = fields.Many2one(
        "spp.case.type",
        string="Case Type",
        required=True,
        help="Type of case to create",
    )
    intensity_level = fields.Selection(
        [
            ("1", "Level 1 - Low Intensity"),
            ("2", "Level 2 - Medium Intensity"),
            ("3", "Level 3 - High Intensity"),
        ],
        default="2",
        required=True,
        help="Level of case management intensity required",
    )
    case_worker_id = fields.Many2one(
        "res.users",
        string="Case Worker",
        domain=[("share", "=", False)],
        help="Assigned case worker (defaults to ticket assignee)",
    )
    supervisor_id = fields.Many2one(
        "res.users",
        string="Supervisor",
        domain=[("share", "=", False)],
        help="Case supervisor",
    )
    team_id = fields.Many2one(
        "spp.case.team",
        string="Team",
        help="Team responsible for the case",
    )

    # Options
    copy_description = fields.Boolean(
        string="Copy Ticket Description to Case",
        default=True,
        help="Copy ticket description as presenting issue in case",
    )
    close_ticket = fields.Boolean(
        string="Close Ticket After Escalation",
        default=True,
        help="Mark ticket as resolved after creating case",
    )
    close_decision = fields.Selection(
        [
            ("upheld", "Upheld"),
            ("partially_upheld", "Partially Upheld"),
            ("rejected", "Rejected"),
            ("withdrawn", "Withdrawn"),
            ("redirected", "Redirected"),
            ("referred_to_case", "Referred to Case"),
        ],
        default="referred_to_case",
        help="Decision to record when closing ticket",
    )
    notes = fields.Text(
        string="Escalation Notes",
        help="Additional notes about the escalation",
    )

    @api.onchange("case_type_id")
    def _onchange_case_type_id(self):
        """Set default intensity from case type."""
        if self.case_type_id and self.case_type_id.default_intensity:
            self.intensity_level = self.case_type_id.default_intensity

    @api.onchange("team_id")
    def _onchange_team_id(self):
        """Set supervisor from team."""
        if self.team_id and self.team_id.supervisor_id:
            self.supervisor_id = self.team_id.supervisor_id

    def action_escalate(self):
        """Create case and link to ticket."""
        self.ensure_one()

        # Validate ticket can be escalated
        if self.ticket_id.case_id:
            raise ValidationError(
                _("Ticket %(ticket_number)s is already linked to Case %(case_name)s.")
                % {"ticket_number": self.ticket_id.number, "case_name": self.ticket_id.case_id.name}
            )

        # Prepare case values
        case_vals = {
            "case_type_id": self.case_type_id.id,
            "intensity_level": self.intensity_level,
            "partner_id": self.ticket_id.partner_id.id,
            "client_type": "individual" if self.ticket_id.partner_id.is_group is False else "group",
            "source_grm_ticket_id": self.ticket_id.id,
            "intake_source": "grm",
        }

        # Set case worker (default to ticket user_id)
        if self.case_worker_id:
            case_vals["case_worker_id"] = self.case_worker_id.id
        elif self.ticket_id.user_id:
            case_vals["case_worker_id"] = self.ticket_id.user_id.id
        else:
            case_vals["case_worker_id"] = self.env.user.id

        # Set supervisor
        if self.supervisor_id:
            case_vals["supervisor_id"] = self.supervisor_id.id

        # Set team
        if self.team_id:
            case_vals["team_id"] = self.team_id.id

        # Copy description if requested
        if self.copy_description and self.ticket_id.description:
            case_vals["presenting_issue"] = (
                f"<p><strong>Escalated from GRM Ticket {self.ticket_id.number}</strong></p>{self.ticket_id.description}"
            )
            if self.notes:
                case_vals["presenting_issue"] += f"<p><strong>Escalation Notes:</strong></p><p>{self.notes}</p>"
        else:
            case_vals["presenting_issue"] = (
                f"<p>Escalated from GRM Ticket {self.ticket_id.number}: {self.ticket_id.name}</p>"
            )
            if self.notes:
                case_vals["presenting_issue"] += f"<p><strong>Escalation Notes:</strong></p><p>{self.notes}</p>"

        # Create the case
        case = self.env["spp.case"].create(case_vals)

        # Link ticket to case
        self.ticket_id.case_id = case.id

        # Close ticket if requested
        if self.close_ticket:
            # Find resolved stage
            resolved_stage = self.env["spp.grm.ticket.stage"].search(
                [
                    "|",
                    ("stage_type", "=", "resolved"),
                    ("is_closed", "=", True),
                ],
                limit=1,
            )
            if resolved_stage:
                self.ticket_id.write(
                    {
                        "stage_id": resolved_stage.id,
                        "decision": self.close_decision,
                    }
                )

        # Post messages
        ticket_message = _(
            "Ticket escalated to Case <a href='/web#id=%(case_id)s&model=spp.case'>%(case_name)s</a>",
            case_id=case.id,
            case_name=case.name,
        )
        if self.notes:
            ticket_message += "<br/><strong>{}</strong> {}".format(_("Notes:"), self.notes)
        self.ticket_id.message_post(
            body=ticket_message,
            subtype_xmlid="mail.mt_note",
        )

        case.message_post(
            body=_(
                "Case created from GRM Ticket "
                "<a href='/web#id=%(ticket_id)s&model=spp.grm.ticket'>%(ticket_number)s</a>: %(ticket_name)s",
                ticket_id=self.ticket_id.id,
                ticket_number=self.ticket_id.number,
                ticket_name=self.ticket_id.name,
            ),
            subtype_xmlid="mail.mt_note",
        )

        # Return action to open the created case
        return {
            "type": "ir.actions.act_window",
            "name": "Case Created",
            "res_model": "spp.case",
            "view_mode": "form",
            "res_id": case.id,
            "target": "current",
        }

    def action_cancel(self):
        """Cancel escalation."""
        return {"type": "ir.actions.act_window_close"}
