import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class GISReportCategory(models.Model):
    """GIS Report Category for organizing reports."""

    _name = "spp.gis.report.category"
    _description = "GIS Report Category"
    _order = "sequence, name"

    name = fields.Char(
        "Name",
        required=True,
        translate=True,
        help="Category name visible to users",
    )
    code = fields.Char(
        "Code",
        required=True,
        help="Unique code identifier for the category",
    )
    sequence = fields.Integer(
        "Sequence",
        default=10,
        help="Display order of the category",
    )
    icon = fields.Char(
        "Icon",
        default="fa-folder",
        help="Font Awesome icon class",
    )
    color = fields.Integer(
        "Color Index",
        help="Color index for visual distinction (0-11)",
    )
    active = fields.Boolean(
        "Active",
        default=True,
        help="Inactive categories are hidden from menus",
    )

    # Relations
    report_ids = fields.One2many(
        "spp.gis.report",
        "category_id",
        "Reports",
        help="Reports in this category",
    )
    report_count = fields.Integer(
        "Report Count",
        compute="_compute_report_count",
        help="Number of reports in this category",
    )
    template_ids = fields.One2many(
        "spp.gis.report.template",
        "category_id",
        "Templates",
        help="Templates in this category",
    )

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "Category code must be unique",
    )

    @api.depends("report_ids")
    def _compute_report_count(self):
        """Compute the number of reports in this category."""
        for category in self:
            category.report_count = len(category.report_ids)

    def action_view_reports(self):
        """Open reports in this category."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "spp.gis.report",
            "view_mode": "list,form",
            "domain": [("category_id", "=", self.id)],
            "context": {"default_category_id": self.id},
        }
