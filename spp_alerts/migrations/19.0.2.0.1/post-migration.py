# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Backfill eval_as_user_id for alert rules that predate 19.0.2.0.1.

The evaluation identity that bounds a rule's monitored search to its
configurer's record-rule visibility is new in this version. For rules created
before the upgrade it defaults to whoever created the rule.
"""


def migrate(cr, version):
    if not version:
        return
    # Every existing row predates eval_as_user_id, so set it authoritatively from
    # create_uid. This is unconditional (not `WHERE ... IS NULL`) because the field
    # carries no Python default: nothing else populates the column at upgrade time,
    # and an IS NULL guard would be defeated if Odoo's _init_column ever pre-filled it.
    cr.execute("UPDATE spp_alert_rule SET eval_as_user_id = create_uid")
