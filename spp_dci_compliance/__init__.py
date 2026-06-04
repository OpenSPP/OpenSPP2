# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from . import controllers, models, routers


def _post_init_hook(env):
    """Configure DCI API for compliance testing after module installation.

    This hook:
    1. Adds the public user to the registry viewer group (required for DCI API searches)
    2. Sets DCI configuration parameters for testing
    """
    # Add public user to registry viewer group for DCI API access
    public_user = env.ref("base.public_user", raise_if_not_found=False)
    registry_viewer_group = env.ref("spp_registry.group_registry_viewer", raise_if_not_found=False)

    if public_user and registry_viewer_group:
        # Write to group's user_ids field (Odoo 19 field name)
        if public_user.id not in registry_viewer_group.user_ids.ids:
            # sudo: install hook granting compliance-test access
            group_sudo = registry_viewer_group.sudo()  # nosemgrep: odoo-sudo-without-context
            group_sudo.write({"user_ids": [(4, public_user.id)]})

    # Set DCI config parameters for compliance testing
    config = env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context

    # Allow unsigned requests for signature verification testing
    config.set_param("dci.allow_unsigned_requests", "true")

    # Set accepted Bearer tokens (matches spdci-compliance test suite default)
    config.set_param("dci.api_tokens", "compliance-test-api-key-12345")

    # Allow HTTP callbacks (test containers use HTTP, not HTTPS)
    config.set_param("dci.allow_http_callbacks", "true")

    # Allow internal callback IPs (Docker network uses private IPs)
    config.set_param("dci.allow_internal_callback_ips", "true")

    # Set sender ID for outgoing messages
    config.set_param("dci.sender_id", "openspp.compliance.test")
