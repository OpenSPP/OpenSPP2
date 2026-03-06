# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import SimulationTestCommon


@tagged("-at_install", "post_install")
class TestSecurity(SimulationTestCommon):
    """Tests for three-tier security model."""

    def test_viewer_can_read_scenarios(self):
        """Test that viewer can read scenarios."""
        scenarios = self.env["spp.simulation.scenario"].with_user(self.user_viewer).search([])
        # Should not raise AccessError
        self.assertIsNotNone(scenarios)

    def test_viewer_cannot_create_scenarios(self):
        """Test that viewer cannot create scenarios."""
        with self.assertRaises(AccessError):
            self.env["spp.simulation.scenario"].with_user(self.user_viewer).create(
                {
                    "name": "Viewer Created",
                    "target_type": "group",
                    "targeting_expression": "true",
                }
            )

    def test_officer_can_create_scenarios(self):
        """Test that officer can create scenarios."""
        scenario = (
            self.env["spp.simulation.scenario"]
            .with_user(self.user_officer)
            .create(
                {
                    "name": "Officer Created",
                    "target_type": "group",
                    "targeting_expression": "true",
                }
            )
        )
        self.assertTrue(scenario.exists())

    def test_officer_can_read_runs(self):
        """Test that officer can read simulation runs."""
        run = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario.id,
                "state": "completed",
                "beneficiary_count": 10,
            }
        )
        run_read = self.env["spp.simulation.run"].with_user(self.user_officer).browse(run.id)
        self.assertEqual(run_read.beneficiary_count, 10)

    def test_viewer_cannot_delete_scenarios(self):
        """Test that viewer cannot delete scenarios."""
        with self.assertRaises(AccessError):
            self.scenario.with_user(self.user_viewer).unlink()

    def test_run_not_deletable_by_anyone(self):
        """Test that runs cannot be deleted even by manager (audit compliance)."""
        run = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario.id,
                "state": "completed",
                "beneficiary_count": 10,
            }
        )
        with self.assertRaises(UserError):
            run.with_user(self.user_manager).unlink()

    def test_manager_can_create_templates(self):
        """Test that manager can create templates."""
        template = (
            self.env["spp.simulation.scenario.template"]
            .with_user(self.user_manager)
            .create(
                {
                    "name": "Manager Template",
                    "category": "age",
                    "target_type": "group",
                    "targeting_expression": "true",
                }
            )
        )
        self.assertTrue(template.exists())

    def test_viewer_cannot_create_templates(self):
        """Test that viewer cannot create templates."""
        with self.assertRaises(AccessError):
            (
                self.env["spp.simulation.scenario.template"]
                .with_user(self.user_viewer)
                .create(
                    {
                        "name": "Viewer Template",
                        "category": "age",
                        "target_type": "group",
                        "targeting_expression": "true",
                    }
                )
            )

    def test_security_groups_hierarchy(self):
        """Test that security group hierarchy is correct."""
        # Manager should imply officer
        self.assertIn(
            self.group_officer,
            self.group_manager.implied_ids,
        )
        # Officer should imply viewer
        self.assertIn(
            self.group_viewer,
            self.group_officer.implied_ids,
        )

    def test_viewer_cannot_write_scenario(self):
        """Test that viewer cannot write to a scenario."""
        with self.assertRaises(AccessError):
            self.scenario.with_user(self.user_viewer).write({"name": "Viewer Modified"})

    def test_officer_cannot_delete_scenario(self):
        """Test that officer cannot delete a scenario."""
        with self.assertRaises(AccessError):
            self.scenario.with_user(self.user_officer).unlink()

    def test_viewer_cannot_access_wizard(self):
        """Test that viewer cannot create a wizard record."""
        # Create two scenarios for comparison
        scenario2 = self.env["spp.simulation.scenario"].create(
            {
                "name": "Test Scenario 2",
                "target_type": "group",
                "targeting_expression": "true",
            }
        )
        with self.assertRaises(AccessError):
            self.env["spp.simulation.compare.wizard"].with_user(self.user_viewer).create(
                {
                    "scenario_ids": [Command.set([self.scenario.id, scenario2.id])],
                }
            )
