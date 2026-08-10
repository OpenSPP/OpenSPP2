# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Neutralize default-credential demo users on upgrade from a pre-fix release.

    The install-time ``post_init_hook`` only runs on a fresh install, not on ``-u``.
    A production database that installed a released version of this module before
    the fix has the well-known-password demo users active — including
    ``user_admin_dmc`` which holds ``base.group_system`` — so upgrading would leave
    a system-admin login vector open. Re-run the same archiving here so the upgrade
    path is covered. Idempotent: on a demo/evaluation database (module.demo True)
    it is a no-op, and it only touches users that are still active.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.spp_drims_sl import (
        DEFAULT_DEMO_USER_XMLIDS,
        deactivate_default_demo_users,
        demo_data_enabled,
    )

    deactivate_default_demo_users(env, DEFAULT_DEMO_USER_XMLIDS, demo_data_enabled(env, "spp_drims_sl"))
