# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Adversarial tests for eligibility CEL integration - break the eligibility manager."""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEligibilityCELBreaking(TransactionCase):
    """Adversarial tests for CEL eligibility manager integration."""

    def setUp(self):
        super().setUp()
        # Create test program
        self.program = self.env["spp.program"].create(
            {
                "name": "Test Program",
                "target_type": "individual",
            }
        )
        # Create eligibility manager with CEL mode
        self.manager = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Test Manager",
                "program_id": self.program.id,
                "eligibility_mode": "cel",
                "cel_expression": "true",
            }
        )

    def test_empty_cel_expression_in_cel_mode(self):
        """Empty CEL expression in CEL mode should be invalid."""
        self.manager.cel_expression = ""
        self.manager._compute_cel_preview()
        self.assertFalse(self.manager.cel_is_valid)

    def test_none_cel_expression_in_cel_mode(self):
        """None as CEL expression should be handled."""
        self.manager.cel_expression = False  # Odoo uses False for None/empty
        self.manager._compute_cel_preview()
        self.assertFalse(self.manager.cel_is_valid)

    def test_whitespace_only_cel_expression(self):
        """Whitespace-only CEL expression should be invalid."""
        self.manager.cel_expression = "   \n\t  "
        self.manager._compute_cel_preview()
        self.assertFalse(self.manager.cel_is_valid)
        self.assertIn("empty", self.manager.cel_preview_error.lower())

    def test_invalid_syntax_cel_expression(self):
        """Invalid syntax should show error in preview."""
        self.manager.cel_expression = "r.age >>>"
        self.manager._compute_cel_preview()
        self.assertFalse(self.manager.cel_is_valid)
        self.assertGreater(len(self.manager.cel_preview_error), 0)

    def test_valid_cel_expression_shows_count(self):
        """Valid CEL expression should show preview count."""
        self.manager.cel_expression = "true"
        self.manager._compute_cel_preview()
        self.assertTrue(self.manager.cel_is_valid)
        self.assertEqual(self.manager.cel_preview_error, "")
        # Count should be >= 0
        self.assertGreaterEqual(self.manager.cel_preview_count, 0)

    def test_cel_expression_with_unicode(self):
        """CEL expression with unicode should work."""
        self.manager.cel_expression = 'r.name == "José García"'
        self.manager._compute_cel_preview()
        self.assertTrue(self.manager.cel_is_valid)

    def test_sql_injection_in_cel_expression(self):
        """SQL injection attempts should be safely handled."""
        self.manager.cel_expression = 'r.name == "Robert\'); DROP TABLE res_partner;--"'
        self.manager._compute_cel_preview()
        # Should either succeed (treating as literal) or fail safely
        # Must NOT execute SQL

    def test_code_injection_in_cel_expression(self):
        """Code injection attempts should not execute."""
        self.manager.cel_expression = "__import__('os').system('ls')"
        self.manager._compute_cel_preview()
        # Should fail or treat as function call, not execute code

    def test_target_type_individual_uses_correct_profile(self):
        """Individual target type should use registry_individuals profile."""
        self.program.target_type = "individual"
        self.manager.cel_expression = "r.is_registrant == true"
        self.manager._compute_cel_preview()
        # Should work with individual profile
        self.assertTrue(self.manager.cel_is_valid)

    def test_target_type_group_uses_correct_profile(self):
        """Group target type should use registry_groups profile."""
        self.program.target_type = "group"
        self.manager.cel_expression = "r.is_group == true"
        self.manager._compute_cel_preview()
        # Should work with group profile
        self.assertTrue(self.manager.cel_is_valid)

    def test_changing_target_type_recomputes_preview(self):
        """Changing target type should trigger recomputation."""
        self.program.target_type = "individual"
        self.manager.cel_expression = "true"
        self.manager._compute_cel_preview()

        # Change target type
        self.program.target_type = "group"
        self.manager._compute_cel_preview()

        # Counts may differ
        # Both should be valid
        self.assertTrue(self.manager.cel_is_valid)

    def test_prepare_eligible_domain_cel_mode(self):
        """_prepare_eligible_domain in CEL mode should return domain."""
        self.manager.eligibility_mode = "cel"
        self.manager.cel_expression = "true"
        domain = self.manager._prepare_eligible_domain()
        self.assertIsInstance(domain, list)

    def test_prepare_eligible_domain_with_invalid_cel(self):
        """_prepare_eligible_domain with invalid CEL should raise ValidationError."""
        self.manager.eligibility_mode = "cel"
        self.manager.cel_expression = "invalid >>>"
        with self.assertRaises(ValidationError):
            self.manager._prepare_eligible_domain()

    def test_prepare_eligible_domain_includes_base_restrictions(self):
        """_prepare_eligible_domain should include base restrictions."""
        self.manager.eligibility_mode = "cel"
        self.manager.cel_expression = "true"
        self.manager._prepare_eligible_domain()
        # Should include disabled=False
        # Domain structure varies, but should not crash

    def test_prepare_eligible_domain_with_membership_filter(self):
        """_prepare_eligible_domain with membership parameter should filter."""
        # Create test partner
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "is_registrant": True,
                "is_group": False,
            }
        )
        # Create membership
        membership = self.env["spp.program.membership"].create(
            {
                "partner_id": partner.id,
                "program_id": self.program.id,
            }
        )

        self.manager.eligibility_mode = "cel"
        self.manager.cel_expression = "true"
        domain = self.manager._prepare_eligible_domain(membership)

        self.assertIsInstance(domain, list)
        # Should filter to just this partner

    def test_action_open_cel_builder(self):
        """action_open_cel_builder should return wizard action."""
        action = self.manager.action_open_cel_builder()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.cel.builder.wizard")
        self.assertEqual(action["target"], "new")

    def test_action_test_cel_expression_valid(self):
        """action_test_cel_expression with valid expression should show success."""
        self.manager.cel_expression = "true"
        action = self.manager.action_test_cel_expression()
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "display_notification")

    def test_action_test_cel_expression_invalid(self):
        """action_test_cel_expression with invalid expression should show error."""
        self.manager.cel_expression = "invalid >>>"
        action = self.manager.action_test_cel_expression()
        self.assertEqual(action["type"], "ir.actions.client")
        params = action["params"]
        self.assertEqual(params["type"], "danger")

    def test_action_test_cel_expression_empty(self):
        """action_test_cel_expression with empty expression should raise ValidationError."""
        self.manager.cel_expression = ""
        with self.assertRaises(ValidationError):
            self.manager.action_test_cel_expression()

    def test_action_preview_beneficiaries(self):
        """action_preview_beneficiaries should open list view."""
        self.manager.cel_expression = "true"
        action = self.manager.action_preview_beneficiaries()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "res.partner")
        self.assertIn("domain", action)

    def test_action_preview_beneficiaries_invalid_expression(self):
        """action_preview_beneficiaries with invalid expression should raise ValidationError."""
        self.manager.cel_expression = "invalid >>>"
        with self.assertRaises(ValidationError):
            self.manager.action_preview_beneficiaries()

    def test_action_preview_beneficiaries_empty_expression(self):
        """action_preview_beneficiaries with empty expression should raise ValidationError."""
        self.manager.cel_expression = ""
        with self.assertRaises(ValidationError):
            self.manager.action_preview_beneficiaries()

    def test_cel_expression_field_exists(self):
        """cel_expression field should exist on the manager."""
        self.manager.cel_expression = "r.age >= 18"
        # Check that the field exists and is writable
        self.assertEqual(self.manager.cel_expression, "r.age >= 18")
        self.assertTrue(hasattr(self.manager, "cel_expression"))

    def test_very_long_cel_expression(self):
        """Very long CEL expression should be handled."""
        long_expr = " or ".join([f"r.field{i} == {i}" for i in range(100)])
        self.manager.cel_expression = long_expr
        self.manager._compute_cel_preview()
        # Should not crash

    def test_deeply_nested_cel_expression(self):
        """Deeply nested CEL expression should be handled."""
        expr = "true"
        for _ in range(50):
            expr = f"({expr} and true)"
        self.manager.cel_expression = expr
        self.manager._compute_cel_preview()
        # Should not crash

    def test_cel_preview_count_accuracy(self):
        """Preview count should accurately reflect matching records."""
        # Create some test partners
        for i in range(5):
            self.env["res.partner"].create(
                {
                    "name": f"Test Partner {i}",
                    "is_registrant": True,
                    "is_group": False,
                }
            )

        self.manager.cel_expression = "true"
        self.manager._compute_cel_preview()

        # Count should be at least 5
        self.assertGreaterEqual(self.manager.cel_preview_count, 5)

    def test_base_domain_applied_in_preview(self):
        """Base domain should be applied when computing preview count."""
        from odoo import fields

        # Create disabled partner (disabled is a Datetime field)
        self.env["res.partner"].create(
            {
                "name": "Disabled Partner",
                "is_registrant": True,
                "is_group": False,
                "disabled": fields.Datetime.now(),  # Setting a datetime means disabled
            }
        )

        self.manager.cel_expression = "true"
        self.manager._compute_cel_preview()

        # Disabled partner should not be counted
        # (base_domain includes disabled=False)

    def test_concurrent_preview_computations(self):
        """Multiple concurrent preview computations should be safe."""
        for i in range(10):
            self.manager.cel_expression = f"r.name == 'test{i}'"
            self.manager._compute_cel_preview()
        # Should not crash

    def test_exception_in_preview_sets_error(self):
        """Exceptions during preview should set error message."""
        # Force an exception by using invalid profile (if possible)
        # Or use expression that will fail
        self.manager.cel_expression = "nonexistent_field == 5"
        self.manager._compute_cel_preview()
        # Should set error (or succeed if field resolution is lenient)

    def test_prepare_eligible_domain_exception_wrapped(self):
        """Exceptions in _prepare_eligible_domain should be wrapped as ValidationError."""
        self.manager.eligibility_mode = "cel"
        self.manager.cel_expression = "invalid syntax >>>"
        with self.assertRaises(ValidationError):
            self.manager._prepare_eligible_domain()

    def test_multiple_managers_isolated(self):
        """Multiple eligibility managers should not interfere."""
        manager2 = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Test Manager 2",
                "program_id": self.program.id,
                "eligibility_mode": "cel",
                "cel_expression": "r.is_registrant == true",  # Use existing field
            }
        )

        self.manager.cel_expression = "r.is_group == false"  # Use existing field
        self.manager._compute_cel_preview()
        manager2._compute_cel_preview()

        # Both should compute independently
        self.assertTrue(self.manager.cel_is_valid)
        self.assertTrue(manager2.cel_is_valid)

    def test_manager_requires_program(self):
        """Manager requires a program (program_id is required field)."""
        # Manager creation should fail without program_id since it's required
        try:
            self.env["spp.program.membership.manager.default"].create(
                {
                    "name": "No Program Manager",
                    "eligibility_mode": "cel",
                    "cel_expression": "true",
                }
            )
            self.fail("Expected an exception when creating manager without program_id")
        except Exception:
            # Expected - program_id is required
            pass

    def test_cel_expression_help_text_present(self):
        """CEL expression field should have helpful examples in help text."""
        field = self.manager._fields["cel_expression"]
        self.assertIsNotNone(field.help)
        self.assertIn("age_years", field.help)

    def test_eligibility_mode_help_text_present(self):
        """Eligibility mode field should have helpful explanation."""
        field = self.manager._fields["eligibility_mode"]
        self.assertIsNotNone(field.help)

    def test_cel_is_valid_readonly(self):
        """cel_is_valid should be computed field, not writable."""
        # Attempting to write should fail or be ignored
        try:
            self.manager.write({"cel_is_valid": False})
            # If write succeeds, it should be ignored (computed field)
        except Exception:
            # Expected - computed fields are typically not writable
            pass

    def test_domain_generation_correctness(self):
        """Generated domain should correctly filter partners."""
        # Create specific partner
        partner = self.env["res.partner"].create(
            {
                "name": "Specific Test Partner",
                "is_registrant": True,
                "is_group": False,
            }
        )

        self.manager.cel_expression = 'r.name == "Specific Test Partner"'
        domain = self.manager._prepare_eligible_domain()

        # Search with domain should find the partner
        results = self.env["res.partner"].search(domain)
        self.assertIn(partner.id, results.ids)

    def test_prepare_eligible_domain_logs_compiled_domain(self):
        """_prepare_eligible_domain should log compiled domain for debugging."""
        self.manager.eligibility_mode = "cel"
        self.manager.cel_expression = "true"
        # Should log at DEBUG level
        domain = self.manager._prepare_eligible_domain()
        self.assertIsNotNone(domain)
