# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Deactivate default-credential demo users on upgrade of a production DB.

The ``post_init_hook`` only fires on install, so a database that already had
``spp_demo`` installed before this fix keeps its active, well-known-password
users (including ``sppadmin``/``demo``) after upgrading. Re-run the same
deactivation on upgrade so already-deployed production instances are remediated,
not just fresh installs. On a demo/evaluation DB (demo data enabled) the users
are left active, exactly as on install.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.spp_demo import (
    DEFAULT_DEMO_USER_XMLIDS,
    deactivate_default_demo_users,
    demo_data_enabled,
)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    deactivate_default_demo_users(env, DEFAULT_DEMO_USER_XMLIDS, demo_data_enabled(env, "spp_demo"))
