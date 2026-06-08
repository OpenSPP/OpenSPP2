from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDisabilityCelFunctions(TransactionCase):
    """Test cases for disability CEL functions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test registrant
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Test CEL Registrant",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - relativedelta(years=35),
            }
        )

        # Create a household group
        cls.household = cls.env["res.partner"].create(
            {
                "name": "Test CEL Household",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create household members
        cls.member_with_disability = cls.env["res.partner"].create(
            {
                "name": "Member With Disability",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - relativedelta(years=45),
            }
        )

        cls.member_without_disability = cls.env["res.partner"].create(
            {
                "name": "Member Without Disability",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - relativedelta(years=42),
            }
        )

        cls.member_with_severe = cls.env["res.partner"].create(
            {
                "name": "Member With Severe Disability",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - relativedelta(years=38),
            }
        )

        # Add members to household
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household.id,
                "individual": cls.member_with_disability.id,
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household.id,
                "individual": cls.member_without_disability.id,
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household.id,
                "individual": cls.member_with_severe.id,
            }
        )

        # Get severity vocabulary codes
        cls.severity_mild = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:dci:cd:dr:02"),
                ("code", "=", "mild"),
            ],
            limit=1,
        )
        cls.severity_severe = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:dci:cd:dr:02"),
                ("code", "=", "severe"),
            ],
            limit=1,
        )

        # Create approved assessment for member_with_disability (mild)
        assessment1 = cls.env["spp.disability.assessment"].create(
            {
                "registrant_id": cls.member_with_disability.id,
                "assessment_date": date.today(),
                "wg_walking": "a_lot",
                "severity_level_id": cls.severity_mild.id if cls.severity_mild else False,
            }
        )
        assessment1.write({"approval_state": "approved"})

        # Create approved assessment for member_with_severe (severe)
        assessment2 = cls.env["spp.disability.assessment"].create(
            {
                "registrant_id": cls.member_with_severe.id,
                "assessment_date": date.today(),
                "wg_seeing": "cannot",
                "wg_hearing": "cannot",
                "severity_level_id": cls.severity_severe.id if cls.severity_severe else False,
                "review_category": "mine",
            }
        )
        assessment2.write({"approval_state": "approved"})

        # Invalidate caches
        cls.member_with_disability.invalidate_recordset()
        cls.member_without_disability.invalidate_recordset()
        cls.member_with_severe.invalidate_recordset()

    def _get_cel_function(self, name):
        """Get a CEL function by name from the registry."""
        registry = self.env["spp.cel.function.registry"]
        return registry.get_handler(name)

    # === has_disability Function Tests ===

    def test_has_disability_true(self):
        """Test has_disability returns True for registrant with disability."""
        func = self._get_cel_function("has_disability")
        if not func:
            self.skipTest("has_disability function not registered")

        result = func(self.env, self.member_with_disability)
        self.assertTrue(result)

    def test_has_disability_false(self):
        """Test has_disability returns False for registrant without disability."""
        func = self._get_cel_function("has_disability")
        if not func:
            self.skipTest("has_disability function not registered")

        result = func(self.env, self.member_without_disability)
        self.assertFalse(result)

    def test_has_disability_none(self):
        """Test has_disability handles None input."""
        func = self._get_cel_function("has_disability")
        if not func:
            self.skipTest("has_disability function not registered")

        result = func(self.env, None)
        self.assertFalse(result)

    # === disability_severity Function Tests ===

    def test_disability_severity_returns_code(self):
        """Test disability_severity returns severity code."""
        func = self._get_cel_function("disability_severity")
        if not func:
            self.skipTest("disability_severity function not registered")

        result = func(self.env, self.member_with_disability)
        if self.severity_mild:
            self.assertEqual(result, self.severity_mild)

    def test_disability_severity_returns_empty_for_no_disability(self):
        """Test disability_severity returns empty for registrant without disability."""
        func = self._get_cel_function("disability_severity")
        if not func:
            self.skipTest("disability_severity function not registered")

        result = func(self.env, self.member_without_disability)
        self.assertFalse(result)

    # === is_severe_disability Function Tests ===

    def test_is_severe_disability_true(self):
        """Test is_severe_disability returns True for severe disability."""
        func = self._get_cel_function("is_severe_disability")
        if not func:
            self.skipTest("is_severe_disability function not registered")

        result = func(self.env, self.member_with_severe)
        self.assertTrue(result)

    def test_is_severe_disability_false_for_mild(self):
        """Test is_severe_disability returns False for mild disability."""
        func = self._get_cel_function("is_severe_disability")
        if not func:
            self.skipTest("is_severe_disability function not registered")

        result = func(self.env, self.member_with_disability)
        self.assertFalse(result)

    def test_is_severe_disability_false_for_no_disability(self):
        """Test is_severe_disability returns False for no disability."""
        func = self._get_cel_function("is_severe_disability")
        if not func:
            self.skipTest("is_severe_disability function not registered")

        result = func(self.env, self.member_without_disability)
        self.assertFalse(result)

    # === household_has_pwd Function Tests ===

    def test_household_has_pwd_true(self):
        """Test household_has_pwd returns True when household has PWD."""
        func = self._get_cel_function("household_has_pwd")
        if not func:
            self.skipTest("household_has_pwd function not registered")

        result = func(self.env, self.household)
        self.assertTrue(result)

    def test_household_has_pwd_false_for_individual(self):
        """Test household_has_pwd returns False for individual."""
        func = self._get_cel_function("household_has_pwd")
        if not func:
            self.skipTest("household_has_pwd function not registered")

        result = func(self.env, self.registrant)
        self.assertFalse(result)

    def test_household_has_pwd_false_for_empty_household(self):
        """Test household_has_pwd returns False for household without PWD."""
        func = self._get_cel_function("household_has_pwd")
        if not func:
            self.skipTest("household_has_pwd function not registered")

        # Create empty household
        empty_household = self.env["res.partner"].create(
            {
                "name": "Empty Household",
                "is_registrant": True,
                "is_group": True,
            }
        )

        result = func(self.env, empty_household)
        self.assertFalse(result)

    # === household_pwd_count Function Tests ===

    def test_household_pwd_count(self):
        """Test household_pwd_count returns correct count."""
        func = self._get_cel_function("household_pwd_count")
        if not func:
            self.skipTest("household_pwd_count function not registered")

        result = func(self.env, self.household)
        self.assertEqual(result, 2)  # member_with_disability and member_with_severe

    def test_household_pwd_count_zero_for_individual(self):
        """Test household_pwd_count returns 0 for individual."""
        func = self._get_cel_function("household_pwd_count")
        if not func:
            self.skipTest("household_pwd_count function not registered")

        result = func(self.env, self.registrant)
        self.assertEqual(result, 0)

    # === needs_reassessment Function Tests ===

    def test_needs_reassessment_false_when_not_due(self):
        """Test needs_reassessment returns False when review not due."""
        func = self._get_cel_function("needs_reassessment")
        if not func:
            self.skipTest("needs_reassessment function not registered")

        # member_with_severe has MINE category (6 years), so not due yet
        result = func(self.env, self.member_with_severe)
        self.assertFalse(result)

    def test_needs_reassessment_true_when_due(self):
        """Test needs_reassessment returns True when review is due."""
        func = self._get_cel_function("needs_reassessment")
        if not func:
            self.skipTest("needs_reassessment function not registered")

        # Create registrant with overdue assessment
        overdue_registrant = self.env["res.partner"].create(
            {
                "name": "Overdue Registrant",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - relativedelta(years=30),
            }
        )

        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": overdue_registrant.id,
                "assessment_date": date.today() - relativedelta(years=2),
                "wg_walking": "a_lot",
                "severity_level_id": self.severity_mild.id if self.severity_mild else False,
                "review_category": "mie",  # 12 months, so overdue
            }
        )
        assessment.write({"approval_state": "approved"})

        overdue_registrant.invalidate_recordset()

        result = func(self.env, overdue_registrant)
        self.assertTrue(result)

    def test_needs_reassessment_false_for_no_disability(self):
        """Test needs_reassessment returns False for no disability."""
        func = self._get_cel_function("needs_reassessment")
        if not func:
            self.skipTest("needs_reassessment function not registered")

        result = func(self.env, self.member_without_disability)
        self.assertFalse(result)


@tagged("post_install", "-at_install")
class TestCelFunctionRegistration(TransactionCase):
    """Test cases for CEL function registration."""

    def test_disability_functions_registered(self):
        """Test that disability functions are registered."""
        registry = self.env["spp.cel.function.registry"]

        expected_functions = [
            "has_disability",
            "disability_severity",
            "is_severe_disability",
            "household_has_pwd",
            "household_pwd_count",
            "needs_reassessment",
        ]

        for func_name in expected_functions:
            self.assertTrue(
                registry.is_registered(func_name),
                f"Function '{func_name}' should be registered",
            )

    def test_function_help_available(self):
        """Test that function help is available."""
        func_model = self.env["spp.cel.disability.functions"]

        help_text = func_model.get_function_help("has_disability")
        self.assertTrue(help_text)
        self.assertIn("approved disability", help_text.lower())

    def test_function_list(self):
        """Test that function list is available."""
        func_model = self.env["spp.cel.disability.functions"]

        func_list = func_model.get_function_list()
        self.assertIn("has_disability", func_list)
        self.assertIn("household_pwd_count", func_list)
