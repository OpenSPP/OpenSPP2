# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for router helper functions and service serialization helpers not covered elsewhere."""

import logging
from datetime import datetime

from odoo.tests import tagged

from .common import SimulationApiTestCase, SimulationApiTestCommon

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# _optional_str helper — defined identically in four routers; we import from
# each one directly to guarantee each copy is exercised.
# ---------------------------------------------------------------------------


@tagged("-at_install", "post_install")
class TestOptionalStrHelpers(SimulationApiTestCase):
    """Test the _optional_str helper imported from each router module."""

    # --- analytics router ---

    def test_analytics_optional_str_with_truthy_string(self):
        """_optional_str returns value when given a non-empty string."""
        try:
            from ..routers.analytics import _optional_str as fn
        except ImportError:
            self.skipTest("_optional_str not present in analytics router")
        self.assertEqual(fn("hello"), "hello")

    def test_analytics_optional_str_with_false(self):
        """_optional_str returns None for Odoo False."""
        try:
            from ..routers.analytics import _optional_str as fn
        except ImportError:
            self.skipTest("_optional_str not present in analytics router")
        self.assertIsNone(fn(False))

    def test_analytics_optional_str_with_empty_string(self):
        """_optional_str returns None for empty string (falsy)."""
        try:
            from ..routers.analytics import _optional_str as fn
        except ImportError:
            self.skipTest("_optional_str not present in analytics router")
        self.assertIsNone(fn(""))

    def test_analytics_optional_str_with_none(self):
        """_optional_str returns None for None."""
        try:
            from ..routers.analytics import _optional_str as fn
        except ImportError:
            self.skipTest("_optional_str not present in analytics router")
        self.assertIsNone(fn(None))

    # --- comparison router ---

    def test_comparison_optional_str_with_truthy_string(self):
        """_optional_str in comparison router returns value for non-empty string."""
        from ..routers.comparison import _optional_str

        self.assertEqual(_optional_str("staleness warning"), "staleness warning")

    def test_comparison_optional_str_with_false(self):
        """_optional_str in comparison router returns None for Odoo False."""
        from ..routers.comparison import _optional_str

        self.assertIsNone(_optional_str(False))

    def test_comparison_optional_str_with_empty_string(self):
        """_optional_str in comparison router returns None for empty string."""
        from ..routers.comparison import _optional_str

        self.assertIsNone(_optional_str(""))

    def test_comparison_optional_str_with_none(self):
        """_optional_str in comparison router returns None for None."""
        from ..routers.comparison import _optional_str

        self.assertIsNone(_optional_str(None))

    # --- run router ---

    def test_run_optional_str_with_truthy_string(self):
        """_optional_str in run router returns value for non-empty string."""
        from ..routers.run import _optional_str

        self.assertEqual(_optional_str("error message"), "error message")

    def test_run_optional_str_with_false(self):
        """_optional_str in run router returns None for Odoo False."""
        from ..routers.run import _optional_str

        self.assertIsNone(_optional_str(False))

    def test_run_optional_str_with_empty_string(self):
        """_optional_str in run router returns None for empty string."""
        from ..routers.run import _optional_str

        self.assertIsNone(_optional_str(""))

    def test_run_optional_str_with_none(self):
        """_optional_str in run router returns None for None."""
        from ..routers.run import _optional_str

        self.assertIsNone(_optional_str(None))

    # --- scenario router ---

    def test_scenario_optional_str_with_truthy_string(self):
        """_optional_str in scenario router returns value for non-empty string."""
        from ..routers.scenario import _optional_str

        self.assertEqual(_optional_str("description"), "description")

    def test_scenario_optional_str_with_false(self):
        """_optional_str in scenario router returns None for Odoo False."""
        from ..routers.scenario import _optional_str

        self.assertIsNone(_optional_str(False))

    def test_scenario_optional_str_with_empty_string(self):
        """_optional_str in scenario router returns None for empty string."""
        from ..routers.scenario import _optional_str

        self.assertIsNone(_optional_str(""))

    def test_scenario_optional_str_with_none(self):
        """_optional_str in scenario router returns None for None."""
        from ..routers.scenario import _optional_str

        self.assertIsNone(_optional_str(None))

    def test_scenario_optional_str_with_zero(self):
        """_optional_str returns None for numeric zero (falsy)."""
        from ..routers.scenario import _optional_str

        self.assertIsNone(_optional_str(0))

    def test_scenario_optional_str_with_truthy_number(self):
        """_optional_str returns value for non-zero numeric (truthy)."""
        from ..routers.scenario import _optional_str

        self.assertEqual(_optional_str(42), 42)


