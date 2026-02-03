# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Privacy Notice for Consent - ISO 27560 / ISO 29184 aligned.

Privacy notices inform data subjects about processing before consent.
See: ISO/IEC 29184:2020 - Online privacy notices and consent
"""

from odoo import api, fields, models


class ConsentNotice(models.Model):
    """
    Privacy Notice shown to data subjects before obtaining consent.

    Aligned with ISO/IEC 29184:2020 requirements for privacy notices.
    Tracks versions to ensure we know what was shown at consent time.
    """

    _name = "spp.consent.notice"
    _description = "Privacy Notice"
    _order = "name, version desc"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Unique code for this notice type",
    )

    # Version tracking
    version = fields.Char(
        required=True,
        default="1.0",
        help="Notice version (e.g., '1.0', '2.1')",
    )
    effective_date = fields.Date(
        required=True,
        default=fields.Date.today,
        help="When this version becomes effective",
    )
    supersedes_id = fields.Many2one(
        "spp.consent.notice",
        string="Supersedes",
        help="Previous version this notice replaces",
    )

    # Content (ISO 29184 elements)
    summary = fields.Text(
        string="Summary",
        translate=True,
        help="Brief plain-language summary of the notice",
    )
    full_text = fields.Html(
        string="Full Notice Text",
        translate=True,
        help="Complete privacy notice content",
    )

    # ISO 29184 required elements
    controller_info = fields.Text(
        string="Data Controller Information",
        translate=True,
        help="Identity and contact details of the controller",
    )
    purpose_description = fields.Text(
        string="Purpose Description",
        translate=True,
        help="Description of processing purposes",
    )
    data_categories_description = fields.Text(
        string="Data Categories",
        translate=True,
        help="Categories of personal data processed",
    )
    recipients_description = fields.Text(
        string="Recipients",
        translate=True,
        help="Categories of recipients",
    )
    retention_description = fields.Text(
        string="Retention Period",
        translate=True,
        help="How long data will be kept",
    )
    rights_description = fields.Text(
        string="Data Subject Rights",
        translate=True,
        help="Information about data subject rights",
    )
    withdrawal_description = fields.Text(
        string="How to Withdraw Consent",
        translate=True,
        help="Instructions for withdrawing consent",
    )

    # DPV Taxonomy References
    purpose_ids = fields.Many2many(
        "spp.consent.purpose",
        "consent_notice_purpose_rel",
        "notice_id",
        "purpose_id",
        string="Purposes",
        help="Data processing purposes covered by this notice",
    )
    data_category_ids = fields.Many2many(
        "spp.consent.personal.data",
        "consent_notice_data_rel",
        "notice_id",
        "data_id",
        string="Data Categories",
        help="Personal data categories covered by this notice",
    )
    processing_type_ids = fields.Many2many(
        "spp.consent.processing",
        "consent_notice_processing_rel",
        "notice_id",
        "processing_id",
        string="Processing Types",
        help="Processing operations covered by this notice",
    )

    # Consent Boundary: Organization Types
    # This defines the MAXIMUM scope - consents using this notice cannot exceed these
    max_recipient_types = fields.Many2many(
        "spp.consent.org.type",
        "consent_notice_max_org_type_rel",
        "notice_id",
        "org_type_id",
        string="Allowed Recipient Types",
        help="Organization types that can receive data under this notice. "
        "When a consent uses this notice, it can only include a subset of these types. "
        "This ensures informed consent - beneficiaries cannot consent to recipients "
        "not described in the notice they were shown.",
    )

    # Contact Information
    dpo_contact = fields.Char(
        string="Data Protection Officer Contact",
        help="Contact information for the DPO (email, phone, or address)",
    )

    # Links
    contact_email = fields.Char(string="Contact Email")
    contact_url = fields.Char(string="Contact URL")
    full_policy_url = fields.Char(string="Full Privacy Policy URL")

    # Jurisdiction
    jurisdiction = fields.Char(
        help="Legal jurisdiction (e.g., 'EU', 'KE')",
    )
    applicable_law = fields.Char(
        help="Applicable data protection law",
    )

    # Language
    language = fields.Selection(
        [
            ("en", "English"),
            ("fr", "French"),
            ("es", "Spanish"),
            ("ar", "Arabic"),
            ("sw", "Swahili"),
        ],
        default="en",
        help="Primary language of the notice",
    )

    # Status
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
    )

    active = fields.Boolean(default=True)

    _unique_code_version = models.Constraint("UNIQUE(code, version)", "Notice code + version must be unique")

    def name_get(self):
        """Display name with version"""
        result = []
        for rec in self:
            result.append((rec.id, f"{rec.name} (v{rec.version})"))
        return result

    def action_activate(self):
        """Activate this notice version"""
        self.ensure_one()
        # Archive previous versions with same code
        previous = self.search(
            [
                ("code", "=", self.code),
                ("id", "!=", self.id),
                ("state", "=", "active"),
            ]
        )
        previous.write({"state": "archived"})
        self.state = "active"

    def action_archive(self):
        """Archive this notice"""
        self.ensure_one()
        self.state = "archived"

    @api.model
    def get_active_notice(self, code):
        """Get the currently active notice for a code"""
        return self.search(
            [
                ("code", "=", code),
                ("state", "=", "active"),
            ],
            limit=1,
        )
