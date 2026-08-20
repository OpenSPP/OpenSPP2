# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Swap the Program Viewer role from Tier-2 ``group_registry_viewer`` to Tier-3
``group_registry_read``.

The role's ``implied_ids`` are seeded from ``data/user_roles.xml`` with
``noupdate="1"``, so a released database (2026.07) keeps the old
``group_registry_viewer`` link on upgrade and would retain the Registry Search
portal menu. This migration unlinks the Tier-2 viewer group, links the Tier-3
read group (same registrant read ACLs, no menu), and re-materializes the group
membership of users already assigned the role.
"""

import logging

from odoo import SUPERUSER_ID, Command, api

_logger = logging.getLogger(__name__)

_ROLE_XMLIDS = ["spp_programs.global_role_program_viewer"]


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    viewer = env.ref("spp_registry.group_registry_viewer", raise_if_not_found=False)
    read = env.ref("spp_registry.group_registry_read", raise_if_not_found=False)
    if not viewer or not read:
        return
    for xmlid in _ROLE_XMLIDS:
        role = env.ref(xmlid, raise_if_not_found=False)
        if not role:
            continue
        commands = []
        if viewer in role.implied_ids:
            commands.append(Command.unlink(viewer.id))
        if read not in role.implied_ids:
            commands.append(Command.link(read.id))
        if commands:
            role.implied_ids = commands
            role.action_update_users()
            _logger.info(
                "Migrated role %s: registry viewer -> registry read (re-synced users)",
                xmlid,
            )
