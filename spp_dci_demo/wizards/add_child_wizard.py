# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Multi-step wizard for adding a child to a household with DCI birth verification.

Wizard flow (3 steps):
  1. Select Household - search/select group, optional applicant
  2. Child Information - enter child details + BRN, verify birth
  3. Review & Submit - see summary, create + auto-submit CR
"""

import json
import logging

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..utils.dci_verification import (
    check_data_matches,
    extract_person_from_dci_response,
    parse_dci_response,
)

_logger = logging.getLogger(__name__)

STAGE_ORDER = ["registrant", "details", "review"]


class SPPDCIDemoAddChildWizard(models.TransientModel):
    """Multi-step wizard for creating an Add Child CR with DCI birth verification."""

    _name = "spp.dci.demo.add.child.wizard"
    _description = "Add Child Wizard (DCI Demo)"

    stage = fields.Selection(
        [
            ("registrant", "Select Household"),
            ("details", "Child Information"),
            ("review", "Review & Submit"),
        ],
        default="registrant",
        required=True,
    )

    # ==================
    # Step 1 - Household
    # ==================
    request_type_id = fields.Many2one(
        "spp.change.request.type",
        string="Request Type",
        readonly=True,
    )

    registrant_id = fields.Many2one(
        "res.partner",
        string="Household",
        domain="[('is_registrant', '=', True), ('is_group', '=', True)]",
    )

    registrant_info_html = fields.Html(
        compute="_compute_registrant_info_html",
        string="Household Info",
    )

    applicant_id = fields.Many2one(
        "res.partner",
        string="Applicant",
        help="Person requesting the change (optional)",
    )

    applicant_phone = fields.Char(
        string="Applicant Phone",
    )

    # ==================
    # Step 2 - Child Details
    # ==================
    given_name = fields.Char(string="Given Name")
    family_name = fields.Char(string="Family Name")
    member_name = fields.Char(
        string="Full Name",
        compute="_compute_member_name",
        store=True,
    )
    birthdate = fields.Date(string="Date of Birth")
    gender_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Gender",
        domain="[('namespace_uri', '=', 'urn:iso:std:iso:5218')]",
    )
    relationship_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Relationship to Head",
        domain="[('vocabulary_id.namespace_uri', '=', "
        "'urn:openspp:vocab:group-membership-type'), "
        "('code', '!=', 'head')]",
    )

    # Birth Verification
    birth_registration_number = fields.Char(string="Birth Registration Number (BRN)")
    dci_data_source_id = fields.Many2one(
        "spp.dci.data.source",
        string="DCI Data Source",
        domain="[('registry_type', '=', 'ns:org:RegistryType:Civil'), ('active', '=', True)]",
    )
    birth_verification_status = fields.Selection(
        [
            ("unverified", "Unverified"),
            ("verified", "Verified"),
            ("not_found", "Not Found"),
            ("error", "Error"),
        ],
        default="unverified",
        string="Verification Status",
    )
    birth_verification_date = fields.Datetime(
        string="Verification Date",
        readonly=True,
    )
    birth_verification_response = fields.Text(
        string="Verification Response",
        readonly=True,
    )
    dci_data_match = fields.Boolean(
        string="DCI Data Matches",
        readonly=True,
    )

    # ==================
    # Step 3 - Review
    # ==================
    preview_html = fields.Html(
        compute="_compute_preview_html",
        string="Summary",
    )

    # ==================
    # Default Values
    # ==================

    @api.model
    def default_get(self, fields_list):
        """Pre-fill request_type_id and registrant from context."""
        res = super().default_get(fields_list)

        # Always pre-set to add_member type
        if "request_type_id" in fields_list:
            request_type = self.env["spp.change.request.type"].search([("code", "=", "add_member")], limit=1)
            if request_type:
                res["request_type_id"] = request_type.id

        # Pre-fill registrant from context
        if "registrant_id" in fields_list:
            if self.env.context.get("active_model") == "res.partner":
                active_id = self.env.context.get("active_id")
                if active_id:
                    partner = self.env["res.partner"].browse(active_id)
                    if partner.exists() and partner.is_registrant and partner.is_group:
                        res["registrant_id"] = partner.id

        return res

    # ==================
    # Computed Fields
    # ==================

    @api.depends("given_name", "family_name")
    def _compute_member_name(self):
        for rec in self:
            if rec.given_name or rec.family_name:
                name_vals = [
                    f"{rec.family_name},"
                    if rec.family_name and rec.given_name
                    else f"{rec.family_name}"
                    if rec.family_name
                    else "",
                    rec.given_name,
                ]
                rec.member_name = " ".join(filter(None, name_vals)).upper()
            else:
                rec.member_name = False

    @api.onchange("given_name", "family_name", "birthdate", "gender_id", "birth_registration_number")
    def _onchange_invalidate_verification(self):
        """Reset verification status when verified fields are edited.

        This is a security control: if the user changes name, DOB, gender, or BRN
        after verification, the verification is no longer valid and must be re-done.
        """
        if self.birth_verification_status == "verified":
            self.birth_verification_status = "unverified"
            self.dci_data_match = False
            self.birth_verification_date = False
            self.birth_verification_response = False
            return {
                "warning": {
                    "title": _("Verification Invalidated"),
                    "message": _("Verification has been reset because you modified verified data. "
                                 "Please verify again after making changes."),
                }
            }

    @api.depends("registrant_id")
    def _compute_registrant_info_html(self):
        for rec in self:
            if rec.registrant_id:
                reg = rec.registrant_id
                info_parts = []

                # Name with ID
                primary_id = ""
                if hasattr(reg, "reg_ids") and reg.reg_ids:
                    first_id = reg.reg_ids[0]
                    if first_id.value:
                        primary_id = first_id.value

                if primary_id:
                    name_part = Markup("<strong>{}</strong> <span class='text-muted'>({})</span>").format(
                        escape(reg.name or "Unknown"), escape(primary_id)
                    )
                else:
                    name_part = Markup("<strong>{}</strong>").format(escape(reg.name or "Unknown"))
                info_parts.append(name_part)

                # Member count
                member_count = len(reg.group_membership_ids) if hasattr(reg, "group_membership_ids") else 0
                info_parts.append(
                    Markup("<span class='text-muted ms-2'><i class='fa fa-users me-1'></i>{} members</span>").format(
                        member_count
                    )
                )

                # Address
                if reg.street:
                    addr = escape(reg.street)
                    if reg.city:
                        addr = Markup("{}, {}").format(escape(reg.street), escape(reg.city))
                    info_parts.append(
                        Markup("<span class='text-muted ms-2'><i class='fa fa-map-marker me-1'></i>{}</span>").format(
                            addr
                        )
                    )

                rec.registrant_info_html = Markup(" ").join(info_parts)
            else:
                rec.registrant_info_html = ""

    @api.depends(
        "registrant_id",
        "given_name",
        "family_name",
        "birthdate",
        "gender_id",
        "relationship_id",
        "birth_registration_number",
        "birth_verification_status",
        "dci_data_match",
        "applicant_id",
    )
    def _compute_preview_html(self):
        for rec in self:
            if not rec.registrant_id:
                rec.preview_html = ""
                continue

            rows = []

            # Household
            rows.append(
                Markup("<tr><td><strong>{}</strong></td><td>{}</td></tr>").format(
                    escape("Household"),
                    escape(rec.registrant_id.name or ""),
                )
            )

            # Child name
            rows.append(
                Markup("<tr><td><strong>{}</strong></td><td>{}</td></tr>").format(
                    escape("Child Name"),
                    escape(rec.member_name or ""),
                )
            )

            # Birthdate
            if rec.birthdate:
                rows.append(
                    Markup("<tr><td><strong>{}</strong></td><td>{}</td></tr>").format(
                        escape("Date of Birth"),
                        escape(str(rec.birthdate)),
                    )
                )

            # Gender
            if rec.gender_id:
                rows.append(
                    Markup("<tr><td><strong>{}</strong></td><td>{}</td></tr>").format(
                        escape("Gender"),
                        escape(rec.gender_id.display or rec.gender_id.code or ""),
                    )
                )

            # Relationship
            if rec.relationship_id:
                rows.append(
                    Markup("<tr><td><strong>{}</strong></td><td>{}</td></tr>").format(
                        escape("Relationship"),
                        escape(rec.relationship_id.display or rec.relationship_id.code or ""),
                    )
                )

            # BRN & Verification
            if rec.birth_registration_number:
                rows.append(
                    Markup("<tr><td><strong>{}</strong></td><td>{}</td></tr>").format(
                        escape("BRN"),
                        escape(rec.birth_registration_number),
                    )
                )

                status_label = dict(rec._fields["birth_verification_status"].selection).get(
                    rec.birth_verification_status, ""
                )
                badge_class = {
                    "verified": "bg-success",
                    "not_found": "bg-warning",
                    "error": "bg-danger",
                    "unverified": "bg-secondary",
                }.get(rec.birth_verification_status, "bg-secondary")

                rows.append(
                    Markup('<tr><td><strong>{}</strong></td><td><span class="badge {}">{}</span></td></tr>').format(
                        escape("Verification Status"),
                        badge_class,
                        escape(status_label),
                    )
                )

                if rec.birth_verification_status == "verified":
                    match_text = "Yes" if rec.dci_data_match else "No"
                    match_class = "text-success" if rec.dci_data_match else "text-danger"
                    rows.append(
                        Markup('<tr><td><strong>{}</strong></td><td class="{}">{}</td></tr>').format(
                            escape("Data Matches"),
                            match_class,
                            escape(match_text),
                        )
                    )

            # Applicant
            if rec.applicant_id:
                rows.append(
                    Markup("<tr><td><strong>{}</strong></td><td>{}</td></tr>").format(
                        escape("Applicant"),
                        escape(rec.applicant_id.name or ""),
                    )
                )

            table = Markup('<table class="table table-sm table-borderless"><tbody>{}</tbody></table>').format(
                Markup("").join(rows)
            )

            rec.preview_html = table

    # ==================
    # Navigation
    # ==================

    def action_next(self):
        """Validate current step and advance to the next stage."""
        self.ensure_one()
        self._validate_current_step()

        current_index = STAGE_ORDER.index(self.stage)
        if current_index < len(STAGE_ORDER) - 1:
            self.stage = STAGE_ORDER[current_index + 1]

        return self._return_wizard_action()

    def action_previous(self):
        """Go back one step."""
        self.ensure_one()

        current_index = STAGE_ORDER.index(self.stage)
        if current_index > 0:
            self.stage = STAGE_ORDER[current_index - 1]

        return self._return_wizard_action()

    def _validate_current_step(self):
        """Validate fields for the current step before advancing."""
        if self.stage == "registrant":
            if not self.registrant_id:
                raise UserError(_("Please select a household before continuing."))
        elif self.stage == "details":
            if not self.given_name:
                raise UserError(_("Please enter the child's given name."))
            if not self.birthdate:
                raise UserError(_("Please enter the child's date of birth."))

    def _return_wizard_action(self):
        """Return action dict to redisplay the same wizard record."""
        return {
            "type": "ir.actions.act_window",
            "name": "Add Child (DCI Demo)",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    # ==================
    # Birth Verification
    # ==================

    def action_verify_birth(self):
        """Verify birth registration via DCI query to CRVS registry."""
        self.ensure_one()

        if not self.birth_registration_number:
            raise UserError(_("Please enter the Birth Registration Number (BRN) before verifying."))

        # Get the DCI data source
        data_source = self.dci_data_source_id or self._get_default_dci_data_source()
        if not data_source:
            raise UserError(
                _(
                    "No DCI data source configured for birth verification. "
                    "Please configure a CRVS data source or contact your administrator."
                )
            )

        from odoo.addons.spp_dci_client.services.client import DCIClient

        try:
            client = DCIClient(data_source, self.env)
            response = client.search_by_id_opencrvs(
                identifier_type="BRN",
                identifier_value=self.birth_registration_number,
                event_type="birth",
            )

            response_json = json.dumps(response, indent=2, default=str)

            # Parse response using shared utility
            verification_status = parse_dci_response(response)

            # Check data match
            data_matches = False
            if verification_status == "verified":
                person_data = extract_person_from_dci_response(response)
                if person_data:
                    gender_display = (self.gender_id.display or "") if self.gender_id else ""
                    data_matches, mismatches = check_data_matches(
                        person_data,
                        given_name=self.given_name,
                        family_name=self.family_name,
                        birthdate=self.birthdate,
                        gender_display=gender_display,
                    )
                    if mismatches:
                        _logger.info(
                            "Wizard DCI data mismatch for BRN %s: %s",
                            self.birth_registration_number,
                            "; ".join(mismatches),
                        )

            self.write(
                {
                    "birth_verification_status": verification_status,
                    "birth_verification_date": fields.Datetime.now(),
                    "birth_verification_response": response_json,
                    "dci_data_match": data_matches,
                }
            )

            _logger.info(
                "Wizard birth verification for BRN %s: status=%s, data_match=%s",
                self.birth_registration_number,
                verification_status,
                data_matches,
            )

            return self._return_wizard_action()

        except UserError:
            raise
        except Exception as e:
            _logger.exception(
                "Wizard birth verification failed for BRN %s",
                self.birth_registration_number,
            )
            self.write(
                {
                    "birth_verification_status": "error",
                    "birth_verification_date": fields.Datetime.now(),
                    "birth_verification_response": str(e),
                }
            )
            raise UserError(self.env._("Birth verification failed: %s") % str(e)) from e

    def _get_default_dci_data_source(self):
        """Get the default DCI data source for birth verification."""
        param_value = self.env["ir.config_parameter"].sudo().get_param("spp_dci_demo.default_crvs_data_source")
        if param_value:
            try:
                data_source = self.env["spp.dci.data.source"].browse(int(param_value))
                if data_source.exists() and data_source.active:
                    return data_source
            except (ValueError, TypeError):
                pass

        return self.env["spp.dci.data.source"].search(
            [
                ("registry_type", "=", "ns:org:RegistryType:Civil"),
                ("active", "=", True),
            ],
            limit=1,
        )

    # ==================
    # Create & Submit
    # ==================

    def action_create_and_submit(self):
        """Create the CR, populate detail fields, and submit for approval.

        Flow:
          1. spp.change.request.create() -> creates CR + empty detail
          2. cr.get_detail().write() -> populate detail with wizard values
          3. cr.action_submit_for_approval() -> submit

        If submit fails, the entire transaction rolls back.
        """
        self.ensure_one()

        try:
            # Step 1: Create the change request
            cr_vals = {
                "request_type_id": self.request_type_id.id,
                "registrant_id": self.registrant_id.id,
                "source_type": "manual",
            }
            if self.applicant_id:
                cr_vals["applicant_id"] = self.applicant_id.id
            if self.applicant_phone:
                cr_vals["applicant_phone"] = self.applicant_phone

            cr = self.env["spp.change.request"].create(cr_vals)

            # Step 2: Populate the detail record
            detail = cr.get_detail()
            if detail:
                detail_vals = {
                    "given_name": self.given_name,
                    "family_name": self.family_name,
                    "member_name": self.member_name,
                    "birthdate": self.birthdate,
                }
                if self.gender_id:
                    detail_vals["gender_id"] = self.gender_id.id
                if self.relationship_id:
                    detail_vals["relationship_id"] = self.relationship_id.id
                if self.birth_registration_number:
                    detail_vals["birth_registration_number"] = self.birth_registration_number
                if self.dci_data_source_id:
                    detail_vals["dci_data_source_id"] = self.dci_data_source_id.id
                if self.birth_verification_status != "unverified":
                    detail_vals["birth_verification_status"] = self.birth_verification_status
                if self.birth_verification_date:
                    detail_vals["birth_verification_date"] = self.birth_verification_date
                if self.birth_verification_response:
                    detail_vals["birth_verification_response"] = self.birth_verification_response
                if self.dci_data_match:
                    detail_vals["dci_data_match"] = self.dci_data_match

                detail.write(detail_vals)

            # Step 3: Submit for approval
            cr.action_submit_for_approval()

            _logger.info(
                "Wizard created and submitted CR %s for household %s",
                cr.name,
                self.registrant_id.name,
            )

            # Step 4: Auto-approve if verified and data matches
            if self.birth_verification_status == "verified" and self.dci_data_match:
                self._try_auto_approve_cr(cr)

            # Return action to open the CR form
            cr_id = cr.id
            return {
                "type": "ir.actions.act_window",
                "name": "Change Request",
                "res_model": "spp.change.request",
                "res_id": cr_id,
                "view_mode": "form",
                "target": "current",
                "context": {
                    "form_view_initial_mode": "readonly",
                },
            }

        except (UserError, ValueError):
            raise
        except Exception as e:
            _logger.exception("Wizard create and submit failed")
            raise UserError(f"Failed to create change request: {e}") from e

    def _try_auto_approve_cr(self, cr):
        """Try to auto-approve the change request if enabled.

        Args:
            cr: The change request to approve
        """
        # Check system parameter
        auto_approve_enabled = (
            self.env["ir.config_parameter"].sudo().get_param("spp_dci_demo.auto_approve_on_match", "False")
        )
        if auto_approve_enabled.lower() not in ("true", "1", "yes"):
            _logger.info("Auto-approval disabled by system parameter")
            return

        # Check if CR can be approved (must be pending/under review)
        if cr.display_state != "pending":
            _logger.info(
                "Change request %s is in state '%s', cannot auto-approve",
                cr.name,
                cr.display_state,
            )
            return

        try:
            # Use action_approve_system() for system-initiated approval
            cr.action_approve_system(comment="Auto-approved: DCI birth verification matched")
        except Exception as e:
            _logger.warning("Failed to auto-approve change request %s: %s", cr.name, str(e))
