# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ConsentScope(models.Model):
    """Scope of consent - what data can be accessed"""

    _name = "spp.consent.scope"
    _description = "Consent Scope"
    _order = "consent_id, resource_type"

    consent_id = fields.Many2one(
        "spp.consent",
        required=True,
        ondelete="cascade",
        index=True,
    )

    resource_type = fields.Selection(
        [
            ("individual", "Individual Data"),
            ("group", "Group/Household Data"),
            ("program_membership", "Program Enrollment"),
            ("all", "All Data"),
        ],
        required=True,
    )

    # Field-level control
    field_access = fields.Selection(
        [
            ("all", "All Fields"),
            ("basic", "Basic Info Only"),
            ("custom", "Custom Field List"),
        ],
        default="basic",
    )

    custom_fields = fields.Text(
        help="Comma-separated field names when field_access='custom'",
    )

    # Purpose limitation
    purpose = fields.Selection(
        [
            ("service_delivery", "Service Delivery"),
            ("eligibility_verification", "Eligibility Verification"),
            ("analytics", "Anonymized Analytics"),
            ("research", "Research"),
            ("audit", "Audit/Compliance"),
        ],
        required=True,
    )

    # Include extensions?
    include_extensions = fields.Boolean(default=False)
    allowed_extensions = fields.Text(
        help="Comma-separated extension names (e.g., 'farmer,disability')",
    )

    description = fields.Text()

    def name_get(self):
        """Display scope as 'resource_type (purpose)'"""
        result = []
        for rec in self:
            name = f"{rec.resource_type} ({rec.purpose})"
            result.append((rec.id, name))
        return result

    def get_allowed_fields(self):
        """Get set of allowed field names"""
        self.ensure_one()

        if self.field_access == "all":
            return None  # All fields allowed

        if self.field_access == "basic":
            # Basic fields per spec
            return {"identifier", "name", "active", "resourceType", "meta"}

        # Custom fields
        if self.custom_fields:
            fields_set = {f.strip() for f in self.custom_fields.split(",")}
            fields_set.add("identifier")  # Always include identifier
            return fields_set

        return {"identifier"}

    def get_allowed_extensions(self):
        """Get set of allowed extension names"""
        self.ensure_one()

        if not self.include_extensions:
            return set()

        if self.allowed_extensions:
            return {ext.strip() for ext in self.allowed_extensions.split(",")}

        # If include_extensions is True but no specific list, allow all
        return None
