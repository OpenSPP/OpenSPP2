# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for ProgramMembership resource operations"""

import logging
from typing import Any

from odoo.api import Environment
from odoo.exceptions import ValidationError

from ..schemas.program_membership import ProgramMembership

_logger = logging.getLogger(__name__)


class ProgramMembershipService:
    """Service for ProgramMembership resource CRUD and mapping"""

    def __init__(self, env: Environment):
        self.env = env

    def search(self, params: dict[str, Any]) -> tuple[list, int]:
        """
        Search for program memberships based on query parameters.

        Args:
            params: Dict with optional keys:
                - beneficiary: Reference string (e.g., "Individual/{system}|{value}")
                - program: Reference string (e.g., "Program/{system}|{value}")
                - status: Enrollment state filter
                - _count: Page size (default 20, max 100)
                - _offset: Skip records (default 0)

        Returns:
            Tuple of (records, total_count)
        """
        domain = []

        # Beneficiary search
        beneficiary = params.get("beneficiary")
        if beneficiary:
            if beneficiary.startswith("Individual/") or beneficiary.startswith("Group/"):
                if beneficiary.startswith("Individual/"):
                    identifier_str = beneficiary.replace("Individual/", "")
                else:
                    identifier_str = beneficiary.replace("Group/", "")

                if "|" in identifier_str:
                    system, value = identifier_str.split("|", 1)
                    reg_id = (
                        self.env["spp.registry.id"]  # nosemgrep: odoo-sudo-without-context
                        .sudo()
                        .search(
                            [
                                ("id_type_id.uri", "=", system),
                                ("value", "=", value),
                            ],
                            limit=1,
                        )
                    )
                    if reg_id and reg_id.partner_id:
                        domain.append(("partner_id", "=", reg_id.partner_id.id))
                    else:
                        # No matching partner found, return empty result
                        domain.append(("id", "=", -1))

        # Program search
        program = params.get("program")
        if program:
            if program.startswith("Program/"):
                identifier_str = program.replace("Program/", "")
                if "|" in identifier_str:
                    system, value = identifier_str.split("|", 1)
                    from .program_service import ProgramService

                    program_service = ProgramService(self.env)
                    prog = program_service.find_by_identifier(system, value)
                    if prog:
                        domain.append(("program_id", "=", prog.id))
                    else:
                        # No matching program found, return empty result
                        domain.append(("id", "=", -1))

        # Status search
        status = params.get("status")
        if status:
            domain.append(("state", "=", status))

        # Execute search
        count = min(int(params.get("_count", 20)), 100)
        offset = int(params.get("_offset", 0))

        Membership = self.env["spp.program.membership"]
        total = Membership.sudo().search_count(domain)  # nosemgrep: odoo-sudo-without-context
        records = Membership.sudo().search(  # nosemgrep: odoo-sudo-without-context
            domain,
            offset=offset,
            limit=count,
            order="create_date desc, id desc",
        )

        return records, total

    def find_by_identifier(self, system_uri: str, value: str):
        """
        Lookup program membership by external identifier.

        Args:
            system_uri: Full URI of identifier type (e.g., urn:openspp:vocab:id-type#national_id)
            value: Identifier value

        Returns:
            spp.program.membership record or empty recordset
        """
        # Program memberships might have identifiers via their partner_id
        # or via a custom identifier system. Check partner's registry IDs.

        reg_id = (
            self.env["spp.registry.id"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [
                    ("id_type_id.uri", "=", system_uri),
                    ("value", "=", value),
                ],
                limit=1,
            )
        )

        if reg_id and reg_id.partner_id:
            # Find membership for this partner
            # We might have multiple memberships, so we need program reference too
            # For now, return the first membership found
            membership = (
                self.env["spp.program.membership"]  # nosemgrep: odoo-sudo-without-context
                .sudo()
                .search(
                    [("partner_id", "=", reg_id.partner_id.id)],
                    limit=1,
                )
            )
            return membership

        return self.env["spp.program.membership"]

    def find_by_partner_and_program(self, partner_id: int, program_id: int):
        """
        Find membership by partner and program.

        Args:
            partner_id: Partner ID
            program_id: Program ID

        Returns:
            spp.program.membership record or empty recordset
        """
        return (
            self.env["spp.program.membership"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [
                    ("partner_id", "=", partner_id),
                    ("program_id", "=", program_id),
                ],
                limit=1,
            )
        )

    def to_api_schema(self, membership, extensions=None) -> dict[str, Any]:
        """
        Convert Odoo program membership to ProgramMembership API schema.

        Args:
            membership: spp.program.membership record
            extensions: List of extension names to include (or None for none)

        Returns:
            Dictionary matching ProgramMembership schema
        """
        if not membership:
            return {}

        # Build identifier list (optional for memberships)
        identifiers = []

        # Use partner's identifiers as the membership identifiers
        if membership.partner_id and membership.partner_id.reg_ids:
            for reg_id in membership.partner_id.reg_ids:
                # Use id_type_id.uri for full code URI
                # NOT namespace_uri which only returns vocabulary namespace
                if reg_id.id_type_id and reg_id.id_type_id.uri and reg_id.value:
                    identifiers.append(
                        {
                            "system": reg_id.id_type_id.uri,
                            "value": reg_id.value,
                        }
                    )

        # Build program reference
        program_ref = self._build_program_reference(membership.program_id)

        # Build beneficiary reference (can be Individual or Group)
        beneficiary_ref = self._build_beneficiary_reference(membership.partner_id)

        # Build ProgramMembership resource
        membership_data = {
            "type": "ProgramMembership",
            "program": program_ref,
            "beneficiary": beneficiary_ref,
            "status": membership.state,
        }

        # Add identifiers if available
        if identifiers:
            membership_data["identifier"] = identifiers

        # Enrollment date
        if membership.enrollment_date:
            # enrollment_date might be date or datetime, handle both
            if hasattr(membership.enrollment_date, "date"):
                membership_data["enrollmentDate"] = membership.enrollment_date.date().isoformat()
            else:
                membership_data["enrollmentDate"] = membership.enrollment_date.isoformat()

        # Exit information
        if membership.exit_date:
            membership_data["exitDate"] = membership.exit_date.isoformat()

        # Exit reason (if we have a field for it in the future)
        # For now, we don't have exit_reason_id in the base model

        # Metadata
        # Use integer microseconds for versionId to avoid float precision issues
        version_id = str(int(membership.write_date.timestamp() * 1000000)) if membership.write_date else "1"
        membership_data["meta"] = {
            "versionId": version_id,
            "lastUpdated": membership.write_date.isoformat() if membership.write_date else None,
            "source": None,  # Memberships don't have source tracking in base module
        }

        return membership_data

    def _build_program_reference(self, program) -> dict:
        """Build Reference to a Program"""
        if not program:
            return {"reference": "Program/unknown", "display": "Unknown Program"}

        # Get program identifier
        identifier_str = f"urn:openspp:program|{program.name.lower().replace(' ', '-')}"

        # Check if program has external identifiers
        if "spp.program.id" in self.env and hasattr(program, "program_id_ids"):
            if program.program_id_ids:
                prog_id = program.program_id_ids[0]
                identifier_str = f"{prog_id.namespace_uri}|{prog_id.value}"

        return {
            "reference": f"Program/{identifier_str}",
            "display": program.name,
        }

    def _build_beneficiary_reference(self, partner) -> dict:
        """Build Reference to beneficiary (Individual or Group)"""
        if not partner:
            return {"reference": "Unknown/unknown", "display": "Unknown Beneficiary"}

        # Determine resource type
        resource_type = "Group" if partner.is_group else "Individual"

        # Get primary identifier
        if partner.reg_ids:
            primary_id = partner.reg_ids[0]
            ref = f"{resource_type}/{primary_id.id_type_id.uri}|{primary_id.value}"
        else:
            # No identifier - this should not happen in a properly configured system
            _logger.error(
                "Partner with id=%s has no external identifiers - cannot create API reference",
                partner.id,
            )
            ref = f"{resource_type}/unknown"

        return {
            "reference": ref,
            "display": partner.name,
        }

    def from_api_schema(self, schema: ProgramMembership) -> dict[str, Any]:
        """
        Convert ProgramMembership API schema to Odoo vals dict.

        CRITICAL:
        - Find program by namespace_uri
        - Find beneficiary by namespace_uri
        - NO database IDs

        Args:
            schema: ProgramMembership schema instance

        Returns:
            Dictionary of values for spp.program.membership.create() or write()
        """
        vals = {}

        # Parse program reference and find program
        program = self._parse_program_reference(schema.program.reference)
        if not program:
            raise ValidationError(f"Program not found: {schema.program.reference}")
        vals["program_id"] = program.id

        # Parse beneficiary reference and find partner
        partner = self._parse_beneficiary_reference(schema.beneficiary.reference)
        if not partner:
            raise ValidationError(f"Beneficiary not found: {schema.beneficiary.reference}")
        vals["partner_id"] = partner.id

        # Status
        vals["state"] = schema.status

        # Enrollment date
        if schema.enrollment_date:
            vals["enrollment_date"] = schema.enrollment_date

        # Exit date
        if schema.exit_date:
            vals["exit_date"] = schema.exit_date

        # Exit reason - would need exit_reason_id field in model
        # For now, we skip this as it's not in the base model

        return vals

    def _parse_program_reference(self, reference: str):
        """
        Parse program reference and return program record.

        Format: Program/{system}|{value}
        """
        if not reference.startswith("Program/"):
            raise ValidationError(f"Invalid program reference format: {reference}")

        identifier_str = reference.replace("Program/", "")
        if "|" not in identifier_str:
            raise ValidationError(f"Invalid program identifier format: {identifier_str}")

        system, value = identifier_str.split("|", 1)

        # URL-decode system URI (e.g., %23 -> #)
        from urllib.parse import unquote

        system = unquote(system)

        # Use ProgramService to find program
        from .program_service import ProgramService

        program_service = ProgramService(self.env)
        return program_service.find_by_identifier(system, value)

    def _parse_beneficiary_reference(self, reference: str):
        """
        Parse beneficiary reference and return partner record.

        Format: Individual/{system}|{value} or Group/{system}|{value}
        """
        if not (reference.startswith("Individual/") or reference.startswith("Group/")):
            raise ValidationError(f"Invalid beneficiary reference format: {reference}")

        # Extract identifier
        if reference.startswith("Individual/"):
            identifier_str = reference.replace("Individual/", "")
        else:
            identifier_str = reference.replace("Group/", "")

        if "|" not in identifier_str:
            raise ValidationError(f"Invalid beneficiary identifier format: {identifier_str}")

        system, value = identifier_str.split("|", 1)

        # URL-decode system URI (e.g., %23 -> #) since references may come from URL contexts
        from urllib.parse import unquote

        system = unquote(system)

        # Find partner by identifier
        reg_id = (
            self.env["spp.registry.id"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [
                    ("id_type_id.uri", "=", system),
                    ("value", "=", value),
                ],
                limit=1,
            )
        )

        if reg_id and reg_id.partner_id:
            return reg_id.partner_id

        return self.env["res.partner"]

    def create(self, schema: ProgramMembership, source: str) -> Any:
        """
        Create new ProgramMembership with source tracking.

        Args:
            schema: ProgramMembership schema
            source: Source system URI (e.g., urn:openspp:api-client:{client_id})

        Returns:
            Created spp.program.membership record
        """
        vals = self.from_api_schema(schema)

        # Add source tracking if the model supports it
        # Base model doesn't have source_system field, but extensions might add it

        membership = self.env["spp.program.membership"].sudo().create(vals)  # nosemgrep: odoo-sudo-without-context

        # Log using beneficiary identifier, not database ID
        partner_id = membership.partner_id.reg_ids[0] if membership.partner_id.reg_ids else None
        beneficiary_str = f"{partner_id.namespace_uri}|{partner_id.value}" if partner_id else "unknown"
        _logger.info("Created program membership for %s via API from %s", beneficiary_str, source)
        return membership

    def update(self, membership, schema: ProgramMembership, source: str) -> Any:
        """
        Update ProgramMembership with source tracking.

        Args:
            membership: Existing spp.program.membership record
            schema: ProgramMembership schema with updates
            source: Source system URI

        Returns:
            Updated spp.program.membership record
        """
        vals = self.from_api_schema(schema)

        # Update membership
        membership.sudo().write(vals)  # nosemgrep: odoo-sudo-without-context

        # Log using beneficiary identifier, not database ID
        partner_id = membership.partner_id.reg_ids[0] if membership.partner_id.reg_ids else None
        beneficiary_str = f"{partner_id.namespace_uri}|{partner_id.value}" if partner_id else "unknown"
        _logger.info("Updated program membership for %s via API from %s", beneficiary_str, source)
        return membership