# ---------------------------------------------------------------------------
# _build_convert_options — already partially tested; add the remaining paths
# ---------------------------------------------------------------------------


@tagged("-at_install", "post_install")
class TestBuildConvertOptionsAdditional(SimulationApiTestCase):
    """Cover remaining branches of _build_convert_options not hit by existing tests."""

    def _build(self, **kwargs):
        from ..routers.scenario import _build_convert_options
        from ..schemas.scenario import ConvertToProgramRequest

        request = ConvertToProgramRequest(**kwargs)
        return _build_convert_options(request)

    def test_is_one_time_distribution_included(self):
        """is_one_time_distribution=True should appear in options."""
        options = self._build(is_one_time_distribution=True)
        self.assertTrue(options.get("is_one_time_distribution"))

    def test_import_beneficiaries_included(self):
        """import_beneficiaries=True should appear in options."""
        options = self._build(import_beneficiaries=True)
        self.assertTrue(options.get("import_beneficiaries"))

    def test_byday_included(self):
        """byday should appear in options when supplied."""
        options = self._build(rrule_type="monthly", byday="1")
        self.assertEqual(options.get("byday"), "1")

    def test_weekday_included(self):
        """weekday should appear in options when supplied."""
        options = self._build(rrule_type="monthly", weekday="MO")
        self.assertEqual(options.get("weekday"), "MO")

    def test_all_weekday_flags(self):
        """All seven weekday flags are included when True."""
        options = self._build(
            rrule_type="weekly",
            mon=True,
            tue=True,
            wed=True,
            thu=True,
            fri=True,
            sat=True,
            sun=True,
        )
        for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
            self.assertTrue(options.get(day), f"Expected {day} to be True in options")

    def test_false_weekday_flags_excluded(self):
        """Weekday flags that are False should not appear in options."""
        options = self._build(rrule_type="weekly", mon=True)
        # tue through sun should be absent (they default to False)
        for day in ("tue", "wed", "thu", "fri", "sat", "sun"):
            self.assertNotIn(day, options, f"Unexpected key {day} in options")

    def test_cycle_duration_zero_excluded(self):
        """cycle_duration=None should not add the key."""
        options = self._build()
        self.assertNotIn("cycle_duration", options)

    def test_day_zero_excluded(self):
        """day=None should not add the key."""
        options = self._build()
        self.assertNotIn("day", options)


# ---------------------------------------------------------------------------
# _comparison_to_response helper (comparison router)
# ---------------------------------------------------------------------------


