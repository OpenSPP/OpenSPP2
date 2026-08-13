# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Backfill eval_as_user_id on GRM rules from create_uid.

The new ``eval_as_user_id`` field (added for #379) bounds a rule's evaluation
to its author's ticket scope. Existing rules predate the field, so attribute it
to whoever created each rule. The field carries no Python ``default`` on purpose
(a default would make Odoo's ``_init_column`` prefill every row with the upgrade
user before this runs), so every pre-existing row is NULL here and the backfill
is effectively unconditional; the ``WHERE ... IS NULL`` guard only makes a re-run
a no-op.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("UPDATE spp_grm_routing_rule SET eval_as_user_id = create_uid WHERE eval_as_user_id IS NULL")
    routing = cr.rowcount
    cr.execute("UPDATE spp_grm_escalation_rule SET eval_as_user_id = create_uid WHERE eval_as_user_id IS NULL")
    escalation = cr.rowcount

    if routing or escalation:
        _logger.warning(
            "Backfilled eval_as_user_id from create_uid on %s routing rule(s) and "
            "%s escalation rule(s). These rules now evaluate with their creator's "
            "record-rule scope; review any rule whose creator's permissions have "
            "changed since it was authored.",
            routing,
            escalation,
        )
