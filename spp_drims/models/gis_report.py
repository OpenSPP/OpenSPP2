# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class GISReportDRIMSExtension(models.Model):
    """Extend GIS Report to support DRIMS-specific data sources."""

    _inherit = "spp.gis.report"

    @api.model
    def _get_gis_report_source_models(self):
        """Add DRIMS models to supported GIS report sources.

        Registers:
        - spp.drims.request: For request distribution, affected population,
          pending requests, relief value, and fulfillment progress reports
        - spp.hazard.incident.area: For incident severity visualization
          by geographic area
        """
        source_models = super()._get_gis_report_source_models()
        return source_models + ["spp.drims.request", "spp.hazard.incident.area"]
