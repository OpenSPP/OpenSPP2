# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DR Service for connecting to Disability Registry systems."""

import json
import logging

from odoo import _, fields
from odoo.exceptions import UserError, ValidationError

from odoo.addons.spp_dci.schemas.constants import RegistryType
from odoo.addons.spp_dci_client.services import DCIClient

from .dr_parsing import extract_disability_data, extract_functional_scores, unwrap_search_data

_logger = logging.getLogger(__name__)


class DRService:
    """Service for interacting with Disability Registry (DR) via DCI API.

    Provides methods to:
    - Query PWD (Person with Disability) status
    - Retrieve functional assessment scores
    - Get disability type information
    - Sync disability data to local cache
    """

    def __init__(self, env, data_source_code="dr_main"):
        """Initialize DR service.

        Args:
            env: Odoo environment
            data_source_code: Code of the DCI data source for DR
        """
        self.env = env
        self.data_source_code = data_source_code

        # Get data source
        self.data_source = self.env["spp.dci.data.source"].get_by_code(data_source_code)

        # Validate it's a DR registry (canonical namespaced registry_type value)
        if self.data_source.registry_type != RegistryType.DISABILITY_REGISTRY.value:
            msg = (
                f"Data source '{data_source_code}' is not a Disability Registry "
                f"(type: {self.data_source.registry_type})"
            )
            raise ValidationError(msg)

        # Initialize DCI client
        self.client = DCIClient(self.data_source, env)

    def get_disability_status(self, partner) -> dict | None:
        """Get disability status for a person.

        Args:
            partner: res.partner record

        Returns:
            dict: Disability status data if found, None otherwise
            Example: {
                'has_disability': True,
                'disability_types': ['Vision', 'Mobility'],
                'functional_scores': {
                    'Vision': 3,
                    'Hearing': 1,
                    'Mobility': 4,
                    'Cognition': 1,
                    'SelfCare': 2,
                    'Communication': 1
                },
                'assessment_date': '2024-11-15',
                'source_registry': 'National DR',
            }

        Raises:
            UserError: If request fails
            ValidationError: If partner is invalid
        """
        if not partner:
            raise ValidationError("Partner is required")

        # Get identifier for querying
        identifier = self._get_partner_identifier(partner)
        if not identifier:
            _logger.warning(
                "No suitable identifier found for partner ID=%s",
                partner.id,
            )
            return None

        identifier_type, identifier_value = identifier

        _logger.info(
            "Querying disability status for partner ID=%s using %s:%s",
            partner.id,
            identifier_type,
            identifier_value,
        )

        try:
            # Search for disability record using DCI client
            response = self.client.search_by_id(
                identifier_type=identifier_type,
                identifier_value=identifier_value,
                record_type="PERSON",
                page=1,
                page_size=1,
            )

            # Parse response
            if not response or "message" not in response:
                _logger.error("Invalid DR search response: %s", response)
                return None

            message = response["message"]

            # Check for search results
            if "search_response" not in message or not message["search_response"]:
                _logger.info(
                    "No disability record found for %s:%s",
                    identifier_type,
                    identifier_value,
                )
                return None

            # Extract first result
            search_response = message["search_response"][0]
            records = unwrap_search_data(search_response.get("data"))
            if not records:
                return None

            record_data = records[0]
            disability_data = self._extract_disability_data(record_data)

            _logger.info(
                "Disability status retrieved for partner ID=%s: PWD=%s",
                partner.id,
                disability_data.get("has_disability", False),
            )
            return disability_data

        except Exception as e:
            _logger.error(
                "Failed to get disability status: %s",
                str(e),
                exc_info=True,
            )
            raise UserError(_("Failed to get disability status: %s") % str(e)) from e

    def get_functional_assessment(self, identifier_type: str, identifier_value: str) -> dict | None:
        """Get functional assessment scores for a person.

        Args:
            identifier_type: Type of identifier (UIN, DRN, etc.)
            identifier_value: The identifier value

        Returns:
            dict: Functional assessment scores if found, None otherwise
            Example: {
                'Vision': 3,
                'Hearing': 1,
                'Mobility': 4,
                'Cognition': 1,
                'SelfCare': 2,
                'Communication': 1,
                'assessment_date': '2024-11-15',
            }

        Raises:
            UserError: If request fails
            ValidationError: If parameters are invalid
        """
        if not identifier_type or not identifier_value:
            raise ValidationError("identifier_type and identifier_value are required")

        _logger.info(
            "Retrieving functional assessment for %s:%s",
            identifier_type,
            identifier_value,
        )

        try:
            # Search for disability record
            response = self.client.search_by_id(
                identifier_type=identifier_type,
                identifier_value=identifier_value,
                record_type="PERSON",
                page=1,
                page_size=1,
            )

            # Parse response
            if not response or "message" not in response:
                _logger.error("Invalid DR search response: %s", response)
                return None

            message = response["message"]

            # Check for search results
            if "search_response" not in message or not message["search_response"]:
                _logger.info(
                    "No functional assessment found for %s:%s",
                    identifier_type,
                    identifier_value,
                )
                return None

            # Extract first result
            search_response = message["search_response"][0]
            records = unwrap_search_data(search_response.get("data"))
            if not records:
                return None

            record_data = records[0]
            scores = self._extract_functional_scores(record_data)

            _logger.info(
                "Functional assessment retrieved for %s:%s",
                identifier_type,
                identifier_value,
            )
            return scores

        except Exception as e:
            _logger.error(
                "Failed to get functional assessment: %s",
                str(e),
                exc_info=True,
            )
            raise UserError(_("Failed to get functional assessment: %s") % str(e)) from e

    def is_pwd(self, partner) -> bool:
        """Quick check if person is registered as PWD (Person with Disability).

        Args:
            partner: res.partner record

        Returns:
            bool: True if person is PWD, False otherwise

        Raises:
            UserError: If request fails
            ValidationError: If partner is invalid
        """
        if not partner:
            raise ValidationError("Partner is required")

        # Try to get from cached status first
        disability_status = self.env["spp.dci.disability.status"].search([("partner_id", "=", partner.id)], limit=1)

        if disability_status and disability_status.state == "synced":
            _logger.debug(
                "Using cached disability status for partner %s: PWD=%s",
                partner.id,
                disability_status.has_disability,
            )
            return disability_status.has_disability

        # Otherwise, fetch from DR
        disability_data = self.get_disability_status(partner)
        if disability_data:
            return disability_data.get("has_disability", False)

        return False

    def sync_disability_data(self, partner) -> bool:
        """Sync disability data for partner and update/create disability_status record.

        Args:
            partner: res.partner record

        Returns:
            bool: True if sync succeeded, False if failed

        Raises:
            UserError: If sync fails
            ValidationError: If partner is invalid
        """
        if not partner:
            raise ValidationError("Partner is required")

        _logger.info(
            "Syncing disability data for partner ID=%s",
            partner.id,
        )

        try:
            # Get disability data from DR
            disability_data = self.get_disability_status(partner)

            # Find or create disability_status record
            disability_status = self.env["spp.dci.disability.status"].search([("partner_id", "=", partner.id)], limit=1)

            # Prepare values
            vals = {
                "partner_id": partner.id,
                "last_sync_date": fields.Datetime.now(),
                "synced_by": self.env.user.id,
            }

            if disability_data:
                # Update with DR data
                vals.update(
                    {
                        "has_disability": disability_data.get("has_disability", False),
                        "disability_types": json.dumps(disability_data.get("disability_types", [])),
                        "functional_scores": json.dumps(disability_data.get("functional_scores", {})),
                        "assessment_date": disability_data.get("assessment_date"),
                        "source_registry": disability_data.get("source_registry"),
                        "raw_data": json.dumps(disability_data.get("raw_data", {})),
                        "state": "synced",
                        "error_message": False,
                    }
                )

                _logger.info(
                    "Disability data synced for partner ID=%s: PWD=%s, types=%s",
                    partner.id,
                    disability_data.get("has_disability"),
                    disability_data.get("disability_types"),
                )
            else:
                # No data found - mark as such
                vals.update(
                    {
                        "has_disability": False,
                        "disability_types": json.dumps([]),
                        "functional_scores": json.dumps({}),
                        "state": "synced",
                        "error_message": False,
                    }
                )

                _logger.info(
                    "No disability data found for partner ID=%s - marked as non-PWD",
                    partner.id,
                )

            # Update or create record
            if disability_status:
                disability_status.write(vals)
            else:
                self.env["spp.dci.disability.status"].create(vals)

            return True

        except Exception as e:
            _logger.error(
                "Failed to sync disability data for partner ID=%s: %s",
                partner.id,
                str(e),
                exc_info=True,
            )
            raise UserError(_("Failed to sync disability data: %s") % str(e)) from e

    def _get_partner_identifier(self, partner):
        """Get suitable identifier for querying DR.

        Tries to find identifier in this priority:
        1. UIN (Universal Identification Number)
        2. DRN (Disability Registration Number)
        3. National ID

        Args:
            partner: res.partner record

        Returns:
            tuple: (identifier_type, identifier_value) or None if not found
        """
        # Search in registry IDs
        reg_ids = self.env["spp.registry.id"].search([("partner_id", "=", partner.id)])

        # Priority order for identifier types
        priority_types = ["UIN", "DRN", "NATIONAL_ID", "NID"]

        for id_type in priority_types:
            for reg_id in reg_ids:
                if reg_id.id_type_id.code == id_type and reg_id.value:
                    return (reg_id.id_type_id.code, reg_id.value)

        # If no priority type found, use first available
        if reg_ids:
            first_id = reg_ids[0]
            return (first_id.id_type_id.code, first_id.value)

        return None

    def _extract_disability_data(self, record_data: dict) -> dict:
        """Extract disability information from a DCI v1.0.0 record.

        Delegates to the stateless module-level helper in dr_parsing.

        Args:
            record_data: A single record dict from reg_records

        Returns:
            dict: Extracted disability data
        """
        return extract_disability_data(record_data)

    def _extract_functional_scores(self, record_data: dict) -> dict:
        """Return functional assessment scores from a DCI v1.0.0 record.

        Delegates to the stateless module-level helper in dr_parsing.
        The DCI v1.0.0 spec has no numeric functional scores, so this always
        returns ``{}``.

        Args:
            record_data: A single record dict from reg_records

        Returns:
            dict: Always ``{}``
        """
        return extract_functional_scores(record_data)
