# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import _, fields, models
from odoo.exceptions import ValidationError


class GISReportWizardProgramsExtension(models.TransientModel):
    """Extend GIS Report Wizard with program context field."""

    _inherit = "spp.gis.report.wizard"

    program_id = fields.Many2one(
        "spp.program",
        string="Program",
        help="Filter data for this program (required for some templates)",
    )

    def _validate_context_requirements(self):
        """Add program requirement validation."""
        super()._validate_context_requirements()
        if self.template_requires_program and not self.program_id:
            raise ValidationError(_("This template requires selecting a program."))

    def _get_context_filter_vals(self):
        """Add program_id to report creation values."""
        vals = super()._get_context_filter_vals()
        if self.program_id:
            vals["program_id"] = self.program_id.id
        return vals

    def _get_context_code_suffix(self):
        """Add program ID to report code suffix."""
        suffix = super()._get_context_code_suffix()
        if self.program_id:
            suffix = f"{suffix}_{self.program_id.id}"
        return suffix
