# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Deactivate this module's default-credential demo users on upgrade.

Companion to spp_demo's upgrade migration: the ``post_init_hook`` only fires on
install, so a database that already had ``spp_farmer_registry_demo`` installed
keeps its active, well-known-password users after upgrading. Re-run the same
deactivation on upgrade. On a demo DB (demo data enabled) they stay active.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.spp_demo import deactivate_default_demo_users, demo_data_enabled
from odoo.addons.spp_farmer_registry_demo import DEFAULT_DEMO_USER_XMLIDS


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    deactivate_default_demo_users(env, DEFAULT_DEMO_USER_XMLIDS, demo_data_enabled(env, "spp_farmer_registry_demo"))
