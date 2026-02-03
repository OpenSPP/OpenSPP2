# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Registrant consent extensions.

Adds consent_summary cache field for O(1) consent lookups in API filtering.
"""

from odoo import api, fields, models


class OpenSPPRegistrant(models.Model):
    _name = "res.partner"
    _inherit = [_name, "spp.consent.mixin"]

    consent_summary = fields.Json(
        string="Consent Summary",
        compute="_compute_consent_summary",
        store=True,
        help="Cached summary of active consents for fast API filtering. "
        "Contains allowed org types, purposes, and specific recipients.",
    )

    @api.depends(
        "consent_ids.status",
        "consent_ids.expiry",
        "consent_ids.recipient_mode",
        "consent_ids.allowed_recipient_types.code",
        "consent_ids.recipient_ids",
        "consent_ids.purpose_ids.code",
    )
    def _compute_consent_summary(self):
        """Build consent summary for fast API lookups.

        Aggregates all valid (given/renewed, not expired) consents into a single
        JSON structure that can be used for O(1) consent checks in API filtering.

        Note: We query consents directly via signatory_id/group_id since the
        consent_ids Many2many might not be populated for all consents.
        """
        today = fields.Date.today()
        Consent = self.env["spp.consent"]

        for partner in self:
            # Query consents where this partner is the signatory or group
            # This works regardless of how the consent was created
            all_consents = Consent.search(
                [
                    "|",
                    ("signatory_id", "=", partner.id),
                    ("group_id", "=", partner.id),
                ]
            )

            # Filter for valid (given/renewed, not expired) consents
            valid_consents = all_consents.filtered(
                lambda consent: consent.status in ("given", "renewed")
                and (not consent.expiry or consent.expiry >= today)
            )

            if not valid_consents:
                partner.consent_summary = {}
                continue

            # Aggregate allowed org types, purposes, and specific recipients
            organization_types = set()
            purposes = set()
            specific_recipients = set()

            for consent in valid_consents:
                # Collect purposes
                purposes.update(consent.purpose_ids.mapped("code"))

                # Collect recipient info based on mode
                if consent.recipient_mode == "category":
                    organization_types.update(consent.allowed_recipient_types.mapped("code"))
                else:
                    specific_recipients.update(consent.recipient_ids.ids)

            partner.consent_summary = {
                "organization_types": sorted(organization_types),
                "purposes": sorted(purposes),
                "specific_recipients": sorted(specific_recipients),
                "last_updated": fields.Datetime.now().isoformat(),
            }
