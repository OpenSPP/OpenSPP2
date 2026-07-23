# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Remove the base.group_system implication from the Key Management Admin group.

Earlier versions shipped ``spp_key_management.group_key_admin`` with
``implied_ids`` linking ``base.group_system``. ``implied_ids`` GRANTS the
implied groups to members, so any user given the key management role
silently became a full Settings/System administrator. Removing the link
from the XML only stops adding it on fresh installs - it never removes an
existing relation - so strip it here. Odoo computes effective membership
as a transitive closure of ``implied_ids``, so removing the link
immediately revokes the escalated privileges from affected users. (The
replacement implication - admin implies operator - is applied by the
regular data load; the groups file is not noupdate.)
"""

import logging

from odoo import SUPERUSER_ID, Command, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    group = env.ref("spp_key_management.group_key_admin", raise_if_not_found=False)
    system = env.ref("base.group_system", raise_if_not_found=False)
    if not group or not system or system not in group.implied_ids:
        return

    affected = len(group.user_ids)
    group.write({"implied_ids": [Command.unlink(system.id)]})
    _logger.warning(
        "Removed the base.group_system implication from the Key Management "
        "Admin group; %s user(s) held the group and lose the transitively "
        "granted system administration rights. Audit changes made by these "
        "users while escalated, grant base.group_system explicitly where it "
        "is genuinely intended, and consider rotating data keys if key "
        "custody policy separates platform admins from key admins.",
        affected,
    )
