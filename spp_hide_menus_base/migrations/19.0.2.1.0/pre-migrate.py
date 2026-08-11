# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""De-duplicate spp.hide.menu before UNIQUE(menu_id) is applied.

``hide_menus()`` creates a row for every menu in ``MENU_APP`` that lacks one, on
every registry load, so those rows exist on any database that has ever booted. A
downstream module seeding its own ``spp.hide.menu`` record for one of those menus
cannot adopt the existing row — its ``<record>`` carries a new xml_id — so it
inserts a second row for the same ``menu_id``. Nothing rejected that until now.

This runs **pre**-migrate deliberately: ``migrate_module(package, 'pre')``
(``odoo/modules/loading.py``) precedes ``registry.init_models(...)``, which is
where the new constraint is applied. Cleaning here means the unique index lands on
data that already satisfies it. It would otherwise fail — and fail *quietly*,
since ``Registry.post_constraint`` logs the failure through ``_schema`` and lets
the upgrade continue, leaving the database unconstrained and still crashing.

Which row survives matters. ``hide_menu()`` snapshots the menu's ``group_ids``
into ``default_group_ids``, so a row created after the menu had already been
collapsed holds nothing but the hide group, and ``show_menu()`` on it would
restore a menu nobody can see. Rows are therefore ranked so that a **degraded**
one — snapshot equal to exactly the hide group — is deleted in preference to one
that can still restore its menu, with the lowest id breaking any remaining tie.
An empty snapshot is not degraded: a menu declaring no groups is correctly
restored to no groups.
"""

import logging

_logger = logging.getLogger(__name__)

_HIDE_GROUP_NAMES = ("group_hide_menus_user", "group_menu_visibility")

# No group can have this id, so every row ranks as non-degraded and the tie-break
# falls through to the lowest id. Used when the hide group cannot be resolved.
_NO_GROUP = -1


def _table_exists(cr, name):
    cr.execute("SELECT to_regclass(%s)", (f"public.{name}",))
    return bool(cr.fetchone()[0])


def _hide_group_id(cr):
    cr.execute(
        """
        SELECT res_id
          FROM ir_model_data
         WHERE model = 'res.groups'
           AND module = 'spp_hide_menus_base'
           AND name IN %s
         ORDER BY CASE name WHEN 'group_hide_menus_user' THEN 0 ELSE 1 END
         LIMIT 1
        """,
        (_HIDE_GROUP_NAMES,),
    )
    row = cr.fetchone()
    return row[0] if row else None


def migrate(cr, version):
    if not version:
        # Fresh install: the constraint is created with the table.
        return

    if not _table_exists(cr, "spp_hide_menu") or not _table_exists(cr, "res_groups_spp_hide_menu_rel"):
        return

    hide_group_id = _hide_group_id(cr)
    if hide_group_id is None:
        _logger.warning(
            "spp_hide_menus_base 19.0.2.1.0: hide group not found; de-duplicating "
            "spp.hide.menu on row id alone, which may keep a row whose "
            "default_group_ids can no longer restore its menu"
        )
        hide_group_id = _NO_GROUP

    cr.execute(
        """
        WITH ranked AS (
            SELECT s.id,
                   ROW_NUMBER() OVER (
                       PARTITION BY s.menu_id
                       ORDER BY CASE
                                    WHEN EXISTS (
                                             SELECT 1 FROM res_groups_spp_hide_menu_rel r
                                              WHERE r.spp_hide_menu_id = s.id
                                                AND r.res_groups_id = %(hide)s
                                         )
                                     AND NOT EXISTS (
                                             SELECT 1 FROM res_groups_spp_hide_menu_rel r
                                              WHERE r.spp_hide_menu_id = s.id
                                                AND r.res_groups_id <> %(hide)s
                                         )
                                    THEN 1
                                    ELSE 0
                                END,
                                s.id
                   ) AS rank
              FROM spp_hide_menu s
             WHERE s.menu_id IS NOT NULL
        )
        SELECT id FROM ranked WHERE rank > 1
        """,
        {"hide": hide_group_id},
    )
    surplus_ids = tuple(row[0] for row in cr.fetchall())
    if not surplus_ids:
        return

    cr.execute(
        "DELETE FROM res_groups_spp_hide_menu_rel WHERE spp_hide_menu_id IN %s",
        (surplus_ids,),
    )
    cr.execute("DELETE FROM spp_hide_menu WHERE id IN %s", (surplus_ids,))

    _logger.info(
        "spp_hide_menus_base 19.0.2.1.0: removed %d duplicate spp.hide.menu row(s) so UNIQUE(menu_id) can be applied",
        len(surplus_ids),
    )
