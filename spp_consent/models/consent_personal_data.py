# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
DPV-aligned Personal Data Categories.

Based on W3C Data Privacy Vocabulary (DPV) personal data taxonomy.
See: https://w3id.org/dpv#PersonalData
"""

from odoo import fields, models


class ConsentPersonalData(models.Model):
    """
    Personal data categories covered by consent - aligned with W3C DPV.

    Categorizes types of personal data that may be processed,
    distinguishing between regular and sensitive (special category) data.
    """

    _name = "spp.consent.personal.data"
    _description = "Personal Data Category (DPV-aligned)"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Unique code (e.g., 'Identifying', 'Financial')",
    )
    description = fields.Text(translate=True)

    # DPV alignment
    dpv_uri = fields.Char(
        string="DPV URI",
        help="W3C DPV URI (e.g., 'https://w3id.org/dpv#Identifying')",
    )
    dpv_concept = fields.Char(
        string="DPV Concept",
        help="DPV concept name (e.g., 'dpv:Identifying')",
    )

    # Special category data (GDPR Article 9)
    is_sensitive = fields.Boolean(
        string="Sensitive Data",
        help="Special category data requiring additional protection (GDPR Art. 9)",
    )
    sensitivity_reason = fields.Selection(
        [
            ("racial_ethnic", "Racial or Ethnic Origin"),
            ("political", "Political Opinions"),
            ("religious", "Religious or Philosophical Beliefs"),
            ("trade_union", "Trade Union Membership"),
            ("genetic", "Genetic Data"),
            ("biometric", "Biometric Data"),
            ("health", "Health Data"),
            ("sex_life", "Sex Life or Sexual Orientation"),
            ("criminal", "Criminal Convictions"),
        ],
        string="Sensitivity Category",
        help="GDPR Article 9 special category",
    )

    # Social protection specific
    is_social_protection = fields.Boolean(
        string="Social Protection Specific",
        help="Data category specific to social protection",
    )

    # Examples of fields in this category
    example_fields = fields.Text(
        help="Example data fields in this category",
    )

    # UI
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _unique_code = models.Constraint("UNIQUE(code)", "Personal data code must be unique")
