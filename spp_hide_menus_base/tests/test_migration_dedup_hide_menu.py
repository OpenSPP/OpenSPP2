# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Exercise the 19.0.2.1.0 pre-migration that de-duplicates ``spp.hide.menu``.

Deleting the surplus rows is only half the repair. The downstream seed that
created a surplus row owns an ``ir.model.data`` entry pointing at it, and a
dangling xml_id is not inert: on the seeding module's next ``-u``,
``_load_records`` finds the record missing, unlinks the stale imd row and
re-creates the record — a second row for the same ``menu_id``, which
``UNIQUE(menu_id)`` now rejects, so that upgrade fails. The migration therefore
repoints those xml_ids onto the survivor and marks them ``noupdate``, without
which dropping the seed later would let ``_process_end`` garbage-collect the
survivor along with the xml_id.

The migration is not importable as a module (``migrations/`` is not a package),
so it is loaded through ``importlib`` — same pattern as
``spp_gis/tests/test_migration_geofence_tags.py``.
"""

import importlib.util
from pathlib import Path

from odoo import Command
from odoo.tests import TransactionCase, tagged

MIGRATION_PATH = Path(__file__).parent.parent / "migrations" / "19.0.2.1.0" / "pre-migrate.py"


def _load_migrate():
    spec = importlib.util.spec_from_file_location("spp_hide_menus_base_pre_migrate_19_0_2_1_0", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.migrate


migrate = _load_migrate()


@tagged("post_install", "-at_install")
class TestHideMenuDedupMigration(TransactionCase):
    """One menu, two rows, one of them seeded with an xml_id."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.HideMenu = cls.env["spp.hide.menu"]
        cls.hide_group = cls.HideMenu._hide_group()

    def _menu_without_hide_row(self):
        taken = self.HideMenu.search([]).mapped("menu_id").ids
        menu = self.env["ir.ui.menu"].search([("id", "not in", taken)], limit=1)
        self.assertTrue(menu, "no unconfigured ir.ui.menu left to test against")
        return menu

    def _drop_unique_constraint(self):
        """Recreate the pre-migration state inside the test transaction.

        DDL rolls back with the transaction, so this cannot leak into sibling
        tests. Without it the duplicate the migration exists to clean up cannot
        be inserted in the first place.
        """
        self.env.cr.execute("ALTER TABLE spp_hide_menu DROP CONSTRAINT IF EXISTS spp_hide_menu_unique_menu")

    def _insert_raw(self, menu, xml_id):
        self.env.cr.execute(
            "INSERT INTO spp_hide_menu (menu_id, state, xml_id) VALUES (%s, 'hide', %s) RETURNING id",
            (menu.id, xml_id),
        )
        return self.env.cr.fetchone()[0]

    def _seed_xmlid(self, name, res_id, noupdate=False):
        self.env.cr.execute(
            """
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
                 VALUES ('spp_hide_menus_base', %s, 'spp.hide.menu', %s, %s)
              RETURNING id
            """,
            (name, res_id, noupdate),
        )
        return self.env.cr.fetchone()[0]

    def _read_imd(self, imd_id):
        self.env.cr.execute("SELECT res_id, noupdate FROM ir_model_data WHERE id = %s", (imd_id,))
        return self.env.cr.fetchone()

    def _surviving_ids(self, menu):
        self.env.cr.execute("SELECT id FROM spp_hide_menu WHERE menu_id = %s", (menu.id,))
        return [r[0] for r in self.env.cr.fetchall()]

    def test_migration_repoints_the_surplus_xmlid_onto_the_survivor(self):
        """The requested fix: adopt the xml_id rather than orphan it.

        Asserted on ``ir_model_data`` directly, because the whole failure mode is
        invisible from the ``spp.hide.menu`` side — the row count is right either
        way, and only the imd row's ``res_id`` says whether the next upgrade of
        the seeding module inserts a duplicate.
        """
        menu = self._menu_without_hide_row()
        self._drop_unique_constraint()
        # Non-degraded, lowest id -> survives. Second row is the seeded surplus.
        survivor_id = self._insert_raw(menu, "test.survivor")
        surplus_id = self._insert_raw(menu, "test.surplus")
        self.HideMenu.browse(survivor_id).default_group_ids = [Command.set([self.env.ref("base.group_user").id])]
        imd_id = self._seed_xmlid("test_seeded_surplus", surplus_id)

        # The ORM defers writes; ``migrate`` reads the rel table in raw SQL and
        # would rank against pre-write data without this.
        self.env.flush_all()
        migrate(self.env.cr, "19.0.2.0.0")

        self.assertEqual(self._surviving_ids(menu), [survivor_id], "the surplus row must be gone")
        res_id, noupdate = self._read_imd(imd_id)
        self.assertEqual(res_id, survivor_id, "the xml_id must point at the survivor, not a deleted row")
        self.assertTrue(noupdate, "without noupdate, dropping the seed later garbage-collects the survivor")

    def test_migration_leaves_an_xmlid_that_already_points_at_the_survivor_alone(self):
        """A seed that won the ranking needs no repoint — and must not be
        silently switched to ``noupdate``.

        ``noupdate`` is applied as part of severing a *surplus* xml_id from a row
        that is about to be deleted. Applying it to a healthy seed would quietly
        stop that module maintaining its own record on upgrade, which is a
        behaviour change nobody asked for.
        """
        menu = self._menu_without_hide_row()
        self._drop_unique_constraint()
        survivor_id = self._insert_raw(menu, "test.survivor")
        self._insert_raw(menu, "test.surplus")
        imd_id = self._seed_xmlid("test_seeded_survivor", survivor_id)

        # The ORM defers writes; ``migrate`` reads the rel table in raw SQL and
        # would rank against pre-write data without this.
        self.env.flush_all()
        migrate(self.env.cr, "19.0.2.0.0")

        res_id, noupdate = self._read_imd(imd_id)
        self.assertEqual(res_id, survivor_id)
        self.assertFalse(noupdate, "a healthy seed must keep updating its own row")

    def test_migration_repoints_every_surplus_xmlid_onto_one_row(self):
        """Two seeds naming the same menu both land on the survivor.

        That is the correct end state under ``UNIQUE(menu_id)``: one row, several
        external ids referring to it.
        """
        menu = self._menu_without_hide_row()
        self._drop_unique_constraint()
        survivor_id = self._insert_raw(menu, "test.survivor")
        first_id = self._insert_raw(menu, "test.surplus_a")
        second_id = self._insert_raw(menu, "test.surplus_b")
        imd_first = self._seed_xmlid("test_seed_a", first_id)
        imd_second = self._seed_xmlid("test_seed_b", second_id)

        # The ORM defers writes; ``migrate`` reads the rel table in raw SQL and
        # would rank against pre-write data without this.
        self.env.flush_all()
        migrate(self.env.cr, "19.0.2.0.0")

        self.assertEqual(self._surviving_ids(menu), [survivor_id])
        self.assertEqual(self._read_imd(imd_first), (survivor_id, True))
        self.assertEqual(self._read_imd(imd_second), (survivor_id, True))

    def test_migration_prefers_keeping_a_row_that_can_still_restore_its_menu(self):
        """The repoint must follow the ranking, not the row order.

        The degraded row here has the LOWER id, so a repoint driven off "keep the
        first" instead of the shared ranking would point the xml_id at the row
        the migration deletes — leaving it dangling, which is the bug this change
        exists to prevent.
        """
        menu = self._menu_without_hide_row()
        self._drop_unique_constraint()
        degraded_id = self._insert_raw(menu, "test.degraded")
        good_id = self._insert_raw(menu, "test.good")
        self.HideMenu.browse(degraded_id).default_group_ids = [Command.set([self.hide_group.id])]
        self.HideMenu.browse(good_id).default_group_ids = [Command.set([self.env.ref("base.group_user").id])]
        imd_id = self._seed_xmlid("test_seed_degraded", degraded_id)

        # The ORM defers writes; ``migrate`` reads the rel table in raw SQL and
        # would rank against pre-write data without this.
        self.env.flush_all()
        migrate(self.env.cr, "19.0.2.0.0")

        self.assertEqual(self._surviving_ids(menu), [good_id], "the degraded row must be the one deleted")
        self.assertEqual(self._read_imd(imd_id), (good_id, True))

    def test_migration_is_a_no_op_without_duplicates(self):
        """No duplicates means no repoint and no ``noupdate`` flipping.

        The migration runs on every upgraded database, the overwhelming majority
        of which are healthy; a healthy one must come out untouched.
        """
        menu = self._menu_without_hide_row()
        only_id = self._insert_raw(menu, "test.only")
        imd_id = self._seed_xmlid("test_seed_only", only_id)

        # The ORM defers writes; ``migrate`` reads the rel table in raw SQL and
        # would rank against pre-write data without this.
        self.env.flush_all()
        migrate(self.env.cr, "19.0.2.0.0")

        self.assertEqual(self._surviving_ids(menu), [only_id])
        self.assertEqual(self._read_imd(imd_id), (only_id, False))

    def test_migration_skips_a_fresh_install(self):
        """``version`` falsy means the table is being created with the
        constraint already on it; there is nothing to clean and nothing to
        repoint."""
        menu = self._menu_without_hide_row()
        only_id = self._insert_raw(menu, "test.only")
        imd_id = self._seed_xmlid("test_seed_fresh", only_id)

        # The ORM defers writes; ``migrate`` reads the rel table in raw SQL and
        # would rank against pre-write data without this.
        self.env.flush_all()
        migrate(self.env.cr, None)

        self.assertEqual(self._read_imd(imd_id), (only_id, False))