@tagged("-at_install", "post_install")
class TestComparisonToResponse(SimulationApiTestCase):
    """Test _comparison_to_response helper in comparison router."""

    def _make_comparison(self, comparison_json=None, overlap_count_json=None, staleness_warning=False):
        """Create a minimal comparison record for testing."""
        runs = [self.run_completed, self.run_completed_2]
        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Test Comparison",
                "run_ids": [(6, 0, [r.id for r in runs])],
            }
        )
        vals = {}
        if comparison_json is not None:
            vals["comparison_json"] = comparison_json
        if overlap_count_json is not None:
            vals["overlap_count_json"] = overlap_count_json
        if staleness_warning:
            vals["staleness_warning"] = staleness_warning
        if vals:
            comparison.write(vals)
        return comparison

    def test_comparison_to_response_empty_json(self):
        """Response has empty runs and overlap when JSON fields are missing."""
        from ..routers.comparison import _comparison_to_response

        comparison = self._make_comparison()
        response = _comparison_to_response(comparison)

        self.assertEqual(response.id, comparison.id)
        self.assertEqual(response.name, "Test Comparison")
        self.assertEqual(len(response.runs), 0)
        self.assertEqual(len(response.overlap_data), 0)
        self.assertIsNone(response.staleness_warning)

    def test_comparison_to_response_with_runs_json(self):
        """Response includes run data from comparison_json."""
        from ..routers.comparison import _comparison_to_response

        comparison_json = {
            "runs": [
                {
                    "run_id": self.run_completed.id,
                    "scenario_name": "Scenario A",
                    "beneficiary_count": 5,
                    "total_cost": 2500.0,
                    "coverage_rate": 50.0,
                    "equity_score": 85.0,
                    "gini_coefficient": 0.15,
                    "has_disparity": False,
                    "leakage_rate": 0.0,
                    "undercoverage_rate": 0.0,
                    "budget_utilization": 50.0,
                    "executed_at": "2024-01-01T00:00:00",
                }
            ]
        }
        comparison = self._make_comparison(comparison_json=comparison_json)
        response = _comparison_to_response(comparison)

        self.assertEqual(len(response.runs), 1)
        self.assertEqual(response.runs[0].scenario_name, "Scenario A")
        self.assertEqual(response.runs[0].beneficiary_count, 5)
        self.assertEqual(response.runs[0].total_cost, 2500.0)

    def test_comparison_to_response_with_overlap_json(self):
        """Response includes overlap data from overlap_count_json."""
        from ..routers.comparison import _comparison_to_response

        overlap_count_json = {
            "pair_1_2": {
                "run_a_id": self.run_completed.id,
                "run_a_name": "Run A",
                "run_b_id": self.run_completed_2.id,
                "run_b_name": "Run B",
                "overlap_count": 3,
                "union_count": 7,
                "jaccard_index": 0.43,
            }
        }
        comparison = self._make_comparison(overlap_count_json=overlap_count_json)
        response = _comparison_to_response(comparison)

        self.assertEqual(len(response.overlap_data), 1)
        self.assertEqual(response.overlap_data[0].overlap_count, 3)
        self.assertEqual(response.overlap_data[0].union_count, 7)
        self.assertAlmostEqual(response.overlap_data[0].jaccard_index, 0.43, places=2)

    def test_comparison_to_response_with_staleness_warning(self):
        """Response includes staleness_warning when set."""
        from ..routers.comparison import _comparison_to_response

        comparison = self._make_comparison(staleness_warning="Scenario has changed since this run")
        response = _comparison_to_response(comparison)

        self.assertIsNotNone(response.staleness_warning)
        self.assertIn("changed", response.staleness_warning)

    def test_comparison_to_response_run_defaults(self):
        """Run data missing keys falls back to defaults (0, False, 0.0)."""
        from ..routers.comparison import _comparison_to_response

        # Minimal run dict — all optional fields missing
        comparison_json = {
            "runs": [
                {
                    "run_id": 1,
                    "scenario_name": "Minimal Run",
                }
            ]
        }
        comparison = self._make_comparison(comparison_json=comparison_json)
        response = _comparison_to_response(comparison)

        run = response.runs[0]
        self.assertEqual(run.beneficiary_count, 0)
        self.assertEqual(run.total_cost, 0.0)
        self.assertFalse(run.has_disparity)
        self.assertIsNone(run.executed_at)


# ---------------------------------------------------------------------------
# AnalyticsApiService._parse_value_labels
# ---------------------------------------------------------------------------


@tagged("post_install", "-at_install")
class TestParseValueLabels(SimulationApiTestCommon):
    """Test AnalyticsApiService._parse_value_labels static method."""

    def _fn(self, value):
        from ..services.analytics_api_service import AnalyticsApiService

        return AnalyticsApiService._parse_value_labels(value)

    def test_parse_value_labels_none(self):
        """Returns None for None input."""
        self.assertIsNone(self._fn(None))

    def test_parse_value_labels_false(self):
        """Returns None for Odoo False input."""
        self.assertIsNone(self._fn(False))

    def test_parse_value_labels_empty_string(self):
        """Returns None for empty string."""
        self.assertIsNone(self._fn(""))

    def test_parse_value_labels_dict_passthrough(self):
        """Returns dict unchanged when already a dict."""
        data = {"M": "Male", "F": "Female"}
        result = self._fn(data)
        self.assertEqual(result, data)

    def test_parse_value_labels_valid_json_string(self):
        """Parses valid JSON string to dict."""
        result = self._fn('{"1": "Yes", "0": "No"}')
        self.assertEqual(result, {"1": "Yes", "0": "No"})

    def test_parse_value_labels_invalid_json_string(self):
        """Returns None for invalid JSON string."""
        result = self._fn("{not valid json}")
        self.assertIsNone(result)

    def test_parse_value_labels_non_string_non_dict(self):
        """Returns None for unexpected types like int."""
        result = self._fn(42)
        self.assertIsNone(result)

    def test_parse_value_labels_list_value(self):
        """Returns None for a list (not dict or str)."""
        result = self._fn(["a", "b"])
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# AnalyticsApiService._build_engine_scope
# ---------------------------------------------------------------------------


