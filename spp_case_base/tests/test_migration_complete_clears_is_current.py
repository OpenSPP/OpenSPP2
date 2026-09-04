# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Exercise the 19.0.2.0.1 post-migration that demotes finished plans.

The code fix in ``action_complete`` only covers future completions. Databases
released before it keep rows with ``state = 'completed'`` and
``is_current = true``, which is what #458 reports: ``current_plan_id`` points at
finished work and the one-current-plan constraint refuses a successor plan. This
pins that the script clears exactly those rows and nothing else.

``migrations/`` is not a package, so the script is loaded through ``importlib``
— same pattern as ``spp_gis/tests/test_migration_geofence_tags.py`` and
``spp_hide_menus_base/tests/test_migration_dedup_hide_menu.py``.
"""

import importlib.util
from pathlib import Path

from odoo import Command
from odoo.tests import TransactionCase, tagged

MIGRATION_PATH = Path(__file__).parent.parent / "migrations" / "19.0.2.0.1" / "post-migration.py"


def _load_migrate():
    spec = importlib.util.spec_from_file_location("spp_case_base_post_migration_19_0_2_0_1", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.migrate


migrate = _load_migrate()


@tagged("post_install", "-at_install")
class TestCompleteClearsIsCurrentMigration(TransactionCase):
    """A released database's stale 'completed but still current' rows."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.case_worker = cls.env["res.users"].create(
            {
                "name": "Migration Case Worker",
                "login": "test_worker_plan_migration",
                "email": "worker_plan_migration@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_case_base.group_case_worker").id),
                ],
            }
        )
        cls.client = cls.env["res.partner"].create({"name": "Migration Client"})
        cls.case_type = cls.env["spp.case.type"].create(
            {
                "name": "Migration Case Type",
                "code": "MIGR01",
                "domain": "social_protection",
            }
        )
        cls.Plan = cls.env["spp.case.intervention.plan"]

    def _case(self, issue):
        return self.env["spp.case"].create(
            {
                "case_type_id": self.case_type.id,
                "partner_id": self.client.id,
                "case_worker_id": self.case_worker.id,
                "presenting_issue": f"<p>{issue}</p>",
            }
        )

    def _stale_plan(self, name, issue):
        """A plan in the shape pre-fix ``action_complete`` left behind.

        The state is forced with SQL on purpose: writing ``state`` through the
        ORM is fine, but going through ``action_complete`` would apply the fix
        and there would be nothing left to migrate.
        """
        plan = self.Plan.create(
            {
                "name": name,
                "case_id": self._case(issue).id,
                "goals": "<p>Goals</p>",
            }
        )
        self.env.cr.execute(
            "UPDATE spp_case_intervention_plan SET state = 'completed', actual_end_date = CURRENT_DATE WHERE id = %s",
            (plan.id,),
        )
        plan.invalidate_recordset(["state", "actual_end_date"])
        self.assertEqual(plan.state, "completed")
        self.assertTrue(plan.is_current, "Test premise: the finished plan is still flagged current")
        return plan

    def test_migration_demotes_completed_plans(self):
        """Test that the script releases is_current on completed plans."""
        stale = self._stale_plan("Stale Completed Plan", "Stale case")

        migrate(self.env.cr, "19.0.2.0.0")

        # The script writes with raw SQL and deliberately does not invalidate,
        # so the read-back has to.
        stale.invalidate_recordset(["is_current"])
        self.assertFalse(stale.is_current, "Migration should release is_current")
        self.assertEqual(stale.state, "completed", "Migration should not touch state")
        self.assertTrue(stale.actual_end_date, "Migration should not touch actual_end_date")
        self.assertFalse(
            stale.case_id.current_plan_id,
            "Case should report no current plan after the migration",
        )

    def test_migration_frees_the_current_plan_slot(self):
        """Test that a successor plan can be created once the migration has run."""
        stale = self._stale_plan("Stale Completed Plan", "Blocked case")
        case = stale.case_id

        migrate(self.env.cr, "19.0.2.0.0")
        stale.invalidate_recordset(["is_current"])

        successor = self.Plan.create(
            {
                "name": "Successor Plan",
                "case_id": case.id,
                "goals": "<p>Next cycle</p>",
            }
        )

        self.assertTrue(successor.is_current, "Successor plan should be current")
        self.assertEqual(case.current_plan_id, successor, "Case should point at the successor")

    def test_migration_leaves_unfinished_plans_alone(self):
        """Test that plans that have not completed keep is_current."""
        keep = self.Plan.create(
            {
                "name": "Active Current Plan",
                "case_id": self._case("Live case").id,
                "goals": "<p>Goals</p>",
                "state": "active",
            }
        )
        self.assertTrue(keep.is_current, "Test premise: the active plan is current")

        migrate(self.env.cr, "19.0.2.0.0")

        keep.invalidate_recordset(["is_current"])
        self.assertTrue(keep.is_current, "An active plan must stay its case's current plan")

    def test_migration_skips_fresh_install(self):
        """Test that the script is a no-op when there is no installed version."""
        stale = self._stale_plan("Stale Completed Plan", "Fresh install case")

        migrate(self.env.cr, None)

        stale.invalidate_recordset(["is_current"])
        self.assertTrue(
            stale.is_current,
            "A fresh install has no legacy rows to repair, so the script must return early",
        )
