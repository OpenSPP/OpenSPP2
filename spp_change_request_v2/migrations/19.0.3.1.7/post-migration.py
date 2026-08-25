# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Drop ``group_cr_manager`` from the CR Requestor role in favour of ``group_cr_user``.

``data/user_roles.xml`` is ``noupdate="1"``, so an existing database keeps the
role exactly as it was first loaded: a requestor holding the manager group, and
through it ``group_cr_validator`` and ``spp_approval.group_approval_approver``.
Editing the XML alone therefore only fixes fresh installs. This migration
re-points the role and re-materialises the group membership of every user
already assigned it.

Users who legitimately need manager rights keep them by holding the manager
group (or a manager role) in their own right — this only removes the grant that
rode in on the requestor role.
"""

import logging

from odoo import SUPERUSER_ID, Command, api

_logger = logging.getLogger(__name__)

_ROLE_XMLID = "spp_change_request_v2.global_role_cr_requestor"


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    role = env.ref(_ROLE_XMLID, raise_if_not_found=False)
    manager = env.ref("spp_change_request_v2.group_cr_manager", raise_if_not_found=False)
    user = env.ref("spp_change_request_v2.group_cr_user", raise_if_not_found=False)
    if not role or not manager or not user:
        _logger.warning(
            "Skipped the CR Requestor role de-escalation: role or groups not found "
            "(role=%s manager=%s user=%s). Verify that the CR Requestor role does not "
            "grant change-request manager rights.",
            bool(role),
            bool(manager),
            bool(user),
        )
        return

    commands = []
    if manager in role.implied_ids:
        commands.append(Command.unlink(manager.id))
    if user not in role.implied_ids:
        commands.append(Command.link(user.id))
    if not commands:
        return

    affected = len(role.user_ids)
    role.implied_ids = commands
    role.action_update_users()
    _logger.warning(
        "Removed the change-request manager grant from the CR Requestor role; "
        "%s user(s) held that role and lose manager rights (approval of change "
        "requests, and delete on change requests, request types and detail "
        "records). Grant the manager group explicitly to anyone who genuinely "
        "needs it, and audit approvals those users performed while holding it.",
        affected,
    )
