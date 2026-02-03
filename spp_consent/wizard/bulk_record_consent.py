# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Bulk Consent Recording Wizard for field efficiency."""

import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BulkRecordConsentWizard(models.TransientModel):
    """Wizard for recording identical consent for multiple beneficiaries at once."""

    _name = "spp.bulk.record.consent.wizard"
    _description = "Bulk Consent Recording Wizard"

    registrant_ids = fields.Many2many(
        "res.partner",
        string="Beneficiaries",
        required=True,
        domain="[('is_registrant', '=', True)]",
        help="Select multiple beneficiaries to record consent for.",
    )

    registrant_count = fields.Integer(
        string="Number of Beneficiaries",
        compute="_compute_registrant_count",
        store=False,
    )

    expiry = fields.Date(
        required=True,
        help="Consent expiration date (must be in the future).",
    )

    purpose_ids = fields.Many2many(
        "spp.consent.purpose",
        string="Purposes",
        required=True,
        help="Select one or more purposes for data processing.",
    )

    personal_data_ids = fields.Many2many(
        "spp.consent.personal.data",
        string="Personal Data Categories",
        required=True,
        help="Select the categories of personal data to be processed.",
    )

    legal_basis = fields.Selection(
        [
            ("consent", "Consent"),
            ("contract", "Contract"),
            ("legal_obligation", "Legal Obligation"),
            ("vital_interest", "Vital Interest"),
            ("public_interest", "Public Interest"),
            ("legitimate_interest", "Legitimate Interest"),
        ],
        default="consent",
        required=True,
        help="Legal basis for processing personal data under applicable data protection law.",
    )

    controller_id = fields.Many2one(
        "res.partner",
        string="Data Controller",
        required=True,
        default=lambda self: self.env.company.partner_id,
        help="The organization responsible for collecting and protecting this data.",
    )

    collection_method = fields.Selection(
        [
            ("written", "Written Form"),
            ("verbal", "Verbal"),
            ("electronic", "Electronic/Digital"),
            ("biometric", "Biometric"),
        ],
        default="written",
        required=True,
        string="Collection Method",
    )

    notice_id = fields.Many2one(
        "spp.consent.notice",
        string="Privacy Notice",
        domain=[("state", "=", "active")],
        help="The privacy notice that was provided to the beneficiaries.",
    )

    notes = fields.Text(
        string="Notes",
        help="Additional information about this bulk consent recording.",
    )

    @api.model
    def default_get(self, fields_list):
        """Pre-populate wizard with selected beneficiaries from list view."""
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if active_ids and "registrant_ids" in fields_list:
            # Filter to valid registrants only
            partners = self.env["res.partner"].browse(active_ids)
            registrants = partners.filtered(lambda p: p.is_registrant)
            res["registrant_ids"] = [Command.set(registrants.ids)]
        return res

    @api.depends("registrant_ids")
    def _compute_registrant_count(self):
        """Compute the number of selected beneficiaries."""
        for rec in self:
            rec.registrant_count = len(rec.registrant_ids)

    @api.constrains("expiry")
    def _check_expiry(self):
        """Validate expiry date is in the future."""
        for rec in self:
            if rec.expiry and rec.expiry <= fields.Date.today():
                raise ValidationError(_("Expiry date must be in the future."))

    def _prepare_consent_vals(self, registrant):
        """Prepare consent values for a single registrant.

        Args:
            registrant: res.partner record

        Returns:
            dict: Values for creating consent record
        """
        vals = {
            "name": f"Bulk Consent - {registrant.name}",
            "signatory_id": registrant.id,
            "expiry": self.expiry,
            "purpose_ids": [Command.set(self.purpose_ids.ids)],
            "personal_data_ids": [Command.set(self.personal_data_ids.ids)],
            "legal_basis": self.legal_basis,
            "controller_id": self.controller_id.id,
            "collection_method": self.collection_method,
            "status": "given",
            "effective_date": fields.Date.today(),
        }
        if self.notice_id:
            vals.update(
                {
                    "notice_id": self.notice_id.id,
                    "notice_version": self.notice_id.version,
                }
            )
        return vals

    def action_record_bulk_consent(self):
        """Record consent for all selected beneficiaries.

        Returns:
            dict: Client action to show notification
        """
        self.ensure_one()

        if not self.registrant_ids:
            raise ValidationError(_("Please select at least one beneficiary."))

        # Create consent records for all registrants using batch creation
        vals_list = [self._prepare_consent_vals(r) for r in self.registrant_ids]
        self.env["spp.consent"].create(vals_list)

        _logger.info(
            "Bulk consent recorded for %d beneficiaries by user %s",
            len(self.registrant_ids),
            self.env.user.name,
        )

        # Show success notification
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bulk Consent Recorded"),
                "message": _("%d consent records created successfully.") % len(self.registrant_ids),
                "type": "success",
                "sticky": False,
            },
        }
