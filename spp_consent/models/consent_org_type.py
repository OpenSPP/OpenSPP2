# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Organization Type model for category-based consent.

Allows beneficiaries to consent to data sharing with categories of organizations
(e.g., "all NGOs" or "all government agencies") rather than specific organizations.
"""

from odoo import fields, models


class ConsentOrgType(models.Model):
    """
    Organization type for category-based consent matching.

    Examples:
    - Government agencies
    - NGOs / Non-profits
    - UN agencies
    - Private sector (often excluded by beneficiaries)
    """

    _name = "spp.consent.org.type"
    _description = "Organization Type for Consent"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Technical code used for matching (e.g., 'ngo', 'government')",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(translate=True)

    # Visual indicator
    color = fields.Integer(string="Color Index")

    _unique_code = models.Constraint("UNIQUE(code)", "Organization type code must be unique")
