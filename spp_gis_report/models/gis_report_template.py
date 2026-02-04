import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class GISReportTemplate(models.Model):
    """Pre-built GIS report templates with JSON configuration storage."""

    _name = "spp.gis.report.template"
    _description = "GIS Report Template"
    _order = "category_id, sequence, name"

    name = fields.Char(
        "Template Name",
        required=True,
        translate=True,
        help="Template name visible to users",
    )
    code = fields.Char(
        "Code",
        required=True,
        help="Unique code identifier for the template",
    )
    description = fields.Text(
        "Description",
        translate=True,
        help="Detailed description of what this template provides",
    )
    category_id = fields.Many2one(
        "spp.gis.report.category",
        "Category",
        help="Category for organizing templates",
    )
    sequence = fields.Integer(
        "Sequence",
        default=10,
        help="Display order within category",
    )
    icon = fields.Char(
        "Icon",
        default="fa-map",
        help="Font Awesome icon class",
    )
    active = fields.Boolean(
        "Active",
        default=True,
        help="Inactive templates are hidden from creation wizard",
    )

    # Template configuration (stored as JSON for flexibility)
    config = fields.Json(
        "Configuration",
        required=True,
        help="Template configuration including source_model, aggregation_method, "
        "normalization_method, color_scheme, etc.",
    )

    # Requirements (what the template needs to function)
    requires_program = fields.Boolean(
        "Requires Program Selection",
        help="User must select a program when creating report from this template",
    )
    requires_incident = fields.Boolean(
        "Requires Incident Selection",
        help="User must select an incident when creating report from this template",
    )
    requires_reference_data = fields.Char(
        "Required Reference Data",
        help="Comma-separated list of required reference data: " "population, household_count, eligible_count",
    )

    # Preview
    preview_image = fields.Binary(
        "Preview Image",
        help="Preview image showing example output",
    )

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "Template code must be unique",
    )

    def action_create_report(self):
        """Open wizard to create a report from this template.

        Returns:
            dict: Window action to open the creation wizard
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Report from Template"),
            "res_model": "spp.gis.report.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_template_id": self.id},
        }
