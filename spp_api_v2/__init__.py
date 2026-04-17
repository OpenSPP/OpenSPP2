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

    # Backfill system_id for existing registrants that don't have one
    _backfill_system_ids(env)


def _backfill_system_ids(env):
    """Assign system_id to all existing registrants missing one."""
    import logging
    import uuid

    _logger = logging.getLogger(__name__)

    system_id_type = env.ref("spp_api_v2.code_id_type_system_id", raise_if_not_found=False)
    if not system_id_type:
        return

    RegistryId = env["spp.registry.id"].sudo()  # nosemgrep: odoo-sudo-without-context
    # nosemgrep: odoo-sudo-without-context, odoo-sudo-on-sensitive-models
    registrants = env["res.partner"].sudo().search([("is_registrant", "=", True)])

    # Find registrants that already have a system_id
    existing = RegistryId.search([("id_type_id", "=", system_id_type.id)])
    has_system_id = {r.partner_id.id for r in existing}

    to_create = []
    for partner in registrants:
        if partner.id not in has_system_id:
            to_create.append(
                {
                    "partner_id": partner.id,
                    "id_type_id": system_id_type.id,
                    "value": str(uuid.uuid4()),
                }
            )

    if to_create:
        RegistryId.create(to_create)
        _logger.info("Backfilled system_id for %d registrants", len(to_create))
