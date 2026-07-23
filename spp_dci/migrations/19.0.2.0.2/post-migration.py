# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Remove the base.group_system implication from the DCI Administrator group.

Earlier versions shipped ``spp_dci.group_dci_admin`` with ``implied_ids``
linking ``base.group_system``. ``implied_ids`` GRANTS the implied groups to
members, so any user given the DCI PII-visibility role silently became a
full Settings/System administrator. The group record is ``noupdate``, so
the corrected XML never reaches already-installed databases - strip the
link here. Odoo computes effective membership as a transitive closure of
``implied_ids``, so removing the link immediately revokes the escalated
privileges from affected users.
"""

import logging

from odoo import SUPERUSER_ID, Command, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    group = env.ref("spp_dci.group_dci_admin", raise_if_not_found=False)
    if not group:
        return

    system = env.ref("base.group_system", raise_if_not_found=False)
    escalated = bool(system) and system in group.implied_ids

    vals = {}
    # The record is noupdate, so refresh the comment that documented the
    # inverted mental model ("Members must already be system administrators")
    # even on databases where the link was already removed manually.
    correct_comment = (
        "Grants visibility to raw DCI payloads, full identifiers, "
        "disability data, and other sensitive fields exposed by the "
        "DCI cache and log models."
    )
    if group.comment != correct_comment:
        vals["comment"] = correct_comment
    if escalated:
        affected = len(group.user_ids)
        vals["implied_ids"] = [Command.unlink(system.id)]

    if not vals:
        return

    group.write(vals)

    if escalated:
        _logger.warning(
            "Removed the base.group_system implication from the DCI Administrator "
            "group; %s user(s) held the group and lose the transitively granted "
            "system administration rights. Audit changes made by these users while "
            "escalated, and grant base.group_system explicitly where it is "
            "genuinely intended.",
            affected,
        )
