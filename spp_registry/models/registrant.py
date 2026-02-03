# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain

_logger = logging.getLogger(__name__)


class SPPRegistrant(models.Model):
    """Extended res.partner for OpenSPP registry management.

    This model consolidates:
    - Base registrant functionality (spp_registry_base)
    - UI computed fields for badges (spp_registry_ui)
    - Donor tracking (spp_registry_donor)

    Scalability notes:
    - Counts use read_group for batch efficiency when loading multiple records
    - Single record access uses prefetched O2M fields (efficient in Odoo 19)
    - No @api.depends to avoid cache invalidation overhead on large datasets
    """

    _inherit = "res.partner"
    _order = "id DESC"

    # Custom Fields - Base
    address = fields.Text()
    disabled = fields.Datetime("Date Disabled")
    disabled_reason = fields.Text("Reason for Disabling")
    disabled_by = fields.Many2one("res.users")

    reg_ids = fields.One2many("spp.registry.id", "partner_id", "Registrant IDs")
    is_registrant = fields.Boolean("Registrant")
    is_group = fields.Boolean("Group")

    name = fields.Char(index=True)

    related_1_ids = fields.One2many("spp.registry.relationship", "destination", "Related to registrant 1")
    related_2_ids = fields.One2many("spp.registry.relationship", "source", "Related to registrant 2")

    phone_number_ids = fields.One2many("spp.phone.number", "partner_id", "Phone Numbers")

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    registration_date = fields.Date(default=lambda self: fields.Date.today())
    tags_ids = fields.Many2many(
        "spp.vocabulary.code",
        relation="res_partner_registrant_tag_rel",
        column1="partner_id",
        column2="tag_id",
        string="Registrant Tags",
        domain="[('namespace_uri', '=', 'urn:openspp:vocab:registrant-tags')]",
    )

    # Vocabulary-based demographic fields
    civil_status_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Civil Status",
        domain="[('namespace_uri', '=', 'urn:un:unsd:pop-census:marital-status')]",
        help="Marital/civil status based on UN Principles and Recommendations for Population and Housing Censuses",
    )
    occupation_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Occupation",
        domain="[('namespace_uri', '=', 'urn:ilo:isco-08')]",
        help="Occupation classification based on ILO ISCO-08 standard",
    )
    income = fields.Float()

    # Computed counts for tab badges (from spp_registry_ui)
    reg_ids_count = fields.Integer(
        string="IDs Count",
        compute="_compute_reg_ids_count",
    )
    relationships_count = fields.Integer(
        string="Relationships Count",
        compute="_compute_relationships_count",
    )

    @api.onchange("phone_number_ids")
    def phone_number_ids_change(self):
        phone = ""
        if self.phone_number_ids:
            phone = ",".join(
                [p for p in self.phone_number_ids.filtered(lambda rec: not rec.disabled).mapped("phone_no")]
            )
        self.phone = phone

    def enable_registrant(self):
        for rec in self:
            if rec.disabled:
                rec.update(
                    {
                        "disabled": None,
                        "disabled_by": None,
                        "disabled_reason": None,
                    }
                )

    @api.onchange("income")
    def _onchange_negative_restrict(self):
        res = {}
        if self.income < 0:
            res["warning"] = {
                "title": "Warning",
                "message": "Negative values are not allowed.",
            }
            res["value"] = {"income": 0}
        return res

    @api.constrains("registration_date")
    def _check_registration_date(self):
        for record in self:
            if record.registration_date:
                if record.registration_date > date.today():
                    error_message = "Registration date must be less than the current date."
                    raise ValidationError(error_message)
                elif "birthdate" in record and record.birthdate and record.registration_date < record.birthdate:
                    error_message = "Registration date must be later than the birth date."
                    raise ValidationError(error_message)

    def unlink(self):
        # Prevent delete for officer/registrar, but allow managers/admins.
        group_registry_manager = self.env.user.has_group("spp_registry.group_registry_manager")
        group_registry_officer = self.env.user.has_group("spp_registry.group_registry_officer")
        group_spp_admin = self.env.user.has_group("spp_security.group_spp_admin")
        # Backward compatibility
        group_spp_registrar = self.env.user.has_group("spp_registry.group_spp_registrar")

        if (group_registry_officer or group_spp_registrar) and not (
            group_spp_admin or group_registry_manager or self.env.user._is_admin()
        ):
            raise AccessError(_("You do not have the necessary permissions to delete partner records."))
        return super().unlink()

    def _check_company_domain(self, companies):
        """Overrides the default domain to include the default company that was setup in company_id field.

        This is to fix the issue that is occuring when the user is trying to create a new company in an
        instance that has "stock" module and "spp_registry_base" module installed. The issue is that the
        `_check_company` function checks if the company of the record is either
        False or the same with the record's company.

        To replicate the issue:
        1. Install the "stock" module and "spp_registry_base" module.
        2. Create a new company.
        3. "Incompatible companies on records" error should not occur.
        """

        domain = super()._check_company_domain(companies)
        domain = Domain(domain) | Domain([("company_id", "=", self.env.company.id)])
        return domain

    def _compute_reg_ids_count(self):
        """Compute ID count using search_count for batch efficiency."""
        if not self.ids:
            for record in self:
                record.reg_ids_count = 0
            return

        RegId = self.env["spp.registry.id"]
        # Use search_count for each partner for simplicity and compatibility
        for record in self:
            record.reg_ids_count = RegId.search_count([("partner_id", "=", record.id)])

    def _compute_relationships_count(self):
        """Compute relationship count using search_count for batch efficiency."""
        if not self.ids:
            for record in self:
                record.relationships_count = 0
            return

        Relationship = self.env["spp.registry.relationship"]
        # Count where partner is source or destination
        for record in self:
            source_count = Relationship.search_count([("source", "=", record.id)])
            dest_count = Relationship.search_count([("destination", "=", record.id)])
            record.relationships_count = source_count + dest_count
