from . import models
from . import wizard

from odoo import api, SUPERUSER_ID


def post_init_hook(env_or_cr, registry=None):
    """Register all active scoring models as indicator providers.

    Supports both Odoo hook signatures:
    - env-based: post_init_hook(env)
    - cr-based: post_init_hook(cr, registry)
    """
    # Handle both signatures - check for Environment object robustly
    if hasattr(env_or_cr, "cr") and hasattr(env_or_cr, "uid"):
        # It's an Environment object
        env = env_or_cr
    elif hasattr(env_or_cr, "execute"):
        # It's a cursor
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})
    else:
        # Fallback - assume cursor
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})

    # Only register if spp_indicators is installed
    if "spp.indicator.registry" in env:
        bridge = env["spp.scoring.indicator.bridge"]
        bridge.register_all_scoring_models()
