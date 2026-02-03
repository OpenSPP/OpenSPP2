"""IBR Service for duplication checks and beneficiary queries."""

import logging

from odoo.exceptions import UserError

from odoo.addons.spp_dci_client.services import DCIClient

_logger = logging.getLogger(__name__)


class DuplicationResult:
    """Result of a duplication check.

    Attributes:
        is_duplicate: Whether a duplicate was found
        matched_programs: List of program names/IDs where duplicates were found
        raw_response: Raw API response for debugging
    """

    def __init__(
        self,
        is_duplicate: bool = False,
        matched_programs: list[str] | None = None,
        raw_response: dict | None = None,
    ):
        """Initialize duplication result.

        Args:
            is_duplicate: Whether a duplicate was found
            matched_programs: List of program names/IDs where duplicates were found
            raw_response: Raw API response
        """
        self.is_duplicate = is_duplicate
        self.matched_programs = matched_programs or []
        self.raw_response = raw_response or {}

    def to_dict(self) -> dict:
        """Convert to dictionary.

        Returns:
            Dictionary representation of the result
        """
        return {
            "is_duplicate": self.is_duplicate,
            "matched_programs": self.matched_programs,
            "raw_response": self.raw_response,
        }


class BeneficiaryInfo:
    """Information about a beneficiary.

    Attributes:
        identifier_type: Type of identifier
        identifier_value: Value of identifier
        name: Beneficiary name
        programs: List of programs they're enrolled in
        metadata: Additional metadata from the registry
    """

    def __init__(
        self,
        identifier_type: str,
        identifier_value: str,
        name: str | None = None,
        programs: list[str] | None = None,
        metadata: dict | None = None,
    ):
        """Initialize beneficiary info.

        Args:
            identifier_type: Type of identifier (UIN, BRN, etc.)
            identifier_value: Value of identifier
            name: Beneficiary name
            programs: List of programs
            metadata: Additional metadata
        """
        self.identifier_type = identifier_type
        self.identifier_value = identifier_value
        self.name = name
        self.programs = programs or []
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "identifier_type": self.identifier_type,
            "identifier_value": self.identifier_value,
            "name": self.name,
            "programs": self.programs,
            "metadata": self.metadata,
        }


