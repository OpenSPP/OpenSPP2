# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Bundle transaction and batch processing service"""

import logging
import re
from typing import Any

from odoo.api import Environment
from odoo.exceptions import UserError, ValidationError

from ..schemas.bundle import Bundle, BundleEntry
from ..schemas.group import Group
from ..schemas.individual import Individual
from .group_service import GroupService
from .individual_service import IndividualService

_logger = logging.getLogger(__name__)


class BundleProcessor:
    """Process transaction and batch bundles atomically"""

    def __init__(self, env: Environment):
        self.env = env
        self.individual_service = IndividualService(env)
        self.group_service = GroupService(env)

    def process_transaction(self, bundle: Bundle, api_client, source: str) -> dict[str, Any]:
        """
        Process a transaction bundle atomically.

        All operations succeed or all fail (rollback).
        Uses database savepoint for atomicity.

        Args:
            bundle: Bundle with type="transaction"
            api_client: Authenticated API client record
            source: Source system URI for tracking

        Returns:
            Bundle with type="transaction-response"

        Raises:
            Exception: If any entry fails (triggers rollback)
        """
        if bundle.type != "transaction":
            raise ValidationError("Bundle type must be 'transaction'")

        placeholder_map = {}  # urn:uuid:xxx -> actual identifier string
        results = []

        # Use savepoint for atomic transaction
        with self.env.cr.savepoint():
            _logger.info(
                "Processing transaction bundle with %s entries",
                len(bundle.entry or []),
            )

            for idx, entry in enumerate(bundle.entry or []):
                try:
                    _logger.debug("Processing transaction entry %s", idx + 1)

                    # Resolve placeholders in this entry
                    resolved_entry = self._resolve_placeholders(entry, placeholder_map)

                    # Process the entry
                    result = self._process_entry(resolved_entry, api_client, source)

                    # Map placeholder to actual identifier
                    if entry.full_url and entry.full_url.startswith("urn:uuid:"):
                        actual_identifier = self._extract_identifier_from_result(result)
                        if actual_identifier:
                            placeholder_map[entry.full_url] = actual_identifier
                            _logger.debug(f"Mapped {entry.full_url} -> {actual_identifier}")

                    results.append(
                        {
                            "fullUrl": entry.full_url,
                            "response": {
                                "status": result["status"],
                                "location": result.get("location"),
                                "etag": result.get("etag"),
                            },
                            "resource": result.get("resource"),
                        }
                    )

                except Exception as e:
                    # Transaction failed - savepoint will rollback automatically
                    _logger.error(f"Transaction entry {idx + 1} failed: {str(e)}", exc_info=True)
                    raise ValidationError(
                        f"Transaction failed at entry {idx + 1} ({entry.full_url or 'unknown'}): {str(e)}"
                    ) from e

        _logger.info(f"Transaction bundle completed successfully with {len(results)} entries")

        return {
            "resourceType": "Bundle",
            "type": "transaction-response",
            "entry": results,
        }

    def process_batch(self, bundle: Bundle, api_client, source: str) -> dict[str, Any]:
        """
        Process a batch bundle independently.

        Each operation is processed independently.
        Partial success allowed - failed entries return error responses.

        Args:
            bundle: Bundle with type="batch"
            api_client: Authenticated API client record
            source: Source system URI for tracking

        Returns:
            Bundle with type="batch-response"
        """
        if bundle.type != "batch":
            raise ValidationError("Bundle type must be 'batch'")

        placeholder_map = {}  # urn:uuid:xxx -> actual identifier string
        results = []

        _logger.info("Processing batch bundle with %s entries", len(bundle.entry or []))

        for idx, entry in enumerate(bundle.entry or []):
            try:
                _logger.debug("Processing batch entry %s", idx + 1)

                # Resolve placeholders in this entry
                resolved_entry = self._resolve_placeholders(entry, placeholder_map)

                # Process the entry
                result = self._process_entry(resolved_entry, api_client, source)

                # Map placeholder to actual identifier
                if entry.full_url and entry.full_url.startswith("urn:uuid:"):
                    actual_identifier = self._extract_identifier_from_result(result)
                    if actual_identifier:
                        placeholder_map[entry.full_url] = actual_identifier
                        _logger.debug(f"Mapped {entry.full_url} -> {actual_identifier}")

                results.append(
                    {
                        "fullUrl": entry.full_url,
                        "response": {
                            "status": result["status"],
                            "location": result.get("location"),
                            "etag": result.get("etag"),
                        },
                        "resource": result.get("resource"),
                    }
                )

            except Exception as e:
                # For batch, continue processing - just record the error
                _logger.warning(f"Batch entry {idx + 1} failed: {str(e)}", exc_info=True)

                # Create error response
                error_response = self._create_error_response(e)

                results.append(
                    {
                        "fullUrl": entry.full_url,
                        "response": {
                            "status": error_response["status"],
                        },
                        "resource": error_response["outcome"],
                    }
                )

        succeeded_count = sum(
            1 for r in results if "OperationOutcome" not in str(r.get("resource", {}).get("resourceType", ""))
        )
        _logger.info(
            "Batch bundle completed with %d entries (%d succeeded)",
            len(results),
            succeeded_count,
        )

        return {
            "resourceType": "Bundle",
            "type": "batch-response",
            "entry": results,
        }

    def _resolve_placeholders(self, entry: BundleEntry, placeholder_map: dict[str, str]) -> BundleEntry:
        """
        Resolve urn:uuid:* placeholders in entry.

        Replaces placeholder references with actual identifiers from placeholder_map.

        Args:
            entry: Bundle entry with potential placeholders
            placeholder_map: Map of urn:uuid:xxx -> actual identifier

        Returns:
            Entry with placeholders resolved
        """
        if not entry.resource:
            return entry

        # Create a copy of the resource dict to modify
        resource = entry.resource.copy()

        # Recursively resolve placeholders in the resource
        resolved_resource = self._resolve_in_dict(resource, placeholder_map)

        # Return new entry with resolved resource
        return BundleEntry(
            full_url=entry.full_url,
            request=entry.request,
            response=entry.response,
            resource=resolved_resource,
            search=entry.search,
        )

    def _resolve_in_dict(self, data: dict | list | str, placeholder_map: dict[str, str]) -> Any:
        """
        Recursively resolve placeholders in a data structure.

        Args:
            data: Dictionary, list, or string that may contain placeholders
            placeholder_map: Map of urn:uuid:xxx -> actual identifier

        Returns:
            Data with placeholders resolved
        """
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                result[key] = self._resolve_in_dict(value, placeholder_map)
            return result

        elif isinstance(data, list):
            return [self._resolve_in_dict(item, placeholder_map) for item in data]

        elif isinstance(data, str):
            # Check if this is a reference that needs resolution
            if data.startswith("urn:uuid:"):
                # This is a placeholder UUID
                if data in placeholder_map:
                    return placeholder_map[data]
                else:
                    _logger.warning(f"Placeholder {data} not found in map - may be forward reference")
                    return data
            else:
                # Check if this is a reference string with embedded placeholder
                # e.g., "Individual/urn:uuid:individual-1" or just "urn:uuid:individual-1"
                for placeholder, actual in placeholder_map.items():
                    if placeholder in data:
                        data = data.replace(placeholder, actual)
                return data

        else:
            # Return as-is for other types
            return data

    def _process_entry(self, entry: BundleEntry, api_client, source: str) -> dict[str, Any]:
        """
        Process a single bundle entry.

        Args:
            entry: Bundle entry with request and resource
            api_client: Authenticated API client
            source: Source system URI

        Returns:
            Dict with status, location, etag, and optionally resource

        Raises:
            Exception: If operation fails
        """
        if not entry.request:
            raise ValidationError("Entry missing request")

        method = entry.request.method.upper()
        url = entry.request.url
        resource_data = entry.resource

        _logger.debug("Processing %s %s", method, url)

        # Determine resource type and operation
        if method == "POST":
            return self._handle_create(url, resource_data, api_client, source)
        elif method == "PUT":
            return self._handle_update(url, resource_data, api_client, source)
        elif method == "GET":
            return self._handle_read(url, api_client)
        elif method == "DELETE":
            return self._handle_delete(url, api_client, source)
        else:
            raise ValidationError(f"Unsupported HTTP method: {method}")

    def _handle_create(self, url: str, resource_data: dict, api_client, source: str) -> dict[str, Any]:
        """Handle POST (create) operation"""
        resource_type = resource_data.get("type")

        if resource_type == "Individual":
            # Check client has create scope
            if not api_client.has_scope("individual", "create"):
                raise ValidationError("Client does not have permission to create individuals")

            # Parse schema
            individual = Individual(**resource_data)

            # Create individual
            partner = self.individual_service.create(individual, source, api_authorized=True)

            # Convert to API schema
            result = self.individual_service.to_api_schema(partner)

            # Build location
            primary_id = result["identifier"][0]
            location = f"/api/v2/spp/Individual/{primary_id['system']}|{primary_id['value']}"

            return {
                "status": "201 Created",
                "location": location,
                "etag": str(partner.write_date.timestamp() if partner.write_date else 1),
                "resource": result,
            }

        elif resource_type == "Group":
            # Check client has create scope
            if not api_client.has_scope("group", "create"):
                raise ValidationError("Client does not have permission to create groups")

            # Parse schema
            group = Group(**resource_data)

            # Create group
            group_record = self.group_service.create(group, source, api_authorized=True)

            # Convert to API schema
            result = self.group_service.to_api_schema(group_record)

            # Build location
            primary_id = result["identifier"][0]
            location = f"/api/v2/spp/Group/{primary_id['system']}|{primary_id['value']}"

            return {
                "status": "201 Created",
                "location": location,
                "etag": str(group_record.write_date.timestamp() if group_record.write_date else 1),
                "resource": result,
            }

        else:
            raise ValidationError(f"Unsupported resource type: {resource_type}")

    def _handle_update(self, url: str, resource_data: dict, api_client, source: str) -> dict[str, Any]:
        """Handle PUT (update) operation"""
        resource_type = resource_data.get("type")

        # Parse URL to get identifier (format: Individual/system|value or Group/system|value)
        match = re.match(r"^(Individual|Group)/(.+)$", url)
        if not match:
            raise ValidationError(f"Invalid URL format: {url}")

        identifier_str = match.group(2)

        if "|" not in identifier_str:
            raise ValidationError(f"Invalid identifier format in URL: {identifier_str}")

        system, value = identifier_str.split("|", 1)

        if resource_type == "Individual":
            # Check client has update scope
            if not api_client.has_scope("individual", "update"):
                raise ValidationError("Client does not have permission to update individuals")

            # Find individual
            partner = self.individual_service.find_by_identifier(system, value)
            if not partner:
                raise ValidationError(f"Individual not found: {system}|{value}")

            # Parse schema
            individual = Individual(**resource_data)

            # Update individual
            partner = self.individual_service.update(partner, individual, source)

            # Convert to API schema
            result = self.individual_service.to_api_schema(partner)

            return {
                "status": "200 OK",
                "location": f"/api/v2/spp/Individual/{system}|{value}",
                "etag": str(partner.write_date.timestamp() if partner.write_date else 1),
                "resource": result,
            }

        elif resource_type == "Group":
            # Check client has update scope
            if not api_client.has_scope("group", "update"):
                raise ValidationError("Client does not have permission to update groups")

            # Find group
            group_record = self.group_service.find_by_identifier(system, value)
            if not group_record:
                raise ValidationError(f"Group not found: {system}|{value}")

            # Parse schema
            group = Group(**resource_data)

            # Update group
            group_record = self.group_service.update(group_record, group, source)

            # Convert to API schema
            result = self.group_service.to_api_schema(group_record)

            return {
                "status": "200 OK",
                "location": f"/api/v2/spp/Group/{system}|{value}",
                "etag": str(group_record.write_date.timestamp() if group_record.write_date else 1),
                "resource": result,
            }

        else:
            raise ValidationError(f"Unsupported resource type: {resource_type}")

    def _handle_read(self, url: str, api_client) -> dict[str, Any]:
        """Handle GET (read) operation"""
        # Parse URL (format: Individual/system|value or Group/system|value)
        match = re.match(r"^(Individual|Group)/(.+)$", url)
        if not match:
            raise ValidationError(f"Invalid URL format: {url}")

        resource_type = match.group(1)
        identifier_str = match.group(2)

        if "|" not in identifier_str:
            raise ValidationError(f"Invalid identifier format in URL: {identifier_str}")

        system, value = identifier_str.split("|", 1)

        if resource_type == "Individual":
            # Check client has read scope
            if not api_client.has_scope("individual", "read"):
                raise ValidationError("Client does not have permission to read individuals")

            # Find individual
            partner = self.individual_service.find_by_identifier(system, value)
            if not partner:
                raise ValidationError(f"Individual not found: {system}|{value}")

            # Convert to API schema
            result = self.individual_service.to_api_schema(partner)

            return {
                "status": "200 OK",
                "location": f"/api/v2/spp/Individual/{system}|{value}",
                "etag": str(partner.write_date.timestamp() if partner.write_date else 1),
                "resource": result,
            }

        elif resource_type == "Group":
            # Check client has read scope
            if not api_client.has_scope("group", "read"):
                raise ValidationError("Client does not have permission to read groups")

            # Find group
            group_record = self.group_service.find_by_identifier(system, value)
            if not group_record:
                raise ValidationError(f"Group not found: {system}|{value}")

            # Convert to API schema
            result = self.group_service.to_api_schema(group_record)

            return {
                "status": "200 OK",
                "location": f"/api/v2/spp/Group/{system}|{value}",
                "etag": str(group_record.write_date.timestamp() if group_record.write_date else 1),
                "resource": result,
            }

        else:
            raise ValidationError(f"Unsupported resource type: {resource_type}")

    def _handle_delete(self, url: str, api_client, source: str) -> dict[str, Any]:
        """Handle DELETE operation"""
        # Parse URL
        match = re.match(r"^(Individual|Group)/(.+)$", url)
        if not match:
            raise ValidationError(f"Invalid URL format: {url}")

        resource_type = match.group(1)
        identifier_str = match.group(2)

        if "|" not in identifier_str:
            raise ValidationError(f"Invalid identifier format in URL: {identifier_str}")

        system, value = identifier_str.split("|", 1)

        if resource_type == "Individual":
            # Check client has delete scope
            if not api_client.has_scope("individual", "delete"):
                raise ValidationError("Client does not have permission to delete individuals")

            # Find individual
            partner = self.individual_service.find_by_identifier(system, value)
            if not partner:
                raise ValidationError(f"Individual not found: {system}|{value}")

            # Soft delete (set active=False)
            partner.with_context(source_system=source).write({"active": False})

            # Get primary identifier for logging
            primary_id = partner.reg_ids[0] if partner.reg_ids else None
            identifier_str = f"{primary_id.namespace_uri}|{primary_id.value}" if primary_id else "unknown"
            _logger.info("Soft deleted individual %s via API from %s", identifier_str, source)

            return {
                "status": "204 No Content",
            }

        elif resource_type == "Group":
            # Check client has delete scope
            if not api_client.has_scope("group", "delete"):
                raise ValidationError("Client does not have permission to delete groups")

            # Find group
            group_record = self.group_service.find_by_identifier(system, value)
            if not group_record:
                raise ValidationError(f"Group not found: {system}|{value}")

            # Soft delete (set active=False)
            group_record.with_context(source_system=source).write({"active": False})

            # Get primary identifier for logging
            primary_id = group_record.reg_ids[0] if group_record.reg_ids else None
            identifier_str = f"{primary_id.namespace_uri}|{primary_id.value}" if primary_id else "unknown"
            _logger.info("Soft deleted group %s via API from %s", identifier_str, source)

            return {
                "status": "204 No Content",
            }

        else:
            raise ValidationError(f"Unsupported resource type: {resource_type}")

    def _extract_identifier_from_result(self, result: dict[str, Any]) -> str | None:
        """
        Extract the identifier from a result for placeholder mapping.

        Args:
            result: Result dict with location and/or resource

        Returns:
            Identifier string (e.g., "Individual/system|value") or None
        """
        # Try to extract from location header
        if result.get("location"):
            # Location is like "/api/v2/spp/Individual/system|value"
            # Extract the "Individual/system|value" part
            location = result["location"]
            match = re.search(r"/(Individual|Group)/(.+)$", location)
            if match:
                resource_type = match.group(1)
                identifier = match.group(2)
                return f"{resource_type}/{identifier}"

        # Try to extract from resource
        if result.get("resource") and result["resource"].get("identifier"):
            resource_type = result["resource"].get("type")
            primary_id = result["resource"]["identifier"][0]
            return f"{resource_type}/{primary_id['system']}|{primary_id['value']}"

        return None

    def _create_error_response(self, exception: Exception) -> dict[str, Any]:
        """
        Create error response from exception.

        Args:
            exception: Exception that occurred

        Returns:
            Dict with status and OperationOutcome
        """
        # Determine status code based on exception type
        if isinstance(exception, ValidationError):
            status_code = "422 Unprocessable Entity"
            severity = "error"
            code = "invalid"
        elif isinstance(exception, UserError):
            status_code = "400 Bad Request"
            severity = "error"
            code = "invalid"
        else:
            status_code = "500 Internal Server Error"
            severity = "fatal"
            code = "exception"

        return {
            "status": status_code,
            "outcome": {
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": severity,
                        "code": code,
                        "diagnostics": str(exception),
                    }
                ],
            },
        }
