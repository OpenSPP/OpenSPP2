# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OpenSPPRecordConsentWizard(models.TransientModel):
    _name = "spp.record.consent.wizard"
    _description = "Record Consent Wizard"

    name = fields.Char("Consent", compute="_compute_name")
    group_id = fields.Many2one(
        "res.partner",
        "Group",
        domain=[("is_registrant", "=", True), ("is_group", "=", True)],
    )
    signatory_id = fields.Many2one(
        "res.partner",
        "Signatory",
        domain=[("is_registrant", "=", True), ("is_group", "=", False)],
        help="The individual whose data will be processed (data subject)",
    )
    expiry = fields.Date("Expiry Date")
    is_group = fields.Boolean("Consent For Group", default=False)

    # Data protection compliance fields (ISO 27560 compliance)
    # Note: Not marked required in wizard to maintain backward compatibility,
    # but they are recommended for data protection compliance
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
        help="Legal basis for processing under applicable data protection law "
        "(e.g., GDPR Article 6, Kenya Data Protection Act, POPIA, LGPD)",
    )

    purpose_ids = fields.Many2many(
        "spp.consent.purpose",
        "record_consent_wizard_purpose_rel",
        "wizard_id",
        "purpose_id",
        string="Purposes",
        help="Why is this data being collected? (Data protection law recommends specifying clear purpose)",
    )

    personal_data_ids = fields.Many2many(
        "spp.consent.personal.data",
        "record_consent_wizard_data_rel",
        "wizard_id",
        "data_id",
        string="Personal Data Categories",
        help="What types of personal data will be collected?",
    )

    notice_id = fields.Many2one(
        "spp.consent.notice",
        string="Privacy Notice",
        domain=[("state", "=", "active")],
        help="Which privacy notice was shown to the data subject? (Recommended for data protection compliance)",
    )

    notice_preview = fields.Html(
        string="Privacy Notice Preview",
        compute="_compute_notice_preview",
        readonly=True,
    )

    collection_method = fields.Selection(
        [
            ("written", "Written/Signed Form"),
            ("verbal", "Verbal (Witnessed)"),
            ("electronic", "Electronic/Digital"),
            ("biometric", "Biometric Confirmation"),
        ],
        default="written",
        help="How was this consent collected?",
    )

    controller_id = fields.Many2one(
        "res.partner",
        string="Data Controller",
        default=lambda self: self.env.company.partner_id,
        help="Organization responsible for data processing",
    )

    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)

        if view_type != "form":
            return arch, view

        # Filter signatory_id domain to group members if opened from a group
        group_id = self.env.context.get("active_id")
        if not group_id:
            return arch, view

        members = self.env["spp.group.membership"].search([("group", "=", group_id)])
        if not members:
            return arch, view

        member_ids = members.mapped("individual.id")
        domain = f"[('id', 'in', {member_ids})]"

        nodes = arch.xpath("//field[@name='signatory_id']")
        for node in nodes:
            node.set("domain", domain)

        return arch, view

    def _validate_consent_data(self):
        """Validate consent data before creation.

        Raises:
            UserError: If validation fails with detailed error messages.
        """
        errors = []

        # Check signatory is selected
        if not self.signatory_id:
            errors.append(_("A data subject (signatory) must be selected."))

        # Check expiry is in future
        if self.expiry and self.expiry <= fields.Date.today():
            errors.append(_("Expiry date must be in the future."))

        # Check group consistency
        if self.is_group and not self.group_id:
            errors.append(_("Group is required when recording group consent."))

        if not self.is_group and self.group_id:
            errors.append(_("Group should not be set for individual consent."))

        # Check data protection compliance fields are set
        if not self.purpose_ids:
            errors.append(
                _(
                    "At least one purpose must be specified for data protection compliance. "
                    "This explains why you are processing personal data."
                )
            )

        if not self.personal_data_ids:
            errors.append(
                _(
                    "At least one personal data category must be specified. "
                    "This documents what types of data you are collecting."
                )
            )

        # Validate controller is set
        if not self.controller_id:
            errors.append(_("Data controller must be specified."))

        if errors:
            raise UserError("\n\n".join(errors))

    def record_consent(self):
        # Validate before creating consent
        self._validate_consent_data()

        vals = {
            "name": self.name,
            "signatory_id": self.signatory_id.id,
            "expiry": self.expiry,
            "legal_basis": self.legal_basis,
            "purpose_ids": [Command.set(self.purpose_ids.ids)],
            "personal_data_ids": [Command.set(self.personal_data_ids.ids)],
            "notice_id": self.notice_id.id,
            "notice_version": self.notice_id.version if self.notice_id else False,
            "collection_method": self.collection_method,
            "controller_id": self.controller_id.id,
            "status": "given",  # Consent is being actively given
            "effective_date": fields.Date.today(),
        }
        if self.is_group:
            vals["group_id"] = self.group_id.id
            return self.group_id.write({"consent_ids": [Command.create(vals)]})
        else:
            return self.signatory_id.write({"consent_ids": [Command.create(vals)]})

    @api.depends("notice_id")
    def _compute_notice_preview(self):
        """Show preview of the privacy notice being used."""
        for rec in self:
            if not rec.notice_id:
                rec.notice_preview = "<p><em>Select a privacy notice to see preview</em></p>"
                continue

            rec.notice_preview = f"""
                <div style="border: 1px solid #ddd; padding: 10px; background: #f9f9f9;">
                    <h4>{rec.notice_id.name} (v{rec.notice_id.version})</h4>
                    <p><strong>Summary:</strong> {rec.notice_id.summary or "N/A"}</p>
                    <p><strong>Controller:</strong> {rec.notice_id.controller_info or "N/A"}</p>
                    <p><em>This is the privacy notice that will be recorded with this consent.</em></p>
                </div>
            """

    @api.depends("signatory_id")
    def _compute_name(self):
        for rec in self:
            rec.name = rec.signatory_id.name if rec.signatory_id else ""

    @api.onchange("notice_id")
    def _onchange_notice_id(self):
        """
        Auto-populate consent terms from the selected privacy notice.

        This implements the "Notice as Template" behavior:
        - When a notice is selected, pre-populate purposes and data categories
        - Users can narrow the scope (select subset) but cannot exceed notice boundaries
        - Allowed recipient types are NOT auto-populated (user must choose)

        Note: The boundary constraint will enforce that final values stay within notice scope.
        """
        if self.notice_id:
            # Pre-populate purposes from notice
            if self.notice_id.purpose_ids and not self.purpose_ids:
                self.purpose_ids = self.notice_id.purpose_ids

            # Pre-populate data categories from notice
            if self.notice_id.data_category_ids and not self.personal_data_ids:
                self.personal_data_ids = self.notice_id.data_category_ids

            # Note: We intentionally do NOT auto-populate allowed_recipient_types
            # because the beneficiary should actively choose which org types to allow.
            # The boundary constraint will ensure they can only choose from what's in the notice.

    @api.onchange("group_id")
    def _get_members(self):
        if not self.group_id:
            return {}

        members = self.env["spp.group.membership"].search([("group", "=", self.group_id.id)])
        member_ids = members.mapped("individual.id")

        return {"domain": {"signatory_id": [("id", "in", member_ids)]}}
