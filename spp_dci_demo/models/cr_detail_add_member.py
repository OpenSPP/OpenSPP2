# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..utils.dci_verification import (
    check_data_matches,
    extract_person_from_dci_response,
    parse_dci_response,
)

_logger = logging.getLogger(__name__)


class SPPCRDetailAddMemberDCI(models.Model):
    """Extend Add Member CR Detail with DCI birth verification fields."""

    _inherit = "spp.cr.detail.add_member"

    # Birth Registration Number entered by social worker
    birth_registration_number = fields.Char(
        string="Birth Registration Number (BRN)",
        tracking=True,
        help="Birth Registration Number from the civil registry (e.g., OpenCRVS)",
    )

    # Verification status
    birth_verification_status = fields.Selection(
        selection=[
            ("unverified", "Unverified"),
            ("verified", "Verified"),
            ("not_found", "Not Found"),
            ("error", "Error"),
        ],
        string="Birth Verification Status",
        default="unverified",
        tracking=True,
        help="Status of birth verification via DCI",
    )

    # Data match status
    dci_data_match = fields.Boolean(
        string="DCI Data Matches",
        readonly=True,
        help="Whether the DCI response data matches the CR detail fields",
    )

    # When verification was performed
    birth_verification_date = fields.Datetime(
        string="Verification Date",
        readonly=True,
        help="When the birth verification was performed",
    )

    # Raw DCI response for audit
    birth_verification_response = fields.Text(
        string="Verification Response",
        readonly=True,
        help="Raw JSON response from DCI verification for audit purposes",
    )

    # Which CRVS registry to verify against
    dci_data_source_id = fields.Many2one(
        "spp.dci.data.source",
        string="DCI Data Source",
        domain="[('registry_type', '=', 'ns:org:RegistryType:Civil'), ('active', '=', True)]",
        help="DCI data source (CRVS registry) to use for birth verification",
    )
    single_dci_data_source = fields.Boolean(
        compute="_compute_single_dci_data_source",
    )

    def _compute_single_dci_data_source(self):
        count = self.env["spp.dci.data.source"].search_count(
            [("registry_type", "=", "ns:org:RegistryType:Civil"), ("active", "=", True)],
        )
        is_single = count <= 1
        for rec in self:
            rec.single_dci_data_source = is_single

    @api.onchange("birth_registration_number")
    def _onchange_birth_registration_number(self):
        """Strip whitespace from BRN on change."""
        if self.birth_registration_number:
            stripped = self.birth_registration_number.strip().upper()
            if stripped != self.birth_registration_number:
                self.birth_registration_number = stripped

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

    @api.model
    def _get_default_dci_data_source(self):
        """Get the default DCI data source for birth verification.

        Looks for a system parameter or finds the first active CRVS data source.
        """
        # Try system parameter first
        param_value = self.env["ir.config_parameter"].sudo().get_param("spp_dci_demo.default_crvs_data_source")
        if param_value:
            try:
                data_source = self.env["spp.dci.data.source"].browse(int(param_value))
                if data_source.exists() and data_source.active:
                    return data_source
            except (ValueError, TypeError):
                pass

        # Fall back to first active CRVS data source
        return self.env["spp.dci.data.source"].search(
            [
                ("registry_type", "=", "ns:org:RegistryType:Civil"),
                ("active", "=", True),
            ],
            limit=1,
        )

    def action_verify_birth(self):
        """Verify birth registration via DCI query to CRVS registry.

        1. Validate BRN is filled
        2. Get DCI data source
        3. Call DCI client to search by BRN
        4. Parse response and update verification status
        """
        self.ensure_one()

        # Validate BRN is provided
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

        # Import DCIClient
        from odoo.addons.spp_dci_client.services.client import DCIClient

        try:
            # Create client and search by BRN
            # OpenCRVS requires special format - use search_by_id_opencrvs
            client = DCIClient(data_source, self.env)
            response = client.search_by_id_opencrvs(
                identifier_type="BRN",
                identifier_value=self.birth_registration_number,
                event_type="birth",
            )

            # Store raw response for audit
            response_json = json.dumps(response, indent=2, default=str)

            # Parse response to determine verification status
            verification_status = self._parse_dci_response(response)

            # Check if DCI data matches CR detail fields
            data_matches = False
            if verification_status == "verified":
                data_matches = self._check_data_matches_dci_response(response)

            # Update record
            self.write(
                {
                    "birth_verification_status": verification_status,
                    "birth_verification_date": fields.Datetime.now(),
                    "birth_verification_response": response_json,
                    "dci_data_match": data_matches,
                }
            )

            # Log success
            _logger.info(
                "Birth verification for BRN %s completed with status: %s, data_match: %s",
                self.birth_registration_number,
                verification_status,
                data_matches,
            )

            # Auto-approve if verified and data matches
            auto_approved = False
            if verification_status == "verified" and data_matches:
                auto_approved = self._try_auto_approve()

            # Return notification
            if verification_status == "verified":
                if auto_approved:
                    message = _("Birth registration verified and CR auto-approved!")
                elif data_matches:
                    message = _("Birth registration verified and data matches!")
                else:
                    message = _("Birth registration verified (data mismatch - manual review required).")
            elif verification_status == "not_found":
                message = _("No matching birth registration found for BRN: %s") % self.birth_registration_number
            else:
                message = _("Birth verification completed with status: %s") % verification_status

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Birth Verification"),
                    "message": message,
                    "type": "success" if verification_status == "verified" else "warning",
                    "sticky": False,
                    "next": {"type": "ir.actions.client", "tag": "soft_reload"},
                },
            }

        except UserError:
            # Re-raise UserError as-is
            raise
        except Exception as e:
            _logger.exception("Birth verification failed for BRN %s", self.birth_registration_number)
            self.write(
                {
                    "birth_verification_status": "error",
                    "birth_verification_date": fields.Datetime.now(),
                    "birth_verification_response": str(e),
                }
            )
            raise UserError(_("Birth verification failed: %s") % str(e)) from e

    def _parse_dci_response(self, response):
        """Parse DCI response to determine verification status.

        Delegates to the standalone utility function.

        Args:
            response: Dict response from DCI search

        Returns:
            Verification status string: 'verified', 'not_found', or 'error'
        """
        return parse_dci_response(response)

    def _extract_person_from_dci_response(self, response):
        """Extract person data from DCI response.

        Delegates to the standalone utility function.

        Args:
            response: Dict response from DCI search

        Returns:
            Dict with normalized person data or None if not found
        """
        return extract_person_from_dci_response(response)

    def _check_data_matches_dci_response(self, response):
        """Check if DCI response data matches the CR detail fields.

        Delegates to the standalone utility function, passing field
        values from this record.

        Args:
            response: Dict response from DCI search

        Returns:
            Boolean indicating if data matches
        """
        person_data = extract_person_from_dci_response(response)
        if not person_data:
            _logger.warning("Could not extract person data from DCI response for matching")
            return False

        gender_display = (self.gender_id.display or "") if self.gender_id else ""
        matches, mismatches = check_data_matches(
            person_data,
            given_name=self.given_name,
            family_name=self.family_name,
            birthdate=self.birthdate,
            gender_display=gender_display,
        )

        if mismatches:
            _logger.info(
                "DCI data mismatch for BRN %s: %s",
                self.birth_registration_number,
                "; ".join(mismatches),
            )
        else:
            _logger.info(
                "DCI data matches CR detail for BRN %s",
                self.birth_registration_number,
            )

        return matches

    def _try_auto_approve(self):
        """Try to auto-approve the change request.

        Only auto-approves if:
        - System parameter spp_dci_demo.auto_approve_on_match is True
        - The change request is in a state that can be approved

        Returns:
            Boolean indicating if auto-approval was successful
        """
        # Check system parameter
        auto_approve_enabled = (
            self.env["ir.config_parameter"].sudo().get_param("spp_dci_demo.auto_approve_on_match", "False")
        )
        if auto_approve_enabled.lower() not in ("true", "1", "yes"):
            _logger.info("Auto-approval disabled by system parameter")
            return False

        # Get the change request
        cr = self.change_request_id
        if not cr:
            _logger.warning("No change request linked to detail, cannot auto-approve")
            return False

        # Check if CR can be approved (must be in pending state)
        if cr.display_state != "pending":
            _logger.info(
                "Change request %s is in state '%s', cannot auto-approve",
                cr.name,
                cr.display_state,
            )
            return False

        try:
            # Use action_approve_system() for system-initiated approval
            cr.action_approve_system(comment=_("Auto-approved: DCI birth verification matched"))
            return True
        except Exception as e:
            _logger.warning(
                "Failed to auto-approve change request %s: %s",
                cr.name,
                str(e),
            )
            return False
