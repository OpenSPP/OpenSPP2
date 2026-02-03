# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for CEL integration in Create Program Wizard."""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCreateProgramWizardCEL(TransactionCase):
    """Tests for CEL eligibility and compliance in program creation wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.currency = cls.env.company.currency_id

        # Create test registrants
        cls.individual_registrant = cls.env["res.partner"].create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.group_registrant = cls.env["res.partner"].create(
            {
                "name": "Test Group",
                "is_registrant": True,
                "is_group": True,
            }
        )

    def _create_wizard(self, **kwargs):
        """Helper to create wizard with common defaults."""
        vals = {
            "name": "CEL Test Program",
            "rrule_type": "monthly",
            "eligibility_domain": "[]",
            "cycle_duration": 1,
            "currency_id": self.currency.id,
            "entitlement_type": "cash",
            "max_amount": 100.0,
        }
        vals.update(kwargs)
        return self.env["spp.program.create.wizard"].create(vals)

    # -------------------------------------------------------------------------
    # Eligibility CEL Tests
    # -------------------------------------------------------------------------
    def test_eligibility_cel_fields_exist(self):
        """Test that eligibility CEL fields are added to wizard."""
        wizard = self._create_wizard()
        self.assertTrue(hasattr(wizard, "eligibility_cel_expression"))
        self.assertTrue(hasattr(wizard, "eligibility_cel_preview_count"))
        self.assertTrue(hasattr(wizard, "eligibility_cel_is_valid"))
        self.assertTrue(hasattr(wizard, "eligibility_cel_error"))

    def test_eligibility_cel_empty_expression_valid(self):
        """Test that empty eligibility CEL expression is valid."""
        wizard = self._create_wizard(eligibility_cel_expression=False)
        # Empty expression should be valid (means all registrants eligible)
        self.assertTrue(wizard.eligibility_cel_is_valid)
        self.assertEqual(wizard.eligibility_cel_error, "")

    def test_eligibility_cel_simple_expression_valid(self):
        """Test simple valid CEL expression."""
        wizard = self._create_wizard(eligibility_cel_expression="r.is_registrant == true")
        # Force compute
        wizard._compute_eligibility_cel_preview()
        self.assertTrue(wizard.eligibility_cel_is_valid)
        self.assertGreaterEqual(wizard.eligibility_cel_preview_count, 1)

    def test_eligibility_cel_invalid_expression_error(self):
        """Test invalid CEL expression sets error."""
        wizard = self._create_wizard(eligibility_cel_expression="invalid_syntax{{{")
        wizard._compute_eligibility_cel_preview()
        self.assertFalse(wizard.eligibility_cel_is_valid)
        self.assertNotEqual(wizard.eligibility_cel_error, "")

    def test_eligibility_cel_profile_based_on_target_type(self):
        """Test that CEL profile changes based on target_type."""
        # Test individual target type
        wizard_individual = self._create_wizard(
            target_type="individual",
            eligibility_cel_expression="r.is_registrant == true",
        )
        wizard_individual._compute_eligibility_cel_preview()
        count_individual = wizard_individual.eligibility_cel_preview_count

        # Test group target type
        wizard_group = self._create_wizard(
            target_type="group",
            eligibility_cel_expression="r.is_registrant == true",
        )
        wizard_group._compute_eligibility_cel_preview()
        count_group = wizard_group.eligibility_cel_preview_count

        # Both should be valid
        self.assertTrue(wizard_individual.eligibility_cel_is_valid)
        self.assertTrue(wizard_group.eligibility_cel_is_valid)

        # Counts should include respective registrant types
        self.assertGreaterEqual(count_individual, 1)
        self.assertGreaterEqual(count_group, 1)

    # -------------------------------------------------------------------------
    # Compliance CEL Tests
    # -------------------------------------------------------------------------
    def test_compliance_cel_fields_exist(self):
        """Test that compliance CEL fields are added to wizard."""
        wizard = self._create_wizard()
        self.assertTrue(hasattr(wizard, "enable_compliance_cel"))
        self.assertTrue(hasattr(wizard, "compliance_cel_expression"))
        self.assertTrue(hasattr(wizard, "compliance_cel_preview_count"))
        self.assertTrue(hasattr(wizard, "compliance_cel_is_valid"))
        self.assertTrue(hasattr(wizard, "compliance_cel_error"))

    def test_compliance_disabled_by_default(self):
        """Test compliance is disabled by default."""
        wizard = self._create_wizard()
        self.assertFalse(wizard.enable_compliance_cel)

    def test_compliance_cel_enabled_valid_expression(self):
        """Test valid compliance CEL expression when enabled."""
        wizard = self._create_wizard(
            enable_compliance_cel=True,
            compliance_cel_expression="r.active == true",
        )
        wizard._compute_compliance_cel_preview()
        self.assertTrue(wizard.compliance_cel_is_valid)
        self.assertGreaterEqual(wizard.compliance_cel_preview_count, 0)

    def test_compliance_cel_disabled_expression_not_validated(self):
        """Test compliance expression not validated when disabled."""
        wizard = self._create_wizard(
            enable_compliance_cel=False,
            compliance_cel_expression="invalid_expression{{{",
        )
        wizard._compute_compliance_cel_preview()
        # Should still be valid because compliance is disabled
        self.assertTrue(wizard.compliance_cel_is_valid)

    def test_compliance_cel_required_when_enabled(self):
        """Test compliance expression required when enabled."""
        wizard = self._create_wizard(
            enable_compliance_cel=True,
            compliance_cel_expression=False,
        )
        # Add cash item to avoid that validation error
        wizard.write(
            {
                "entitlement_cash_item_ids": [
                    (0, 0, {"amount": 50.0}),
                ],
            }
        )

        with self.assertRaisesRegex(
            UserError,
            "Compliance CEL expression is required",
        ):
            wizard._check_required_fields()

    # -------------------------------------------------------------------------
    # Manager Creation Tests
    # -------------------------------------------------------------------------
    def test_eligibility_manager_gets_cel_expression(self):
        """Test eligibility manager receives CEL expression."""
        wizard = self._create_wizard(eligibility_cel_expression="r.is_registrant == true")

        # Create a program
        program = self.env["spp.program"].create(
            {
                "name": "Test CEL Program",
                "target_type": "individual",
            }
        )

        # Get eligibility manager vals
        vals = wizard._get_default_eligibility_manager_val(program.id)

        self.assertEqual(vals.get("eligibility_mode"), "cel")
        self.assertEqual(vals.get("cel_expression"), "r.is_registrant == true")

    def test_eligibility_manager_no_cel_without_expression(self):
        """Test eligibility manager doesn't get CEL mode without expression."""
        wizard = self._create_wizard(eligibility_cel_expression=False)

        program = self.env["spp.program"].create(
            {
                "name": "Test No CEL Program",
                "target_type": "individual",
            }
        )

        vals = wizard._get_default_eligibility_manager_val(program.id)

        # Should not set CEL mode
        self.assertNotEqual(vals.get("eligibility_mode"), "cel")

    def test_compliance_manager_created_when_enabled(self):
        """Test a dedicated compliance manager is created when enabled.

        Compliance is now handled by a separate spp.compliance.manager.default,
        not on the eligibility manager.
        """
        wizard = self._create_wizard(
            eligibility_cel_expression="r.is_registrant == true",
            enable_compliance_cel=True,
            compliance_cel_expression="r.active == true",
        )

        # Create a program
        program = self.env["spp.program"].create(
            {
                "name": "Test Compliance CEL Program",
                "target_type": "individual",
            }
        )

        # Get eligibility manager vals - should NOT include compliance (separate manager)
        vals = wizard._get_default_eligibility_manager_val(program.id)

        # Verify eligibility CEL is set but NOT compliance CEL (separate manager now)
        self.assertEqual(vals.get("eligibility_mode"), "cel")
        self.assertEqual(vals.get("cel_expression"), "r.is_registrant == true")
        # Compliance is now on a separate manager, not on eligibility
        self.assertIsNone(vals.get("compliance_cel_mode"))
        self.assertIsNone(vals.get("compliance_cel_expression"))

    def test_eligibility_manager_no_compliance_cel_when_disabled(self):
        """Test eligibility manager doesn't get compliance CEL when disabled."""
        wizard = self._create_wizard(
            eligibility_cel_expression="r.is_registrant == true",
            enable_compliance_cel=False,
        )

        program = self.env["spp.program"].create(
            {
                "name": "Test No Compliance CEL Program",
                "target_type": "individual",
            }
        )

        vals = wizard._get_default_eligibility_manager_val(program.id)

        # Verify eligibility CEL is set but not compliance CEL
        self.assertEqual(vals.get("eligibility_mode"), "cel")
        self.assertEqual(vals.get("cel_expression"), "r.is_registrant == true")
        self.assertIsNone(vals.get("compliance_cel_mode"))
        self.assertIsNone(vals.get("compliance_cel_expression"))

    def test_eligibility_and_compliance_use_separate_managers(self):
        """Test that eligibility and compliance use separate manager models.

        Eligibility is handled by spp.program.membership.manager.default.
        Compliance is handled by spp.compliance.manager.default.
        This ensures non-compliant registrants are still enrolled but flagged, not excluded.
        """
        # Create program with separate eligibility and compliance managers
        program = self.env["spp.program"].create(
            {
                "name": "Test Separate Managers Program",
                "target_type": "individual",
            }
        )

        # Create eligibility manager
        eligibility_manager = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Test Eligibility Manager",
                "program_id": program.id,
                "eligibility_mode": "cel",
                "cel_expression": "r.is_registrant == true",
            }
        )

        # Create dedicated compliance manager
        compliance_manager = self.env["spp.compliance.manager.default"].create(
            {
                "name": "Test Compliance Manager",
                "program_id": program.id,
                "compliance_cel_expression": "r.active == true",
            }
        )

        # Eligibility manager's _prepare_eligible_domain should use eligibility CEL
        eligible_domain = eligibility_manager._prepare_eligible_domain()
        self.assertIsInstance(eligible_domain, list)

        # Compliance manager's get_compliance_domain should use compliance CEL
        compliance_domain = compliance_manager.get_compliance_domain()
        self.assertIsInstance(compliance_domain, list)

        # They are different models with different domain methods
        self.assertNotEqual(
            eligibility_manager._name,
            compliance_manager._name,
            "Eligibility and compliance should be separate model types",
        )

    # -------------------------------------------------------------------------
    # Validation Tests
    # -------------------------------------------------------------------------
    def test_check_required_fields_invalid_eligibility_cel(self):
        """Test validation fails for invalid eligibility CEL."""
        wizard = self._create_wizard(eligibility_cel_expression="invalid_syntax{{{")
        wizard._compute_eligibility_cel_preview()
        # Add cash item to avoid that validation error
        wizard.write(
            {
                "entitlement_cash_item_ids": [
                    (0, 0, {"amount": 50.0}),
                ],
            }
        )

        with self.assertRaisesRegex(
            UserError,
            "Eligibility CEL expression is invalid",
        ):
            wizard._check_required_fields()

    def test_check_required_fields_invalid_compliance_cel(self):
        """Test validation fails for invalid compliance CEL."""
        wizard = self._create_wizard(
            enable_compliance_cel=True,
            compliance_cel_expression="invalid_syntax{{{",
        )
        wizard._compute_compliance_cel_preview()
        # Add cash item to avoid that validation error
        wizard.write(
            {
                "entitlement_cash_item_ids": [
                    (0, 0, {"amount": 50.0}),
                ],
            }
        )

        with self.assertRaisesRegex(
            UserError,
            "Compliance CEL expression is invalid",
        ):
            wizard._check_required_fields()

    # -------------------------------------------------------------------------
    # Preview Action Tests
    # -------------------------------------------------------------------------
    def test_action_preview_eligibility_no_expression(self):
        """Test preview action raises error without expression."""
        wizard = self._create_wizard(eligibility_cel_expression=False)

        with self.assertRaisesRegex(
            UserError,
            "Please enter a CEL expression first",
        ):
            wizard.action_preview_eligibility()

    def test_action_preview_eligibility_invalid_expression(self):
        """Test preview action raises error for invalid expression."""
        wizard = self._create_wizard(eligibility_cel_expression="invalid{{{")
        wizard._compute_eligibility_cel_preview()

        with self.assertRaisesRegex(
            UserError,
            "Cannot preview invalid expression",
        ):
            wizard.action_preview_eligibility()

    def test_action_preview_eligibility_returns_action(self):
        """Test preview action returns proper window action.

        The preview action reloads the wizard form to show preview results inline,
        so it returns the wizard model, not res.partner.
        """
        wizard = self._create_wizard(eligibility_cel_expression="r.is_registrant == true")
        wizard._compute_eligibility_cel_preview()

        action = wizard.action_preview_eligibility()

        self.assertEqual(action.get("type"), "ir.actions.act_window")
        # Preview reloads the wizard form to show inline preview
        self.assertEqual(action.get("res_model"), "spp.program.create.wizard")
        self.assertEqual(action.get("res_id"), wizard.id)
        # Preview partners should be populated
        self.assertTrue(wizard.is_previewing)
        self.assertTrue(len(wizard.eligibility_preview_partner_ids) > 0)


