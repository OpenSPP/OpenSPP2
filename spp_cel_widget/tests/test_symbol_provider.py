"""Tests for CEL Symbol Provider."""

from odoo.tests.common import TransactionCase


class TestCelSymbolProvider(TransactionCase):
    """Test cases for spp.cel.symbol.provider model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env["spp.cel.symbol.provider"]

    def test_get_symbols_individuals_profile(self):
        """Test that individuals profile returns correct symbols."""
        result = self.provider.get_symbols_for_profile("registry_individuals")

        # Check basic structure
        self.assertEqual(result["profile"], "registry_individuals")
        self.assertEqual(result["root_model"], "res.partner")
        self.assertIn("variables", result)
        self.assertIn("functions", result)
        self.assertIn("operators", result)
        self.assertIn("keywords", result)

        # Check 'r' variable exists
        var_names = [v["name"] for v in result["variables"]]
        self.assertIn("r", var_names)

        # Check 'r' has fields
        me_var = next(v for v in result["variables"] if v["name"] == "r")
        self.assertIn("fields", me_var)
        self.assertGreater(len(me_var["fields"]), 0)

    def test_get_symbols_groups_profile(self):
        """Test that groups profile returns members variable."""
        result = self.provider.get_symbols_for_profile("registry_groups")

        self.assertEqual(result["profile"], "registry_groups")

        var_names = [v["name"] for v in result["variables"]]
        self.assertIn("r", var_names)
        self.assertIn("members", var_names)

        # Check members is iterable
        members_var = next(v for v in result["variables"] if v["name"] == "members")
        self.assertTrue(members_var.get("iterable"))

    def test_get_symbols_unknown_profile(self):
        """Test that unknown profile returns error."""
        result = self.provider.get_symbols_for_profile("unknown_profile")

        self.assertIn("error", result)
        self.assertEqual(len(result["variables"]), 0)

    def test_builtin_functions_included(self):
        """Test that built-in functions are included."""
        result = self.provider.get_symbols_for_profile("registry_individuals")

        func_names = [f["name"] for f in result["functions"]]

        # Check common functions
        self.assertIn("age_years", func_names)
        self.assertIn("today", func_names)
        self.assertIn("exists", func_names)
        self.assertIn("count", func_names)

    def test_function_has_signature(self):
        """Test that functions have signature and documentation."""
        result = self.provider.get_symbols_for_profile("registry_individuals")

        age_years = next(f for f in result["functions"] if f["name"] == "age_years")

        self.assertIn("signature", age_years)
        self.assertIn("doc", age_years)
        self.assertIn("params", age_years)
        self.assertIn("return_type", age_years)

    def test_operators_included(self):
        """Test that operators are included."""
        result = self.provider.get_symbols_for_profile("registry_individuals")

        op_symbols = [o["symbol"] for o in result["operators"]]

        self.assertIn("and", op_symbols)
        self.assertIn("or", op_symbols)
        self.assertIn("==", op_symbols)
        self.assertIn(">=", op_symbols)

    def test_keywords_included(self):
        """Test that keywords are included."""
        result = self.provider.get_symbols_for_profile("registry_individuals")

        self.assertIn("true", result["keywords"])
        self.assertIn("false", result["keywords"])

    def test_field_has_type_info(self):
        """Test that fields have type information."""
        result = self.provider.get_symbols_for_profile("registry_individuals")

        me_var = next(v for v in result["variables"] if v["name"] == "r")

        # Find a field
        if me_var["fields"]:
            field = me_var["fields"][0]
            self.assertIn("name", field)
            self.assertIn("type", field)

    def test_validate_valid_expression(self):
        """Test validation of a valid expression."""
        result = self.provider.validate_expression(
            'r.name == "Test"',
            "registry_individuals",
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])

    def test_validate_empty_expression(self):
        """Test validation of empty expression."""
        result = self.provider.validate_expression("", "registry_individuals")

        self.assertFalse(result["valid"])
        self.assertGreater(len(result["errors"]), 0)

    def test_validate_syntax_error(self):
        """Test validation catches syntax errors."""
        result = self.provider.validate_expression(
            "r.name ==",  # Incomplete expression
            "registry_individuals",
        )

        self.assertFalse(result["valid"])
        self.assertGreater(len(result["errors"]), 0)

    def test_get_available_profiles(self):
        """Test getting list of available profiles."""
        profiles = self.provider.get_available_profiles()

        self.assertIsInstance(profiles, list)
        self.assertGreater(len(profiles), 0)

        # Check profile structure
        profile = profiles[0]
        self.assertIn("name", profile)
        self.assertIn("doc", profile)

    # ─── Tests for new CEL Variables and Library features ─────────────────

    def test_infer_context_individual(self):
        """Test context inference for individual profiles."""
        context = self.provider._infer_context_from_profile("registry_individuals")
        self.assertEqual(context, "individual")

    def test_infer_context_group(self):
        """Test context inference for group profiles."""
        context = self.provider._infer_context_from_profile("registry_groups")
        self.assertEqual(context, "group")

    def test_infer_context_other(self):
        """Test context inference for non-registry profiles."""
        context = self.provider._infer_context_from_profile("program_memberships")
        self.assertEqual(context, "both")

    def test_get_symbols_includes_cel_variables(self):
        """Test that symbols result includes cel_variables key."""
        result = self.provider.get_symbols_for_profile("registry_individuals")

        self.assertIn("cel_variables", result)
        self.assertIsInstance(result["cel_variables"], list)

    def test_get_symbols_includes_library(self):
        """Test that symbols result includes library key."""
        result = self.provider.get_symbols_for_profile("registry_individuals")

        self.assertIn("library", result)
        self.assertIsInstance(result["library"], list)

    def test_empty_result_includes_new_keys(self):
        """Test that empty result structure includes new keys."""
        result = self.provider._empty_result("test_profile", "test error")

        self.assertIn("cel_variables", result)
        self.assertIn("library", result)
        self.assertEqual(result["cel_variables"], [])
        self.assertEqual(result["library"], [])


class TestCelSymbolProviderWithVariables(TransactionCase):
    """Test CEL symbol provider with actual variable records."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env["spp.cel.symbol.provider"]
        cls.test_var = None

        # Create test variable if the model exists
        if "spp.cel.variable" in cls.env:
            cls.Variable = cls.env["spp.cel.variable"]
            cls.test_var = cls.Variable.create(
                {
                    "name": "test_is_adult",
                    "cel_accessor": "is_adult",
                    "source_type": "computed",
                    "value_type": "boolean",
                    "cel_expression": "age_years(r.birthdate) >= 18",
                    "applies_to": "individual",
                    "state": "active",
                }
            )

    @classmethod
    def tearDownClass(cls):
        if cls.test_var:
            cls.test_var.unlink()
        super().tearDownClass()

    def test_cel_variable_returned_for_individual(self):
        """Test that CEL variables are returned for individual profile."""
        if "spp.cel.variable" not in self.env:
            self.skipTest("spp.cel.variable model not available")

        result = self.provider.get_symbols_for_profile("registry_individuals")

        # Find our test variable
        var_names = [v["name"] for v in result["cel_variables"]]
        self.assertIn("is_adult", var_names)

        # Check variable structure
        test_var = next(v for v in result["cel_variables"] if v["name"] == "is_adult")
        self.assertEqual(test_var["value_type"], "boolean")
        self.assertEqual(test_var["cel_expression"], "age_years(r.birthdate) >= 18")

    def test_cel_variable_context_filtering(self):
        """Test that CEL variables are filtered by context."""
        if "spp.cel.variable" not in self.env:
            self.skipTest("spp.cel.variable model not available")

        # Create a group-only variable
        group_var = self.Variable.create(
            {
                "name": "test_hh_size",
                "cel_accessor": "hh_size_test",
                "source_type": "aggregate",
                "value_type": "number",
                "cel_expression": "members.count(true)",
                "applies_to": "group",
                "state": "active",
            }
        )

        # Check it appears in group profile
        group_result = self.provider.get_symbols_for_profile("registry_groups")
        group_var_names = [v["name"] for v in group_result["cel_variables"]]
        self.assertIn("hh_size_test", group_var_names)

        # Check it does NOT appear in individual profile
        ind_result = self.provider.get_symbols_for_profile("registry_individuals")
        ind_var_names = [v["name"] for v in ind_result["cel_variables"]]
        self.assertNotIn("hh_size_test", ind_var_names)

        # Cleanup
        group_var.unlink()


