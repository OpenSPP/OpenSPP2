from odoo import fields, models


class SPPGRMTeam(models.Model):
    """GRM Team model for organizing ticket handlers.

    Teams represent groups of users responsible for handling tickets
    in specific areas or categories with defined management structure.
    """

    _name = "spp.grm.team"
    _description = "GRM Team"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(
        string="Team Name",
        required=True,
        translate=True,
        help="Name of the GRM team",
    )
    active = fields.Boolean(
        default=True,
        help="Set to inactive to hide team without deleting it",
    )
    manager_id = fields.Many2one(
        comodel_name="res.users",
        string="Team Manager",
        help="User responsible for managing this team",
    )
    member_ids = fields.Many2many(
        comodel_name="res.users",
        relation="grm_team_member_rel",
        column1="team_id",
        column2="user_id",
        string="Team Members",
        help="Users who are members of this team",
    )
    area_ids = fields.Many2many(
        comodel_name="spp.area",
        relation="grm_team_area_rel",
        column1="team_id",
        column2="area_id",
        string="Areas",
        help="Geographic areas this team is responsible for (optional)",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        help="Company this team belongs to",
    )

    # Statistics (computed fields)
    ticket_count = fields.Integer(
        string="Number of Tickets",
        compute="_compute_ticket_count",
        help="Total number of tickets assigned to this team",
    )
    open_ticket_count = fields.Integer(
        string="Open Tickets",
        compute="_compute_ticket_count",
        help="Number of open tickets assigned to this team",
    )

    def _compute_ticket_count(self):
        """Compute ticket statistics for the team.

        Note: No @api.depends as this is a search-based computed field
        that should be recomputed on each access.
        """
        for team in self:
            tickets = self.env["spp.grm.ticket"].search([("team_id", "=", team.id)])
            team.ticket_count = len(tickets)
            team.open_ticket_count = len(tickets.filtered(lambda t: not t.is_closed))

    def name_get(self):
        """Display team name with member count."""
        result = []
        for team in self:
            member_count = len(team.member_ids)
            name = f"{team.name} ({member_count} members)"
            result.append((team.id, name))
        return result

    def action_view_tickets(self):
        """Open view with tickets assigned to this team."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Tickets - {self.name}",
            "res_model": "spp.grm.ticket",
            "view_mode": "tree,form,kanban",
            "domain": [("team_id", "=", self.id)],
            "context": {"default_team_id": self.id},
        }
