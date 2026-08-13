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
import re

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
    # inverted mental model - even on databases where the link was already
    # removed manually. Strip only the stale sentence: an operator who
    # rewrote or extended the comment keeps their text (noupdate promises
    # that); only the wrong claim goes.
    stale_marker = "Members must already be system administrators"
    correct_comment = (
        "Grants visibility to raw DCI payloads, full identifiers, "
        "disability data, and other sensitive fields exposed by the "
        "DCI cache and log models."
    )
    if group.comment and stale_marker in group.comment:
        cleaned = re.sub(r"\s*Members must already be system administrators\.?", "", group.comment).strip()
        vals["comment"] = cleaned or correct_comment
    if escalated:
        # all_user_ids: transitive membership. Nothing implies this group
        # (in shipped XML or this version), so this equals the direct
        # members and matches the spp_key_management migration's counting.
        affected = len(group.all_user_ids)
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
