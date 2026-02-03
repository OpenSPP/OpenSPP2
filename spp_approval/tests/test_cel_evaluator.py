"""Tests for CEL expression evaluator."""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCELEvaluator(TransactionCase):
    """Test cases for CEL expression evaluation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.evaluator = cls.env["spp.cel.evaluator"]

        # Create test partner for evaluation context
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "email": "test@example.com",
                "is_company": True,
            }
        )

    def test_is_available(self):
        """Test CEL availability check."""
        # Should return True if cel-python is installed, False otherwise
        result = self.evaluator.is_available()
        self.assertIsInstance(result, bool)

    def test_validate_empty_expression(self):
        """Test validation of empty expression."""
        result = self.evaluator.validate("")
        self.assertTrue(result["valid"])
        self.assertIsNone(result["error"])

    def test_validate_none_expression(self):
        """Test validation of None expression."""
        result = self.evaluator.validate(None)
        self.assertTrue(result["valid"])

    def test_evaluate_empty_expression(self):
        """Test evaluation of empty expression returns True."""
        result = self.evaluator.evaluate("", self.partner)
        self.assertTrue(result)

    def test_evaluate_none_expression(self):
        """Test evaluation of None expression returns True."""
        result = self.evaluator.evaluate(None, self.partner)
        self.assertTrue(result)


@tagged("post_install", "-at_install")
class TestCELEvaluatorWithLibrary(TransactionCase):
    """Test cases for CEL expression evaluation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.evaluator = cls.env["spp.cel.evaluator"]

        # CEL is always available via spp_cel_domain
        if not cls.evaluator.is_available():
            raise cls.skipException("CEL evaluator not available")

        # Create test partner
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner CEL",
                "email": "cel@example.com",
                "is_company": True,
                "credit_limit": 5000.0,
            }
        )

        # Create test model reference
        cls.test_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

    def test_validate_valid_expression(self):
        """Test validation of valid CEL expression."""
        result = self.evaluator.validate("record.id > 0")
        self.assertTrue(result["valid"])
        self.assertIsNone(result["error"])

    def test_validate_invalid_expression(self):
        """Test validation of invalid CEL expression."""
        result = self.evaluator.validate("record.id > ")
        self.assertFalse(result["valid"])
        self.assertIsNotNone(result["error"])

    def test_evaluate_simple_comparison(self):
        """Test evaluation of simple comparison."""
        result = self.evaluator.evaluate("record.id > 0", self.partner)
        self.assertTrue(result)

    def test_evaluate_string_comparison(self):
        """Test evaluation of string comparison."""
        result = self.evaluator.evaluate('record.name == "Test Partner CEL"', self.partner)
        self.assertTrue(result)

    def test_evaluate_boolean_logic(self):
        """Test evaluation of boolean logic."""
        result = self.evaluator.evaluate("record.id > 0 and record.is_company == true", self.partner)
        self.assertTrue(result)

    def test_evaluate_numeric_comparison(self):
        """Test evaluation of numeric comparison."""
        result = self.evaluator.evaluate("record.credit_limit > 1000", self.partner)
        self.assertTrue(result)

    def test_evaluate_false_condition(self):
        """Test evaluation of condition that returns false."""
        result = self.evaluator.evaluate("record.id < 0", self.partner)
        self.assertFalse(result)

    def test_evaluate_user_context(self):
        """Test that user context is available."""
        result = self.evaluator.evaluate("user.id > 0", self.partner)
        self.assertTrue(result)

    def test_evaluate_company_context(self):
        """Test that company context is available."""
        result = self.evaluator.evaluate("company.id > 0", self.partner)
        self.assertTrue(result)


@tagged("post_install", "-at_install")
class TestApprovalDefinitionCEL(TransactionCase):
    """Test cases for approval definition CEL integration."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.evaluator = cls.env["spp.cel.evaluator"]

        # Create test model reference
        cls.test_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

        # Create test user
        cls.test_user = cls.env["res.users"].create(
            {
                "name": "CEL Test User",
                "login": "cel_test_user",
                "email": "cel_test@example.com",
            }
        )

        # Create test partner
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner Definition",
                "user_id": cls.test_user.id,
            }
        )

    def test_definition_without_cel(self):
        """Test definition without CEL expressions works normally."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "Non-CEL Definition",
                "model_id": self.test_model.id,
                "approval_type": "user",
                "approval_user_ids": [(4, self.test_user.id)],
            }
        )

        # Should use standard domain matching
        result = definition.matches_record(self.partner)
        self.assertTrue(result)

    def test_definition_with_cel_condition(self):
        """Test definition with CEL condition."""
        if not self.evaluator.is_available():
            self.skipTest("CEL library not installed")

        definition = self.env["spp.approval.definition"].create(
            {
                "name": "CEL Condition Definition",
                "model_id": self.test_model.id,
                "approval_type": "user",
                "approval_user_ids": [(4, self.test_user.id)],
                "use_cel_condition": True,
                "cel_condition": "record.id > 0",
            }
        )

        result = definition.matches_record(self.partner)
        self.assertTrue(result)

    def test_definition_cel_condition_false(self):
        """Test definition with CEL condition that returns false."""
        if not self.evaluator.is_available():
            self.skipTest("CEL library not installed")

        definition = self.env["spp.approval.definition"].create(
            {
                "name": "CEL False Condition",
                "model_id": self.test_model.id,
                "approval_type": "user",
                "approval_user_ids": [(4, self.test_user.id)],
                "use_cel_condition": True,
                "cel_condition": "record.id < 0",
            }
        )

        result = definition.matches_record(self.partner)
        self.assertFalse(result)

    def test_definition_cel_reviewer(self):
        """Test definition with CEL reviewer expression."""
        if not self.evaluator.is_available():
            self.skipTest("CEL library not installed")

        definition = self.env["spp.approval.definition"].create(
            {
                "name": "CEL Reviewer Definition",
                "model_id": self.test_model.id,
                "approval_type": "user",
                "approval_user_ids": [(4, self.test_user.id)],
                "use_cel_reviewer": True,
                "cel_reviewer_expression": "record.user_id.id",
            }
        )

        approvers = definition.get_approvers(self.partner)
        # Should return the user_id of the partner
        self.assertIn(self.test_user, approvers)

    def test_definition_invalid_cel_raises_error(self):
        """Test that invalid CEL expression raises validation error."""
        if not self.evaluator.is_available():
            self.skipTest("CEL library not installed")

        with self.assertRaises(ValidationError):
            self.env["spp.approval.definition"].create(
                {
                    "name": "Invalid CEL Definition",
                    "model_id": self.test_model.id,
                    "approval_type": "user",
                    "approval_user_ids": [(4, self.test_user.id)],
                    "use_cel_condition": True,
                    "cel_condition": "invalid syntax {{{{",
                }
            )

    def test_cel_valid_computed_fields(self):
        """Test CEL validation computed fields."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "Validation Test",
                "model_id": self.test_model.id,
                "approval_type": "user",
                "approval_user_ids": [(4, self.test_user.id)],
            }
        )

        # Without CEL expression
        self.assertTrue(definition.is_cel_condition_valid)
        self.assertFalse(definition.cel_condition_error)

        # With valid CEL expression (if library available)
        if self.evaluator.is_available():
            definition.cel_condition = "record.id > 0"
            definition._compute_cel_valid()
            self.assertTrue(definition.is_cel_condition_valid)
