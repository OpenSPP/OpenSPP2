# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for simulation API service."""

import logging

from odoo.tests import tagged

from .common import SimulationApiTestCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestSimulationApiService(SimulationApiTestCommon):
    """Test simulation API service functionality."""

    def _get_service(self):
        """Import and create the service."""
        from ..services.simulation_api_service import SimulationApiService

        return SimulationApiService(self.env)

    # --- Template Tests ---

    def test_list_templates(self):
        """Test listing active templates."""
        service = self._get_service()
        result = service.list_templates()

        self.assertIsInstance(result, list)
        self.assertGreaterEqual(len(result), 1, "Should have at least the test template")

        template = next((t for t in result if t["id"] == self.template.id), None)
        self.assertIsNotNone(template, "Test template should be in results")
        self.assertEqual(template["name"], "Test Template")
        self.assertEqual(template["category"], "age")
        self.assertEqual(template["target_type"], "group")
        self.assertEqual(template["default_amount"], 1000.0)

    def test_list_templates_excludes_inactive(self):
        """Test that inactive templates are excluded."""
        service = self._get_service()

        inactive_template = self.env["spp.simulation.scenario.template"].create(
            {
                "name": "Inactive Template",
                "category": "age",
                "target_type": "group",
                "targeting_expression": "true",
                "active": False,
            }
        )

        result = service.list_templates()
        template_ids = [t["id"] for t in result]
        self.assertNotIn(inactive_template.id, template_ids)

    # --- Scenario CRUD Tests ---

    def test_create_scenario_from_template(self):
        """Test creating a scenario from a template."""
        service = self._get_service()
        result = service.create_scenario(
            {
                "name": "From Template",
                "template_id": self.template.id,
            }
        )

        self.assertIn("id", result)
        self.assertEqual(result["name"], "From Template")
        self.assertEqual(result["target_type"], "group")
        self.assertEqual(
            result["targeting_expression"],
            "age_years(r.birthdate) >= 60",
        )

    def test_create_scenario_custom(self):
        """Test creating a custom scenario without template."""
        service = self._get_service()
        result = service.create_scenario(
            {
                "name": "Custom Scenario",
                "target_type": "individual",
                "targeting_expression": "is_female(r)",
                "budget_amount": 25000.0,
                "budget_strategy": "cap_total",
                "entitlement_rules": [
                    {
                        "name": "Base payment",
                        "amount_mode": "fixed",
                        "amount": 200.0,
                    }
                ],
            }
        )

        self.assertIn("id", result)
        self.assertEqual(result["name"], "Custom Scenario")
        self.assertEqual(result["target_type"], "individual")
        self.assertEqual(result["budget_amount"], 25000.0)
        self.assertEqual(result["budget_strategy"], "cap_total")
        self.assertGreaterEqual(len(result["entitlement_rules"]), 1)

    def test_list_scenarios(self):
        """Test listing scenarios."""
        service = self._get_service()
        result = service.list_scenarios()

        self.assertIsInstance(result, list)
        self.assertGreaterEqual(len(result), 1)

        scenario_ids = [s["id"] for s in result]
        self.assertIn(self.scenario.id, scenario_ids)

    def test_list_scenarios_filter_by_state(self):
        """Test listing scenarios with state filter."""
        service = self._get_service()

        result_draft = service.list_scenarios(state="draft")
        result_ready = service.list_scenarios(state="ready")

        # Our test scenario is draft
        draft_ids = [s["id"] for s in result_draft]
        self.assertIn(self.scenario.id, draft_ids)

        ready_ids = [s["id"] for s in result_ready]
        self.assertNotIn(self.scenario.id, ready_ids)

    def test_get_scenario(self):
        """Test getting a single scenario by ID."""
        service = self._get_service()
        result = service.get_scenario(self.scenario.id)

        self.assertEqual(result["id"], self.scenario.id)
        self.assertEqual(result["name"], "Test Scenario")
        self.assertEqual(result["state"], "draft")
        self.assertIn("entitlement_rules", result)
        self.assertGreaterEqual(len(result["entitlement_rules"]), 1)

    def test_get_scenario_not_found(self):
        """Test getting a non-existent scenario raises ValueError."""
        service = self._get_service()

        with self.assertRaises(ValueError):
            service.get_scenario(99999999)

    def test_update_scenario(self):
        """Test updating scenario fields."""
        service = self._get_service()
        result = service.update_scenario(
            self.scenario.id,
            {
                "name": "Updated Scenario",
                "budget_amount": 75000.0,
            },
        )

        self.assertEqual(result["name"], "Updated Scenario")
        self.assertEqual(result["budget_amount"], 75000.0)

    def test_update_scenario_replace_rules(self):
        """Test updating scenario replaces entitlement rules."""
        service = self._get_service()
        result = service.update_scenario(
            self.scenario.id,
            {
                "entitlement_rules": [
                    {
                        "name": "New rule A",
                        "amount_mode": "fixed",
                        "amount": 300.0,
                    },
                    {
                        "name": "New rule B",
                        "amount_mode": "fixed",
                        "amount": 150.0,
                    },
                ],
            },
        )

        self.assertEqual(len(result["entitlement_rules"]), 2)

    # --- Simulation Run Tests ---

    def test_run_simulation(self):
        """Test running a simulation on a scenario."""
        service = self._get_service()

        # Scenario needs a targeting expression to transition to ready
        self.scenario.write({"targeting_expression": "true"})

        result = service.run_simulation(self.scenario.id)

        self.assertIn("id", result)
        self.assertIn("state", result)
        self.assertIn(result["state"], ("completed", "failed"))
        self.assertIn("beneficiary_count", result)
        self.assertIn("total_cost", result)

    def test_run_simulation_auto_transitions_draft_to_ready(self):
        """Test that run_simulation auto-transitions draft scenarios to ready."""
        service = self._get_service()

        # Scenario is in draft with targeting expression
        self.assertEqual(self.scenario.state, "draft")
        self.scenario.write({"targeting_expression": "true"})

        service.run_simulation(self.scenario.id)

        # Should have transitioned to ready
        self.scenario.invalidate_recordset()
        self.assertEqual(self.scenario.state, "ready")

    def test_run_simulation_not_found(self):
        """Test running simulation for non-existent scenario."""
        service = self._get_service()

        with self.assertRaises(ValueError):
            service.run_simulation(99999999)

    # --- Run Detail Tests ---

    def test_get_run(self):
        """Test getting full run details."""
        service = self._get_service()

        # Run a simulation first
        self.scenario.write({"targeting_expression": "true"})
        run_result = service.run_simulation(self.scenario.id)
        run_id = run_result["id"]

        result = service.get_run(run_id)

        self.assertEqual(result["id"], run_id)
        self.assertIn("distribution_json", result)
        self.assertIn("fairness_json", result)
        self.assertIn("targeting_efficiency_json", result)
        self.assertIn("geographic_json", result)
        self.assertIn("scenario_snapshot_json", result)

    def test_get_run_not_found(self):
        """Test getting a non-existent run raises ValueError."""
        service = self._get_service()

        with self.assertRaises(ValueError):
            service.get_run(99999999)

    # --- Comparison Tests ---

    def test_compare_runs(self):
        """Test comparing two simulation runs."""
        service = self._get_service()

        # Create two scenarios with different expressions and run them
        scenario_a = self.env["spp.simulation.scenario"].create(
            {
                "name": "Comparison A",
                "target_type": "group",
                "targeting_expression": "true",
                "budget_amount": 10000.0,
                "state": "draft",
            }
        )
        self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": scenario_a.id,
                "name": "Rule A",
                "amount_mode": "fixed",
                "amount": 100.0,
            }
        )
        run_a = service.run_simulation(scenario_a.id)

        scenario_b = self.env["spp.simulation.scenario"].create(
            {
                "name": "Comparison B",
                "target_type": "group",
                "targeting_expression": "true",
                "budget_amount": 20000.0,
                "state": "draft",
            }
        )
        self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": scenario_b.id,
                "name": "Rule B",
                "amount_mode": "fixed",
                "amount": 200.0,
            }
        )
        run_b = service.run_simulation(scenario_b.id)

        result = service.compare_runs([run_a["id"], run_b["id"]])

        self.assertIn("id", result)
        self.assertIn("runs", result)
        self.assertEqual(len(result["runs"]), 2)
        self.assertIn("overlap", result)

    def test_compare_runs_requires_minimum_two(self):
        """Test that compare_runs requires at least two run IDs."""
        service = self._get_service()

        with self.assertRaises(ValueError):
            service.compare_runs([1])