class TestCelSymbolProviderWithExpressions(TransactionCase):
    """Test CEL symbol provider with library expressions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env["spp.cel.symbol.provider"]
        cls.test_expr = None

        # Create test expression if the model exists and has required fields
        if "spp.cel.expression" in cls.env:
            cls.Expression = cls.env["spp.cel.expression"]
            fields = cls.Expression._fields

            # Only create if spp_studio fields are available
            if "is_inline" in fields:
                cls.test_expr = cls.Expression.create(
                    {
                        "name": "Test Eligibility Logic",
                        "expression_type": "filter",
                        "context_type": "group",
                        "cel_expression": "members.count(true) >= 2",
                        "output_type": "boolean",
                        "is_inline": False,
                        "state": "published",
                    }
                )

    @classmethod
    def tearDownClass(cls):
        if cls.test_expr:
            cls.test_expr.unlink()
        super().tearDownClass()

    def test_library_expression_returned(self):
        """Test that published library expressions are returned."""
        if "spp.cel.expression" not in self.env:
            self.skipTest("spp.cel.expression model not available")

        if not hasattr(self, "test_expr") or not self.test_expr:
            self.skipTest("spp_studio not available")

        result = self.provider.get_symbols_for_profile("registry_groups")

        # Find our test expression
        expr_names = [e["name"] for e in result["library"]]
        self.assertIn("Test Eligibility Logic", expr_names)

        # Check expression structure
        test_expr = next(e for e in result["library"] if e["name"] == "Test Eligibility Logic")
        self.assertEqual(test_expr["expression_type"], "filter")
        self.assertEqual(test_expr["output_type"], "boolean")
        self.assertEqual(test_expr["cel_expression"], "members.count(true) >= 2")

    def test_library_context_filtering(self):
        """Test that library expressions are filtered by context."""
        if "spp.cel.expression" not in self.env:
            self.skipTest("spp.cel.expression model not available")

        if not hasattr(self, "test_expr") or not self.test_expr:
            self.skipTest("spp_studio not available")

        # Our test expression is group context
        # Check it appears in group profile
        group_result = self.provider.get_symbols_for_profile("registry_groups")
        group_expr_names = [e["name"] for e in group_result["library"]]
        self.assertIn("Test Eligibility Logic", group_expr_names)

        # Check it does NOT appear in individual profile
        ind_result = self.provider.get_symbols_for_profile("registry_individuals")
        ind_expr_names = [e["name"] for e in ind_result["library"]]
        self.assertNotIn("Test Eligibility Logic", ind_expr_names)
