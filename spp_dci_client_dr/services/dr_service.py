# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DR Service for connecting to Disability Registry systems."""

import json
import logging

from odoo import fields
from odoo.exceptions import UserError, ValidationError

from odoo.addons.spp_dci_client.services import DCIClient

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

        # Validate it's a DR registry
        if self.data_source.registry_type != "DR":
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
            if "data" not in search_response or not search_response["data"]:
                return None

            record_data = (
                search_response["data"][0] if isinstance(search_response["data"], list) else search_response["data"]
            )

            # Extract disability information
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
            raise UserError(f"Failed to get disability status: {str(e)}") from e

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
            if "data" not in search_response or not search_response["data"]:
                return None

            record_data = (
                search_response["data"][0] if isinstance(search_response["data"], list) else search_response["data"]
            )

            # Extract functional scores
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
            raise UserError(f"Failed to get functional assessment: {str(e)}") from e

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
            raise UserError(f"Failed to sync disability data: {str(e)}") from e

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
        """Extract disability information from DCI record data.

        Args:
            record_data: DCI record data from search response

        Returns:
            dict: Extracted disability data
        """
        disability_data = {
            "has_disability": False,
            "disability_types": [],
            "functional_scores": {},
            "raw_data": record_data,
        }

        # Check for disability flag
        if "has_disability" in record_data:
            disability_data["has_disability"] = bool(record_data["has_disability"])
        elif "is_pwd" in record_data:
            disability_data["has_disability"] = bool(record_data["is_pwd"])

        # Extract disability types
        if "disability_types" in record_data:
            types_data = record_data["disability_types"]
            if isinstance(types_data, list):
                disability_data["disability_types"] = types_data
            elif isinstance(types_data, str):
                # Handle comma-separated string
                disability_data["disability_types"] = [t.strip() for t in types_data.split(",") if t.strip()]

        # Extract functional scores
        disability_data["functional_scores"] = self._extract_functional_scores(record_data)

        # Extract assessment date
        if "assessment_date" in record_data:
            disability_data["assessment_date"] = record_data["assessment_date"]
        elif "disability_assessment_date" in record_data:
            disability_data["assessment_date"] = record_data["disability_assessment_date"]

        # Extract source registry
        if "source_registry" in record_data:
            disability_data["source_registry"] = record_data["source_registry"]
        elif "registry_name" in record_data:
            disability_data["source_registry"] = record_data["registry_name"]

        return disability_data

    def _extract_functional_scores(self, record_data: dict) -> dict:
        """Extract functional assessment scores from record data.

        Args:
            record_data: DCI record data

        Returns:
            dict: Functional scores by domain
            Example: {'Vision': 3, 'Hearing': 1, 'Mobility': 4, ...}
        """
        scores = {}

        # Try to extract from functional_scores field
        if "functional_scores" in record_data:
            scores_data = record_data["functional_scores"]
            if isinstance(scores_data, dict):
                scores = scores_data
            elif isinstance(scores_data, str):
                # Try to parse JSON string
                try:
                    scores = json.loads(scores_data)
                except json.JSONDecodeError:
                    _logger.warning("Failed to parse functional_scores JSON")

        # Try to extract individual domain scores
        functional_domains = [
            "Vision",
            "Hearing",
            "Mobility",
            "Cognition",
            "SelfCare",
            "Communication",
        ]

        for domain in functional_domains:
            # Try various field name formats
            for field_name in [
                f"functional_{domain.lower()}",
                f"{domain.lower()}_score",
                domain.lower(),
                domain,
            ]:
                if field_name in record_data and record_data[field_name]:
                    try:
                        scores[domain] = int(record_data[field_name])
                    except (ValueError, TypeError):
                        _logger.warning(
                            "Invalid functional score for %s: %s",
                            domain,
                            record_data[field_name],
                        )

        return scores
