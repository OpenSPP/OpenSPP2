# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Backfill eval_as_user_id for alert rules that predate 19.0.2.0.1.

The evaluation identity that bounds a rule's monitored search to its
configurer's record-rule visibility is new in this version. For rules created
before the upgrade it defaults to whoever created the rule.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("UPDATE spp_alert_rule SET eval_as_user_id = create_uid WHERE eval_as_user_id IS NULL")
