# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CRVS Service for connecting to Civil Registration and Vital Statistics systems."""

import json
import logging

from odoo import _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.spp_dci.schemas.constants import RegistryType
from odoo.addons.spp_dci_client.services import DCIClient

_logger = logging.getLogger(__name__)


class CRVSService:
    """Service for interacting with CRVS registries via DCI API.

    Provides methods to:
    - Verify birth records
    - Check death status
    - Subscribe to vital events
    - Process CRVS notifications
    """

    def __init__(self, env, data_source_code="crvs_main"):
        """Initialize CRVS service.

        Args:
            env: Odoo environment
            data_source_code: Code of the DCI data source for CRVS
        """
        self.env = env
        self.data_source_code = data_source_code

        # Get data source
        self.data_source = self.env["spp.dci.data.source"].get_by_code(data_source_code)

        # Validate it's a CRVS registry
        if self.data_source.registry_type != RegistryType.CRVS.value:
            raise ValidationError(
                f"Data source '{data_source_code}' is not a CRVS registry (type: {self.data_source.registry_type})"
            )

        # Initialize DCI client
        self.client = DCIClient(self.data_source, env)

    def verify_birth(self, identifier_type: str, identifier_value: str) -> dict | None:
        """Verify birth record in CRVS system.

        Args:
            identifier_type: Type of identifier (BRN, UIN, etc.)
            identifier_value: The identifier value

        Returns:
            dict: Birth record data if found, None otherwise
            Example: {
                'identifier_type': 'BRN',
                'identifier_value': '123456',
                'birth_date': '2020-01-15',
                'person_name': 'John Doe',
                'mother_name': 'Jane Doe',
                'father_name': 'James Doe',
                'place_of_birth': 'General Hospital',
            }

        Raises:
            UserError: If request fails
            ValidationError: If parameters are invalid
        """
        if not identifier_type or not identifier_value:
            raise ValidationError("identifier_type and identifier_value are required")

        _logger.info(
            "Verifying birth record in CRVS for %s:%s",
            identifier_type,
            identifier_value,
        )

        try:
            # OpenCRVS rejects the upstream `idtype-value` query shape (HTTP 400
            # "expected expression"); use the OpenCRVS-specific helper that
            # builds the nested-expression envelope the server accepts.
            response = self.client.search_by_id_opencrvs(
                identifier_type=identifier_type,
                identifier_value=identifier_value,
                event_type="birth",
                page=1,
                page_size=1,
            )

            record_data = self._first_record(response)
            if record_data is None:
                _logger.info("No birth record found for %s:%s", identifier_type, identifier_value)
                return None

            _logger.info("Birth record verified for %s:%s", identifier_type, identifier_value)
            # Return the raw record so the CEL bridge dispatcher can navigate
            # variable.dci_attribute_path against the OpenCRVS shape directly.
            # Callers that want the legacy flat shape can apply
            # _extract_birth_data themselves.
            return record_data

        except Exception as e:
            _logger.error("Failed to verify birth record: %s", str(e), exc_info=True)
            raise UserError(_("Failed to verify birth record: %s") % str(e)) from e

    def check_death(self, identifier_type: str, identifier_value: str) -> bool:
        """Check if person is deceased in CRVS system.

        Args:
            identifier_type: Type of identifier (UIN, BRN, DRN, etc.)
            identifier_value: The identifier value

        Returns:
            bool: True if person is deceased, False otherwise

        Raises:
            UserError: If request fails
            ValidationError: If parameters are invalid
        """
        if not identifier_type or not identifier_value:
            raise ValidationError("identifier_type and identifier_value are required")

        _logger.info(
            "Checking death status in CRVS for %s:%s",
            identifier_type,
            identifier_value,
        )

        try:
            # OpenCRVS rejects the upstream `idtype-value` shape — call the
            # OpenCRVS-specific helper that builds the nested-expression
            # envelope. event_type='death' targets the death-event collection.
            response = self.client.search_by_id_opencrvs(
                identifier_type=identifier_type,
                identifier_value=identifier_value,
                event_type="death",
                page=1,
                page_size=1,
            )

            is_deceased = self._first_record(response) is not None
            if is_deceased:
                _logger.info(
                    "Death record found for %s:%s - person is deceased",
                    identifier_type,
                    identifier_value,
                )
            else:
                _logger.info("No death record found for %s:%s", identifier_type, identifier_value)
            return is_deceased

        except Exception as e:
            _logger.error("Failed to check death status: %s", str(e), exc_info=True)
            raise UserError(_("Failed to check death status: %s") % str(e)) from e

    def subscribe_events(self, event_types: list | None = None) -> list[str]:
        """Subscribe to CRVS vital events.

        Args:
            event_types: List of event types to subscribe to (default: ['BIRTH', 'DEATH'])

        Returns:
            list[str]: List of subscription IDs

        Raises:
            UserError: If subscription fails
            ValidationError: If parameters are invalid
        """
        if not event_types:
            event_types = ["BIRTH", "DEATH"]

        _logger.info(
            "Subscribing to CRVS events %s",
            event_types,
        )

        subscription_ids = []

        try:
            # Subscribe to each event type using DCI client
            for event_type in event_types:
                response = self.client.subscribe(
                    event_type=event_type,
                    notify_record_type="Person",
                )

                # Parse response
                if not response or "message" not in response:
                    _logger.error(
                        "Invalid CRVS subscribe response for %s: %s",
                        event_type,
                        response,
                    )
                    continue

                message = response["message"]

                # Extract subscription ID from ACK response
                subscription_id = (
                    message.get("correlation_id") or message.get("subscription_id") or message.get("transaction_id")
                )

                if subscription_id:
                    subscription_ids.append(subscription_id)
                    _logger.info(
                        "Successfully subscribed to CRVS event '%s' with ID: %s",
                        event_type,
                        subscription_id,
                    )
                else:
                    _logger.warning(
                        "No subscription_id in CRVS response for %s: %s",
                        event_type,
                        message,
                    )

            if not subscription_ids:
                raise UserError(_("Failed to subscribe to any CRVS events"))

            return subscription_ids

        except UserError:
            raise
        except Exception as e:
            _logger.error("Failed to subscribe to CRVS events: %s", str(e), exc_info=True)
            raise UserError(_("Failed to subscribe to CRVS events: %s") % str(e)) from e

    def unsubscribe_events(self, subscription_codes: list[str]) -> dict:
        """Unsubscribe from CRVS vital events.

        Args:
            subscription_codes: List of subscription codes to unsubscribe

        Returns:
            dict: Unsubscribe response

        Raises:
            UserError: If unsubscribe fails
            ValidationError: If parameters are invalid
        """
        if not subscription_codes:
            raise ValidationError("subscription_codes is required")

        _logger.info(
            "Unsubscribing from CRVS events: %s",
            subscription_codes,
        )

        try:
            response = self.client.unsubscribe(subscription_codes=subscription_codes)

            _logger.info("Successfully unsubscribed from CRVS events: %s", subscription_codes)
            return response

        except Exception as e:
            _logger.error("Failed to unsubscribe from CRVS events: %s", str(e), exc_info=True)
            raise UserError(_("Failed to unsubscribe from CRVS events: %s") % str(e)) from e

    def process_notification(self, notification_data: dict) -> int:
        """Process CRVS notification and create event record.

        Args:
            notification_data: Notification data from CRVS webhook
            Example: {
                'header': {...},
                'message': {
                    'event_type': 'DEATH',
                    'event_date': '2024-12-01',
                    'identifiers': [
                        {'type': 'UIN', 'value': '123456789'},
                        {'type': 'DRN', 'value': 'D-2024-12345'}
                    ],
                    'person': {...},
                    ...
                }
            }

        Returns:
            int: ID of created crvs_event record

        Raises:
            ValidationError: If notification data is invalid
        """
        if not notification_data:
            raise ValidationError("notification_data is required")

        _logger.info("Processing CRVS notification: %s", notification_data)

        try:
            # Extract message from envelope
            if "message" in notification_data:
                message = notification_data["message"]
            else:
                message = notification_data

            # Extract event details
            event_type = message.get("event_type", "").lower()
            event_date = message.get("event_date")

            # Extract identifiers
            identifiers = message.get("identifiers", [])
            identifier_type = None
            identifier_value = None

            if identifiers:
                # Use first identifier
                first_id = identifiers[0]
                identifier_type = first_id.get("type")
                identifier_value = first_id.get("value")

            # Create CRVS event record
            event = self.env["spp.dci.crvs.event"].create(
                {
                    "event_type": event_type,
                    "identifier_type": identifier_type,
                    "identifier_value": identifier_value,
                    "event_date": event_date,
                    "raw_data": json.dumps(notification_data, indent=2),
                    "state": "received",
                }
            )

            _logger.info(
                "Created CRVS event record %s (type: %s, identifier: %s:%s)",
                event.name,
                event_type,
                identifier_type,
                identifier_value,
            )

            # Auto-process the event
            event.process_event()

            return event.id

        except Exception as e:
            _logger.error("Failed to process CRVS notification: %s", str(e), exc_info=True)
            raise ValidationError(_("Failed to process CRVS notification: %s") % str(e)) from e

    @staticmethod
    def _first_record(response):
        """Unwrap an OpenCRVS DCI response to the first registry record.

        SPDCI shape returned by search_by_id_opencrvs:

            response.message.search_response[i].data.reg_records[j]

        Returns the first non-empty record across all search_response items,
        or None if no records are present (typical for HTTP 200 with an
        empty reg_records array — what OpenCRVS returns for "not found").
        """
        if not isinstance(response, dict):
            return None
        message = response.get("message") or {}
        for sr in message.get("search_response") or []:
            data = sr.get("data") or {}
            if not isinstance(data, dict):
                continue
            for rec in data.get("reg_records") or []:
                if isinstance(rec, dict):
                    return rec
        return None

    def _extract_birth_data(self, record_data: dict) -> dict:
        """Extract birth information from DCI record data.

        Args:
            record_data: DCI record data from search response

        Returns:
            dict: Extracted birth data
        """
        birth_data = {}

        # Extract basic fields
        if "identifiers" in record_data:
            for identifier in record_data["identifiers"]:
                if identifier.get("type") == "BRN":
                    birth_data["identifier_type"] = "BRN"
                    birth_data["identifier_value"] = identifier.get("value")
                    break

        # Extract birth date
        if "birth_date" in record_data:
            birth_data["birth_date"] = record_data["birth_date"]
        elif "birthdate" in record_data:
            birth_data["birth_date"] = record_data["birthdate"]

        # Extract person info
        if "name" in record_data:
            birth_data["person_name"] = record_data["name"]
        elif "given_name" in record_data and "family_name" in record_data:
            birth_data["person_name"] = f"{record_data['given_name']} {record_data['family_name']}"

        # Extract parent info
        if "mother_name" in record_data:
            birth_data["mother_name"] = record_data["mother_name"]
        if "father_name" in record_data:
            birth_data["father_name"] = record_data["father_name"]

        # Extract place of birth
        if "place_of_birth" in record_data:
            birth_data["place_of_birth"] = record_data["place_of_birth"]

        return birth_data