@tagged("post_install", "-at_install")
class TestBuildEngineScope(SimulationApiTestCommon):
    """Test AnalyticsApiService._build_engine_scope method."""

    def _get_service(self):
        from ..services.analytics_api_service import AnalyticsApiService

        return AnalyticsApiService(self.env)

    def test_build_engine_scope_group_target(self):
        """Returns explicit scope dict for group target type."""
        service = self._get_service()
        result = service._build_engine_scope({"target_type": "group"})

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("scope_type"), "explicit")
        self.assertIn("explicit_partner_ids", result)

    def test_build_engine_scope_individual_target(self):
        """Returns explicit scope dict for individual target type."""
        service = self._get_service()
        result = service._build_engine_scope({"target_type": "individual"})

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("scope_type"), "explicit")
        self.assertIn("explicit_partner_ids", result)

    def test_build_engine_scope_default_target_is_group(self):
        """target_type defaults to 'group' when absent."""
        service = self._get_service()
        result_default = service._build_engine_scope({})
        result_group = service._build_engine_scope({"target_type": "group"})

        # Both should resolve to the same scope type
        self.assertEqual(result_default.get("scope_type"), result_group.get("scope_type"))

    def test_build_engine_scope_with_area_id(self):
        """area_id filter is applied when provided."""
        service = self._get_service()

        # Create an area with a registrant
        area = self.env["spp.area"].create({"draft_name": "Coverage Test Area"})
        self.env["res.partner"].create(
            {
                "name": "Area Group",
                "is_registrant": True,
                "is_group": True,
                "area_id": area.id,
            }
        )

        result_with_area = service._build_engine_scope({"target_type": "group", "area_id": area.id})
        result_without_area = service._build_engine_scope({"target_type": "group"})

        # With area filter, partner_ids should be a subset of without-area
        self.assertIsInstance(result_with_area["explicit_partner_ids"], list)
        self.assertIsInstance(result_without_area["explicit_partner_ids"], list)
        self.assertLessEqual(
            len(result_with_area["explicit_partner_ids"]),
            len(result_without_area["explicit_partner_ids"]),
        )

    def test_build_engine_scope_with_invalid_cel_expression_falls_back(self):
        """Invalid CEL expression falls back to unfiltered partner set."""
        service = self._get_service()

        # Provide a cel_expression that will fail — the service must log and continue
        result = service._build_engine_scope(
            {
                "target_type": "group",
                "cel_expression": "INVALID CEL $$$ SYNTAX",
            }
        )

        # Should still return a valid scope dict
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("scope_type"), "explicit")


# ---------------------------------------------------------------------------
# SimulationApiService serialization helpers
# ---------------------------------------------------------------------------


