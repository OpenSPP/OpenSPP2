# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class GISReportDRIMSExtension(models.Model):
    """Extend GIS Report to support DRIMS models as data sources."""

    _inherit = "spp.gis.report"

    @api.model
    def _get_gis_report_source_models(self):
        """Add DRIMS models to supported GIS report sources."""
        models = super()._get_gis_report_source_models()
        return models + ["spp.drims.request"]
