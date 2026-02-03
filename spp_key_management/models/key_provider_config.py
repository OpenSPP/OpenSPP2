# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Configuration-based Key Provider.

Reads encryption keys from odoo.conf. Simple but suitable for
development and small deployments.

Configuration example in odoo.conf:
    [options]
    spp_encryption_key_pii = <base64-encoded-32-byte-key>
    spp_encryption_key_financial = <base64-encoded-32-byte-key>
    spp_index_salt_default = <base64-encoded-32-byte-salt>

Generate keys with:
    python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
"""

import base64
import hashlib
import logging

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools import config

_logger = logging.getLogger(__name__)


class ConfigKeyProvider(models.AbstractModel):
    """Configuration file based key provider.

    Reads keys from odoo.conf. Suitable for development and
    simple deployments where key management infrastructure
    is not available.

    Security Note:
        Keys in config files should be protected by filesystem
        permissions. For production, consider DatabaseKeyProvider
        or VaultKeyProvider.
    """

    _name = "spp.key.provider.config"
    _inherit = "spp.key.provider"
    _description = "Configuration File Key Provider"

    @api.model
    def get_data_key(self, key_id, version=None):
        """Read encryption key from odoo.conf.

        Args:
            key_id: Key identifier (e.g., 'pii')
            version: Ignored (config provider doesn't support versions)

        Returns:
            bytes: The raw key material

        Raises:
            UserError: If key is not configured
        """
        config_key = f"spp_encryption_key_{key_id}"
        key_b64 = config.get(config_key)

        if not key_b64:
            raise UserError(
                _(
                    "Encryption key '%(key_id)s' not found in configuration.\n\n"
                    "Add the following to odoo.conf:\n"
                    "%(config_key)s = <base64-encoded-key>\n\n"
                    "Generate a key with:\n"
                    'python -c "import secrets, base64; '
                    'print(base64.b64encode(secrets.token_bytes(32)).decode())"'
                )
                % {"key_id": key_id, "config_key": config_key}
            )

        try:
            key = base64.b64decode(key_b64)
            if len(key) != 32:
                raise UserError(
                    _(
                        "Encryption key '%(key_id)s' has invalid length. "
                        "Expected 32 bytes (256 bits), got %(length)d bytes."
                    )
                    % {"key_id": key_id, "length": len(key)}
                )
            return key
        except Exception as e:
            raise UserError(
                _("Failed to decode encryption key '%(key_id)s': %(error)s") % {"key_id": key_id, "error": str(e)}
            ) from e

    @api.model
    def get_index_salt(self, purpose):
        """Get salt for blind index computation.

        Reads from config or derives from master key.

        Args:
            purpose: Salt purpose (e.g., 'national_id')

        Returns:
            bytes: The salt value
        """
        config_key = f"spp_index_salt_{purpose}"
        salt_b64 = config.get(config_key)

        if salt_b64:
            try:
                return base64.b64decode(salt_b64)
            except Exception as e:
                _logger.warning(
                    "Failed to decode index salt '%s': %s. Using derived salt.",
                    purpose,
                    e,
                )

        # Derive salt from master key + purpose
        # This ensures consistent salts without explicit configuration
        _logger.debug("Index salt for '%s' not configured. Deriving from master key.", purpose)
        try:
            master_key = self.get_data_key("pii")
            return hashlib.sha256(purpose.encode() + b":" + master_key).digest()
        except UserError as err:
            # SECURITY: No fallback - fail hard if no master key
            raise UserError(
                _(
                    "Cannot derive salt for '%(purpose)s': no master key configured.\n\n"
                    "Configure spp_encryption_key_pii in odoo.conf or use explicit salt:\n"
                    "spp_index_salt_%(purpose)s = <base64-encoded-salt>"
                )
                % {"purpose": purpose}
            ) from err

    @api.model
    def get_key_metadata(self, key_id):
        """Get metadata about a config-based key."""
        return {
            "key_id": key_id,
            "algorithm": "AES-256-GCM",
            "provider": "config",
            "supports_rotation": False,
            "supports_versioning": False,
        }
