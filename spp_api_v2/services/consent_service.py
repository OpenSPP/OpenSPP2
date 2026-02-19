# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for consent-based data filtering"""

import logging
import uuid
from typing import Any

from odoo.api import Environment

_logger = logging.getLogger(__name__)


class ConsentService:
    """Service for applying consent-based filtering to API responses"""

    def __init__(self, env: Environment):
        self.env = env
        self._request_id = None
        self._ip_address = None
        self._user_agent = None

    def set_request_context(
        self,
        request_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ):
        """Set request context for access logging."""
        self._request_id = request_id or str(uuid.uuid4())
        self._ip_address = ip_address
        self._user_agent = user_agent

    def _check_consent_fast(self, registrant_id: int, api_client) -> bool:
        """
        Fast consent check using consent_summary cache.

        Uses the cached consent_summary JSON on res.partner for O(1) lookups
        instead of querying the consent tables directly.

        SECURITY NOTES:
        - Uses sudo() because API handlers run as Public user (uid=3)
        - Only accesses consent_summary (aggregated consent metadata, no PII)
        - Does NOT return any registrant data - only True/False consent status
        - Falls back to full consent query in check_access() if needed

        Args:
            registrant_id: ID of registrant whose data is being accessed
            api_client: spp.api.client record

        Returns:
            True if consent exists based on cached summary, False otherwise
        """
        # SECURITY: Use sudo() since API handlers run as Public user (uid=3)
        # which doesn't have res.partner read access by default.
        # Safe because we only read consent_summary (no PII exposed).
        # nosemgrep: odoo-sudo-without-context, odoo-sudo-on-sensitive-models
        registrant = self.env["res.partner"].sudo().browse(registrant_id)

        # Get consent summary - returns {} if not set or False
        summary = registrant.consent_summary or {}

        if not summary:
            return False

        # Category-based consent check (O(1))
        # organization_type is the computed field that returns the code
        org_type_code = api_client.organization_type
        if org_type_code and org_type_code in summary.get("organization_types", []):
            return True

        # Specific recipient check (O(1))
        if api_client.partner_id.id in summary.get("specific_recipients", []):
            return True

        return False

    def filter_response(
        self,
        registrant_id: int,
        api_client,
        resource_type: str,
        data: dict[str, Any],
        resource_identifier: str | None = None,
        log_access: bool = True,
    ) -> dict[str, Any]:
        """
        Filter response data based on consent.

        CRITICAL: Fail closed - if no consent, return minimal data.

        Args:
            registrant_id: ID of registrant whose data is being accessed
            api_client: spp.api.client record
            resource_type: Type of resource (individual, group, etc.)
            data: The full response data dict
            resource_identifier: External identifier for access logging
            log_access: Whether to log this access (default True)

        Returns:
            Filtered data based on consent, or minimal data if no consent
        """
        # Check if client has legal basis that doesn't require individual consent
        # Per GDPR Article 6, these bases allow processing without consent:
        # - legal_obligation: Required by law (e.g., interagency data sharing mandates)
        # - vital_interest: Life-threatening emergencies
        # - public_interest: Public interest tasks (e.g., social protection programs)
        # - public_task: Official authority (e.g., government agencies)
        # - contract: Contractual necessity (still needs a contract, not individual consent)
        # - legitimate_interest: Legitimate business interest (requires balancing test)
        non_consent_bases = (
            "legal_obligation",
            "vital_interest",
            "public_interest",
            "public_task",
            "contract",
            "legitimate_interest",
        )
        if api_client.legal_basis in non_consent_bases:
            # Still apply client scope filtering for field-level access control
            filtered = self._apply_client_scope_filter(api_client, resource_type, data)
            return filtered

        # Find active consent using API-specific check
        # CRITICAL: Must pass api_client for category-based consent matching
        # Use sudo() for access since API client user may not have direct consent access
        consent = (
            self.env["spp.consent"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .check_api_consent(
                registrant_id,
                api_client.partner_id.id,
                resource_type,
                api_client,  # Required for category-based consent (e.g., "all NGOs")
            )
        )

        if not consent:
            # Check if there's any consent (without resource_type filter) to distinguish
            # between "no consent" and "scope mismatch"
            org_type_code = getattr(api_client, "organization_type", None) if api_client else None
            base_consent = (
                self.env["spp.consent"]  # nosemgrep: odoo-sudo-without-context
                .sudo()
                .check_consent(
                    registrant_id=registrant_id,
                    recipient_id=api_client.partner_id.id,
                    recipient_org_type=org_type_code,
                )
            )

            # If base consent exists but check_api_consent returned empty, it's a scope mismatch
            if base_consent:
                # Check if base consent has any API scopes
                if base_consent.api_scope_ids:
                    return {
                        "identifier": data.get("identifier", []),
                        "_consent": {
                            "status": "scope_mismatch",
                            "message": f"Consent does not cover {resource_type} data",
                        },
                    }

            # Return minimal identifier-only response (only include non-None identifier)
            identifier = data.get("identifier", [])
            # Filter out None values from identifier list items
            if identifier:
                # Clean identifier list - remove None values from dict items
                clean_identifier = []
                for ident in identifier:
                    if ident and isinstance(ident, dict):
                        # Remove None values from identifier dict
                        clean_ident = {k: v for k, v in ident.items() if v is not None}
                        if clean_ident:  # Only add if not empty after filtering
                            clean_identifier.append(clean_ident)
                    elif ident:  # If it's not a dict, just add it if not None
                        clean_identifier.append(ident)

                # Return ONLY type and identifier - no other fields
                return {
                    "type": data.get("type"),
                    "identifier": clean_identifier if clean_identifier else identifier,
                    "_consent": {
                        "status": "no_consent",
                        "message": "No active consent for this data access",
                    },
                }
            else:
                return {
                    "type": data.get("type"),
                    "_consent": {
                        "status": "no_consent",
                        "message": "No active consent for this data access",
                    },
                }

        # Find matching scope
        scope = consent.api_scope_ids.filtered(lambda s: s.resource_type in (resource_type, "all"))

        if not scope:
            # Return minimal response for scope mismatch (only type and identifier)
            identifier = data.get("identifier", [])
            # Clean identifier - remove None values
            clean_identifier = []
            for ident in identifier:
                if ident and isinstance(ident, dict):
                    clean_ident = {k: v for k, v in ident.items() if v is not None}
                    if clean_ident:
                        clean_identifier.append(clean_ident)
                elif ident:
                    clean_identifier.append(ident)
            return {
                "type": data.get("type"),
                "identifier": clean_identifier if clean_identifier else identifier,
                "_consent": {
                    "status": "scope_mismatch",
                    "message": f"Consent does not cover {resource_type} data",
                },
            }

        # Apply field filtering based on consent scope
        filtered = self._filter_fields(data, scope[0], api_client)

        # Log the access
        if log_access and consent:
            self._log_access(
                consent=consent,
                api_client=api_client,
                resource_type=resource_type,
                resource_identifier=resource_identifier or data.get("id", "unknown"),
                action="read",
                fields_accessed=list(filtered.keys()),
                extensions_accessed=list(filtered.get("extension", {}).keys()) if "extension" in filtered else None,
                purpose=scope[0].purpose if scope else None,
            )

        return filtered

    def _get_audit_service(self, api_client):
        """Get an ApiAuditService instance with current request context."""
        from .api_audit_service import ApiAuditService

        return ApiAuditService(
            self.env,
            api_client,
            request_id=self._request_id,
            ip_address=self._ip_address,
            user_agent=self._user_agent,
        )

    def _log_access(
        self,
        consent,
        api_client,
        resource_type: str,
        resource_identifier: str,
        action: str,
        fields_accessed: list | None = None,
        extensions_accessed: list | None = None,
        search_parameters: dict | None = None,
        result_count: int | None = None,
        purpose: str | None = None,
    ):
        """Log a data access event using ApiAuditService."""
        audit_service = self._get_audit_service(api_client)

        if action == "search":
            audit_service.log_search(
                resource_type=resource_type,
                search_parameters=search_parameters or {},
                result_count=result_count or 0,
                consent=consent,
                purpose=purpose,
            )
        else:
            audit_service.log_read(
                resource_type=resource_type,
                resource_identifier=resource_identifier,
                consent=consent,
                purpose=purpose,
                fields_returned=fields_accessed,
                extensions_returned=extensions_accessed,
            )

    def log_search_access(
        self,
        consent,
        api_client,
        resource_type: str,
        search_parameters: dict,
        result_count: int,
        purpose: str | None = None,
    ):
        """
        Log a search/list operation.

        Called by routers after a search to log the access.
        """
        audit_service = self._get_audit_service(api_client)
        audit_service.log_search(
            resource_type=resource_type,
            search_parameters=search_parameters,
            result_count=result_count,
            consent=consent,
            purpose=purpose,
        )

    def _filter_fields(self, data: dict, consent_scope, api_client) -> dict[str, Any]:
        """
        Filter fields based on consent scope and client scope.

        Args:
            data: Full response data
            consent_scope: spp.consent.scope record
            api_client: spp.api.client record

        Returns:
            Filtered data dict
        """
        # Get allowed fields from consent
        consent_allowed = consent_scope.get_allowed_fields()

        # Get allowed fields from client scope
        # Convert PascalCase type to snake_case resource name (e.g., "ProgramMembership" -> "program_membership")
        import re

        resource_type = data.get("type", "")
        resource_type_snake = re.sub(r"(?<!^)(?=[A-Z])", "_", resource_type).lower()
        client_allowed = api_client.get_allowed_fields(resource_type_snake)

        # Determine final allowed fields
        if consent_allowed is None and client_allowed is None:
            # Both allow all fields
            allowed = set(data.keys())
        elif consent_allowed is None:
            # Consent allows all, client restricts
            allowed = client_allowed
        elif client_allowed is None:
            # Client allows all, consent restricts
            allowed = consent_allowed
        else:
            # Both restrict - intersection
            allowed = consent_allowed & client_allowed

        # Always include identifier and type
        allowed.add("identifier")
        allowed.add("type")

        # Filter data - only include allowed fields, and filter out None values (except type and identifier)
        filtered = {}
        for k, v in data.items():
            if k in allowed:
                # Always include type and identifier, even if None
                if k in ("type", "identifier"):
                    filtered[k] = v
                # For other fields, only include if not None
                elif v is not None:
                    filtered[k] = v

        # Handle extensions
        if "extension" in data:
            allowed_extensions = consent_scope.get_allowed_extensions()

            if allowed_extensions is None:
                # All extensions allowed by consent
                filtered["extension"] = data["extension"]
            elif allowed_extensions:
                # Filter to allowed extensions
                filtered["extension"] = {k: v for k, v in data["extension"].items() if k in allowed_extensions}

        # Add consent metadata to response (use DPV-aligned status)
        # Keep original status in metadata, but use "active" for header
        consent_status = consent_scope.consent_id.status
        filtered["_consent"] = {
            "status": consent_status,  # Keep original status in metadata
            "statusUri": consent_scope.consent_id.status_dpv_uri,
            "scope": consent_scope.resource_type,
            "purpose": consent_scope.purpose,
            "expires": consent_scope.consent_id.expiry.isoformat() if consent_scope.consent_id.expiry else None,
        }

        return filtered

    def _apply_client_scope_filter(self, api_client, resource_type: str, data: dict) -> dict[str, Any]:
        """
        Apply client scope filtering (for clients with legal basis).

        Args:
            api_client: spp.api.client record
            resource_type: Type of resource (snake_case, e.g., "program_membership")
            data: Full response data

        Returns:
            Filtered data based on client scopes
        """
        # resource_type parameter is already in snake_case from the router
        allowed = api_client.get_allowed_fields(resource_type)

        if allowed is None:
            # Client can access all fields - but still filter out None values (except type and identifier)
            filtered = {}
            for key, value in data.items():
                if key in ("type", "identifier"):
                    filtered[key] = value
                elif value is not None:
                    filtered[key] = value
        else:
            # Filter to allowed fields
            allowed.add("identifier")
            allowed.add("type")
            filtered = {
                k: v for k, v in data.items() if k in allowed and (k in ("type", "identifier") or v is not None)
            }

        # Add metadata about legal basis (always add, even when all fields allowed)
        filtered["_consent"] = {
            "status": "legal_basis",
            "basis": api_client.legal_basis,
            "reference": api_client.legal_basis_reference,
        }

        return filtered

    def check_access(self, registrant_id: int, api_client, resource_type: str, action: str) -> bool:
        """
        Check if client has permission to perform action on resource.

        Uses consent_summary cache for O(1) initial check, falling back to
        full consent query only when needed.

        Args:
            registrant_id: ID of registrant
            api_client: spp.api.client record
            resource_type: Type of resource
            action: Action to perform (read, create, update, delete)

        Returns:
            True if access allowed, False otherwise
        """
        # Check client scope
        if not api_client.has_scope(resource_type, action):
            _logger.warning(
                "Client %s does not have %s scope for %s",
                api_client.client_id,
                action,
                resource_type,
            )
            return False

        # For read operations, check consent
        if action in ("read", "search"):
            # Check if client requires consent
            if api_client.is_require_consent:
                # Fast path: Use consent_summary cache for O(1) check
                if self._check_consent_fast(registrant_id, api_client):
                    return True

                # Slow path: Full consent query (for edge cases or when cache is stale)
                # CRITICAL: Must pass api_client for category-based consent matching
                consent = (
                    self.env["spp.consent"]  # nosemgrep: odoo-sudo-without-context
                    .sudo()
                    .check_api_consent(
                        registrant_id,
                        api_client.partner_id.id,
                        resource_type,
                        api_client,  # Required for category-based consent (e.g., "all NGOs")
                    )
                )
                if not consent:
                    # SECURITY: Don't log registrant_id (could expose PII patterns)
                    _logger.warning(
                        "No consent found for client %s to access %s resource",
                        api_client.client_id,
                        resource_type,
                    )
                    return False

        return True
