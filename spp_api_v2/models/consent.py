# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
API V2 Consent Extensions.

Extends the base spp.consent model with API-specific features.
The base model in spp_consent provides:
- DPV-aligned consent management
- Category-based recipient matching (recipient_mode, allowed_recipient_types)
- Core consent checking (check_consent method)

This module adds API-specific extensions:
- API scopes (what resources/fields can be accessed)
- Access logging for GDPR accountability
- API-specific consent checking (uses base check_consent)
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class Consent(models.Model):
    """Extend consent model for API V2 data sharing."""

    _inherit = "spp.consent"

    # ========================================================================
    # API-SPECIFIC FIELDS
    # These extend the base consent model with API-specific features.
    # Generic consent features (recipient_mode, allowed_recipient_types) are
    # defined in the base spp_consent module.
    # ========================================================================

    # What they can access via API
    api_scope_ids = fields.One2many(
        "spp.consent.scope",
        "consent_id",
        string="API Scopes",
        help="Define what resources and fields can be accessed via API",
    )

    # Access log for GDPR accountability (unified API audit log)
    access_log_ids = fields.One2many(
        "spp.api.audit.log",
        "consent_id",
        string="Access Logs",
    )
    access_count = fields.Integer(compute="_compute_access_count")

    @api.depends("access_log_ids")
    def _compute_access_count(self):
        for rec in self:
            rec.access_count = len(rec.access_log_ids)

    def action_view_access_logs(self):
        """Open access log view for this consent"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Access Logs: {self.name}",
            "res_model": "spp.api.audit.log",
            "view_mode": "list,form",
            "domain": [("consent_id", "=", self.id)],
        }

    @api.model
    def check_api_consent(self, registrant_id, recipient_id, resource_type, api_client=None):
        """
        Check if active consent exists for registrant to allow API access.

        This method extends the base check_consent with API-specific scope checking.
        It uses the base consent module's recipient matching (specific or category-based).

        Args:
            registrant_id: ID of registrant whose data is being accessed
            recipient_id: ID of organization requesting access
            resource_type: Type of resource (individual, group, etc.)
            api_client: Optional spp.api.client record for category-based matching

        Returns:
            spp.consent record if active consent with matching API scope found,
            otherwise empty recordset
        """
        # Get organization type from API client for category-based matching
        org_type_code = None
        if api_client:
            org_type_code = getattr(api_client, "organization_type", None)

        # Use base consent check - handles specific and category matching
        consent = self.check_consent(
            registrant_id=registrant_id,
            recipient_id=recipient_id,
            recipient_org_type=org_type_code,
        )

        if not consent:
            # Try group consent for individuals
            if resource_type == "individual":
                partner = self.env["res.partner"].browse(registrant_id)
                # Get active group memberships
                active_memberships = partner.individual_membership_ids.filtered(lambda m: not m.is_ended)
                if active_memberships:
                    # Check consent for each group (typically just one)
                    for membership in active_memberships:
                        consent = self.check_consent(
                            registrant_id=membership.group.id,
                            recipient_id=recipient_id,
                            recipient_org_type=org_type_code,
                        )
                        if consent:
                            break

        if not consent:
            return self.env["spp.consent"]

        # API-specific: Also check that consent covers this resource type via api_scope_ids
        matching_scope = consent.api_scope_ids.filtered(lambda s: s.resource_type in (resource_type, "all"))
        if not matching_scope:
            # Consent exists but doesn't cover this resource type
            return self.env["spp.consent"]

        return consent

    def generate_api_receipt(self):
        """
        Generate an API-specific consent receipt.

        This wraps the base receipt with API-specific scope information.

        Returns a dict suitable for JSON serialization.
        """
        self.ensure_one()

        # Get base receipt from DPV-aligned generate_receipt
        receipt = self.generate_receipt()

        # Add API-specific scopes
        receipt["api_scopes"] = [
            {
                "purpose": scope.purpose,
                "resource_type": scope.resource_type,
                "field_access": scope.field_access,
            }
            for scope in self.api_scope_ids
        ]

        # Add recipient mode info (uses base consent fields)
        receipt["recipient_mode"] = self.recipient_mode
        if self.recipient_mode == "category" and self.allowed_recipient_types:
            receipt["allowed_recipient_types"] = [
                {"code": t.code, "name": t.name} for t in self.allowed_recipient_types
            ]

        return receipt