class IBRService:
    """Service for interacting with Integrated Beneficiary Registry (IBR) via DCI API.

    This service provides methods for checking duplicate enrollments,
    searching for beneficiaries, and querying enrollment status across programs.
    """

    def __init__(self, data_source, env):
        """Initialize IBR service.

        Args:
            data_source: spp.dci.data.source record for IBR
            env: Odoo environment
        """
        if not data_source:
            raise ValueError("data_source is required")

        self.data_source = data_source
        self.env = env
        self.client = DCIClient(data_source, env)

        # Validate that this is an IBR data source
        if hasattr(data_source, "registry_type") and data_source.registry_type != "ibr":
            _logger.warning(
                "Data source '%s' is not configured as IBR (registry_type: %s)",
                data_source.name,
                data_source.registry_type,
            )

    def check_duplication(self, partner) -> dict:
        """Check for duplicate enrollments across programs.

        This method searches the IBR for the given partner using their
        identifiers to determine if they're already enrolled in other programs.

        Args:
            partner: res.partner record to check

        Returns:
            Dictionary with:
                - is_duplicate: bool indicating if duplicate found
                - matched_programs: list of program names/IDs
                - raw_response: raw API response

        Raises:
            UserError: If partner has no identifiers or API request fails
        """
        if not partner:
            raise ValueError("partner is required")

        _logger.info("Checking duplication for partner_id=%s", partner.id)

        # Get partner identifiers
        identifiers = self._get_partner_identifiers(partner)
        if not identifiers:
            raise UserError(
                f"Partner '{partner.name}' has no identifiers configured. "
                "Please add at least one identifier before checking for duplicates."
            )

        # Search for each identifier
        all_matches = []
        all_programs = set()
        raw_responses = []

        for id_type, id_value in identifiers:
            try:
                _logger.debug(
                    "Searching IBR for identifier: %s:%s",
                    id_type,
                    id_value,
                )

                # Search IBR using DCIClient
                response = self.client.search_by_id(
                    identifier_type=id_type,
                    identifier_value=id_value,
                    record_type="PERSON",
                    page=1,
                    page_size=10,
                )

                raw_responses.append(response)

                # Parse response to extract matches and programs
                matches = self._parse_search_response(response)
                all_matches.extend(matches)

                # Extract program information from matches
                for match in matches:
                    programs = match.get("programs", [])
                    all_programs.update(programs)

            except Exception as e:
                _logger.error(
                    "Error searching IBR for %s:%s - %s",
                    id_type,
                    id_value,
                    str(e),
                )
                # Continue with other identifiers even if one fails
                continue

        # Determine if duplicate found
        is_duplicate = len(all_matches) > 0
        matched_programs = sorted(list(all_programs))

        result = DuplicationResult(
            is_duplicate=is_duplicate,
            matched_programs=matched_programs,
            raw_response=raw_responses,
        )

        _logger.info(
            "Duplication check complete for partner %s: is_duplicate=%s, programs=%s",
            partner.id,
            is_duplicate,
            matched_programs,
        )

        return result.to_dict()

    def search_beneficiary(
        self,
        identifier_type: str,
        identifier_value: str,
    ) -> list[dict]:
        """Search for beneficiary by identifier.

        Args:
            identifier_type: Type of identifier (UIN, BRN, MRN, DRN, etc.)
            identifier_value: Value of the identifier

        Returns:
            List of matched beneficiary dictionaries

        Raises:
            UserError: If API request fails
        """
        _logger.info(
            "Searching for beneficiary: %s:%s",
            identifier_type,
            identifier_value,
        )

        try:
            # Search using DCIClient
            response = self.client.search_by_id(
                identifier_type=identifier_type,
                identifier_value=identifier_value,
                record_type="PERSON",
                page=1,
                page_size=10,
            )

            # Parse response
            matches = self._parse_search_response(response)

            _logger.info(
                "Found %d beneficiary match(es) for %s:%s",
                len(matches),
                identifier_type,
                identifier_value,
            )

            return matches

        except Exception as e:
            error_msg = f"Failed to search for beneficiary {identifier_type}:{identifier_value}: {str(e)}"
            _logger.error(error_msg)
            raise UserError(error_msg) from e

    def get_enrollment_status(
        self,
        identifier_type: str,
        identifier_value: str,
    ) -> dict:
        """Get enrollment status for a beneficiary.

        Args:
            identifier_type: Type of identifier (UIN, BRN, MRN, DRN, etc.)
            identifier_value: Value of the identifier

        Returns:
            Dictionary with:
                - enrolled: bool indicating if beneficiary is enrolled
                - programs: list of program names/IDs
                - beneficiary_info: beneficiary details

        Raises:
            UserError: If API request fails
        """
        _logger.info(
            "Getting enrollment status for: %s:%s",
            identifier_type,
            identifier_value,
        )

        try:
            # Search for beneficiary
            matches = self.search_beneficiary(identifier_type, identifier_value)

            # Extract enrollment information
            enrolled = len(matches) > 0
            all_programs = set()
            beneficiary_info = None

            if matches:
                # Use first match as primary beneficiary info
                first_match = matches[0]
                beneficiary_info = BeneficiaryInfo(
                    identifier_type=identifier_type,
                    identifier_value=identifier_value,
                    name=first_match.get("name"),
                    programs=first_match.get("programs", []),
                    metadata=first_match,
                ).to_dict()

                # Collect all programs from all matches
                for match in matches:
                    programs = match.get("programs", [])
                    all_programs.update(programs)

            result = {
                "enrolled": enrolled,
                "programs": sorted(list(all_programs)),
                "beneficiary_info": beneficiary_info,
            }

            _logger.info(
                "Enrollment status for %s:%s - enrolled: %s, programs: %s",
                identifier_type,
                identifier_value,
                enrolled,
                result["programs"],
            )

            return result

        except Exception as e:
            error_msg = f"Failed to get enrollment status for {identifier_type}:{identifier_value}: {str(e)}"
            _logger.error(error_msg)
            raise UserError(error_msg) from e

    def _get_partner_identifiers(self, partner) -> list[tuple]:
        """Get list of identifiers for a partner.

        Args:
            partner: res.partner record

        Returns:
            List of (identifier_type, identifier_value) tuples
        """
        identifiers = []

        # Check if partner has reg_ids relationship (from spp_registry)
        if hasattr(partner, "reg_ids"):
            for registry_id in partner.reg_ids:
                if registry_id.id_type_id and registry_id.value:
                    # Get the ID type code/name
                    id_type_code = (
                        registry_id.id_type_id.code
                        if hasattr(registry_id.id_type_id, "code")
                        else registry_id.id_type_id.name
                    )
                    identifiers.append((id_type_code, registry_id.value))

        return identifiers

    def _parse_search_response(self, response: dict) -> list[dict]:
        """Parse DCI search response to extract matches.

        Args:
            response: Raw DCI API response

        Returns:
            List of matched beneficiary dictionaries
        """
        matches = []

        try:
            # Extract message from response envelope
            message = response.get("message", {})

            # Get search response items
            search_response = message.get("search_response", [])

            for item in search_response:
                # Extract data from response item
                data = item.get("data", [])

                for record in data:
                    # Parse record structure
                    # This structure may vary depending on the IBR implementation
                    beneficiary = {
                        "reference_id": item.get("reference_id"),
                        "name": self._extract_name(record),
                        "identifiers": self._extract_identifiers(record),
                        "programs": self._extract_programs(record),
                        "raw_data": record,
                    }
                    matches.append(beneficiary)

        except Exception as e:
            _logger.error("Error parsing search response: %s", str(e), exc_info=True)
            # Return empty list on parse error
            return []

        return matches

    def _extract_name(self, record: dict) -> str | None:
        """Extract name from record.

        Args:
            record: Record data dictionary

        Returns:
            Name string or None
        """
        # Try full name fields first
        for field in ["name", "full_name"]:
            if field in record and record[field]:
                return record[field]

        # Try to construct name from given_name + family_name
        given = record.get("given_name", "")
        family = record.get("family_name", "")
        if given or family:
            return f"{given} {family}".strip()

        return None

    def _extract_identifiers(self, record: dict) -> list[dict]:
        """Extract identifiers from record.

        Args:
            record: Record data dictionary

        Returns:
            List of identifier dictionaries
        """
        identifiers = []

        # Check for identifiers field
        if "identifiers" in record:
            ids = record["identifiers"]
            if isinstance(ids, list):
                identifiers.extend(ids)
            elif isinstance(ids, dict):
                identifiers.append(ids)

        # Check for common identifier fields
        id_fields = ["uin", "brn", "mrn", "drn", "national_id"]
        for field in id_fields:
            if field in record and record[field]:
                identifiers.append(
                    {
                        "type": field.upper(),
                        "value": record[field],
                    }
                )

        return identifiers

    def _extract_programs(self, record: dict) -> list[str]:
        """Extract program information from record.

        Args:
            record: Record data dictionary

        Returns:
            List of program names/IDs
        """
        programs = []

        # Check for programs field
        if "programs" in record:
            progs = record["programs"]
            if isinstance(progs, list):
                for prog in progs:
                    if isinstance(prog, str):
                        programs.append(prog)
                    elif isinstance(prog, dict):
                        # Try to extract program name/ID
                        prog_name = prog.get("name") or prog.get("id") or prog.get("code")
                        if prog_name:
                            programs.append(str(prog_name))

        # Check for enrollment field
        if "enrollments" in record:
            enrollments = record["enrollments"]
            if isinstance(enrollments, list):
                for enrollment in enrollments:
                    if isinstance(enrollment, dict):
                        prog_name = (
                            enrollment.get("program_name") or enrollment.get("program_id") or enrollment.get("program")
                        )
                        if prog_name:
                            programs.append(str(prog_name))

        return programs
