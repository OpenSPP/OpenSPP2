# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for scenario update logic, including targeting_expression_explanation fix."""

from odoo.tests import tagged

from .common import SimulationApiTestCase


@tagged("-at_install", "post_install")
class TestScenarioUpdate(SimulationApiTestCase):
    """Test scenario update endpoint logic and schema fields."""

    def test_update_request_has_targeting_expression_explanation(self):
        """Test ScenarioUpdateRequest schema includes targeting_expression_explanation."""
        from ..schemas.scenario import ScenarioUpdateRequest

        request = ScenarioUpdateRequest(
            targeting_expression="r.age >= 60",
            targeting_expression_explanation="Senior citizens aged 60 and above",
        )

        self.assertEqual(request.targeting_expression, "r.age >= 60")
        self.assertEqual(
            request.targeting_expression_explanation,
            "Senior citizens aged 60 and above",
        )

    def test_update_request_targeting_expression_explanation_defaults_none(self):
        """Test targeting_expression_explanation defaults to None."""
        from ..schemas.scenario import ScenarioUpdateRequest

        request = ScenarioUpdateRequest(name="Test")
        self.assertIsNone(request.targeting_expression_explanation)

    def test_update_scenario_with_targeting_expression_explanation(self):
        """Test updating scenario passes targeting_expression_explanation to Odoo."""
        from ..routers.scenario import _scenario_to_response

        # Write targeting_expression_explanation directly
        self.scenario_draft.write(
            {
                "targeting_expression_explanation": "Households with elderly members",
            }
        )
        self.scenario_draft.invalidate_recordset()

        response = _scenario_to_response(self.scenario_draft)

        self.assertEqual(
            response.targeting_expression_explanation,
            "Households with elderly members",
        )

    def test_update_scenario_clears_targeting_expression_explanation(self):
        """Test that setting targeting_expression_explanation to empty returns None."""
        from ..routers.scenario import _scenario_to_response

        # First set it
        self.scenario_draft.write({"targeting_expression_explanation": "Some explanation"})
        self.scenario_draft.invalidate_recordset()

        # Then clear it
        self.scenario_draft.write({"targeting_expression_explanation": False})
        self.scenario_draft.invalidate_recordset()

        response = _scenario_to_response(self.scenario_draft)
        self.assertIsNone(response.targeting_expression_explanation)

    def test_update_request_all_fields(self):
        """Test ScenarioUpdateRequest with all fields populated."""
        from ..schemas.scenario import EntitlementRuleSchema, ScenarioUpdateRequest

        request = ScenarioUpdateRequest(
            name="Updated Name",
            description="Updated description",
            category="disability",
            target_type="individual",
            targeting_expression="r.has_disability == true",
            targeting_expression_explanation="People with disabilities",
            ideal_population_expression="r.is_vulnerable == true",
            budget_amount=100000.0,
            budget_strategy="proportional_reduction",
            entitlement_rules=[
                EntitlementRuleSchema(
                    amount_mode="fixed",
                    amount=500.0,
                )
            ],
        )

        self.assertEqual(request.name, "Updated Name")
        self.assertEqual(request.description, "Updated description")
        self.assertEqual(request.category, "disability")
        self.assertEqual(request.target_type, "individual")
        self.assertEqual(request.targeting_expression, "r.has_disability == true")
        self.assertEqual(request.targeting_expression_explanation, "People with disabilities")
        self.assertEqual(request.ideal_population_expression, "r.is_vulnerable == true")
        self.assertEqual(request.budget_amount, 100000.0)
        self.assertEqual(request.budget_strategy, "proportional_reduction")
        self.assertEqual(len(request.entitlement_rules), 1)

    def test_scenario_response_includes_ideal_population_expression(self):
        """Test ScenarioResponse includes ideal_population_expression."""
        from ..routers.scenario import _scenario_to_response

        self.scenario_draft.write({"ideal_population_expression": "r.is_vulnerable == true"})
        self.scenario_draft.invalidate_recordset()

        response = _scenario_to_response(self.scenario_draft)
        self.assertEqual(response.ideal_population_expression, "r.is_vulnerable == true")

    def test_scenario_response_empty_optional_fields_are_none(self):
        """Test that empty optional string fields convert to None (not False)."""
        from ..routers.scenario import _scenario_to_response

        # Create scenario with no optional fields
        scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "Minimal Scenario",
                "target_type": "group",
                "state": "draft",
            }
        )

        response = _scenario_to_response(scenario)

        self.assertIsNone(response.description)
        self.assertIsNone(response.category)
        self.assertIsNone(response.targeting_expression)
        self.assertIsNone(response.targeting_expression_explanation)
        self.assertIsNone(response.ideal_population_expression)
        self.assertIsNone(response.targeting_preview_error)
        self.assertIsNone(response.program_id)

    def test_optional_str_helper(self):
        """Test _optional_str converts Odoo False to None."""
        from ..routers.scenario import _optional_str

        self.assertIsNone(_optional_str(False))
        self.assertIsNone(_optional_str(""))
        self.assertIsNone(_optional_str(None))
        self.assertEqual(_optional_str("hello"), "hello")
        self.assertEqual(_optional_str("0"), "0")
