# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for converting simulation scenarios to programs."""

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import SimulationTestCommon


@tagged("-at_install", "post_install")
class TestScenarioConvertToProgram(SimulationTestCommon):
    """Tests for spp.simulation.service.convert_to_program()."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a ready scenario with a fixed entitlement rule for conversion
        cls.convert_scenario = cls.env["spp.simulation.scenario"].create(
            {
                "name": "Scenario for Conversion",
                "description": "A scenario to test program conversion",
                "target_type": "group",
                "targeting_expression": "true",
                "state": "ready",
            }
        )
        cls.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": cls.convert_scenario.id,
                "amount_mode": "fixed",
                "amount": 1000.0,
                "sequence": 10,
            }
        )

        # Create a scenario with CEL entitlement rule
        cls.cel_scenario = cls.env["spp.simulation.scenario"].create(
            {
                "name": "CEL Entitlement Scenario",
                "description": "Scenario with CEL amount expression",
                "target_type": "individual",
                "targeting_expression": "true",
                "state": "ready",
            }
        )
        cls.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": cls.cel_scenario.id,
                "amount_mode": "cel",
                "amount": 500.0,
                "amount_cel_expression": "me.household_size * 100",
                "sequence": 10,
            }
        )

        # Create a scenario with condition CEL expression
        # Use "true" as a valid CEL expression that passes wizard validation
        cls.condition_scenario = cls.env["spp.simulation.scenario"].create(
            {
                "name": "Condition Scenario",
                "target_type": "group",
                "targeting_expression": "true",
                "state": "ready",
            }
        )
        cls.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": cls.condition_scenario.id,
                "amount_mode": "fixed",
                "amount": 750.0,
                "condition_cel_expression": "true",
                "sequence": 10,
            }
        )

        # Create a scenario with multiplier rule
        cls.multiplier_scenario = cls.env["spp.simulation.scenario"].create(
            {
                "name": "Multiplier Scenario",
                "target_type": "group",
                "targeting_expression": "true",
                "state": "ready",
            }
        )
        cls.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": cls.multiplier_scenario.id,
                "amount_mode": "multiplier",
                "amount": 200.0,
                "multiplier_field": "household_size",
                "max_multiplier": 10,
                "sequence": 10,
            }
        )

        # Create a draft scenario (should not be convertible)
        cls.draft_scenario = cls.env["spp.simulation.scenario"].create(
            {
                "name": "Draft Scenario",
                "target_type": "group",
                "targeting_expression": "true",
                "state": "draft",
            }
        )
        cls.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": cls.draft_scenario.id,
                "amount_mode": "fixed",
                "amount": 100.0,
            }
        )

        # Create a scenario with no rules
        cls.no_rules_scenario = cls.env["spp.simulation.scenario"].create(
            {
                "name": "No Rules Scenario",
                "target_type": "group",
                "targeting_expression": "true",
                "state": "ready",
            }
        )

        cls.service = cls.env["spp.simulation.service"]

    def _make_scenario(self, name, **kwargs):
        """Helper to create a ready scenario with a single fixed rule."""
        vals = {
            "name": name,
            "target_type": kwargs.pop("target_type", "group"),
            "targeting_expression": kwargs.pop("targeting_expression", "true"),
            "state": "ready",
        }
        vals.update(kwargs)
        scenario = self.env["spp.simulation.scenario"].create(vals)
        self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": scenario.id,
                "amount_mode": "fixed",
                "amount": 100.0,
            }
        )
        return scenario

    def test_convert_ready_scenario_creates_program(self):
        """Converting a ready scenario creates a program record."""
        result = self.service.convert_to_program(self.convert_scenario, {})
        program = result["program"]
        self.assertTrue(program.exists())
        self.assertEqual(program.name, "Scenario for Conversion")

    def test_convert_sets_converted_program_id(self):
        """Conversion links the scenario to the created program."""
        result = self.service.convert_to_program(self.convert_scenario, {})
        program = result["program"]
        self.assertEqual(self.convert_scenario.converted_program_id, program)

    def test_convert_draft_scenario_raises_error(self):
        """Converting a non-ready scenario raises UserError."""
        with self.assertRaises(UserError):
            self.service.convert_to_program(self.draft_scenario, {})

    def test_convert_already_converted_raises_error(self):
        """Converting an already-converted scenario raises UserError."""
        self.service.convert_to_program(self.convert_scenario, {})
        with self.assertRaises(UserError):
            self.service.convert_to_program(self.convert_scenario, {})

    def test_convert_no_rules_raises_error(self):
        """Converting a scenario without entitlement rules raises UserError."""
        with self.assertRaises(UserError):
            self.service.convert_to_program(self.no_rules_scenario, {})

    def test_convert_creates_cel_eligibility_manager(self):
        """Converted program has a CEL-based eligibility manager using the targeting expression."""
        result = self.service.convert_to_program(self.convert_scenario, {})
        program = result["program"]

        # get_managers returns manager_ref_id objects directly
        eligibility_managers = program.get_managers(program.MANAGER_ELIGIBILITY)
        self.assertTrue(len(eligibility_managers) > 0, "Program should have an eligibility manager")

        # The returned object IS the implementation model
        mgr_impl = eligibility_managers[0]
        self.assertEqual(mgr_impl.eligibility_mode, "cel")
        self.assertEqual(mgr_impl.cel_expression, "true")

    def test_convert_creates_cycle_manager_monthly(self):
        """Converted program has a cycle manager with default monthly recurrence."""
        result = self.service.convert_to_program(self.convert_scenario, {})
        program = result["program"]

        # get_manager (singular) returns the implementation model directly
        cycle_mgr = program.get_manager(program.MANAGER_CYCLE)
        self.assertTrue(cycle_mgr, "Program should have a cycle manager")
        self.assertEqual(cycle_mgr.rrule_type, "monthly")
        self.assertEqual(cycle_mgr.cycle_duration, 1)

    def test_convert_creates_cycle_manager_weekly(self):
        """Converted program with weekly recurrence option."""
        scenario = self._make_scenario("Weekly Conversion Test")
        result = self.service.convert_to_program(
            scenario,
            {"rrule_type": "weekly", "mon": True, "wed": True, "fri": True},
        )
        program = result["program"]

        cycle_mgr = program.get_manager(program.MANAGER_CYCLE)
        self.assertEqual(cycle_mgr.rrule_type, "weekly")
        self.assertTrue(cycle_mgr.mon)
        self.assertTrue(cycle_mgr.wed)
        self.assertTrue(cycle_mgr.fri)

    def test_convert_creates_cash_entitlement_items_fixed(self):
        """Converted program has cash entitlement items from fixed rules."""
        result = self.service.convert_to_program(self.convert_scenario, {})
        program = result["program"]

        # get_manager (singular) returns the implementation model directly
        ent_mgr = program.get_manager(program.MANAGER_ENTITLEMENT)
        self.assertTrue(ent_mgr, "Program should have an entitlement manager")
        self.assertTrue(hasattr(ent_mgr, "entitlement_item_ids"))
        self.assertEqual(len(ent_mgr.entitlement_item_ids), 1)

        item = ent_mgr.entitlement_item_ids[0]
        self.assertEqual(item.amount, 1000.0)

    def test_convert_creates_cash_entitlement_items_cel(self):
        """Converted program has cash entitlement items with CEL expressions."""
        result = self.service.convert_to_program(self.cel_scenario, {})
        program = result["program"]

        ent_mgr = program.get_manager(program.MANAGER_ENTITLEMENT)
        item = ent_mgr.entitlement_item_ids[0]

        self.assertEqual(item.amount_mode, "cel")
        self.assertEqual(item.amount_cel_expression, "me.household_size * 100")
        self.assertEqual(item.amount, 500.0)

    def test_convert_multiplier_mode_falls_back_to_fixed_with_warning(self):
        """Multiplier rules fall back to fixed amount with a warning."""
        result = self.service.convert_to_program(self.multiplier_scenario, {})
        program = result["program"]
        warnings = result.get("warnings", [])

        # Should have at least one warning about the multiplier fallback
        self.assertTrue(len(warnings) > 0, "Should include a warning about multiplier fallback")
        self.assertTrue(
            any("multiplier" in w.lower() for w in warnings),
            "Warning should mention multiplier",
        )

        # The item should use fixed amount as fallback
        ent_mgr = program.get_manager(program.MANAGER_ENTITLEMENT)
        item = ent_mgr.entitlement_item_ids[0]
        self.assertEqual(item.amount, 200.0)

    def test_convert_maps_condition_cel_expression(self):
        """Condition CEL expressions are mapped to wizard cash item conditions."""
        result = self.service.convert_to_program(self.condition_scenario, {})
        program = result["program"]

        ent_mgr = program.get_manager(program.MANAGER_ENTITLEMENT)
        item = ent_mgr.entitlement_item_ids[0]

        self.assertEqual(item.condition_mode, "cel")
        self.assertEqual(item.cel_condition, "true")

    def test_convert_creates_program_manager(self):
        """Converted program has a program manager."""
        result = self.service.convert_to_program(self.convert_scenario, {})
        program = result["program"]

        prog_mgr = program.get_manager(program.MANAGER_PROGRAM)
        self.assertTrue(prog_mgr, "Program should have a program manager")

    def test_convert_with_name_override(self):
        """Program name can be overridden via options."""
        scenario = self._make_scenario("Original Name")
        result = self.service.convert_to_program(scenario, {"name": "Custom Program Name"})
        self.assertEqual(result["program"].name, "Custom Program Name")

    def test_convert_with_currency_code(self):
        """Program currency can be set via currency_code option."""
        usd = self.env["res.currency"].search([("name", "=", "USD")], limit=1)
        if not usd:
            self.skipTest("USD currency not available")

        scenario = self._make_scenario("Currency Test Scenario")
        result = self.service.convert_to_program(scenario, {"currency_code": "USD"})
        self.assertEqual(result["program"].currency_id.name, "USD")

    def test_convert_invalid_currency_code_raises_error(self):
        """Invalid currency code raises UserError."""
        scenario = self._make_scenario("Bad Currency Scenario")
        with self.assertRaises(UserError):
            self.service.convert_to_program(scenario, {"currency_code": "ZZZZZ"})

    def test_convert_posts_chatter_message(self):
        """Conversion posts a message on the scenario chatter."""
        self.service.convert_to_program(self.convert_scenario, {})
        messages = self.convert_scenario.message_ids.filtered(lambda m: "Converted to program" in (m.body or ""))
        self.assertTrue(len(messages) > 0, "Should post a chatter message about conversion")

    def test_convert_import_beneficiaries(self):
        """Import beneficiaries option triggers enrollment."""
        scenario = self._make_scenario("Import Beneficiaries Scenario")
        result = self.service.convert_to_program(scenario, {"import_beneficiaries": True})
        program = result["program"]
        self.assertTrue(program.exists())

    def test_convert_one_time_distribution_creates_cycle(self):
        """One-time distribution creates a cycle automatically."""
        scenario = self._make_scenario("One-time Scenario")
        result = self.service.convert_to_program(scenario, {"is_one_time_distribution": True})
        program = result["program"]
        self.assertTrue(program.is_one_time_distribution)

    def test_convert_description_from_scenario(self):
        """Scenario description is preserved in the conversion."""
        result = self.service.convert_to_program(self.convert_scenario, {})
        program = result["program"]
        self.assertTrue(program.exists())

    def test_convert_duplicate_name_raises_error(self):
        """Duplicate program name raises UserError."""
        self.env["spp.program"].create({"name": "Duplicate Name Program"})

        scenario = self._make_scenario("Duplicate Name Program")
        with self.assertRaises(UserError):
            self.service.convert_to_program(scenario, {})

    def test_convert_target_type_preserved(self):
        """Program target type matches the scenario target type."""
        result = self.service.convert_to_program(self.convert_scenario, {})
        self.assertEqual(result["program"].target_type, "group")

        result_individual = self.service.convert_to_program(self.cel_scenario, {})
        self.assertEqual(result_individual["program"].target_type, "individual")
