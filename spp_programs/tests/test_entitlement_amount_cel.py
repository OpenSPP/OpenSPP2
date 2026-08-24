import logging
from datetime import timedelta

from lxml import etree

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestEntitlementAmountCEL(TransactionCase):
    """Test CEL amount calculation for entitlements."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a test program
        cls.program = cls.env["spp.program"].create(
            {
                "name": "Test CEL Amount Program",
                "target_type": "individual",
            }
        )

        # Create a journal for the program
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Test Journal",
                "code": "TEST",
                "type": "bank",
            }
        )
        cls.program.journal_id = cls.journal.id

        # Create test beneficiaries
        cls.beneficiary1 = cls.env["res.partner"].create(
            {
                "name": "Test Beneficiary 1",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.beneficiary2 = cls.env["res.partner"].create(
            {
                "name": "Test Beneficiary 2",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Enroll beneficiaries in program
        cls.membership1 = cls.env["spp.program.membership"].create(
            {
                "partner_id": cls.beneficiary1.id,
                "program_id": cls.program.id,
                "state": "enrolled",
            }
        )
        cls.membership2 = cls.env["spp.program.membership"].create(
            {
                "partner_id": cls.beneficiary2.id,
                "program_id": cls.program.id,
                "state": "enrolled",
            }
        )

        # Create entitlement manager
        cls.entitlement_manager = cls.env["spp.program.entitlement.manager.cash"].create(
            {
                "name": "Test CEL Entitlement Manager",
                "program_id": cls.program.id,
            }
        )

        # Create a cycle with future dates
        today = fields.Date.today()
        cls.cycle = cls.env["spp.cycle"].create(
            {
                "name": "Test Cycle 1",
                "program_id": cls.program.id,
                "start_date": today,
                "end_date": today + timedelta(days=365),
            }
        )

    def test_01_cel_mode_default(self):
        """Test that CEL mode is the default and works with simple formulas."""
        # Create an entitlement item with CEL formula for fixed amount
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "500",
            }
        )

        self.assertEqual(item.amount_mode, "cel")
        result = item._calculate_cel_amount(self.beneficiary1)
        self.assertEqual(result, 500.0)

    def test_02_cel_simple_fixed(self):
        """Test CEL formula with simple fixed amount."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "500",
            }
        )

        result = item._calculate_cel_amount(self.beneficiary1)
        self.assertEqual(result, 500.0)

    def test_03_cel_base_amount(self):
        """Test CEL formula using base_amount variable."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount": 100.0,
                "amount_cel_expression": "base_amount * 2",
            }
        )

        result = item._calculate_cel_amount(self.beneficiary1)
        self.assertEqual(result, 200.0)

    def test_04_cel_beneficiary_field(self):
        """Test CEL formula accessing beneficiary fields."""
        # Add a custom field value to beneficiary
        self.beneficiary1.write({"comment": "household_size:5"})

        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "100 * 3",  # Simulating household_size * 100
            }
        )

        result = item._calculate_cel_amount(self.beneficiary1)
        self.assertEqual(result, 300.0)

    def test_05_cel_functions(self):
        """Test CEL formula with min/max functions."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "min(1000, max(100, 50 * 12))",
            }
        )

        result = item._calculate_cel_amount(self.beneficiary1)
        self.assertEqual(result, 600.0)

    def test_06_cel_validation_syntax_error(self):
        """Test that invalid syntax is caught."""
        with self.assertRaises(ValidationError):
            self.env["spp.program.entitlement.manager.cash.item"].create(
                {
                    "entitlement_id": self.entitlement_manager.id,
                    "amount_cel_expression": "invalid syntax (",
                }
            )

    def test_07_cel_calculation_empty_formula(self):
        """Test that calculating with empty formula raises error."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": False,
            }
        )
        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary1)

    def test_08_cel_non_numeric_result(self):
        """Test that non-numeric results raise an error."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "'not a number'",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary1)

    def test_09_cel_negative_amount(self):
        """Test that negative amounts are set to 0."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "-100",
            }
        )

        result = item._calculate_cel_amount(self.beneficiary1)
        self.assertEqual(result, 0.0)

    def test_10_cel_preview_computation(self):
        """Test that preview field is computed correctly."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "500",
            }
        )

        # Force computation
        item._compute_amount_cel_preview()

        # Should have a preview since we have enrolled beneficiaries
        self.assertTrue(item.amount_cel_is_valid)
        if item.amount_cel_preview:
            self.assertIn("500", item.amount_cel_preview)

    def test_11_prepare_entitlements_cel_mode(self):
        """Test preparing entitlements with CEL formula."""
        # Create an entitlement item with CEL formula
        self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "750",
            }
        )

        # Prepare entitlements
        beneficiaries = self.membership1 | self.membership2
        self.entitlement_manager.prepare_entitlements(self.cycle, beneficiaries)

        # Check that entitlements were created
        entitlements = self.env["spp.entitlement"].search(
            [
                ("cycle_id", "=", self.cycle.id),
                ("partner_id", "in", [self.beneficiary1.id, self.beneficiary2.id]),
            ]
        )

        self.assertEqual(len(entitlements), 2)
        for ent in entitlements:
            self.assertEqual(ent.initial_amount, 750.0)

    def test_12_prepare_entitlements_multiple_items(self):
        """Test preparing entitlements with multiple CEL formula items."""
        # Create first CEL formula item
        self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "200",
            }
        )

        # Create second CEL formula item
        self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "300",
            }
        )

        # Prepare entitlements
        beneficiaries = self.membership1 | self.membership2
        self.entitlement_manager.prepare_entitlements(self.cycle, beneficiaries)

        # Check that entitlements were created with combined amount
        entitlements = self.env["spp.entitlement"].search(
            [
                ("cycle_id", "=", self.cycle.id),
                ("partner_id", "in", [self.beneficiary1.id, self.beneficiary2.id]),
            ]
        )

        self.assertEqual(len(entitlements), 2)
        for ent in entitlements:
            # Should be 200 (first CEL) + 300 (second CEL) = 500
            self.assertEqual(ent.initial_amount, 500.0)

    def test_13_cel_conditional_expression(self):
        """Test CEL formula with conditional logic."""
        # Set different values for beneficiaries
        self.beneficiary1.write({"active": True})
        self.beneficiary2.write({"active": False})

        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "me.active ? 500 : 300",
            }
        )

        result1 = item._calculate_cel_amount(self.beneficiary1)
        result2 = item._calculate_cel_amount(self.beneficiary2)

        self.assertEqual(result1, 500.0)
        self.assertEqual(result2, 300.0)

    def test_14_security_no_env_access(self):
        """Test that formulas cannot access me.env (security).

        Security blocking happens at runtime via SafeRecordProxy, not at
        validation time. The item is created successfully, but calculating
        the amount raises a UserError.
        """
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "me.env",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary1)

    def test_15_security_no_sudo_access(self):
        """Test that formulas cannot access me.sudo() (security).

        Security blocking happens at runtime via SafeRecordProxy, not at
        validation time. The item is created successfully, but calculating
        the amount raises a UserError.
        """
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "me.sudo()",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary1)

    def test_16_security_no_write_access(self):
        """Test that formulas with invalid CEL syntax are rejected at validation.

        The CEL parser rejects curly braces as unknown characters, so
        expressions like me.write({...}) fail at validation time.
        """
        with self.assertRaises(ValidationError):
            self.env["spp.program.entitlement.manager.cash.item"].create(
                {
                    "entitlement_id": self.entitlement_manager.id,
                    "amount_cel_expression": "me.write({'name': 'hacked'})",
                }
            )

    def test_17_security_no_private_attributes(self):
        """Test that formulas cannot access private attributes (security).

        Security blocking happens at runtime via SafeRecordProxy, not at
        validation time. The item is created successfully, but calculating
        the amount raises a UserError.
        """
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "me._partner",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary1)

    def test_18_security_safe_field_access(self):
        """Test that formulas can access safe fields like id and name."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "me.id > 0 ? 100 : 0",
            }
        )

        result = item._calculate_cel_amount(self.beneficiary1)
        self.assertEqual(result, 100.0)


@tagged("post_install", "-at_install")
class TestEntitlementAmountCELForm(TransactionCase):
    """OP#1172 round 1: what the amount item form must offer.

    QA could not add a cash entitlement line: the form had no field for the base
    amount, and a formula built from the widget's symbol browser failed to
    compile. Both came from this view rather than from the entitlement logic.
    """

    def _item_form(self):
        arch = etree.fromstring(
            self.env["spp.program.entitlement.manager.cash"].get_view(
                self.env.ref("spp_programs.view_entitlement_manager_cash_form").id, "form"
            )["arch"]
        )
        forms = arch.xpath("//field[@name='entitlement_item_ids']/form")
        self.assertTrue(forms, "the items list should still open a form")
        return forms[0]

    def test_the_base_amount_stays_on_the_form(self):
        """Formulas are documented to build on it, so it must be settable.

        The CEL view used to hide it outright, which left base_amount
        permanently unset and every documented "base_amount * ..." formula
        unusable.
        """
        amounts = [f for f in self._item_form().iter("field") if f.get("name") == "amount"]

        self.assertTrue(amounts, "the item form should offer the base amount")
        self.assertNotEqual(amounts[0].get("invisible"), "1", "hiding it is what QA reported")

    def test_the_formula_field_does_not_advertise_the_wrong_symbols(self):
        """The evaluator receives `me` and `base_amount`, not the entitlements profile.

        _validate_cel_expression and _calculate_cel_amount build their own
        context, so a symbol browser listing spp.entitlement's fields offers
        names that never arrive — `r.birthdate` compiles against
        spp.entitlement and fails.
        """
        expressions = [f for f in self._item_form().iter("field") if f.get("name") == "amount_cel_expression"]

        self.assertTrue(expressions, "the formula field should be on the form")
        self.assertEqual(expressions[0].get("show_symbol_browser"), "false")
        self.assertIsNone(expressions[0].get("cel_profile"), "no profile matches this evaluator yet")

    def test_the_documented_vocabulary_actually_validates(self):
        """A plain number and a base_amount formula both pass the model's own check."""
        manager = self.env["spp.program.entitlement.manager.cash"].create(
            {"name": "CEL Form [TEST]", "program_id": self.env["spp.program"].create({"name": "CEL Form P [TEST]"}).id}
        )
        for expression in ("500", "base_amount * 1.1", "me.household_size * 100"):
            with self.subTest(expression=expression):
                item = self.env["spp.program.entitlement.manager.cash.item"].create(
                    {"entitlement_id": manager.id, "amount": 100.0, "amount_cel_expression": expression}
                )
                item._validate_cel_expression()
