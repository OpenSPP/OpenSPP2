# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for registry variable activation and field population.

These tests verify:
1. Standard variables from spp_studio are activated on module install
2. Demo-specific variables are activated on module install
3. Income and disability fields are populated by the generator
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRegistryVariableActivation(TransactionCase):
    """Test registry variable activation during module installation."""

    def test_standard_variables_activated(self):
        """Test that standard variables from spp_studio are activated."""
        from odoo.addons.spp_mis_demo_v2.models.indicator_providers import (
            STANDARD_VARIABLES,
        )

        Variable = self.env["spp.cel.variable"]

        for xml_id in STANDARD_VARIABLES:
            variable = self.env.ref(xml_id, raise_if_not_found=False)
            if variable:
                self.assertEqual(
                    variable.state,
                    "active",
                    f"Standard variable {xml_id} should be active, got {variable.state}",
                )

    def test_demo_variables_activated(self):
        """Test that demo-specific variables are activated."""
        from odoo.addons.spp_mis_demo_v2.models.indicator_providers import (
            DEMO_VARIABLES,
        )

        for xml_id in DEMO_VARIABLES:
            variable = self.env.ref(xml_id, raise_if_not_found=False)
            if variable:
                self.assertEqual(
                    variable.state,
                    "active",
                    f"Demo variable {xml_id} should be active, got {variable.state}",
                )

    def test_key_variables_exist_and_active(self):
        """Test that key variables used in CEL expressions exist and are active."""
        key_variables = [
            # Used in Universal Child Grant
            "spp_studio.var_child_count",
            "spp_mis_demo_v2.var_base_child_grant",
            # Used in Elderly Social Pension
            "spp_studio.var_age",
            "spp_studio.var_retirement_age",
            # Used in Emergency Relief Fund
            "spp_studio.var_dependency_ratio",
            "spp_studio.var_is_female_headed",
            "spp_studio.var_elderly_count",
            # Used in Cash Transfer Program
            "spp_studio.var_hh_total_income",
            "spp_studio.var_poverty_line",
            "spp_studio.var_hh_size",
            # Used in Disability Support Grant
            "spp_studio.var_has_disabled_member",
        ]

        for xml_id in key_variables:
            variable = self.env.ref(xml_id, raise_if_not_found=False)
            self.assertTrue(
                variable,
                f"Key variable {xml_id} should exist",
            )
            if variable:
                self.assertEqual(
                    variable.state,
                    "active",
                    f"Key variable {xml_id} should be active for CEL expressions to work",
                )

    def test_variable_activation_idempotent(self):
        """Test that activating already-active variables doesn't cause errors."""
        from odoo.addons.spp_mis_demo_v2.models.indicator_providers import (
            DEMO_VARIABLES,
            _activate_variables,
        )

        # Run activation again (variables should already be active)
        activated, skipped, errors = _activate_variables(self.env, DEMO_VARIABLES, "Test")

        # Should have no errors
        self.assertEqual(len(errors), 0, f"Re-activation should not cause errors: {errors}")
        # All should be skipped (already active)
        self.assertEqual(
            skipped,
            len(DEMO_VARIABLES),
            "All variables should be skipped as already active",
        )
        self.assertEqual(activated, 0, "No variables should need activation")

    def test_activate_variables_handles_missing_gracefully(self):
        """Test that _activate_variables handles missing variables gracefully."""
        from odoo.addons.spp_mis_demo_v2.models.indicator_providers import (
            _activate_variables,
        )

        # Try to activate non-existent variables
        fake_xml_ids = [
            "spp_mis_demo_v2.var_nonexistent_1",
            "spp_mis_demo_v2.var_nonexistent_2",
        ]

        activated, skipped, errors = _activate_variables(self.env, fake_xml_ids, "Test")

        # Should not raise, just log warnings
        self.assertEqual(activated, 0)
        self.assertEqual(len(errors), 0)  # Missing vars are warnings, not errors


@tagged("post_install", "-at_install")
class TestGeneratorFieldPopulation(TransactionCase):
    """Test that the generator populates income and disability fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_country = cls.env.ref("base.us")

    def test_create_individual_member_sets_income(self):
        """Test _create_individual_member sets income from income param."""
        from datetime import date

        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Income",
                "locale_origin": self.test_country.id,
            }
        )

        member_data = {
            "name": "Test Income Person",
            "gender": "male",
            "age": 35,
            "income": 5000,
        }

        registration_date = date.today()
        member = generator._create_individual_member(member_data, registration_date)

        self.assertEqual(
            member.income,
            5000.0,
            "income should be set from income parameter",
        )

    def test_create_individual_member_defaults(self):
        """Test _create_individual_member with minimal data."""
        from datetime import date

        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Defaults",
                "locale_origin": self.test_country.id,
            }
        )

        member_data = {
            "name": "Test Minimal Person",
            "age": 25,
        }

        registration_date = date.today()
        member = generator._create_individual_member(member_data, registration_date)

        # Should not have income set
        self.assertEqual(member.income, 0.0, "income should default to 0")

    def test_random_individual_has_income_for_adults(self):
        """Test _create_random_individual sets income for adults."""
        from datetime import date

        try:
            from faker import Faker
        except ImportError:
            self.skipTest("faker not installed")

        fake = Faker()
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Random Income",
                "locale_origin": self.test_country.id,
            }
        )

        registration_date = date.today()

        # Create adult (age >= 18) - should have income
        adult = generator._create_random_individual(fake, "John Smith", "male", 35, registration_date, [])
        self.assertGreater(
            adult.income,
            0,
            "Adult should have income set",
        )
        self.assertLessEqual(
            adult.income,
            8000,
            "income should be within expected range",
        )

    def test_random_individual_no_income_for_children(self):
        """Test _create_random_individual doesn't set income for children."""
        from datetime import date

        try:
            from faker import Faker
        except ImportError:
            self.skipTest("faker not installed")

        fake = Faker()
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Child Income",
                "locale_origin": self.test_country.id,
            }
        )

        registration_date = date.today()

        # Create child (age < 18) - should not have income
        child = generator._create_random_individual(fake, "Jane Smith", "female", 10, registration_date, [])
        self.assertEqual(
            child.income,
            0.0,
            "Child should not have income set",
        )

    def test_income_distribution_tiers(self):
        """Test that income is distributed across expected tiers.

        Expected: 70% low (500-2000), 25% moderate (2000-4000), 5% high (4000-8000)
        """
        from datetime import date

        try:
            from faker import Faker
        except ImportError:
            self.skipTest("faker not installed")

        fake = Faker()
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Income Tiers",
                "locale_origin": self.test_country.id,
            }
        )

        registration_date = date.today()
        sample_size = 100
        low_count = 0
        moderate_count = 0
        high_count = 0

        for i in range(sample_size):
            member = generator._create_random_individual(fake, f"Person{i} Test", "male", 30, registration_date, [])
            income = member.income
            if income <= 2000:
                low_count += 1
            elif income <= 4000:
                moderate_count += 1
            else:
                high_count += 1

        # Check low tier is majority (allow for variance)
        self.assertGreater(
            low_count,
            sample_size * 0.5,  # At least 50% low income
            f"Low income tier ({low_count}/{sample_size}) should be majority",
        )


