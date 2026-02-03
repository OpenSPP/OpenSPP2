"""Abstract Key Provider Interface.

Defines the contract that all key providers must implement.
This allows pluggable key management strategies from simple config
to enterprise KMS solutions.

Implementations:
- ConfigKeyProvider: Keys from odoo.conf (development)
- DatabaseKeyProvider: Envelope encryption with DB storage (production)
- VaultKeyProvider: HashiCorp Vault integration (enterprise)
- AWSKMSKeyProvider: AWS Key Management Service (cloud)
- GCPKMSKeyProvider: Google Cloud KMS (cloud)
- AzureKeyVaultProvider: Azure Key Vault (cloud)
"""

import logging
from abc import abstractmethod

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class KeyProvider(models.AbstractModel):
    """Abstract base class for key providers.

    All key management implementations must inherit from this class
    and implement the required methods.
    """

    _name = "spp.key.provider"
    _description = "Abstract Key Provider Interface"

    @abstractmethod
    def get_data_key(self, key_id, version=None):
        """Get a data encryption key.

        Args:
            key_id: Unique identifier for the key
            version: Optional specific version to retrieve

        Returns:
            bytes: The encryption key material (typically 256 bits)

        Raises:
            UserError: If key cannot be retrieved
        """
        raise NotImplementedError("Subclasses must implement get_data_key")

    @abstractmethod
    def get_index_salt(self, purpose):
        """Get a salt for blind index computation.

        Salts are used with HMAC to create searchable blind indexes
        without revealing the original value.

        Args:
            purpose: The purpose identifier for the salt (e.g., 'email', 'phone')

        Returns:
            bytes: The salt value (typically 256 bits)

        Raises:
            UserError: If salt cannot be retrieved
        """
        raise NotImplementedError("Subclasses must implement get_index_salt")

    def rotate_key(self, key_id):
        """Rotate a key to a new version.

        Creates a new version of the key while keeping old versions
        available for decryption of existing data.

        Args:
            key_id: The key to rotate

        Returns:
            int: The new key version number

        Note:
            Not all providers support key rotation. Default implementation
            raises NotImplementedError.
        """
        raise NotImplementedError(f"{self._name} does not support key rotation")

    def list_key_versions(self, key_id):
        """List all versions of a key.

        Args:
            key_id: The key to list versions for

        Returns:
            list: List of version numbers

        Note:
            Not all providers support versioning. Default implementation
            returns [1].
        """
        return [1]

    def get_provider_info(self):
        """Get information about this key provider.

        Returns:
            dict: Provider information including:
                - name: Human-readable provider name
                - type: Provider type code
                - supports_rotation: Whether key rotation is supported
                - supports_versioning: Whether key versioning is supported
                - connection_status: Current connection status
        """
        return {
            "name": self._description,
            "type": self._name.split(".")[-1],
            "supports_rotation": False,
            "supports_versioning": False,
            "connection_status": "unknown",
        }

    def test_connection(self):
        """Test the connection to the key management backend.

        Returns:
            bool: True if connection is successful

        Raises:
            UserError: If connection test fails with details
        """
        try:
            # Try to get a test key
            self.get_data_key("__connection_test__")
            return True
        except Exception as e:
            _logger.warning("Key provider connection test failed: %s", str(e))
            return False


class KeyProviderRegistry(models.Model):
    """Registry of configured key providers.

    Allows configuring which key provider to use for different purposes.
    """

    _name = "spp.key.provider.registry"
    _description = "Key Provider Registry"
    _order = "sequence, name"

    name = fields.Char(
        string="Name",
        required=True,
    )

    provider_type = fields.Selection(
        selection=[
            ("config", "Configuration File"),
            ("database", "Database (Envelope Encryption)"),
            ("vault", "HashiCorp Vault"),
            ("aws_kms", "AWS KMS"),
            ("gcp_kms", "Google Cloud KMS"),
            ("azure_keyvault", "Azure Key Vault"),
        ],
        string="Provider Type",
        required=True,
        default="database",
    )

    purpose_ids = fields.Many2many(
        comodel_name="spp.key.purpose",
        string="Purposes",
        help="Key purposes this provider handles. Leave empty for default provider.",
    )

    is_default = fields.Boolean(
        string="Default Provider",
        default=False,
        help="Use this provider when no specific provider is configured for a purpose",
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )

    active = fields.Boolean(
        default=True,
    )

    # Connection status
    connection_status = fields.Selection(
        selection=[
            ("unknown", "Not Tested"),
            ("connected", "Connected"),
            ("error", "Error"),
        ],
        string="Connection Status",
        default="unknown",
        readonly=True,
    )

    last_test_date = fields.Datetime(
        string="Last Test",
        readonly=True,
    )

    last_test_message = fields.Text(
        string="Last Test Message",
        readonly=True,
    )

    _default_unique = models.Constraint(
        "EXCLUDE (is_default WITH =) WHERE (is_default = TRUE AND active = TRUE)",
        "Only one provider can be the default",
    )

    def _get_provider_model(self):
        """Get the provider model based on type.

        Returns:
            AbstractModel: The key provider model
        """
        provider_models = {
            "config": "spp.key.provider.config",
            "database": "spp.key.provider.database",
            "vault": "spp.key.provider.vault",
            "aws_kms": "spp.key.provider.aws.kms",
            "gcp_kms": "spp.key.provider.gcp.kms",
            "azure_keyvault": "spp.key.provider.azure.keyvault",
        }
        model_name = provider_models.get(self.provider_type)
        if not model_name:
            raise UserError(f"Unknown provider type: {self.provider_type}")

        return self.env[model_name]

    def get_provider(self):
        """Get the provider instance.

        Returns:
            KeyProvider: The provider instance
        """
        self.ensure_one()
        return self._get_provider_model()

    def action_test_connection(self):
        """Test the connection to this provider."""
        self.ensure_one()
        try:
            provider = self.get_provider()
            result = provider.test_connection()

            if result:
                self.write(
                    {
                        "connection_status": "connected",
                        "last_test_date": fields.Datetime.now(),
                        "last_test_message": "Connection successful",
                    }
                )
            else:
                self.write(
                    {
                        "connection_status": "error",
                        "last_test_date": fields.Datetime.now(),
                        "last_test_message": "Connection test returned False",
                    }
                )
        except Exception as e:
            self.write(
                {
                    "connection_status": "error",
                    "last_test_date": fields.Datetime.now(),
                    "last_test_message": str(e),
                }
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Connection Test",
                "message": self.last_test_message,
                "type": "success" if self.connection_status == "connected" else "danger",
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }

    @api.model
    def get_provider_for_purpose(self, purpose_code):
        """Get the appropriate provider for a purpose.

        Args:
            purpose_code: The purpose code (e.g., 'pii', 'financial')

        Returns:
            KeyProvider: The provider to use
        """
        # First, look for a provider specifically configured for this purpose
        Purpose = self.env["spp.key.purpose"]
        purpose = Purpose.search([("code", "=", purpose_code)], limit=1)

        if purpose:
            registry = self.search(
                [
                    ("purpose_ids", "in", purpose.ids),
                    ("active", "=", True),
                ],
                order="sequence",
                limit=1,
            )

            if registry:
                return registry.get_provider()

        # Fall back to default provider
        default_registry = self.search(
            [
                ("is_default", "=", True),
                ("active", "=", True),
            ],
            limit=1,
        )

        if default_registry:
            return default_registry.get_provider()

        # Ultimate fallback: database provider
        return self.env["spp.key.provider.database"]
