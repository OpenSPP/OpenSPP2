import logging

from odoo.exceptions import UserError

from . import models

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Ensure the default encryption provider is ready for signing.

    The base data creates the provider without a type/key. Configure it with
    jwcrypto and generate a key so downstream modules can use it immediately.

    Note: If the master key is not configured, key generation is skipped.
    This allows the module to be installed in test environments where the
    master key is set up programmatically after module loading.
    """
    # Import here to avoid circular dependency at module load time
    from odoo.addons.spp_key_management.exceptions import MasterKeyNotConfiguredError

    provider = env.ref("spp_encryption.encryption_provider_default", raise_if_not_found=False)
    if provider:
        updates = {}
        if not provider.type:
            updates["type"] = "jwcrypto"
        if updates:
            provider.write(updates)
        if provider.type == "jwcrypto" and not provider.key_id:
            try:
                provider.generate_key()
            except MasterKeyNotConfiguredError:
                _logger.info(
                    "Skipping key generation for default provider: master key not configured. "
                    "Configure spp_master_key in odoo.conf for production use."
                )
            except UserError:
                # Re-raise other UserErrors (e.g., invalid key format)
                raise
