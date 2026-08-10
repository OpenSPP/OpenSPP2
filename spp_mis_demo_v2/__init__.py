# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from . import models
from . import wizard
from .models.indicator_providers import post_init_hook as _activate_demo_variables

_logger = logging.getLogger(__name__)

# res.users records created with the shared, documented password "demo" by
# data/demo_users.xml. They load via the `data` section, so they exist after
# any install — including a production database installed without demo data,
# where the well-known credentials would be a login vector. (The base.user_admin
# and spp_demo.* records in that file are re-roles of existing users, handled by
# spp_demo's own hook.) The archiving helper is kept self-contained here so this
# module carries no dependency on another module's security helper.
DEFAULT_DEMO_USER_XMLIDS = [
    "spp_mis_demo_v2.demo_user_local_registrar",
    "spp_mis_demo_v2.demo_user_global_registrar",
    "spp_mis_demo_v2.demo_user_cr_local_validator",
    "spp_mis_demo_v2.demo_user_cr_hq_validator",
    "spp_mis_demo_v2.demo_user_program_manager",
    "spp_mis_demo_v2.demo_user_program_validator",
    "spp_mis_demo_v2.demo_user_cycle_approver",
]


def demo_data_enabled(env, module_name):
    """Return True if demo data was loaded for ``module_name`` on this database."""
    module = env["ir.module.module"].search([("name", "=", module_name)], limit=1)
    return bool(module.demo)


def deactivate_default_demo_users(env, xmlids, demo_enabled):
    """Deactivate default-credential demo users unless demo data is enabled.

    On a database with demo data (an evaluation/demo instance) the accounts are
    left active so demos work. On a database WITHOUT demo data (a
    production-style install) they are archived so the well-known ``demo``
    password cannot be used to log in. Returns the users that were deactivated.
    """
    if demo_enabled:
        return env["res.users"].browse()
    users = env["res.users"].browse()
    for xmlid in xmlids:
        user = env.ref(xmlid, raise_if_not_found=False)
        if user and user.active:
            users |= user
    if users:
        users.active = False
        _logger.warning(
            "Demo data is disabled; archived %d default-credential MIS demo "
            "user(s): %s. Re-activate them deliberately only on a "
            "non-production instance.",
            len(users),
            ", ".join(users.mapped("login")),
        )
    return users


def post_init_hook(env):
    """Activate demo registry variables, then neutralize default-credential users.

    Wraps the variable-activation hook so the manifest's single ``post_init_hook``
    entry both prepares the MIS demo variables and archives the well-known-password
    demo users on a production install (they stay active when demo data is enabled).
    """
    _activate_demo_variables(env)
    deactivate_default_demo_users(env, DEFAULT_DEMO_USER_XMLIDS, demo_data_enabled(env, "spp_mis_demo_v2"))
