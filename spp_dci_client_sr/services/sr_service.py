# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""SR Service for connecting to external Social Registries."""

import logging

from odoo.exceptions import UserError, ValidationError

from odoo.addons.spp_dci_client.services import DCIClient

_logger = logging.getLogger(__name__)


class SRService:
    """Service for interacting with Social Registries via DCI API.

    Provides methods to:
    - Search for persons/households in the SR
    - Get program enrollment information
    - Subscribe to updates from the SR
    - Verify beneficiary eligibility

    When OpenSPP is deployed as an MIS, this service queries external
    Social Registries for beneficiary data and eligibility information.
    """

    def __init__(self, env, data_source_code: str):
        """Initialize SR service.

        Args:
            env: Odoo environment
            data_source_code: Code of the DCI data source to use

        Raises:
            UserError: If data source not found or not configured for SR
        """
        self.env = env
        self.data_source_code = data_source_code

        # Get data source
        data_source = env["spp.dci.data.source"].search(
            [("code", "=", data_source_code)],
            limit=1,
        )

        if not data_source:
            raise UserError(f"DCI data source '{data_source_code}' not found")

        if data_source.registry_type != "sr":
            _logger.warning(
                "Data source '%s' is type '%s', expected 'sr'",
                data_source_code,
                data_source.registry_type,
            )

        self.data_source = data_source
        self.client = DCIClient(data_source, env)

    def check_connection(self) -> bool:
        """Test connection to the SR.

        Returns:
            bool: True if connection successful

        Raises:
            Exception: If connection fails
        """
        # Try a simple search to verify connectivity
        try:
            self.client.search(
                query_type="idtype-value",
                query_value="test:connection-check",
                registry_type="ns:registry_type:social_registry",
            )
            return True
        except Exception as e:
            _logger.error("SR connection check failed: %s", str(e))
            raise

    def search_person(
        self,
        identifier_type: str,
        identifier_value: str,
        async_mode: bool = False,
    ) -> dict | None:
        """Search for a person in the Social Registry.

        Args:
            identifier_type: Type of identifier (UIN, NIN, etc.)
            identifier_value: Value of the identifier
            async_mode: If True, returns immediately with correlation_id

        Returns:
            dict: Person data if found (sync mode)
            dict: {"correlation_id": str} if async mode
            None: If not found

        Raises:
            UserError: If search fails
        """
        try:
            query_value = f"{identifier_type}:{identifier_value}"

            if async_mode:
                response = self.client.search_async(
                    query_type="idtype-value",
                    query_value=query_value,
                    registry_type="ns:registry_type:social_registry",
                )
                correlation_id = response.get("message", {}).get("correlation_id")
                return {"correlation_id": correlation_id} if correlation_id else None
            else:
                response = self.client.search(
                    query_type="idtype-value",
                    query_value=query_value,
                    registry_type="ns:registry_type:social_registry",
                )

            # Extract search results
            message = response.get("message", {})
            search_response = message.get("search_response", [])

            if not search_response:
                return None

            # Get first successful result
            for result in search_response:
                if result.get("status") == "succ":
                    data = result.get("data", {})
                    reg_records = data.get("reg_records", [])
                    if reg_records:
                        return reg_records[0]

            return None

        except Exception as e:
            _logger.error(
                "SR person search failed: %s",
                str(e),
                exc_info=True,
            )
            raise UserError(f"Failed to search SR: {str(e)}") from e

    def search_household(
        self,
        household_id: str,
        async_mode: bool = False,
    ) -> dict | None:
        """Search for a household in the Social Registry.

        Args:
            household_id: Household identifier
            async_mode: If True, returns immediately with correlation_id

        Returns:
            dict: Household data if found
            None: If not found
        """
        try:
            if async_mode:
                response = self.client.search_async(
                    query_type="idtype-value",
                    query_value=f"HHID:{household_id}",
                    registry_type="ns:registry_type:social_registry",
                    reg_sub_type="group",
                )
                correlation_id = response.get("message", {}).get("correlation_id")
                return {"correlation_id": correlation_id} if correlation_id else None
            else:
                response = self.client.search(
                    query_type="idtype-value",
                    query_value=f"HHID:{household_id}",
                    registry_type="ns:registry_type:social_registry",
                    reg_sub_type="group",
                )

            message = response.get("message", {})
            search_response = message.get("search_response", [])

            if not search_response:
                return None

            for result in search_response:
                if result.get("status") == "succ":
                    data = result.get("data", {})
                    reg_records = data.get("reg_records", [])
                    if reg_records:
                        return reg_records[0]

            return None

        except Exception as e:
            _logger.error("SR household search failed: %s", str(e), exc_info=True)
            raise UserError(f"Failed to search SR for household: {str(e)}") from e

    def get_program_enrollment(
        self,
        identifier_type: str,
        identifier_value: str,
    ) -> list:
        """Get program enrollment for a person.

        Args:
            identifier_type: Type of identifier
            identifier_value: Value of the identifier

        Returns:
            list: List of enrolled programs with details
        """
        person_data = self.search_person(identifier_type, identifier_value)

        if not person_data:
            return []

        return person_data.get("enrolled_programs", [])

    def check_eligibility(
        self,
        identifier_type: str,
        identifier_value: str,
        program_id: str | None = None,
    ) -> dict:
        """Check eligibility status for a person.

        Args:
            identifier_type: Type of identifier
            identifier_value: Value of the identifier
            program_id: Optional specific program to check

        Returns:
            dict: Eligibility information including:
                - found: bool - Whether person exists in SR
                - eligible: bool - Whether person is eligible
                - enrolled_programs: list - Current program enrollments
                - reason: str - Reason if not eligible
        """
        try:
            person_data = self.search_person(identifier_type, identifier_value)

            if not person_data:
                return {
                    "found": False,
                    "eligible": False,
                    "enrolled_programs": [],
                    "reason": "Person not found in Social Registry",
                }

            enrolled_programs = person_data.get("enrolled_programs", [])

            # Basic eligibility - person exists in SR
            result = {
                "found": True,
                "eligible": True,
                "enrolled_programs": enrolled_programs,
                "reason": None,
            }

            # If specific program requested, check if already enrolled
            if program_id:
                for prog in enrolled_programs:
                    prog_id = prog.get("id") if isinstance(prog, dict) else prog
                    if prog_id == program_id:
                        result["eligible"] = False
                        result["reason"] = f"Already enrolled in program {program_id}"
                        break

            return result

        except Exception as e:
            _logger.error("Eligibility check failed: %s", str(e), exc_info=True)
            return {
                "found": False,
                "eligible": False,
                "enrolled_programs": [],
                "reason": f"Error checking eligibility: {str(e)}",
            }

    def subscribe_updates(
        self,
        event_types: list | None = None,
    ) -> list[str]:
        """Subscribe to updates from the Social Registry.

        Args:
            event_types: List of event types to subscribe to
                (e.g., ["ENROLLMENT", "DISENROLLMENT", "UPDATE"])

        Returns:
            list: List of subscription IDs

        Raises:
            UserError: If subscription fails
        """
        if not event_types:
            event_types = ["ENROLLMENT", "DISENROLLMENT", "UPDATE"]

        subscription_ids = []

        for event_type in event_types:
            try:
                response = self.client.subscribe(
                    event_type=event_type,
                    notify_record_type="Person",
                )

                correlation_id = response.get("message", {}).get("correlation_id")
                if correlation_id:
                    subscription_ids.append(correlation_id)
                    _logger.info(
                        "Subscribed to SR event %s: %s",
                        event_type,
                        correlation_id,
                    )

            except Exception as e:
                _logger.error(
                    "Failed to subscribe to SR event %s: %s",
                    event_type,
                    str(e),
                )
                raise UserError(f"Failed to subscribe to SR updates: {str(e)}") from e

        if not subscription_ids:
            raise UserError("No subscriptions were created")

        return subscription_ids

    def unsubscribe(self, subscription_codes: list[str]) -> dict:
        """Unsubscribe from SR updates.

        Args:
            subscription_codes: List of subscription codes to cancel

        Returns:
            dict: Unsubscribe response

        Raises:
            ValidationError: If no subscription codes provided
            UserError: If unsubscribe fails
        """
        if not subscription_codes:
            raise ValidationError("subscription_codes is required")

        try:
            return self.client.unsubscribe(subscription_codes=subscription_codes)
        except Exception as e:
            _logger.error("Failed to unsubscribe from SR: %s", str(e))
            raise UserError(f"Failed to unsubscribe: {str(e)}") from e

    def sync_person_to_local(
        self,
        identifier_type: str,
        identifier_value: str,
        partner_id: int | None = None,
    ) -> "models.Model":
        """Sync person data from SR to local SR record.

        Args:
            identifier_type: Type of identifier
            identifier_value: Value of the identifier
            partner_id: Optional local partner ID to link

        Returns:
            spp.dci.sr.record: Created or updated SR record

        Raises:
            UserError: If person not found or sync fails
        """
        person_data = self.search_person(identifier_type, identifier_value)

        if not person_data:
            raise UserError(f"Person with {identifier_type}:{identifier_value} not found in SR")

        SRRecord = self.env["spp.dci.sr.record"].sudo()

        # Find or create partner if not provided
        if not partner_id:
            # Try to find by identifier. The model is spp.registry.id;
            # earlier code referenced a non-existent 'spp.id', which
            # raised KeyError on every lookup-by-identifier call.
            id_record = (
                self.env["spp.registry.id"]
                .sudo()
                .search(
                    [
                        ("id_type_id.code", "=", identifier_type),
                        ("value", "=", identifier_value),
                    ],
                    limit=1,
                )
            )
            if id_record:
                partner_id = id_record.partner_id.id

        if not partner_id:
            raise UserError(f"Could not find local partner for {identifier_type}:{identifier_value}")

        # Find existing SR record
        existing = SRRecord.search(
            [
                ("partner_id", "=", partner_id),
                ("source_registry", "=", self.data_source.our_sender_id),
            ],
            limit=1,
        )

        if existing:
            existing._update_from_sr_response(person_data)
            return existing
        else:
            # Create new record
            vals = {
                "partner_id": partner_id,
                "source_registry": self.data_source.our_sender_id,
                "identifier_type": identifier_type,
                "identifier_value": identifier_value,
                "external_id": person_data.get("id"),
            }

            record = SRRecord.create(vals)
            record._update_from_sr_response(person_data)
            return record
