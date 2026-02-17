# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import TransactionCase


class SimulationTestCommon(TransactionCase):
    """Shared test fixtures for spp_simulation tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Security groups
        cls.group_viewer = cls.env.ref("spp_simulation.group_simulation_viewer")
        cls.group_officer = cls.env.ref("spp_simulation.group_simulation_officer")
        cls.group_manager = cls.env.ref("spp_simulation.group_simulation_manager")

        # Test users with different access levels
        cls.user_viewer = cls.env["res.users"].create(
            {
                "name": "Test Simulation Viewer",
                "login": "test_sim_viewer",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.group_viewer.id),
                ],
            }
        )
        cls.user_officer = cls.env["res.users"].create(
            {
                "name": "Test Simulation Officer",
                "login": "test_sim_officer",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.group_officer.id),
                ],
            }
        )
        cls.user_manager = cls.env["res.users"].create(
            {
                "name": "Test Simulation Manager",
                "login": "test_sim_manager",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.group_manager.id),
                ],
            }
        )

        # Create test area
        cls.area = cls.env["spp.area"].create(
            {
                "draft_name": "Test Area",
            }
        )

        # Create test registrants (groups)
        cls.group_registrants = cls.env["res.partner"]
        for i in range(5):
            partner = cls.env["res.partner"].create(
                {
                    "name": f"Test Household {i + 1}",
                    "is_registrant": True,
                    "is_group": True,
                    "area_id": cls.area.id,
                }
            )
            cls.group_registrants |= partner

        # Create test registrants (individuals)
        cls.individual_registrants = cls.env["res.partner"]
        for i in range(10):
            partner = cls.env["res.partner"].create(
                {
                    "name": f"Test Individual {i + 1}",
                    "is_registrant": True,
                    "is_group": False,
                }
            )
            cls.individual_registrants |= partner

        # Create a basic scenario template
        cls.template = cls.env["spp.simulation.scenario.template"].create(
            {
                "name": "Test Template",
                "category": "categorical",
                "target_type": "group",
                "targeting_expression": "true",
                "default_amount": 500.0,
                "default_amount_mode": "fixed",
                "icon": "fa-users",
            }
        )

        # Create a basic scenario
        cls.scenario = cls.env["spp.simulation.scenario"].create(
            {
                "name": "Test Scenario",
                "target_type": "group",
                "targeting_expression": "true",
                "state": "ready",
            }
        )

        # Create entitlement rule for the scenario
        cls.rule_fixed = cls.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": cls.scenario.id,
                "amount_mode": "fixed",
                "amount": 1000.0,
            }
        )
