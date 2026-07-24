# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from . import models

# Farmer-registry-specific demo users created with the well-known password
# "demo" by data/demo_users.xml (in addition to the spp_demo users this module
# re-roles, which spp_demo's own post_init_hook already neutralizes).
DEFAULT_DEMO_USER_XMLIDS = [
    "spp_farmer_registry_demo.demo_user_cr_local_validator",
    "spp_farmer_registry_demo.demo_user_cr_hq_validator",
    "spp_farmer_registry_demo.demo_user_program_manager",
    "spp_farmer_registry_demo.demo_user_cycle_approver",
]


def post_init_hook(env):
    """Neutralize this module's default-credential demo users in production."""
    from odoo.addons.spp_demo import deactivate_default_demo_users, demo_data_enabled

    deactivate_default_demo_users(env, DEFAULT_DEMO_USER_XMLIDS, demo_data_enabled(env, "spp_farmer_registry_demo"))
