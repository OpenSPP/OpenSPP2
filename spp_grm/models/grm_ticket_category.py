from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SPPGRMCategory(models.Model):
    """Enhanced Ticket Category model with hierarchy and defaults.

    Categories can be organized hierarchically and provide default
    values for tickets including severity, sensitivity, SLA, and team assignment.
    """

    _name = "spp.grm.ticket.category"
    _description = "Grievance Redress Mechanism Ticket Category"
    _order = "sequence, id"
    _parent_name = "parent_id"
    _parent_store = True

    sequence = fields.Integer(default=10)
    active = fields.Boolean(
        default=True,
    )
    name = fields.Char(
        required=True,
        translate=True,
    )
    code = fields.Char(
        string="Code",
        help="Unique identifier code for this category",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    # Hierarchy Fields
    parent_id = fields.Many2one(
        comodel_name="spp.grm.ticket.category",
        string="Parent Category",
        ondelete="restrict",
        index=True,
        help="Parent category for creating hierarchical category structure",
    )
    parent_path = fields.Char(
        index=True,
        help="Technical field for hierarchy management",
    )
    child_ids = fields.One2many(
        comodel_name="spp.grm.ticket.category",
        inverse_name="parent_id",
        string="Child Categories",
        help="Sub-categories under this category",
    )
    subcategory_ids = fields.One2many(
        comodel_name="spp.grm.ticket.subcategory",
        inverse_name="category_id",
        string="Subcategories",
        help="Second-level subcategories under this category",
    )

    # Default Values for Tickets
    default_severity = fields.Selection(
        selection=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        string="Default Severity",
        help="Default severity level for tickets in this category",
    )
    default_sensitivity = fields.Selection(
        selection=[
            ("standard", "Standard"),
            ("sensitive", "Sensitive"),
            ("highly_sensitive", "Highly Sensitive"),
        ],
        string="Default Sensitivity",
        help="Default data sensitivity for tickets in this category",
    )
    default_sla_hours = fields.Integer(
        string="Default SLA Hours",
        help="Default SLA resolution time in hours for tickets in this category",
    )
    default_team_id = fields.Many2one(
        comodel_name="spp.grm.team",
        string="Default Team",
        help="Default team to assign tickets in this category",
    )

    # Automation Settings
    should_auto_escalate = fields.Boolean(
        string="Auto Escalate",
        default=False,
        help="Automatically escalate tickets in this category based on SLA rules",
    )
    auto_create_case = fields.Boolean(
        string="Auto Create Case",
        default=False,
        help="Automatically create a case management record for tickets in this category",
    )

    @api.constrains("code")
    def _check_code_unique(self):
        """Ensure category code is unique if provided."""
        for category in self:
            if category.code:
                duplicate = self.search(
                    [
                        ("code", "=", category.code),
                        ("id", "!=", category.id),
                        ("company_id", "=", category.company_id.id),
                    ],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(
                        _(
                            "Category code '%(code)s' already exists for company %(company)s. "
                            "Category codes must be unique per company.",
                            code=category.code,
                            company=category.company_id.name,
                        )
                    )

    @api.constrains("parent_id")
    def _check_category_recursion(self):
        """Prevent circular references in category hierarchy."""
        if not self._check_recursion():
            raise ValidationError(_("Error! You cannot create recursive categories."))

    def name_get(self):
        """Display full category path in name."""
        result = []
        for category in self:
            names = []
            current = category
            while current:
                names.append(current.name)
                current = current.parent_id
            result.append((category.id, " / ".join(reversed(names))))
        return result
