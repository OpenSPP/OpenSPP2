# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extension to spp.dci.data.source for compliance testing."""

from odoo import fields, models


class DCIDataSourceCompliance(models.Model):
    """Add compliance testing flag to DCI data sources."""

    _inherit = "spp.dci.data.source"

    is_compliance_test = fields.Boolean(
        string="Compliance Test",
        default=False,
        help="Mark this data source as used for DCI compliance testing. "
        "Only one data source should have this flag enabled.",
    )
