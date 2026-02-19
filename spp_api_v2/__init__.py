from . import models
from . import routers
from . import middleware
from . import services
from . import wizards


def _post_init_hook(env):
    """
    Auto-generate JWT secret on module install if not configured.
    Sync FastAPI endpoint registry.

    SECURITY: This ensures the module works out of the box without
    manual configuration, while still using a secure random secret.
    """
    import secrets

    ICP = env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context
    existing_secret = ICP.get_param("spp_api_v2.jwt_secret")

    if not existing_secret:
        # Generate a cryptographically secure 64-byte secret
        secret = secrets.token_urlsafe(64)
        ICP.set_param("spp_api_v2.jwt_secret", secret)
        # Log without exposing the secret
        import logging

        _logger = logging.getLogger(__name__)
        _logger.info("Generated JWT secret for spp_api_v2 module")

    # Sync FastAPI endpoint registry
    endpoint = env.ref("spp_api_v2.fastapi_endpoint_api_v2", raise_if_not_found=False)
    if endpoint:
        endpoint.action_sync_registry()
        _logger.info("Synced FastAPI endpoint registry for spp_api_v2")