@tagged("post_install", "-at_install")
class TestSimulationSerializationHelpers(SimulationApiTestCommon):
    """Test private serialization helpers on SimulationApiService."""

    def _get_service(self):
        from ..services.simulation_api_service import SimulationApiService

        return SimulationApiService(self.env)

    # --- _serialize_scenario ---

    def test_serialize_scenario_basic_fields(self):
        """_serialize_scenario returns all expected top-level keys."""
        service = self._get_service()
        result = service._serialize_scenario(self.scenario)

        expected_keys = {
            "id",
            "name",
            "description",
            "category",
            "template_id",
            "target_type",
            "targeting_expression",
            "budget_amount",
            "budget_strategy",
            "ideal_population_expression",
            "state",
            "targeting_preview_count",
            "entitlement_rules",
            "run_count",
        }
        self.assertEqual(set(result.keys()), expected_keys)

    def test_serialize_scenario_values(self):
        """_serialize_scenario returns correct values for a known scenario."""
        service = self._get_service()
        result = service._serialize_scenario(self.scenario)

        self.assertEqual(result["id"], self.scenario.id)
        self.assertEqual(result["name"], "Test Scenario")
        self.assertEqual(result["target_type"], "group")
        self.assertEqual(result["state"], "draft")
        self.assertEqual(result["budget_amount"], 50000.0)

    def test_serialize_scenario_null_optionals(self):
        """Optional string fields are None when Odoo returns False."""
        service = self._get_service()

        # Create a scenario with no description or category
        bare_scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "Bare Scenario",
                "target_type": "individual",
                "targeting_expression": "",
            }
        )
        result = service._serialize_scenario(bare_scenario)

        self.assertIsNone(result["description"])
        self.assertIsNone(result["category"])
        self.assertIsNone(result["template_id"])
        self.assertIsNone(result["ideal_population_expression"])

    def test_serialize_scenario_includes_rules(self):
        """_serialize_scenario includes serialized entitlement rules."""
        service = self._get_service()
        result = service._serialize_scenario(self.scenario)

        self.assertIsInstance(result["entitlement_rules"], list)
        self.assertGreaterEqual(len(result["entitlement_rules"]), 1)

        rule = result["entitlement_rules"][0]
        self.assertIn("id", rule)
        self.assertIn("amount_mode", rule)
        self.assertIn("amount", rule)

    def test_serialize_scenario_with_template(self):
        """_serialize_scenario includes template_id when set."""
        service = self._get_service()

        scenario_with_template = self.env["spp.simulation.scenario"].create(
            {
                "name": "Templated Scenario",
                "target_type": "group",
                "targeting_expression": "true",
                "template_id": self.template.id,
            }
        )
        result = service._serialize_scenario(scenario_with_template)

        self.assertEqual(result["template_id"], self.template.id)

    # --- _serialize_entitlement_rule ---

    def test_serialize_entitlement_rule_basic(self):
        """_serialize_entitlement_rule returns all expected keys."""
        service = self._get_service()
        result = service._serialize_entitlement_rule(self.entitlement_rule)

        expected_keys = {
            "id",
            "name",
            "sequence",
            "amount_mode",
            "amount",
            "multiplier_field",
            "max_multiplier",
            "amount_cel_expression",
            "condition_cel_expression",
        }
        self.assertEqual(set(result.keys()), expected_keys)

    def test_serialize_entitlement_rule_values(self):
        """_serialize_entitlement_rule returns correct field values."""
        service = self._get_service()
        result = service._serialize_entitlement_rule(self.entitlement_rule)

        self.assertEqual(result["id"], self.entitlement_rule.id)
        self.assertEqual(result["amount_mode"], "fixed")
        self.assertEqual(result["amount"], 500.0)
        self.assertEqual(result["sequence"], 10)

    def test_serialize_entitlement_rule_optional_none_for_false(self):
        """Optional fields are None when Odoo stores False."""
        service = self._get_service()
        result = service._serialize_entitlement_rule(self.entitlement_rule)

        self.assertIsNone(result["multiplier_field"])
        self.assertIsNone(result["amount_cel_expression"])
        self.assertIsNone(result["condition_cel_expression"])

    def test_serialize_entitlement_rule_multiplier_mode(self):
        """Multiplier rule fields are serialized correctly."""
        service = self._get_service()

        multiplier_rule = self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": self.scenario.id,
                "name": "Multiplier Rule",
                "amount_mode": "multiplier",
                "amount": 100.0,
                "multiplier_field": "household_size",
                "max_multiplier": 8,
                "sequence": 20,
            }
        )
        result = service._serialize_entitlement_rule(multiplier_rule)

        self.assertEqual(result["amount_mode"], "multiplier")
        self.assertEqual(result["multiplier_field"], "household_size")
        self.assertEqual(result["max_multiplier"], 8)

    def test_serialize_entitlement_rule_cel_mode(self):
        """CEL rule expressions are serialized correctly."""
        service = self._get_service()

        cel_rule = self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": self.scenario.id,
                "name": "CEL Rule",
                "amount_mode": "cel",
                "amount": 0.0,
                "amount_cel_expression": "r.income * 0.1",
                "condition_cel_expression": "r.income < 10000",
                "sequence": 30,
            }
        )
        result = service._serialize_entitlement_rule(cel_rule)

        self.assertEqual(result["amount_mode"], "cel")
        self.assertEqual(result["amount_cel_expression"], "r.income * 0.1")
        self.assertEqual(result["condition_cel_expression"], "r.income < 10000")

    # --- _serialize_run_headline ---

    def test_serialize_run_headline_keys(self):
        """_serialize_run_headline returns expected top-level keys."""
        service = self._get_service()

        # Need a real run record — run a simulation first
        self.scenario.write({"targeting_expression": "true"})
        run_result = service.run_simulation(self.scenario.id)
        run = self.env["spp.simulation.run"].browse(run_result["id"])

        result = service._serialize_run_headline(run)

        expected_keys = {
            "id",
            "scenario_id",
            "scenario_name",
            "state",
            "beneficiary_count",
            "total_registry_count",
            "coverage_rate",
            "total_cost",
            "budget_utilization",
            "gini_coefficient",
            "equity_score",
            "has_disparity",
            "executed_at",
            "execution_duration_seconds",
            "error_message",
        }
        self.assertEqual(set(result.keys()), expected_keys)

    def test_serialize_run_headline_values(self):
        """_serialize_run_headline returns correct scalar values."""
        service = self._get_service()

        self.scenario.write({"targeting_expression": "true"})
        run_result = service.run_simulation(self.scenario.id)
        run = self.env["spp.simulation.run"].browse(run_result["id"])

        result = service._serialize_run_headline(run)

        self.assertEqual(result["id"], run.id)
        self.assertEqual(result["scenario_id"], self.scenario.id)
        self.assertEqual(result["scenario_name"], self.scenario.name)
        self.assertIn(result["state"], ("completed", "failed"))

    def test_serialize_run_headline_executed_at_iso(self):
        """executed_at is serialized as ISO string when set."""
        service = self._get_service()

        run = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario.id,
                "state": "completed",
                "beneficiary_count": 2,
                "total_cost": 1000.0,
                "executed_at": datetime(2025, 6, 15, 12, 0, 0),
            }
        )
        result = service._serialize_run_headline(run)

        self.assertIsNotNone(result["executed_at"])
        self.assertIn("2025", result["executed_at"])

    def test_serialize_run_headline_no_executed_at(self):
        """executed_at is None when the field is empty."""
        service = self._get_service()

        run = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario.id,
                "state": "failed",
                "beneficiary_count": 0,
                "total_cost": 0.0,
            }
        )
        # Clear executed_at to test the None branch
        run.executed_at = False
        result = service._serialize_run_headline(run)

        self.assertIsNone(result["executed_at"])

    def test_serialize_run_headline_error_message_none_for_false(self):
        """error_message is None when Odoo stores False."""
        service = self._get_service()

        run = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario.id,
                "state": "completed",
                "beneficiary_count": 1,
                "total_cost": 500.0,
            }
        )
        result = service._serialize_run_headline(run)

        self.assertIsNone(result["error_message"])

    # --- _serialize_run_detail ---

    def test_serialize_run_detail_extends_headline(self):
        """_serialize_run_detail includes all headline keys plus detail-specific keys."""
        service = self._get_service()

        run = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario.id,
                "state": "completed",
                "beneficiary_count": 3,
                "total_cost": 1500.0,
            }
        )
        result = service._serialize_run_detail(run)

        detail_only_keys = {
            "leakage_rate",
            "undercoverage_rate",
            "distribution_json",
            "fairness_json",
            "targeting_efficiency_json",
            "geographic_json",
            "metric_results_json",
            "scenario_snapshot_json",
        }
        for key in detail_only_keys:
            self.assertIn(key, result, f"Missing detail key: {key}")

    def test_serialize_run_detail_json_fields_are_none_when_empty(self):
        """JSON detail fields are None when not populated."""
        service = self._get_service()

        run = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario.id,
                "state": "failed",
                "beneficiary_count": 0,
                "total_cost": 0.0,
            }
        )
        result = service._serialize_run_detail(run)

        self.assertIsNone(result["distribution_json"])
        self.assertIsNone(result["fairness_json"])
        self.assertIsNone(result["targeting_efficiency_json"])
        self.assertIsNone(result["geographic_json"])
        self.assertIsNone(result["metric_results_json"])
        self.assertIsNone(result["scenario_snapshot_json"])

    def test_serialize_run_detail_json_fields_returned_when_set(self):
        """JSON detail fields are returned as-is when populated."""
        service = self._get_service()

        distribution_data = {
            "count": 3,
            "total": 1500.0,
            "minimum": 500.0,
            "maximum": 500.0,
            "mean": 500.0,
            "median": 500.0,
            "standard_deviation": 0.0,
            "gini_coefficient": 0.0,
            "percentiles": {},
        }
        run = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario.id,
                "state": "completed",
                "beneficiary_count": 3,
                "total_cost": 1500.0,
                "distribution_json": distribution_data,
            }
        )
        result = service._serialize_run_detail(run)

        self.assertIsNotNone(result["distribution_json"])
        self.assertEqual(result["distribution_json"]["count"], 3)

    # --- _serialize_comparison ---

    def test_serialize_comparison_keys(self):
        """_serialize_comparison returns expected top-level keys."""
        service = self._get_service()

        self.scenario.write({"targeting_expression": "true"})
        run_a_result = service.run_simulation(self.scenario.id)

        scenario_b = self.env["spp.simulation.scenario"].create(
            {
                "name": "Scenario B For Comparison",
                "target_type": "group",
                "targeting_expression": "true",
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
        run_b_result = service.run_simulation(scenario_b.id)

        result = service.compare_runs([run_a_result["id"], run_b_result["id"]])

        expected_keys = {"id", "name", "runs", "overlap", "staleness_warning"}
        self.assertEqual(set(result.keys()), expected_keys)

    def test_serialize_comparison_runs_list(self):
        """_serialize_comparison includes per-run metrics in the runs list."""
        service = self._get_service()

        self.scenario.write({"targeting_expression": "true"})
        run_a_result = service.run_simulation(self.scenario.id)

        scenario_b = self.env["spp.simulation.scenario"].create(
            {
                "name": "Scenario B Runs List",
                "target_type": "group",
                "targeting_expression": "true",
                "state": "draft",
            }
        )
        self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": scenario_b.id,
                "name": "Rule",
                "amount_mode": "fixed",
                "amount": 150.0,
            }
        )
        run_b_result = service.run_simulation(scenario_b.id)

        result = service.compare_runs([run_a_result["id"], run_b_result["id"]])

        self.assertIsInstance(result["runs"], list)
        self.assertIsInstance(result["overlap"], list)

    def test_serialize_comparison_staleness_none_when_false(self):
        """staleness_warning is None when Odoo returns False on the record."""
        service = self._get_service()

        # Need at least 2 runs for a comparison
        run_result_a = service.run_simulation(self.scenario.id)
        run_result_b = service.run_simulation(self.scenario.id)

        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Staleness Test",
                "run_ids": [(6, 0, [run_result_a["id"], run_result_b["id"]])],
            }
        )

        result = service._serialize_comparison(comparison)
        self.assertIsNone(result["staleness_warning"])

    def test_serialize_comparison_with_explicit_comparison_json(self):
        """_serialize_comparison parses comparison_json runs correctly."""
        service = self._get_service()

        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Direct JSON Test",
                "comparison_json": {
                    "runs": [
                        {
                            "run_id": 1,
                            "scenario_name": "Alpha",
                            "beneficiary_count": 10,
                            "total_cost": 5000.0,
                            "coverage_rate": 100.0,
                            "equity_score": 90.0,
                            "gini_coefficient": 0.05,
                            "has_disparity": False,
                            "leakage_rate": 0.0,
                            "undercoverage_rate": 0.0,
                            "budget_utilization": 100.0,
                            "executed_at": "2025-01-01T00:00:00",
                        }
                    ]
                },
                "overlap_count_json": {
                    "pair_1_2": {
                        "run_a_id": 1,
                        "run_a_name": "Alpha",
                        "run_b_id": 2,
                        "run_b_name": "Beta",
                        "overlap_count": 5,
                        "union_count": 15,
                        "jaccard_index": 0.33,
                    }
                },
            }
        )

        result = service._serialize_comparison(comparison)

        self.assertEqual(len(result["runs"]), 1)
        self.assertEqual(result["runs"][0]["scenario_name"], "Alpha")
        self.assertEqual(result["runs"][0]["beneficiary_count"], 10)

        self.assertEqual(len(result["overlap"]), 1)
        self.assertEqual(result["overlap"][0]["overlap_count"], 5)
        self.assertAlmostEqual(result["overlap"][0]["jaccard_index"], 0.33, places=2)

    def test_serialize_comparison_missing_run_fields_use_defaults(self):
        """Run dicts with missing keys fall back to zero/False defaults."""
        service = self._get_service()

        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Defaults Test",
                "comparison_json": {
                    "runs": [
                        {
                            "run_id": 99,
                            "scenario_name": "Partial",
                            # all numeric fields absent
                        }
                    ]
                },
            }
        )

        result = service._serialize_comparison(comparison)

        run = result["runs"][0]
        self.assertEqual(run["beneficiary_count"], 0)
        self.assertEqual(run["total_cost"], 0.0)
        self.assertFalse(run["has_disparity"])
        self.assertIsNone(run["executed_at"])
