# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

_logger = logging.getLogger(__name__)

# res.users records created with the shared, documented password "demo" by
# data/demo_users.xml (including "user_admin_dmc", which holds base.group_system).
# They load via the `data` section, so they exist after any install — including a
# production database installed without demo data, where the well-known
# credentials would be a login vector. This module does not depend on spp_demo,
# so the archiving helper is kept self-contained here.
DEFAULT_DEMO_USER_XMLIDS = [
    "spp_drims_sl.user_admin_dmc",
    "spp_drims_sl.user_wh_staff_colombo",
    "spp_drims_sl.user_wh_staff_kandy",
    "spp_drims_sl.user_wh_colombo",
    "spp_drims_sl.user_wh_kandy",
    "spp_drims_sl.user_approver_national",
    "spp_drims_sl.user_approver_western",
    "spp_drims_sl.user_approver_central",
    "spp_drims_sl.user_officer_colombo",
    "spp_drims_sl.user_officer_gampaha",
    "spp_drims_sl.user_officer_kandy",
    "spp_drims_sl.user_officer_galle",
    "spp_drims_sl.user_viewer_secretary",
    "spp_drims_sl.user_viewer_director",
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
            "Demo data is disabled; archived %d default-credential DRIMS-SL demo "
            "user(s): %s. Re-activate them deliberately only on a "
            "non-production instance.",
            len(users),
            ", ".join(users.mapped("login")),
        )
    return users


def post_init_hook(env):
    """Neutralize the default-credential demo users on a production install."""
    deactivate_default_demo_users(env, DEFAULT_DEMO_USER_XMLIDS, demo_data_enabled(env, "spp_drims_sl"))