@tagged("post_install", "-at_install")
class TestCreateProgramWizardCashItemCEL(TransactionCase):
    """Tests for CEL in cash entitlement items."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.currency = cls.env.company.currency_id

        # Create base wizard
        cls.wizard = cls.env["spp.program.create.wizard"].create(
            {
                "name": "Cash CEL Test Program",
                "rrule_type": "monthly",
                "eligibility_domain": "[]",
                "cycle_duration": 1,
                "currency_id": cls.currency.id,
                "entitlement_type": "cash",
                "max_amount": 500.0,
            }
        )

        # Create test registrant
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Test Cash Beneficiary",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def _create_cash_item(self, **kwargs):
        """Helper to create cash item with defaults."""
        vals = {
            "amount": 100.0,
            "currency_id": self.currency.id,
            "program_id": self.wizard.id,
        }
        vals.update(kwargs)
        return self.env["spp.program.create.wizard.entitlement.cash.item"].create(vals)

    def test_cash_item_cel_fields_exist(self):
        """Test cash item has CEL fields."""
        item = self._create_cash_item()
        self.assertTrue(hasattr(item, "amount_mode"))
        self.assertTrue(hasattr(item, "amount_cel_expression"))
        self.assertTrue(hasattr(item, "has_condition"))
        self.assertTrue(hasattr(item, "condition_mode"))
        self.assertTrue(hasattr(item, "cel_condition"))

    def test_cash_item_fixed_mode_default(self):
        """Test cash item defaults to fixed mode."""
        item = self._create_cash_item()
        self.assertEqual(item.amount_mode, "fixed")

    def test_cash_item_cel_amount_valid_formula(self):
        """Test valid CEL amount formula."""
        item = self._create_cash_item(
            amount_mode="cel",
            amount_cel_expression="r.household_size * 100",
        )
        item._compute_amount_cel_preview()
        self.assertTrue(item.amount_cel_is_valid)

    def test_cash_item_cel_amount_invalid_formula(self):
        """Test invalid CEL amount formula."""
        item = self._create_cash_item(
            amount_mode="cel",
            amount_cel_expression="invalid{{syntax",
        )
        item._compute_amount_cel_preview()
        self.assertFalse(item.amount_cel_is_valid)
        self.assertNotEqual(item.amount_cel_error, "")

    def test_cash_item_condition_disabled_by_default(self):
        """Test condition is disabled by default."""
        item = self._create_cash_item()
        self.assertFalse(item.has_condition)

    def test_cash_item_cel_condition_valid(self):
        """Test valid CEL condition."""
        item = self._create_cash_item(
            has_condition=True,
            condition_mode="cel",
            cel_condition="r.is_registrant == true",
        )
        item._compute_condition_cel_preview()
        self.assertTrue(item.cel_is_valid)
        self.assertGreaterEqual(item.cel_preview_count, 0)

    def test_cash_item_cel_condition_invalid(self):
        """Test invalid CEL condition."""
        item = self._create_cash_item(
            has_condition=True,
            condition_mode="cel",
            cel_condition="invalid{{syntax",
        )
        item._compute_condition_cel_preview()
        self.assertFalse(item.cel_is_valid)
        self.assertNotEqual(item.cel_error, "")


@tagged("post_install", "-at_install")
class TestCreateProgramWizardInKindItemCEL(TransactionCase):
    """Tests for CEL in in-kind entitlement items."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.currency = cls.env.company.currency_id

        # Create product for in-kind
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test In-Kind Product",
                "type": "consu",
            }
        )

        # Create base wizard
        cls.wizard = cls.env["spp.program.create.wizard"].create(
            {
                "name": "InKind CEL Test Program",
                "rrule_type": "monthly",
                "eligibility_domain": "[]",
                "cycle_duration": 1,
                "currency_id": cls.currency.id,
                "entitlement_type": "inkind",
            }
        )

        # Create test registrant
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Test InKind Beneficiary",
                "is_registrant": True,
                "is_group": True,
            }
        )

    def _create_inkind_item(self, **kwargs):
        """Helper to create in-kind item with defaults."""
        vals = {
            "product_id": self.product.id,
            "quantity": 5.0,
            "program_id": self.wizard.id,
        }
        vals.update(kwargs)
        return self.env["spp.program.create.wizard.entitlement.item"].create(vals)

    def test_inkind_item_cel_fields_exist(self):
        """Test in-kind item has CEL fields."""
        item = self._create_inkind_item()
        self.assertTrue(hasattr(item, "quantity_mode"))
        self.assertTrue(hasattr(item, "quantity_cel_expression"))
        self.assertTrue(hasattr(item, "has_condition"))
        self.assertTrue(hasattr(item, "condition_mode"))
        self.assertTrue(hasattr(item, "condition_cel_expression"))

    def test_inkind_item_fixed_mode_default(self):
        """Test in-kind item defaults to fixed mode."""
        item = self._create_inkind_item()
        self.assertEqual(item.quantity_mode, "fixed")

    def test_inkind_item_cel_quantity_valid_formula(self):
        """Test valid CEL quantity formula."""
        item = self._create_inkind_item(
            quantity_mode="cel",
            quantity_cel_expression="r.household_size * 2",
        )
        item._compute_quantity_cel_preview()
        self.assertTrue(item.quantity_cel_is_valid)

    def test_inkind_item_cel_quantity_invalid_formula(self):
        """Test invalid CEL quantity formula."""
        item = self._create_inkind_item(
            quantity_mode="cel",
            quantity_cel_expression="invalid{{syntax",
        )
        item._compute_quantity_cel_preview()
        self.assertFalse(item.quantity_cel_is_valid)
        self.assertNotEqual(item.quantity_cel_error, "")

    def test_inkind_item_condition_disabled_by_default(self):
        """Test condition is disabled by default."""
        item = self._create_inkind_item()
        self.assertFalse(item.has_condition)

    def test_inkind_item_cel_condition_valid(self):
        """Test valid CEL condition."""
        item = self._create_inkind_item(
            has_condition=True,
            condition_mode="cel",
            condition_cel_expression="r.is_registrant == true",
        )
        item._compute_condition_cel_preview()
        self.assertTrue(item.condition_cel_is_valid)
        self.assertGreaterEqual(item.condition_cel_preview_count, 0)

    def test_inkind_item_cel_condition_invalid(self):
        """Test invalid CEL condition."""
        item = self._create_inkind_item(
            has_condition=True,
            condition_mode="cel",
            condition_cel_expression="invalid{{syntax",
        )
        item._compute_condition_cel_preview()
        self.assertFalse(item.condition_cel_is_valid)
        self.assertNotEqual(item.condition_cel_error, "")
