# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from . import models
from . import wizard

# res.users records created with the shared, documented password "demo" by
# data/demo_users.xml. They load via the `data` section, so they exist after
# any install — including a production database installed without demo data,
# where the well-known credentials would be a login vector. This module depends
# on spp_drims_sl, so it reuses that module's self-contained archiving helper.
DEFAULT_DEMO_USER_XMLIDS = [
    "spp_drims_sl_demo.user_kumari",
    "spp_drims_sl_demo.user_rajitha",
    "spp_drims_sl_demo.user_silva",
    "spp_drims_sl_demo.user_perera",
    "spp_drims_sl_demo.user_fernando",
    "spp_drims_sl_demo.user_secretary",
]


def post_init_hook(env):
    """Neutralize this module's default-credential demo users in production."""
    from odoo.addons.spp_drims_sl import deactivate_default_demo_users, demo_data_enabled

    deactivate_default_demo_users(env, DEFAULT_DEMO_USER_XMLIDS, demo_data_enabled(env, "spp_drims_sl_demo"))
