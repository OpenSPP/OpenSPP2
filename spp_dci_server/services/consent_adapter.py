# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Consent Adapter - Wraps spp_api_v2 ConsentService for DCI protocol."""

import logging
from typing import Any

from odoo.api import Environment

_logger = logging.getLogger(__name__)


class DCIConsentAdapter:
    """Adapts spp_api_v2 ConsentService for DCI protocol.

    This adapter bridges the DCI search service with the existing consent
    infrastructure from spp_api_v2. It uses the sender registry's inherited
    fields (organization_type, legal_basis) for consent checking.

    Key features:
    - Legal basis bypass for government interoperability
    - Category-based consent matching by organization_type
    - Field-level consent filtering
    - Access logging for GDPR accountability
    """

    # Legal bases that don't require individual consent (GDPR Article 6)
    NON_CONSENT_LEGAL_BASES = (
        "legal_obligation",  # Required by law
        "vital_interest",  # Life-threatening emergencies
        "public_interest",  # Public interest tasks
        "public_task",  # Official authority
        "contract",  # Contractual necessity
        "legitimate_interest",  # Legitimate business interest
    )

    def __init__(self, env: Environment, sender_registry=None):
        """Initialize adapter with Odoo environment and optional sender.

        Args:
            env: Odoo environment
            sender_registry: spp.dci.sender.registry record (optional)
        """
        self.env = env
        self.sender = sender_registry
        self._consent_service = None

    @property
    def consent_service(self):
        """Lazy-load ConsentService from spp_api_v2."""
        if self._consent_service is None:
            try:
                from odoo.addons.spp_api_v2.services.consent_service import (
                    ConsentService,
                )

                self._consent_service = ConsentService(self.env)
            except ImportError:
                _logger.warning("spp_api_v2 ConsentService not available")
                self._consent_service = None
        return self._consent_service

    def set_sender(self, sender_registry):
        """Set the DCI sender for consent checks.

        Args:
            sender_registry: spp.dci.sender.registry record
        """
        self.sender = sender_registry

    def has_legal_basis_bypass(self) -> bool:
        """Check if sender has legal basis that bypasses individual consent.

        Returns:
            True if sender can access data without individual consent
        """
        if not self.sender:
            return False

        return self.sender.legal_basis in self.NON_CONSENT_LEGAL_BASES

    def can_access_registrant(self, registrant_id: int, resource_type: str = "individual") -> bool:
        """Check if this DCI sender can access the registrant's data.

        Args:
            registrant_id: ID of registrant whose data is being accessed
            resource_type: Type of resource (individual, group)

        Returns:
            True if access is allowed, False otherwise
        """
        if not self.sender:
            _logger.warning("No DCI sender configured for consent check")
            return False

        # Legal basis bypass for government agencies
        if self.has_legal_basis_bypass():
            _logger.debug(
                "DCI sender %s has legal basis '%s' - bypassing consent check",
                self.sender.sender_id,
                self.sender.legal_basis,
            )
            return True

        # Check if sender requires consent
        if not self.sender.is_require_consent:
            return True

        # Use spp.consent check_api_consent (sender inherits from spp.api.client)
        consent = (
            self.env["spp.consent"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .check_api_consent(
                registrant_id=registrant_id,
                recipient_id=self.sender.partner_id.id,
                resource_type=resource_type,
                api_client=self.sender,  # Works because sender inherits spp.api.client
            )
        )

        if consent:
            return True

        _logger.debug(
            "No consent found for DCI sender %s to access registrant %s",
            self.sender.sender_id,
            registrant_id,
        )
        return False

    def filter_dci_response(
        self,
        registrant_id: int,
        dci_data: dict[str, Any],
        resource_type: str = "individual",
        log_access: bool = True,
    ) -> dict[str, Any]:
        """Apply consent filtering to DCI response data.

        Args:
            registrant_id: ID of registrant whose data is being accessed
            dci_data: DCI-formatted data dict (Person or Group)
            resource_type: Type of resource (individual, group)
            log_access: Whether to log this access

        Returns:
            Filtered data based on consent, or original data if legal basis applies
        """
        if not self.sender:
            _logger.warning("No DCI sender configured - returning unfiltered data")
            return dci_data

        # Legal basis bypass - return full data with metadata
        if self.has_legal_basis_bypass():
            dci_data["_consent"] = {
                "status": "legal_basis",
                "basis": self.sender.legal_basis,
                "reference": self.sender.legal_basis_reference,
            }
            return dci_data

        # Use ConsentService if available
        if self.consent_service:
            return self.consent_service.filter_response(
                registrant_id=registrant_id,
                api_client=self.sender,
                resource_type=resource_type,
                data=dci_data,
                log_access=log_access,
            )

        # Fallback: Basic consent check without field filtering
        if self.can_access_registrant(registrant_id, resource_type):
            dci_data["_consent"] = {"status": "active"}
            return dci_data

        # No consent - return minimal data
        return {
            "identifier": dci_data.get("identifier", []),
            "_consent": {
                "status": "no_consent",
                "message": "No active consent for this data access",
            },
        }

    def build_consented_domain(self, base_domain: list) -> list:
        """Build Odoo domain that filters to registrants with valid consent.

        This is more efficient than post-filtering when doing bulk searches.

        Args:
            base_domain: Starting Odoo domain

        Returns:
            Domain with consent filter added
        """
        if not self.sender:
            return base_domain

        # Legal basis bypass - no additional filtering needed
        if self.has_legal_basis_bypass():
            return base_domain

        # Check if consent model exists
        if "spp.consent" not in self.env:
            return base_domain

        # Build consent domain
        # This is a simplified approach - for full accuracy, consent should be
        # checked per-record after search results are returned
        consent_domain = list(base_domain)

        # Option 1: Simple - require active consent
        # This may be too restrictive as it doesn't account for category-based consent
        # consent_domain.append(("consent_ids.state", "=", "active"))

        # Option 2: Filter by recipient (specific consent)
        # consent_domain.append(("consent_ids.recipient_id", "=", self.sender.partner_id.id))

        # Option 3: Filter by organization type (category consent)
        # This requires checking allowed_recipient_types which is more complex

        # For now, we use the simple approach and recommend post-filtering
        # for accurate consent checking
        if self.sender.is_require_consent:
            consent_domain.append(("consent_ids.status", "=", "active"))

        return consent_domain

    def log_dci_access(
        self,
        registrant_id: int,
        resource_type: str,
        action: str = "read",
        fields_accessed: list | None = None,
    ):
        """Log DCI data access for GDPR accountability.

        Args:
            registrant_id: ID of registrant whose data was accessed
            resource_type: Type of resource (individual, group)
            action: Action performed (read, search)
            fields_accessed: List of fields that were accessed
        """
        if not self.sender:
            return

        # Find consent for logging
        consent = (
            self.env["spp.consent"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .check_api_consent(
                registrant_id=registrant_id,
                recipient_id=self.sender.partner_id.id,
                resource_type=resource_type,
                api_client=self.sender,
            )
        )

        if consent and "spp.consent.access.log" in self.env:
            try:
                self.env["spp.consent.access.log"].sudo().log_access(  # nosemgrep: odoo-sudo-without-context
                    consent=consent,
                    api_client=self.sender,
                    resource_type=resource_type,
                    resource_identifier=str(registrant_id),
                    action=action,
                    fields_accessed=fields_accessed,
                )
            except Exception:
                _logger.exception("Failed to log DCI consent access")
