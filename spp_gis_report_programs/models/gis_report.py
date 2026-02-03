# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
from odoo.osv import expression


class GISReportProgramsExtension(models.Model):
    """Extend GIS Report with program context filtering."""

    _inherit = "spp.gis.report"

    program_id = fields.Many2one(
        "spp.program",
        "Program Context",
        help="Filter records to those related to this program",
    )

    def _apply_context_filters(self, domain):
        """Add program context filter to domain."""
        domain = super()._apply_context_filters(domain)

        if self.program_id and self.source_model == "res.partner":
            # Filter to registrants enrolled in the program
            domain = expression.AND([
                domain,
                [("program_membership_ids.program_id", "=", self.program_id.id)]
            ])

        return domain
