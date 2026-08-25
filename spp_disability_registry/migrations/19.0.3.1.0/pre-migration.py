# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Carry existing role assignments across the OP#1173 role simplification.

Two things happen to the group set in this version:

* ``group_disability_manager`` is renamed to ``group_disability_approver``.
  Renaming the XML id rather than declaring a new record keeps the same
  ``res.groups`` row, so everyone already holding it stays where they are.
  Declaring a new id instead would have created a second group and left the
  old one behind, unreferenced but still assigned.

* ``group_disability_validator`` is removed. Its ACLs were identical to
  Assessor's, so its holders move to Assessor -- which is the access they
  actually had, not an upgrade to Approver. Approving needs a deliberate
  decision by an admin, and a migration is the wrong place to grant it.

The membership move matters because Odoo 19 does not materialise implied
groups: ``group_ids`` holds only what was assigned directly and
``all_group_ids`` derives the rest. A user assigned Validator alone is not a
row in Assessor, so letting the module drop Validator at the end of the
upgrade would leave them with no disability access whatsoever.
"""

import logging

_logger = logging.getLogger(__name__)

MODULE = "spp_disability_registry"

# (model, old name, new name)
RENAMES = [
    ("res.groups.privilege", "privilege_disability_manager", "privilege_disability_approver"),
    ("res.groups", "group_disability_manager", "group_disability_approver"),
]


def _res_id(cr, model, name):
    cr.execute(
        "SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s AND model = %s",
        (MODULE, name, model),
    )
    row = cr.fetchone()
    return row[0] if row else None


def migrate(cr, version):
    if not version:
        return

    # --- 1. Validator holders become Assessors, before Validator is dropped.
    validator_id = _res_id(cr, "res.groups", "group_disability_validator")
    assessor_id = _res_id(cr, "res.groups", "group_disability_assessor")
    if validator_id and assessor_id:
        cr.execute(
            """
            INSERT INTO res_groups_users_rel (gid, uid)
            SELECT %s, rel.uid
              FROM res_groups_users_rel rel
             WHERE rel.gid = %s
               AND NOT EXISTS (
                     SELECT 1 FROM res_groups_users_rel existing
                      WHERE existing.gid = %s AND existing.uid = rel.uid
                   )
            """,
            (assessor_id, validator_id, assessor_id),
        )
        if cr.rowcount:
            _logger.info(
                "OP#1173: moved %s user(s) from the removed Disability Validator role to Assessor",
                cr.rowcount,
            )

    # --- 2. Rename manager -> approver, keeping the underlying rows.
    for model, old, new in RENAMES:
        if _res_id(cr, model, new) is not None:
            # Already renamed (re-run, or a fresh install that never had the
            # old id). Nothing to do, and renaming would break the
            # (module, name) uniqueness.
            continue
        cr.execute(
            "UPDATE ir_model_data SET name = %s WHERE module = %s AND name = %s AND model = %s",
            (new, MODULE, old, model),
        )
        if cr.rowcount:
            _logger.info("OP#1173: renamed %s.%s to %s", MODULE, old, new)
