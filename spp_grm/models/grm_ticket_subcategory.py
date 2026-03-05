from odoo import fields, models


class SPPGRMTicketSubcategory(models.Model):
    """Subcategory model for GRM tickets.

    Provides a second level of categorization under the main category.
    """

    _name = "spp.grm.ticket.subcategory"
    _description = "GRM Ticket Subcategory"
    _order = "category_id, sequence, name"

    name = fields.Char(
        required=True,
        translate=True,
    )
    code = fields.Char(
        help="Unique code for this subcategory",
    )
    category_id = fields.Many2one(
        comodel_name="spp.grm.ticket.category",
        string="Parent Category",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(translate=True)

    # Default settings inherited when selected
    default_severity = fields.Selection(
        selection=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
    )
    default_sla_hours = fields.Integer(
        string="Default SLA Hours",
        help="Override category SLA hours for this subcategory",
    )

    # Statistics
    ticket_count = fields.Integer(
        compute="_compute_ticket_count",
        string="Tickets",
    )

    _code_category_unique = models.Constraint(
        "UNIQUE(code, category_id)",
        "Subcategory code must be unique within the category!",
    )

    def _compute_ticket_count(self):
        for subcat in self:
            subcat.ticket_count = self.env["spp.grm.ticket"].search_count([("subcategory_id", "=", subcat.id)])

    def name_get(self):
        """Display full path: Category / Subcategory."""
        result = []
        for subcat in self:
            name = f"{subcat.category_id.name} / {subcat.name}"
            result.append((subcat.id, name))
        return result
