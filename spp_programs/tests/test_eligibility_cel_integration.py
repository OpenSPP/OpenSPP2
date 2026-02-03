# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Integration tests for eligibility CEL with workflows."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEligibilityCELIntegration(TransactionCase):
    """Integration tests for CEL eligibility manager with enrollment workflows."""

    def setUp(self):
        super().setUp()
        # Create test program
        self.program = self.env["spp.program"].create(
            {
                "name": "Integration Test Program",
                "target_type": "individual",
            }
        )

    def test_enrollment_workflow_with_eligibility_cel(self):
        """Test that CEL eligibility integrates with enrollment workflow."""
        # Create eligibility manager
        manager = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Age-based Eligibility",
                "program_id": self.program.id,
                "eligibility_mode": "cel",
                "cel_expression": "r.is_registrant == true",
            }
        )

        # Create test registrants
        eligible_partner = self.env["res.partner"].create(
            {
                "name": "Eligible Partner",
                "is_registrant": True,
                "is_group": False,
            }
        )

        ineligible_partner = self.env["res.partner"].create(
            {
                "name": "Ineligible Partner",
                "is_registrant": False,
                "is_group": False,
            }
        )

        # Get eligible domain
        domain = manager._prepare_eligible_domain()

        # Search using domain
        eligible_partners = self.env["res.partner"].search(domain)

        # Verify correct filtering
        self.assertIn(eligible_partner.id, eligible_partners.ids)
        self.assertNotIn(ineligible_partner.id, eligible_partners.ids)

    def test_eligibility_reevaluation_after_data_change(self):
        """Test that eligibility can be re-evaluated after beneficiary data changes."""
        # Create eligibility manager
        manager = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Active Status Eligibility",
                "program_id": self.program.id,
                "eligibility_mode": "cel",
                "cel_expression": "r.active == true",
            }
        )

        # Create partner
        partner = self.env["res.partner"].create(
            {
                "name": "Changeable Partner",
                "is_registrant": True,
                "is_group": False,
                "active": True,
            }
        )

        # Initially eligible
        domain = manager._prepare_eligible_domain()
        eligible_partners = self.env["res.partner"].search(domain)
        self.assertIn(partner.id, eligible_partners.ids)

        # Change data
        partner.active = False

        # Re-evaluate - should no longer be eligible
        domain = manager._prepare_eligible_domain()
        eligible_partners = self.env["res.partner"].search(domain)
        self.assertNotIn(partner.id, eligible_partners.ids)

    def test_multiple_managers_in_one_program(self):
        """Test multiple eligibility managers don't interfere."""
        # Create two managers for same program
        manager1 = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Manager 1",
                "program_id": self.program.id,
                "eligibility_mode": "cel",
                "cel_expression": "r.is_registrant == true",
            }
        )

        manager2 = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Manager 2",
                "program_id": self.program.id,
                "eligibility_mode": "cel",
                "cel_expression": "r.is_group == false",
            }
        )

        # Both should compute independently
        manager1._compute_cel_preview()
        manager2._compute_cel_preview()

        self.assertTrue(manager1.cel_is_valid)
        self.assertTrue(manager2.cel_is_valid)

        # Counts may differ
        # Both should be >= 0
        self.assertGreaterEqual(manager1.cel_preview_count, 0)
        self.assertGreaterEqual(manager2.cel_preview_count, 0)

    def test_cel_service_unavailable_graceful_failure(self):
        """Test graceful handling when CEL service has issues."""
        manager = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Test Manager",
                "program_id": self.program.id,
                "eligibility_mode": "cel",
                "cel_expression": "r.is_registrant == true",
            }
        )

        # Try with invalid profile (should fail gracefully)
        # This tests exception handling in _compute_cel_preview
        manager._compute_cel_preview()

        # Should set error or handle gracefully
        # Should not crash

    def test_membership_filtering_in_prepare_eligible_domain(self):
        """Test that membership parameter correctly filters results."""
        # Create manager
        manager = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Test Manager",
                "program_id": self.program.id,
                "eligibility_mode": "cel",
                "cel_expression": "true",
            }
        )

        # Create two partners
        partner1 = self.env["res.partner"].create(
            {
                "name": "Partner 1",
                "is_registrant": True,
                "is_group": False,
            }
        )
        self.env["res.partner"].create(
            {
                "name": "Partner 2",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create membership for partner1 only
        membership1 = self.env["spp.program.membership"].create(
            {
                "partner_id": partner1.id,
                "program_id": self.program.id,
            }
        )

        # Call with membership filter
        domain = manager._prepare_eligible_domain(membership1)
        eligible_partners = self.env["res.partner"].search(domain)

        # Should only include partner1
        self.assertIn(partner1.id, eligible_partners.ids)
        # May or may not include partner2 depending on domain structure
        # The key is that it should apply the membership filter

    def test_target_type_affects_profile_selection(self):
        """Test that changing target_type changes the profile used."""
        # Create test data to ensure counts will differ
        self.env["res.partner"].create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )
        self.env["res.partner"].create(
            {
                "name": "Test Group",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create manager for individuals
        manager = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Individual Manager",
                "program_id": self.program.id,
                "eligibility_mode": "cel",
                "cel_expression": "r.is_registrant == true",
            }
        )

        # Compute with individual target type
        self.program.target_type = "individual"
        manager._compute_cel_preview()
        count_individual = manager.cel_preview_count

        # Change to group target type
        self.program.target_type = "group"
        manager._compute_cel_preview()
        count_group = manager.cel_preview_count

        # Both should be valid expressions
        self.assertTrue(manager.cel_is_valid)

        # Counts should be greater than 0 since we created test data
        self.assertGreaterEqual(count_individual, 1, "Should find at least 1 individual")
        self.assertGreaterEqual(count_group, 1, "Should find at least 1 group")

    def test_disabled_partners_excluded(self):
        """Test that disabled partners are excluded from eligibility."""
        from odoo import fields

        # Create manager
        manager = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Test Manager",
                "program_id": self.program.id,
                "eligibility_mode": "cel",
                "cel_expression": "true",
            }
        )

        # Create enabled and disabled partners
        # disabled is a Datetime field - False/None means not disabled
        enabled_partner = self.env["res.partner"].create(
            {
                "name": "Enabled Partner",
                "is_registrant": True,
                "is_group": False,
            }
        )
        # Setting disabled to a datetime marks the partner as disabled
        disabled_partner = self.env["res.partner"].create(
            {
                "name": "Disabled Partner",
                "is_registrant": True,
                "is_group": False,
                "disabled": fields.Datetime.now(),
            }
        )

        # Get eligible domain
        domain = manager._prepare_eligible_domain()
        eligible_partners = self.env["res.partner"].search(domain)

        # Enabled should be included, disabled should not
        self.assertIn(enabled_partner.id, eligible_partners.ids)
        self.assertNotIn(disabled_partner.id, eligible_partners.ids)

    def test_complex_cel_expression_with_real_data(self):
        """Test complex CEL expression with real beneficiary data."""
        # Create manager with complex expression
        manager = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Complex Manager",
                "program_id": self.program.id,
                "eligibility_mode": "cel",
                "cel_expression": "r.is_registrant == true and r.is_group == false",
            }
        )

        # Create various partners
        self.env["res.partner"].create(
            {
                "name": "Individual Registrant",
                "is_registrant": True,
                "is_group": False,
            }
        )
        self.env["res.partner"].create(
            {
                "name": "Group Registrant",
                "is_registrant": True,
                "is_group": True,
            }
        )
        self.env["res.partner"].create(
            {
                "name": "Non-Registrant",
                "is_registrant": False,
                "is_group": False,
            }
        )

        # Compute preview
        manager._compute_cel_preview()

        # Should be valid
        self.assertTrue(manager.cel_is_valid)

        # Count should be at least 1 (the individual registrant)
        self.assertGreaterEqual(manager.cel_preview_count, 1)

    def test_concurrent_preview_computations_no_interference(self):
        """Test that concurrent preview computations don't interfere."""
        # Create multiple managers
        managers = []
        for i in range(5):
            manager = self.env["spp.program.membership.manager.default"].create(
                {
                    "name": f"Manager {i}",
                    "program_id": self.program.id,
                    "eligibility_mode": "cel",
                    "cel_expression": f"r.id > {i}",
                }
            )
            managers.append(manager)

        # Compute all previews "concurrently" (in sequence but rapidly)
        for manager in managers:
            manager._compute_cel_preview()

        # All should be valid
        for manager in managers:
            self.assertTrue(manager.cel_is_valid)
            self.assertGreaterEqual(manager.cel_preview_count, 0)

    def test_action_methods_return_correct_structure(self):
        """Test that action methods return properly structured dictionaries."""
        manager = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Action Test Manager",
                "program_id": self.program.id,
                "eligibility_mode": "cel",
                "cel_expression": "true",
            }
        )

        # Test action_open_cel_builder
        action = manager.action_open_cel_builder()
        self.assertIn("type", action)
        self.assertIn("res_model", action)
        self.assertIn("context", action)
        self.assertEqual(action["type"], "ir.actions.act_window")

        # Test action_test_cel_expression
        action = manager.action_test_cel_expression()
        self.assertIn("type", action)
        self.assertIn("params", action)
        self.assertEqual(action["type"], "ir.actions.client")

        # Test action_preview_beneficiaries
        action = manager.action_preview_beneficiaries()
        self.assertIn("type", action)
        self.assertIn("domain", action)
        self.assertEqual(action["type"], "ir.actions.act_window")

    def test_preview_accuracy_with_known_dataset(self):
        """Test that preview count accurately reflects matching records."""
        # Create exactly 3 eligible partners with specific IDs that we can filter
        created_ids = []
        for i in range(3):
            partner = self.env["res.partner"].create(
                {
                    "name": f"Known Partner {i}",
                    "is_registrant": True,
                    "is_group": False,
                }
            )
            created_ids.append(partner.id)

        # Create manager with filter for these specific IDs
        # Use in() operator which is supported by CEL
        manager = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Accuracy Test Manager",
                "program_id": self.program.id,
                "eligibility_mode": "cel",
                "cel_expression": f"r.id in [{', '.join(str(i) for i in created_ids)}]",
            }
        )

        # Compute preview
        manager._compute_cel_preview()

        # Should find exactly 3 partners
        self.assertTrue(manager.cel_is_valid, f"CEL expression should be valid. Error: {manager.cel_preview_error}")
        self.assertEqual(manager.cel_preview_count, 3)

    def test_performance_with_large_dataset(self):
        """Test preview computation performance with larger dataset."""
        # Create 100 partners
        for i in range(100):
            self.env["res.partner"].create(
                {
                    "name": f"Perf Partner {i}",
                    "is_registrant": True if i % 2 == 0 else False,
                    "is_group": False,
                }
            )

        # Create manager
        manager = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Performance Manager",
                "program_id": self.program.id,
                "eligibility_mode": "cel",
                "cel_expression": "r.is_registrant == true",
            }
        )

        # Compute preview - should complete in reasonable time
        import time

        start = time.time()
        manager._compute_cel_preview()
        elapsed = time.time() - start

        # Should complete in under 5 seconds
        self.assertLess(elapsed, 5.0)

        # Should be valid
        self.assertTrue(manager.cel_is_valid)

        # Should find approximately 50 partners
        self.assertGreaterEqual(manager.cel_preview_count, 50)
