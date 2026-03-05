# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase


class TestTriageRules(TransactionCase):
    """Test Case triage rules with CEL expressions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.TriageRule = cls.env["spp.case.triage.rule"]
        cls.Case = cls.env["spp.case"]
        cls.CaseType = cls.env["spp.case.type"]
        cls.Partner = cls.env["res.partner"]
        cls.User = cls.env["res.users"]

        # Create test case types
        cls.case_type_general = cls.CaseType.create(
            {
                "name": "General Support",
                "code": "GEN",
            }
        )
        cls.case_type_protection = cls.CaseType.create(
            {
                "name": "Child Protection",
                "code": "CP",
            }
        )
        cls.case_type_emergency = cls.CaseType.create(
            {
                "name": "Emergency Response",
                "code": "ER",
            }
        )

        # Create test partner (client)
        cls.partner = cls.Partner.create(
            {
                "name": "Test Client",
            }
        )

        # Get a case worker user
        cls.case_worker = cls.User.search([("share", "=", False)], limit=1)
        if not cls.case_worker:
            cls.case_worker = cls.env.ref("base.user_admin")

    def _create_case(self, **kwargs):
        """Helper to create a case with default values."""
        defaults = {
            "case_type_id": self.case_type_general.id,
            "partner_id": self.partner.id,
            "case_worker_id": self.case_worker.id,
            "presenting_issue": "<p>Test presenting issue</p>",
            "intensity_level": "2",
            "priority": "medium",
            "intake_source": "walk_in",
            "client_type": "individual",
        }
        defaults.update(kwargs)
        return self.Case.create(defaults)

    # =====================================================
    # UNIT TESTS - Test individual components
    # =====================================================

    def test_triage_rule_creation(self):
        """Test triage rule can be created with proper defaults."""
        rule = self.TriageRule.create(
            {
                "name": "High Priority for GRM Cases",
                "condition_cel": "intake_source == 'grm'",
                "set_priority": "high",
            }
        )
        self.assertTrue(rule.active)
        self.assertEqual(rule.match_count, 0)
        self.assertEqual(rule.sequence, 10)

    def test_expression_evaluation_with_operators(self):
        """Test CEL expression evaluation with AND/OR operators."""
        rule = self.TriageRule.create(
            {
                "name": "Test Expression",
                "condition_cel": "",
            }
        )

        # Test OR (or)
        context = {"intake_source": "walk_in", "client_type": "household"}
        result = rule._evaluate_expression("intake_source == 'grm' or client_type == 'household'", context)
        self.assertTrue(result)

        # Test AND (and)
        context = {"intake_source": "grm", "client_type": "household"}
        result = rule._evaluate_expression("intake_source == 'grm' and client_type == 'household'", context)
        self.assertTrue(result)

        # Test failure case
        context = {"intake_source": "walk_in", "client_type": "individual"}
        result = rule._evaluate_expression("intake_source == 'grm' or client_type == 'household'", context)
        self.assertFalse(result)

    # =====================================================
    # INTEGRATION TESTS - Verify triage actually works
    # =====================================================

    def test_apply_triage_sets_priority(self):
        """Test apply_triage() actually changes case priority.

        Note: Triage is automatically applied on case creation,
        so we create the case first, then the rule, then manually apply.
        """
        # Create case BEFORE creating the triage rule
        case = self._create_case(intake_source="grm", priority="low")
        self.assertEqual(case.priority, "low")

        # Now create a triage rule
        rule = self.TriageRule.create(
            {
                "name": "Set High Priority for GRM",
                "condition_cel": "intake_source == 'grm'",
                "set_priority": "urgent",
            }
        )

        # Apply triage manually
        result = self.TriageRule.apply_triage(case)

        self.assertTrue(result, "apply_triage should return True when rule matches")
        self.assertEqual(case.priority, "urgent", "Priority should be changed to urgent")
        self.assertEqual(rule.match_count, 1, "Rule match_count should increment")

    def test_apply_triage_sets_intensity(self):
        """Test apply_triage() actually changes case intensity level.

        Note: Triage is automatically applied on case creation,
        so we create the case first, then the rule, then manually apply.
        """
        # Create case BEFORE creating the triage rule
        case = self._create_case(client_type="household", intensity_level="1")
        self.assertEqual(case.intensity_level, "1")

        # Now create a triage rule
        self.TriageRule.create(
            {
                "name": "Set High Intensity for Households",
                "condition_cel": "client_type == 'household'",
                "set_intensity": "3",
            }
        )

        result = self.TriageRule.apply_triage(case)

        self.assertTrue(result)
        self.assertEqual(case.intensity_level, "3", "Intensity should be changed to level 3")

    def test_apply_triage_sets_case_type(self):
        """Test apply_triage() can change case type based on conditions.

        Note: Triage is automatically applied on case creation,
        so we create the case first, then the rule, then manually apply.
        """
        # Create case BEFORE creating the triage rule
        case = self._create_case(
            intake_source="referral",
            case_type_id=self.case_type_general.id,
        )
        self.assertEqual(case.case_type_id, self.case_type_general)

        # Now create a triage rule
        self.TriageRule.create(
            {
                "name": "Auto-assign Protection Type",
                "condition_cel": "intake_source == 'referral'",
                "set_case_type_id": self.case_type_protection.id,
            }
        )

        result = self.TriageRule.apply_triage(case)

        self.assertTrue(result)
        self.assertEqual(case.case_type_id, self.case_type_protection, "Case type should be changed")

    def test_apply_triage_multiple_fields(self):
        """Test apply_triage() can set multiple fields at once."""
        self.TriageRule.create(
            {
                "name": "Emergency Triage",
                "condition_cel": "intake_source == 'grm'",
                "set_intensity": "3",
                "set_priority": "urgent",
                "set_case_type_id": self.case_type_emergency.id,
            }
        )

        case = self._create_case(
            intake_source="grm",
            intensity_level="1",
            priority="low",
            case_type_id=self.case_type_general.id,
        )

        result = self.TriageRule.apply_triage(case)

        self.assertTrue(result)
        self.assertEqual(case.intensity_level, "3")
        self.assertEqual(case.priority, "urgent")
        self.assertEqual(case.case_type_id, self.case_type_emergency)

    def test_apply_triage_no_match(self):
        """Test apply_triage() returns False when no rules match."""
        rule = self.TriageRule.create(
            {
                "name": "GRM Only Rule",
                "condition_cel": "intake_source == 'grm'",
                "set_priority": "urgent",
            }
        )

        # Create a non-GRM case
        case = self._create_case(intake_source="walk_in", priority="low")

        result = self.TriageRule.apply_triage(case)

        self.assertFalse(result, "Should return False when no rules match")
        self.assertEqual(case.priority, "low", "Priority should remain unchanged")
        self.assertEqual(rule.match_count, 0, "Rule should have 0 matches")

    def test_apply_triage_first_match_wins(self):
        """Test that first matching rule (by sequence) is applied.

        Note: Triage is automatically applied on case creation,
        so we create the case first, then the rules, then manually apply.
        """
        # Create case BEFORE creating the triage rules
        case = self._create_case(priority="low")
        self.assertEqual(case.priority, "low")

        # Now create two rules that could both match
        rule1 = self.TriageRule.create(
            {
                "name": "First Rule",
                "sequence": 10,
                "condition_cel": "",  # Always matches
                "set_priority": "high",
            }
        )
        rule2 = self.TriageRule.create(
            {
                "name": "Second Rule",
                "sequence": 20,
                "condition_cel": "",  # Would also match
                "set_priority": "urgent",
            }
        )

        result = self.TriageRule.apply_triage(case)

        self.assertTrue(result)
        # First rule should win (lower sequence)
        self.assertEqual(case.priority, "high", "First matching rule should be applied")
        self.assertEqual(rule1.match_count, 1)
        self.assertEqual(rule2.match_count, 0, "Second rule should not have matched")

    def test_apply_triage_inactive_rules_skipped(self):
        """Test that inactive triage rules are not applied."""
        rule = self.TriageRule.create(
            {
                "name": "Inactive Rule",
                "active": False,
                "condition_cel": "",  # Would always match if active
                "set_priority": "urgent",
            }
        )

        case = self._create_case(priority="low")

        result = self.TriageRule.apply_triage(case)

        self.assertFalse(result)
        self.assertEqual(case.priority, "low", "Priority should remain unchanged")
        self.assertEqual(rule.match_count, 0)

    def test_apply_triage_empty_condition_matches_all(self):
        """Test that empty condition matches all cases."""
        self.TriageRule.create(
            {
                "name": "Catch-All Rule",
                "condition_cel": "",  # Empty = always matches
                "set_priority": "medium",
            }
        )

        case = self._create_case(
            intake_source="walk_in",
            client_type="individual",
            priority="low",
        )

        result = self.TriageRule.apply_triage(case)

        self.assertTrue(result, "Empty condition should match")
        self.assertEqual(case.priority, "medium")

    def test_triage_rule_complex_condition(self):
        """Test triage with complex multi-condition expression."""
        self.TriageRule.create(
            {
                "name": "Complex Triage Rule",
                "condition_cel": (
                    "(intake_source == 'grm' or intake_source == 'referral') and client_type == 'household'"
                ),
                "set_intensity": "3",
                "set_priority": "high",
            }
        )

        # Case that should NOT match (individual, not household)
        case1 = self._create_case(
            intake_source="grm",
            client_type="individual",
            intensity_level="1",
            priority="low",
        )
        result1 = self.TriageRule.apply_triage(case1)
        self.assertFalse(result1)
        self.assertEqual(case1.intensity_level, "1")

        # Case that SHOULD match (grm + household)
        case2 = self._create_case(
            intake_source="grm",
            client_type="household",
            intensity_level="1",
            priority="low",
        )
        result2 = self.TriageRule.apply_triage(case2)
        self.assertTrue(result2)
        self.assertEqual(case2.intensity_level, "3")
        self.assertEqual(case2.priority, "high")

    def test_evaluate_builds_correct_context(self):
        """Test that evaluate() builds context with all expected variables."""
        rule = self.TriageRule.create(
            {
                "name": "Test Context",
                "condition_cel": "intake_source == 'grm' and client_type == 'household'",
            }
        )

        case = self._create_case(
            intake_source="grm",
            client_type="household",
        )

        # Build context and verify expected variables
        context = rule._build_evaluation_context(case)

        self.assertIn("case", context)
        self.assertIn("client", context)
        self.assertIn("case_type", context)
        self.assertIn("intake_source", context)
        self.assertIn("client_type", context)
        self.assertEqual(context["intake_source"], "grm")
        self.assertEqual(context["client_type"], "household")

        # Verify evaluate() works with real case
        result = rule.evaluate(case)
        self.assertTrue(result)
