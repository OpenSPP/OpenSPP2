import logging

from . import models
from . import routers
from . import services

_logger = logging.getLogger(__name__)


# Auth bypass system parameters the DR demo relies on. Set on first install
# so a fresh DR answers SP requests without the operator having to find
# Settings → Technical → System Parameters and create two ir.config_parameter
# rows by hand (the keys are easy to mistype — see the typo trap noted in the
# demo runbook).
#
# SECURITY NOTE: these flags disable signature verification and bearer-token
# enforcement on the /dci_api/* endpoint. They are appropriate for the demo
# and for dev environments; PRODUCTION DEPLOYMENTS MUST FLIP THEM BACK TO
# 'false' and configure a Sender Registry entry + bearer token instead.
_DEMO_AUTH_BYPASS_PARAMS = (
    ("dci.bypass_bearer_auth", "true"),
    ("dci.allow_unsigned_requests", "true"),
)


def post_init_hook(env):
    """Seed DCI auth-bypass system parameters on fresh install.

    The hook never overwrites an existing value — if an operator previously
    set either parameter to 'false' (or anything else), upgrading the module
    leaves their choice alone. Only first installs get the demo defaults.
    """
    Param = env["ir.config_parameter"].sudo()
    for key, value in _DEMO_AUTH_BYPASS_PARAMS:
        existing = Param.search([("key", "=", key)], limit=1)
        if existing:
            _logger.info(
                "spp_dci_server_disability post_init_hook: %s already set to %r, leaving as-is",
                key,
                existing.value,
            )
            continue
        Param.set_param(key, value)
        _logger.warning(
            "spp_dci_server_disability post_init_hook: set %s=%r (DEMO-MODE AUTH BYPASS — "
            "flip to 'false' in Settings → Technical → System Parameters for production)",
            key,
            value,
        )
