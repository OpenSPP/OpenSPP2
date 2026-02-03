# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Unified authentication service for API clients.

Provides a common abstraction for both OAuth 2.0 and DCI HTTP Signature
authentication methods, enabling consistent consent and authorization handling.
"""

import logging
from dataclasses import dataclass

_logger = logging.getLogger(__name__)


@dataclass
class AuthenticatedClient:
    """Unified representation of an authenticated API caller.

    This class wraps either an OAuth spp.api.client or a DCI spp.dci.sender.registry
    record, providing a consistent interface for authorization and consent checks.

    Since spp.dci.sender.registry inherits from spp.api.client, both types share
    the same base fields (organization_type, legal_basis, is_require_consent, etc.).

    Attributes:
        record: The underlying Odoo record (spp.api.client or inheriting model)
        auth_type: Authentication method used ('oauth2', 'http_signature', 'none')
    """

    record: "odoo.models.Model"  # spp.api.client or inheriting model
    auth_type: str  # 'oauth2', 'http_signature', 'none'

    @property
    def id(self) -> int:
        """Get record ID."""
        return self.record.id

    @property
    def name(self) -> str:
        """Get client name."""
        return self.record.name

    @property
    def client_id(self) -> str | None:
        """Get OAuth client_id (only for OAuth clients)."""
        return getattr(self.record, "client_id", None)

    @property
    def sender_id(self) -> str | None:
        """Get DCI sender_id (only for DCI clients)."""
        return getattr(self.record, "sender_id", None)

    @property
    def partner_id(self):
        """Get linked organization partner."""
        return self.record.partner_id

    @property
    def organization_type(self) -> str | None:
        """Get organization type for category-based consent matching."""
        return self.record.organization_type

    @property
    def legal_basis(self) -> str | None:
        """Get GDPR legal basis for data processing."""
        return self.record.legal_basis

    @property
    def legal_basis_reference(self) -> str | None:
        """Get reference to authorizing law or MOU."""
        return self.record.legal_basis_reference

    @property
    def require_consent(self) -> bool:
        """Check if explicit individual consent is required."""
        return self.record.is_require_consent

    @property
    def is_oauth(self) -> bool:
        """Check if this is an OAuth client."""
        return self.auth_type == "oauth2"

    @property
    def is_dci(self) -> bool:
        """Check if this is a DCI HTTP Signature client."""
        return self.auth_type == "http_signature"

    def has_scope(self, resource: str, action: str) -> bool:
        """Check if client has permission for resource/action.

        Args:
            resource: Resource type (individual, group, program, etc.)
            action: Action (read, write, create, delete)

        Returns:
            True if client has the required scope
        """
        if hasattr(self.record, "has_scope"):
            return self.record.has_scope(resource, action)
        # Default to True if no scope checking available
        return True

    def get_allowed_fields(self, resource_type: str) -> set | None:
        """Get allowed fields for a resource type based on client scopes.

        Args:
            resource_type: Type of resource (individual, group)

        Returns:
            Set of allowed field names, or None if all fields allowed
        """
        if hasattr(self.record, "get_allowed_fields"):
            return self.record.get_allowed_fields(resource_type)
        return None  # All fields allowed

    def has_legal_basis_bypass(self) -> bool:
        """Check if client has legal basis that bypasses individual consent.

        Per GDPR Article 6, these bases allow processing without consent:
        - legal_obligation: Required by law
        - vital_interest: Life-threatening emergencies
        - public_interest: Public interest tasks
        - public_task: Official authority

        Returns:
            True if consent check can be bypassed
        """
        non_consent_bases = (
            "legal_obligation",
            "vital_interest",
            "public_interest",
            "public_task",
            "contract",
            "legitimate_interest",
        )
        return self.legal_basis in non_consent_bases

    def __repr__(self) -> str:
        identifier = self.client_id or self.sender_id or str(self.id)
        return f"AuthenticatedClient({self.auth_type}:{identifier})"


class AuthService:
    """Service for authenticating API clients.

    Provides unified authentication for both OAuth and DCI clients.
    """

    def __init__(self, env):
        """Initialize auth service.

        Args:
            env: Odoo environment
        """
        self.env = env

    def authenticate_oauth(self, client_id: str, client_secret: str) -> AuthenticatedClient | None:
        """Authenticate OAuth client by credentials.

        Args:
            client_id: OAuth client ID
            client_secret: OAuth client secret

        Returns:
            AuthenticatedClient if valid, None otherwise
        """
        ApiClient = self.env["spp.api.client"]
        client = ApiClient.authenticate(client_id, client_secret)
        if client:
            return AuthenticatedClient(record=client, auth_type="oauth2")
        return None

    def authenticate_dci_sender(self, sender_id: str) -> AuthenticatedClient | None:
        """Lookup DCI sender by sender_id.

        Note: Signature verification should be done separately before calling this.

        Args:
            sender_id: DCI sender identifier

        Returns:
            AuthenticatedClient if found, None otherwise
        """
        if "spp.dci.sender.registry" not in self.env:
            _logger.warning("DCI sender registry not available")
            return None

        SenderRegistry = self.env["spp.dci.sender.registry"]
        sender = SenderRegistry.get_by_sender_id(sender_id)
        if sender:
            return AuthenticatedClient(record=sender, auth_type="http_signature")
        return None

    def get_client_by_id(self, client_id: int) -> AuthenticatedClient | None:
        """Get authenticated client by database ID.

        Args:
            client_id: Database ID of spp.api.client

        Returns:
            AuthenticatedClient if found, None otherwise
        """
        ApiClient = self.env["spp.api.client"]
        client = ApiClient.browse(client_id)
        if client.exists():
            auth_type = client.auth_type or "oauth2"
            return AuthenticatedClient(record=client, auth_type=auth_type)
        return None
