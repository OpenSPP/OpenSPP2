# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for simulation scenario API logic."""

from odoo.tests import tagged

from .common import SimulationApiTestCase


@tagged("-at_install", "post_install")
class TestScenarioApi(SimulationApiTestCase):
    """Test scenario endpoint logic and schemas."""

    def test_scenario_to_response_conversion(self):
        """Test conversion of Odoo scenario to Pydantic response."""
        from ..routers.scenario import _scenario_to_response

        response = _scenario_to_response(self.scenario_draft)

        # Verify basic fields
        self.assertEqual(response.id, self.scenario_draft.id)
        self.assertEqual(response.name, "Draft Test Scenario")
        self.assertEqual(response.target_type, "group")
        self.assertEqual(response.state, "draft")
        self.assertEqual(response.targeting_expression, "true")

        # Verify entitlement rules
        self.assertEqual(len(response.entitlement_rules), 1)
        self.assertEqual(response.entitlement_rules[0].amount_mode, "fixed")
        self.assertEqual(response.entitlement_rules[0].amount, 1000.0)

        # Verify computed fields
        self.assertIsNotNone(response.targeting_preview_count)
        self.assertIsNotNone(response.run_count)

    def test_scenario_response_schema_validation(self):
        """Test ScenarioResponse schema validation."""
        from ..schemas.scenario import EntitlementRuleResponse, ScenarioResponse

        # Test with minimal fields
        response = ScenarioResponse(
            id=1,
            name="Test Scenario",
            target_type="group",
            state="draft",
            targeting_expression="true",
            budget_amount=0.0,
            budget_strategy="none",
            targeting_preview_count=0,
            run_count=0,
            latest_beneficiary_count=0,
            latest_equity_score=0.0,
            entitlement_rules=[],
        )

        self.assertEqual(response.id, 1)
        self.assertEqual(response.name, "Test Scenario")
        self.assertEqual(len(response.entitlement_rules), 0)

        # Test with entitlement rules
        response_with_rules = ScenarioResponse(
            id=2,
            name="Test Scenario With Rules",
            target_type="individual",
            state="ready",
            targeting_expression="r.age > 18",
            budget_amount=10000.0,
            budget_strategy="cap_total",
            targeting_preview_count=100,
            run_count=5,
            latest_beneficiary_count=95,
            latest_equity_score=87.5,
            entitlement_rules=[
                EntitlementRuleResponse(
                    id=1,
                    amount_mode="fixed",
                    amount=500.0,
                    multiplier_field=None,
                    max_multiplier=None,
                    amount_cel_expression=None,
                    condition_cel_expression=None,
                )
            ],
        )

        self.assertEqual(len(response_with_rules.entitlement_rules), 1)
        self.assertEqual(response_with_rules.entitlement_rules[0].amount, 500.0)

    def test_scenario_create_request_schema(self):
        """Test ScenarioCreateRequest schema."""
        from ..schemas.scenario import EntitlementRuleSchema, ScenarioCreateRequest

        # Test minimal request
        request = ScenarioCreateRequest(
            name="New Scenario",
            target_type="group",
        )

        self.assertEqual(request.name, "New Scenario")
        self.assertEqual(request.target_type, "group")
        self.assertEqual(len(request.entitlement_rules), 0)
        self.assertIsNone(request.description)

        # Test full request
        full_request = ScenarioCreateRequest(
            name="Full Scenario",
            description="A complete scenario",
            category="age",
            target_type="individual",
            targeting_expression="r.age >= 60",
            targeting_expression_explanation="Senior citizens",
            ideal_population_expression="r.is_vulnerable == true",
            budget_amount=50000.0,
            budget_strategy="proportional_reduction",
            entitlement_rules=[
                EntitlementRuleSchema(
                    amount_mode="fixed",
                    amount=1000.0,
                    multiplier_field=None,
                    max_multiplier=None,
                    amount_cel_expression=None,
                    condition_cel_expression=None,
                )
            ],
            program_id=1,
        )

        self.assertEqual(full_request.name, "Full Scenario")
        self.assertEqual(full_request.description, "A complete scenario")
        self.assertEqual(full_request.budget_amount, 50000.0)
        self.assertEqual(len(full_request.entitlement_rules), 1)
        self.assertEqual(full_request.program_id, 1)

    def test_scenario_update_request_schema(self):
        """Test ScenarioUpdateRequest schema."""
        from ..schemas.scenario import ScenarioUpdateRequest

        # All fields are optional
        request = ScenarioUpdateRequest()
        self.assertIsNone(request.name)
        self.assertIsNone(request.description)

        # Test partial update
        partial_update = ScenarioUpdateRequest(
            name="Updated Name",
            budget_amount=20000.0,
        )

        self.assertEqual(partial_update.name, "Updated Name")
        self.assertEqual(partial_update.budget_amount, 20000.0)
        self.assertIsNone(partial_update.description)

    def test_scenario_list_response_schema(self):
        """Test ScenarioListResponse schema."""
        from ..schemas.scenario import ScenarioListResponse, ScenarioResponse

        scenarios = [
            ScenarioResponse(
                id=1,
                name="Scenario 1",
                target_type="group",
                state="draft",
                targeting_expression="true",
                budget_amount=0.0,
                budget_strategy="none",
                targeting_preview_count=0,
                run_count=0,
                latest_beneficiary_count=0,
                latest_equity_score=0.0,
                entitlement_rules=[],
            ),
            ScenarioResponse(
                id=2,
                name="Scenario 2",
                target_type="individual",
                state="ready",
                targeting_expression="true",
                budget_amount=10000.0,
                budget_strategy="cap_total",
                targeting_preview_count=50,
                run_count=2,
                latest_beneficiary_count=45,
                latest_equity_score=88.0,
                entitlement_rules=[],
            ),
        ]

        response = ScenarioListResponse(
            scenarios=scenarios,
            total_count=2,
        )

        self.assertEqual(len(response.scenarios), 2)
        self.assertEqual(response.total_count, 2)
        self.assertEqual(response.scenarios[0].name, "Scenario 1")
        self.assertEqual(response.scenarios[1].name, "Scenario 2")

    def test_entitlement_rule_schema(self):
        """Test EntitlementRuleSchema validation."""
        from ..schemas.scenario import EntitlementRuleSchema

        # Test fixed amount mode
        rule_fixed = EntitlementRuleSchema(
            amount_mode="fixed",
            amount=500.0,
        )
        self.assertEqual(rule_fixed.amount_mode, "fixed")
        self.assertEqual(rule_fixed.amount, 500.0)
        self.assertIsNone(rule_fixed.multiplier_field)

        # Test multiplier mode
        rule_multiplier = EntitlementRuleSchema(
            amount_mode="multiplier",
            amount=100.0,
            multiplier_field="household_size",
            max_multiplier=10,
        )
        self.assertEqual(rule_multiplier.amount_mode, "multiplier")
        self.assertEqual(rule_multiplier.multiplier_field, "household_size")
        self.assertEqual(rule_multiplier.max_multiplier, 10)

        # Test CEL mode
        rule_cel = EntitlementRuleSchema(
            amount_mode="cel",
            amount=0.0,
            amount_cel_expression="r.income * 0.1",
            condition_cel_expression="r.income < 10000",
        )
        self.assertEqual(rule_cel.amount_mode, "cel")
        self.assertEqual(rule_cel.amount_cel_expression, "r.income * 0.1")
        self.assertEqual(rule_cel.condition_cel_expression, "r.income < 10000")

    def test_api_client_has_simulation_all_scope(self):
        """Test API client with simulation:all scope."""
        self.assertTrue(self.api_client.has_scope("simulation", "all"))

    def test_scenario_with_multiple_rules(self):
        """Test scenario response with multiple entitlement rules."""
        # Create additional rules
        self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": self.scenario_draft.id,
                "amount_mode": "multiplier",
                "amount": 100.0,
                "multiplier_field": "household_size",
                "max_multiplier": 5,
            }
        )

        from ..routers.scenario import _scenario_to_response

        response = _scenario_to_response(self.scenario_draft)

        # Should have 2 rules now
        self.assertEqual(len(response.entitlement_rules), 2)

        # Verify first rule (original)
        self.assertEqual(response.entitlement_rules[0].amount_mode, "fixed")
        self.assertEqual(response.entitlement_rules[0].amount, 1000.0)

        # Verify second rule (new)
        self.assertEqual(response.entitlement_rules[1].amount_mode, "multiplier")
        self.assertEqual(response.entitlement_rules[1].amount, 100.0)
        self.assertEqual(response.entitlement_rules[1].multiplier_field, "household_size")
        self.assertEqual(response.entitlement_rules[1].max_multiplier, 5)

    def test_scenario_with_program_reference(self):
        """Test scenario response with program reference."""
        # Create a program
        program = self.env["spp.program"].create(
            {
                "name": "Test Program",
            }
        )

        # Create scenario with program reference
        scenario_with_program = self.env["spp.simulation.scenario"].create(
            {
                "name": "Scenario With Program",
                "target_type": "group",
                "targeting_expression": "true",
                "program_id": program.id,
            }
        )

        from ..routers.scenario import _scenario_to_response

        response = _scenario_to_response(scenario_with_program)

        self.assertIsNotNone(response.program_id)
        self.assertEqual(response.program_id, program.id)

    def test_scenario_states(self):
        """Test scenarios in different states."""
        from ..routers.scenario import _scenario_to_response

        # Draft scenario
        draft_response = _scenario_to_response(self.scenario_draft)
        self.assertEqual(draft_response.state, "draft")

        # Ready scenario
        ready_response = _scenario_to_response(self.scenario_ready)
        self.assertEqual(ready_response.state, "ready")

        # Archived scenario
        archived_scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "Archived Scenario",
                "target_type": "group",
                "targeting_expression": "true",
                "state": "archived",
            }
        )
        archived_response = _scenario_to_response(archived_scenario)
        self.assertEqual(archived_response.state, "archived")

    def test_scenario_with_budget_strategies(self):
        """Test scenarios with different budget strategies."""
        from ..routers.scenario import _scenario_to_response

        # None strategy
        scenario_none = self.env["spp.simulation.scenario"].create(
            {
                "name": "No Budget Strategy",
                "target_type": "group",
                "targeting_expression": "true",
                "budget_strategy": "none",
                "budget_amount": 0.0,
            }
        )
        response_none = _scenario_to_response(scenario_none)
        self.assertEqual(response_none.budget_strategy, "none")

        # Cap total strategy
        scenario_cap = self.env["spp.simulation.scenario"].create(
            {
                "name": "Cap Total Strategy",
                "target_type": "group",
                "targeting_expression": "true",
                "budget_strategy": "cap_total",
                "budget_amount": 10000.0,
            }
        )
        response_cap = _scenario_to_response(scenario_cap)
        self.assertEqual(response_cap.budget_strategy, "cap_total")
        self.assertEqual(response_cap.budget_amount, 10000.0)

        # Proportional reduction strategy
        scenario_prop = self.env["spp.simulation.scenario"].create(
            {
                "name": "Proportional Reduction Strategy",
                "target_type": "group",
                "targeting_expression": "true",
                "budget_strategy": "proportional_reduction",
                "budget_amount": 15000.0,
            }
        )
        response_prop = _scenario_to_response(scenario_prop)
        self.assertEqual(response_prop.budget_strategy, "proportional_reduction")
        self.assertEqual(response_prop.budget_amount, 15000.0)
