# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SPPCRApplyAddMemberDCI(models.AbstractModel):
    """Extend Add Member CR apply to create verified BRN registry ID."""

    _inherit = "spp.cr.apply.add_member"

    def apply(self, change_request):
        """Apply change request and create BRN registry ID if birth was verified.

        Extends the base apply() to:
        1. Create the individual and group membership (via super)
        2. If birth was verified, create a verified BRN registry ID on the individual
        3. Auto-enroll the new individual in the household's programs
        """
        # Call parent apply - creates individual and membership
        result = super().apply(change_request)

        # Get the detail record
        detail = change_request.get_detail()
        if not detail:
            return result

        # Check if birth was verified and BRN is present
        if (
            detail.birth_verification_status == "verified"
            and detail.birth_registration_number
            and detail.created_individual_id
        ):
            self._create_verified_brn_registry_id(detail)

        # Auto-enroll in household's programs if enabled
        if detail.created_individual_id and change_request.registrant_id:
            self._auto_enroll_in_household_programs(
                detail.created_individual_id,
                change_request.registrant_id,
            )

        return result

    def _create_verified_brn_registry_id(self, detail):
        """Create a verified BRN registry ID on the created individual.

        Args:
            detail: The CR detail record containing verification data
        """
        # Get the BRN ID type vocabulary code
        brn_id_type = self.env.ref(
            "spp_dci_demo.code_id_type_brn",
            raise_if_not_found=False,
        )

        if not brn_id_type:
            _logger.warning(
                "BRN ID type vocabulary code not found (spp_dci_demo.code_id_type_brn). "
                "Cannot create verified registry ID."
            )
            return

        # Check if the individual already has a BRN
        existing_brn = self.env["spp.registry.id"].search(
            [
                ("partner_id", "=", detail.created_individual_id.id),
                ("id_type_id", "=", brn_id_type.id),
            ],
            limit=1,
        )

        if existing_brn:
            _logger.info(
                "Individual %s already has a BRN registry ID, updating with verification data",
                detail.created_individual_id.id,
            )
            # Update existing record with verification data
            existing_brn.write(
                {
                    "value": detail.birth_registration_number,
                    "status": "valid",
                    "verification_method": "dci_api",
                    "verification_date": detail.birth_verification_date,
                    "verification_source": self._get_verification_source(detail),
                    "verification_response": detail.birth_verification_response,
                }
            )
        else:
            # Create new registry ID with verification data
            registry_id_vals = {
                "partner_id": detail.created_individual_id.id,
                "id_type_id": brn_id_type.id,
                "value": detail.birth_registration_number,
                "status": "valid",
                "verification_method": "dci_api",
                "verification_date": detail.birth_verification_date,
                "verification_source": self._get_verification_source(detail),
                "verification_response": detail.birth_verification_response,
            }

            self.env["spp.registry.id"].create(registry_id_vals)

            _logger.info(
                "Created verified BRN registry ID for individual %s (BRN: %s)",
                detail.created_individual_id.id,
                detail.birth_registration_number,
            )

    def _get_verification_source(self, detail):
        """Get the verification source name from the data source.

        Args:
            detail: The CR detail record

        Returns:
            String identifying the verification source
        """
        if detail.dci_data_source_id:
            return detail.dci_data_source_id.name
        # Try to get from default
        default_source = detail._get_default_dci_data_source()
        if default_source:
            return default_source.name
        return "DCI API"

    def _auto_enroll_in_household_programs(self, individual, household):
        """Auto-enroll the household and new individual in the configured program.

        Args:
            individual: The newly created individual (res.partner)
            household: The household/group (res.partner)
        """
        # Get program ID from system parameter
        program_id_str = self.env["ir.config_parameter"].sudo().get_param("spp_dci_demo.enrollment_program_id", "")
        if not program_id_str:
            _logger.info("No enrollment program configured (spp_dci_demo.enrollment_program_id)")
            return

        try:
            program_id = int(program_id_str)
        except (ValueError, TypeError):
            _logger.warning("Invalid enrollment_program_id: %s", program_id_str)
            return

        # Check if program membership model exists
        if "spp.program.membership" not in self.env:
            _logger.info("spp.program.membership model not available, skipping enrollment")
            return

        # Get the program
        program = self.env["spp.program"].browse(program_id)
        if not program.exists():
            _logger.warning("Enrollment program ID %s does not exist", program_id)
            return

        _logger.info(
            "Auto-enrolling household %s and members in program %s",
            household.id,
            program.name,
        )

        # Enroll the household (group) if not already enrolled
        self._enroll_partner_in_program(household, program)

        # Enroll all household members including the new child
        # Invalidate cache so the newly created membership is included
        household.invalidate_recordset(["group_membership_ids"])
        if hasattr(household, "group_membership_ids"):
            for membership in household.group_membership_ids:
                if membership.individual:
                    self._enroll_partner_in_program(membership.individual, program)

    def _enroll_partner_in_program(self, partner, program):
        """Enroll a partner (individual or group) in a program.

        Args:
            partner: The partner to enroll (res.partner)
            program: The program to enroll in (spp.program)
        """
        # Check if already enrolled
        existing = self.env["spp.program.membership"].search(
            [
                ("partner_id", "=", partner.id),
                ("program_id", "=", program.id),
            ],
            limit=1,
        )

        if existing:
            _logger.info(
                "Partner %s already in program %s (state: %s)",
                partner.id,
                program.name,
                existing.state,
            )
            return

        # Create enrollment
        try:
            self.env["spp.program.membership"].create(
                {
                    "partner_id": partner.id,
                    "program_id": program.id,
                    "state": "enrolled",
                }
            )
            _logger.info(
                "Enrolled partner %s in program %s",
                partner.id,
                program.name,
            )
        except Exception as e:
            _logger.warning(
                "Failed to enroll partner %s in program %s: %s",
                partner.id,
                program.name,
                str(e),
            )
