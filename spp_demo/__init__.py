# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from . import locale_providers
from . import models
from . import wizard

_logger = logging.getLogger(__name__)

# res.users records created with the shared, documented password "demo" by
# data/users_data.xml (including "sppadmin" with SPP admin rights). They load
# via the `data` section, so they exist after any install — including a
# production database installed without demo data, where the well-known
# credentials would be a login vector.
DEFAULT_DEMO_USER_XMLIDS = [
    "spp_demo.demo_viewer",
    "spp_demo.demo_officer",
    "spp_demo.demo_supervisor",
    "spp_demo.demo_manager",
    "spp_demo.demo_admin",
]


def demo_data_enabled(env, module_name):
    """Return True if demo data was loaded for ``module_name`` on this database."""
    module = env["ir.module.module"].search([("name", "=", module_name)], limit=1)
    return bool(module.demo)


def deactivate_default_demo_users(env, xmlids, demo_enabled):
    """Deactivate default-credential demo users unless demo data is enabled.

    On a database with demo data (an evaluation/demo instance) the accounts are
    left active so demos and generators work. On a database WITHOUT demo data (a
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
            "Demo data is disabled; archived %d default-credential demo "
            "user(s): %s. Re-activate them deliberately only on a "
            "non-production instance.",
            len(users),
            ", ".join(users.mapped("login")),
        )
    return users


def post_init_hook(env):
    """Neutralize the default-credential demo users on a production install."""
    deactivate_default_demo_users(env, DEFAULT_DEMO_USER_XMLIDS, demo_data_enabled(env, "spp_demo"))
