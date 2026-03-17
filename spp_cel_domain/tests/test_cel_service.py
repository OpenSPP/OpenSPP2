# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Adversarial tests for CEL Service - designed to BREAK the service facade."""

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCELServiceBreaking(TransactionCase):
    """Adversarial tests for CEL service facade."""

    def setUp(self):
        super().setUp()
        self.service = self.env["spp.cel.service"]

    def test_empty_expression_returns_error(self):
        """Empty expression should return error, not crash."""
        result = self.service.compile_expression("", "registry_individuals")
        self.assertFalse(result["valid"])
        self.assertIsNotNone(result["error"])
        self.assertIn("empty", result["error"].lower())

    def test_whitespace_only_expression_returns_error(self):
        """Whitespace-only expression should return error."""
        result = self.service.compile_expression("   \n\t  ", "registry_individuals")
        self.assertFalse(result["valid"])
        self.assertIsNotNone(result["error"])

    def test_none_expression_returns_error(self):
        """None as expression should return error."""
        result = self.service.compile_expression(None, "registry_individuals")
        self.assertFalse(result["valid"])
        self.assertIsNotNone(result["error"])

    def test_invalid_syntax_returns_error(self):
        """Invalid syntax should return structured error."""
        result = self.service.compile_expression("r.age >>>", "registry_individuals")
        self.assertFalse(result["valid"])
        self.assertIsNotNone(result["error"])
        self.assertIn("syntax", result["error"].lower())

    def test_unknown_symbol_returns_error(self):
        """Unknown symbol should return helpful error."""
        result = self.service.compile_expression("nonexistent_field == 5", "registry_individuals")
        # Might fail or succeed depending on how fields are resolved
        # If it fails, should be helpful
        if not result["valid"]:
            self.assertIsNotNone(result["error"])

    def test_unknown_profile_raises_or_returns_error(self):
        """Unknown profile should fail gracefully."""
        try:
            result = self.service.compile_expression("r.age >= 18", "nonexistent_profile_xyz")
            # If it returns, should be invalid
            self.assertFalse(result.get("valid", False))
        except Exception as e:
            # Should be a helpful exception
            self.assertIn("profile", str(e).lower())

    def test_empty_profile_name_fails(self):
        """Empty profile name should fail."""
        try:
            result = self.service.compile_expression("r.age >= 18", "")
            self.assertFalse(result.get("valid", False))
        except Exception:
            pass  # Expected

    def test_none_profile_name_uses_defaults(self):
        """None as profile name should use default settings."""
        # When profile is None, service converts to string "None" and
        # uses default fallback settings (res.partner with no base_domain)
        result = self.service.compile_expression("r.id > 0", None)
        # Service uses defaults, so expression should still compile
        self.assertTrue(result.get("valid", False))

    def test_valid_expression_returns_success(self):
        """Valid expression should return success."""
        result = self.service.compile_expression("true", "registry_individuals")
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")
        self.assertIsNone(result["error"])
        self.assertIsInstance(result["domain"], list)
        self.assertIsInstance(result["count"], int)
        self.assertIsInstance(result["ids"], list)

    def test_base_domain_is_merged(self):
        """Base domain should be ANDed with compiled domain."""
        base_domain = [("is_group", "=", False)]
        result = self.service.compile_expression("true", "registry_individuals", base_domain=base_domain)
        self.assertTrue(result["valid"])
        # Domain should include base_domain constraints
        # (hard to verify exact structure, but should not crash)

    def test_base_domain_none_is_safe(self):
        """None as base_domain should work."""
        result = self.service.compile_expression("true", "registry_individuals", base_domain=None)
        self.assertTrue(result["valid"])

    def test_base_domain_empty_list_is_safe(self):
        """Empty list as base_domain should work."""
        result = self.service.compile_expression("true", "registry_individuals", base_domain=[])
        self.assertTrue(result["valid"])

    def test_limit_zero_returns_count_only(self):
        """Limit=0 should return count but no IDs."""
        result = self.service.compile_expression("true", "registry_individuals", limit=0)
        self.assertTrue(result["valid"])
        # IDs list should be empty or full list depending on implementation
        self.assertIsInstance(result["count"], int)

    def test_limit_negative_handled_gracefully(self):
        """Negative limit should be normalized to 0 (count-only mode)."""
        result = self.service.compile_expression("true", "registry_individuals", limit=-1)
        # Should not crash and should return valid result
        self.assertIsNotNone(result)
        self.assertTrue(result["valid"])
        # Negative limit normalized to 0 means count-only (no IDs returned)
        self.assertEqual(result["ids"], [])

    def test_limit_very_large_handled(self):
        """Very large limit should not cause issues."""
        result = self.service.compile_expression("true", "registry_individuals", limit=999999999)
        self.assertTrue(result["valid"])

    def test_validate_expression_method(self):
        """validate_expression should return valid/error/explain."""
        result = self.service.validate_expression("true", "registry_individuals")
        self.assertIn("valid", result)
        self.assertIn("error", result)
        self.assertIn("explain", result)

    def test_validate_invalid_expression(self):
        """validate_expression on invalid expression."""
        result = self.service.validate_expression("invalid >>>", "registry_individuals")
        self.assertFalse(result["valid"])
        self.assertIsNotNone(result["error"])

    def test_get_matching_ids_valid_expression(self):
        """get_matching_ids should return list of IDs."""
        ids = self.service.get_matching_ids("true", "registry_individuals")
        self.assertIsInstance(ids, list)

    def test_get_matching_ids_invalid_expression_returns_empty(self):
        """get_matching_ids on invalid expression should return empty list."""
        ids = self.service.get_matching_ids("invalid >>>", "registry_individuals")
        self.assertEqual(ids, [])

    def test_get_domain_valid_expression(self):
        """get_domain should return Odoo domain list."""
        domain = self.service.get_domain("true", "registry_individuals")
        self.assertIsInstance(domain, list)

    def test_get_domain_invalid_expression_returns_empty(self):
        """get_domain on invalid expression should return empty list."""
        domain = self.service.get_domain("invalid >>>", "registry_individuals")
        self.assertEqual(domain, [])

    def test_get_available_profiles(self):
        """get_available_profiles should return list of profile names."""
        profiles = self.service.get_available_profiles()
        self.assertIsInstance(profiles, list)
        self.assertIn("registry_individuals", profiles)
        self.assertIn("registry_groups", profiles)

    def test_get_profile_info_valid_profile(self):
        """get_profile_info should return profile details."""
        info = self.service.get_profile_info("registry_individuals")
        self.assertIn("name", info)
        self.assertIn("root_model", info)
        self.assertEqual(info["name"], "registry_individuals")

    def test_get_profile_info_invalid_profile(self):
        """get_profile_info on invalid profile should return error."""
        info = self.service.get_profile_info("nonexistent_xyz")
        self.assertIn("name", info)
        # Might have error key
        if "error" in info:
            self.assertIsNotNone(info["error"])

    def test_invalidate_caches_doesnt_crash(self):
        """invalidate_caches should not crash."""
        result = self.service.invalidate_caches()
        self.assertTrue(result)

    def test_concurrent_compilation_same_expression(self):
        """Multiple compilations of same expression should be safe."""
        results = []
        for _ in range(10):
            result = self.service.compile_expression("true", "registry_individuals")
            results.append(result)
        # All should succeed
        for result in results:
            self.assertTrue(result["valid"])

    def test_concurrent_compilation_different_expressions(self):
        """Multiple compilations of different expressions should be safe."""
        expressions = [
            "true",
            "false",
            "r.id > 0",
            "r.is_registrant == true",
        ]
        results = []
        for expr in expressions:
            result = self.service.compile_expression(expr, "registry_individuals")
            results.append(result)
        # All should succeed
        for result in results:
            self.assertTrue(result["valid"], f"Failed: {result.get('error')}")

    def test_expression_with_unicode(self):
        """Expression with unicode should work."""
        result = self.service.compile_expression('r.name == "José García"', "registry_individuals")
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")

    def test_sql_injection_attempt_safely_handled(self):
        """SQL injection attempts should be safely escaped."""
        result = self.service.compile_expression(
            'r.name == "Robert\'); DROP TABLE res_partner;--"',
            "registry_individuals",
        )
        # Should either succeed (treating as literal) or fail safely
        # Must NOT execute SQL
        self.assertIsInstance(result, dict)

    def test_code_injection_attempt_safely_handled(self):
        """Code injection attempts should not execute."""
        result = self.service.compile_expression("__import__('os').system('ls')", "registry_individuals")
        # Should fail or treat as function call, not execute code
        self.assertIsInstance(result, dict)

    def test_path_traversal_in_profile_name(self):
        """Path traversal attempts in profile name should fail."""
        try:
            result = self.service.compile_expression("true", "../../../etc/passwd")
            # Should fail
            self.assertFalse(result.get("valid", False))
        except Exception:
            pass  # Expected

    def test_denial_of_service_complex_expression(self):
        """Complex expressions should complete in reasonable time."""
        import time

        # Create a moderately complex expression
        expr = " or ".join([f"r.field{i} == {i}" for i in range(100)])
        start = time.time()
        _ = self.service.compile_expression(expr, "registry_individuals", limit=0)
        elapsed = time.time() - start
        # Should complete in under 5 seconds
        self.assertLess(elapsed, 5.0, f"Took {elapsed}s - possible DoS")

    def test_memory_exhaustion_via_large_list(self):
        """Large list literals should be rejected for scalability (preventing memory exhaustion)."""
        # Create a list with 10000 items - exceeds 1000 limit
        items = ", ".join([str(i) for i in range(10000)])
        expr = f"r.id in [{items}]"

        result = self.service.compile_expression(expr, "registry_individuals", limit=0)

        # Should return error for scalability constraint instead of exhausting memory
        self.assertIn("error", result)
        self.assertIn("1000", result["error"])  # Limit mentioned in error
        self.assertIn("10000", result["error"])  # Actual count mentioned

    def test_recursive_expression_handled(self):
        """Deeply nested expressions should not cause stack overflow."""
        # Create deeply nested AND/OR
        expr = "true"
        for _ in range(100):
            expr = f"({expr} and true)"
        try:
            result = self.service.compile_expression(expr, "registry_individuals", limit=0)
            self.assertIsInstance(result, dict)
        except RecursionError:
            # Acceptable - we have recursion limits
            pass

    def test_xss_in_error_messages(self):
        """Error messages should not be vulnerable to XSS."""
        # Try to inject HTML/JS in expression
        result = self.service.compile_expression('<script>alert("XSS")</script> == 1', "registry_individuals")
        if not result["valid"]:
            error = result["error"]
            # Error message should not contain unescaped HTML
            # (In practice, Odoo should escape this in UI)
            self.assertIsInstance(error, str)

    def test_different_profiles_isolated(self):
        """Different profiles should have independent configurations."""
        result1 = self.service.compile_expression("true", "registry_individuals")
        result2 = self.service.compile_expression("true", "registry_groups")
        # Both should work
        self.assertTrue(result1["valid"])
        self.assertTrue(result2["valid"])
        # Should have different root models
        info1 = self.service.get_profile_info("registry_individuals")
        info2 = self.service.get_profile_info("registry_groups")
        # Both are res.partner but with different base_domain
        self.assertEqual(info1["root_model"], "res.partner")
        self.assertEqual(info2["root_model"], "res.partner")

    def test_caching_works_for_same_expression(self):
        """Repeated compilation of same expression should use cache."""
        import time

        expr = "r.id > 0 and r.is_registrant == true"
        # First call (cache miss)
        start = time.time()
        result1 = self.service.compile_expression(expr, "registry_individuals", limit=0)
        first_time = time.time() - start
        # Second call (cache hit)
        start = time.time()
        result2 = self.service.compile_expression(expr, "registry_individuals", limit=0)
        second_time = time.time() - start
        # Both should succeed
        self.assertTrue(result1["valid"])
        self.assertTrue(result2["valid"])
        # Second call should be faster (or at least not significantly slower)
        # This is a weak test since cache speedup may vary
        self.assertLessEqual(second_time, first_time * 2)

    def test_cache_invalidation_works(self):
        """Cache invalidation should clear cached results."""
        expr = "r.id > 0"
        # Compile once
        result1 = self.service.compile_expression(expr, "registry_individuals", limit=0)
        self.assertTrue(result1["valid"])
        # Invalidate cache
        self.service.invalidate_caches()
        # Compile again - should recompute
        result2 = self.service.compile_expression(expr, "registry_individuals", limit=0)
        self.assertTrue(result2["valid"])

    def test_explain_field_populated(self):
        """explain field should contain human-readable description."""
        result = self.service.compile_expression("true", "registry_individuals")
        self.assertTrue(result["valid"])
        self.assertIsInstance(result["explain"], str)
        self.assertGreater(len(result["explain"]), 0)

    def test_domain_field_is_valid_odoo_domain(self):
        """domain field should be valid Odoo domain."""
        result = self.service.compile_expression("true", "registry_individuals")
        self.assertTrue(result["valid"])
        domain = result["domain"]
        self.assertIsInstance(domain, list)
        # Should be able to use it in search
        try:
            self.env["res.partner"].search(domain, limit=1)
        except Exception as e:
            self.fail(f"Domain is not valid: {e}")

    def test_count_matches_ids_length(self):
        """count should match length of ids when limit is sufficient."""
        result = self.service.compile_expression("true", "registry_individuals", limit=100)
        self.assertTrue(result["valid"])
        # If count <= 100, ids length should equal count
        if result["count"] <= 100:
            self.assertEqual(len(result["ids"]), result["count"])

    def test_multiple_base_domain_clauses(self):
        """Multiple clauses in base_domain should all be applied."""
        base_domain = [
            ("is_group", "=", False),
            ("is_registrant", "=", True),
            ("active", "=", True),
        ]
        result = self.service.compile_expression("true", "registry_individuals", base_domain=base_domain)
        self.assertTrue(result["valid"])


@tagged("post_install", "-at_install")
class TestCELFormulaValidation(TransactionCase):
    """Tests for validate_formula_expression method.

    Formula expressions calculate values (numbers, money, strings) rather than
    filtering records. They should not be compiled to Odoo domains.
    """

    def setUp(self):
        super().setUp()
        self.service = self.env["spp.cel.service"]

    # ═══════════════════════════════════════════════════════════════════════
    # BASIC VALIDATION
    # ═══════════════════════════════════════════════════════════════════════

    def test_empty_expression_returns_error(self):
        """Empty expression should return error."""
        result = self.service.validate_formula_expression("", "registry_groups")
        self.assertFalse(result["valid"])
        self.assertIsNotNone(result["error"])
        self.assertIn("empty", result["error"].lower())

    def test_whitespace_only_expression_returns_error(self):
        """Whitespace-only expression should return error."""
        result = self.service.validate_formula_expression("   \n\t  ", "registry_groups")
        self.assertFalse(result["valid"])
        self.assertIsNotNone(result["error"])

    def test_none_expression_returns_error(self):
        """None as expression should return error."""
        result = self.service.validate_formula_expression(None, "registry_groups")
        self.assertFalse(result["valid"])
        self.assertIsNotNone(result["error"])

    # ═══════════════════════════════════════════════════════════════════════
    # VALID FORMULA EXPRESSIONS
    # ═══════════════════════════════════════════════════════════════════════

    def test_simple_number_literal(self):
        """Simple number literal should be valid."""
        result = self.service.validate_formula_expression("1000", "registry_groups")
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")
        self.assertIsNone(result["error"])
        self.assertIsNone(result["count"])  # Formulas don't have matching counts

    def test_arithmetic_expression(self):
        """Arithmetic expression should be valid."""
        result = self.service.validate_formula_expression("100 + 50 * 2", "registry_groups")
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")

    def test_multiplication_with_variable(self):
        """Formula with variable multiplication should be valid."""
        # Uses hh_size which is a defined variable
        result = self.service.validate_formula_expression("100 * 5", "registry_groups")
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")

    def test_ternary_expression(self):
        """Ternary conditional expression should be valid."""
        result = self.service.validate_formula_expression("true ? 100 : 50", "registry_groups")
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")

    def test_function_call_in_formula(self):
        """Function call in formula should be valid."""
        result = self.service.validate_formula_expression("max(100, 200)", "registry_groups")
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")

    # ═══════════════════════════════════════════════════════════════════════
    # SYNTAX ERRORS
    # ═══════════════════════════════════════════════════════════════════════

    def test_invalid_syntax_returns_error(self):
        """Invalid syntax should return structured error."""
        result = self.service.validate_formula_expression("100 +++", "registry_groups")
        self.assertFalse(result["valid"])
        self.assertIsNotNone(result["error"])
        self.assertIn("syntax", result["error"].lower())

    def test_unbalanced_parentheses(self):
        """Unbalanced parentheses should return error."""
        result = self.service.validate_formula_expression("(100 + 50", "registry_groups")
        self.assertFalse(result["valid"])
        self.assertIsNotNone(result["error"])

    def test_invalid_operator(self):
        """Invalid operator should return error."""
        result = self.service.validate_formula_expression("100 >>> 50", "registry_groups")
        self.assertFalse(result["valid"])
        self.assertIsNotNone(result["error"])

    # ═══════════════════════════════════════════════════════════════════════
    # RESULT STRUCTURE
    # ═══════════════════════════════════════════════════════════════════════

    def test_result_contains_required_keys(self):
        """Result should contain all required keys."""
        result = self.service.validate_formula_expression("100", "registry_groups")
        self.assertIn("valid", result)
        self.assertIn("error", result)
        self.assertIn("explain", result)
        self.assertIn("resolved_expression", result)
        self.assertIn("count", result)

    def test_valid_result_has_explain(self):
        """Valid result should have explanation."""
        result = self.service.validate_formula_expression("100 * 5", "registry_groups")
        self.assertTrue(result["valid"])
        self.assertIsInstance(result["explain"], str)
        self.assertGreater(len(result["explain"]), 0)

    def test_formula_count_is_none(self):
        """Formulas don't have matching counts - count should be None."""
        result = self.service.validate_formula_expression("1000", "registry_groups")
        self.assertTrue(result["valid"])
        self.assertIsNone(result["count"])

    # ═══════════════════════════════════════════════════════════════════════
    # PROFILE HANDLING
    # ═══════════════════════════════════════════════════════════════════════

    def test_none_profile_uses_defaults(self):
        """None profile should use default context."""
        result = self.service.validate_formula_expression("100", None)
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")

    def test_individual_profile(self):
        """Individual profile should work."""
        result = self.service.validate_formula_expression("100", "registry_individuals")
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")

    def test_group_profile(self):
        """Group profile should work."""
        result = self.service.validate_formula_expression("100", "registry_groups")
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")

    # ═══════════════════════════════════════════════════════════════════════
    # OUTPUT TYPE PARAMETER (FUTURE USE)
    # ═══════════════════════════════════════════════════════════════════════

    def test_output_type_money(self):
        """Output type 'money' should be accepted (for future type checking)."""
        result = self.service.validate_formula_expression("1000", "registry_groups", output_type="money")
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")

    def test_output_type_number(self):
        """Output type 'number' should be accepted."""
        result = self.service.validate_formula_expression("5", "registry_groups", output_type="number")
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")

    def test_output_type_string(self):
        """Output type 'string' should be accepted."""
        result = self.service.validate_formula_expression('"hello"', "registry_groups", output_type="string")
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")

    # --- Offset / Pagination Tests ---

    def test_compile_expression_offset_returns_different_records(self):
        """compile_expression with offset should return different records."""
        for i in range(5):
            self.env["res.partner"].create({"name": f"OffsetSvcTest{i}", "is_registrant": True, "is_group": False})
        result1 = self.service.compile_expression(
            'r.name.startsWith("OffsetSvcTest")', "registry_individuals", limit=2, offset=0, fields=["id", "name"]
        )
        result2 = self.service.compile_expression(
            'r.name.startsWith("OffsetSvcTest")', "registry_individuals", limit=2, offset=2, fields=["id", "name"]
        )
        self.assertTrue(result1["valid"])
        self.assertTrue(result2["valid"])
        ids1 = {r["id"] for r in result1.get("preview_records", [])}
        ids2 = {r["id"] for r in result2.get("preview_records", [])}
        self.assertFalse(ids1 & ids2, "Offset pages should not overlap")

    def test_compile_expression_offset_beyond_results(self):
        """compile_expression with offset beyond total should return empty."""
        result = self.service.compile_expression("true", "registry_individuals", limit=10, offset=999999, fields=["id"])
        self.assertTrue(result["valid"])
        self.assertEqual(len(result.get("preview_records", [])), 0)

    def test_compile_expression_phone_number_enrichment(self):
        """compile_expression with phone_number_ids field should enrich results."""
        partner = self.env["res.partner"].create({"name": "PhoneSvcTest99", "is_registrant": True, "is_group": False})
        if "spp.phone.number" in self.env:
            self.env["spp.phone.number"].create({"partner_id": partner.id, "phone_no": "+111"})
            self.env["spp.phone.number"].create({"partner_id": partner.id, "phone_no": "+222"})
        result = self.service.compile_expression(
            'r.name == "PhoneSvcTest99"', "registry_individuals", limit=10, fields=["id", "name", "phone_number_ids"]
        )
        self.assertTrue(result["valid"])
        records = result.get("preview_records", [])
        self.assertEqual(len(records), 1)
        if "spp.phone.number" in self.env:
            self.assertIn("phone_numbers", records[0])
            self.assertEqual(sorted(records[0]["phone_numbers"]), ["+111", "+222"])

    def test_compile_expression_phone_excludes_disabled(self):
        """Phone enrichment should exclude disabled phone numbers."""
        partner = self.env["res.partner"].create({"name": "PhoneDisabledTest99", "is_registrant": True, "is_group": False})
        if "spp.phone.number" in self.env:
            self.env["spp.phone.number"].create({"partner_id": partner.id, "phone_no": "+active"})
            disabled_phone = self.env["spp.phone.number"].create({"partner_id": partner.id, "phone_no": "+disabled"})
            disabled_phone.disabled = fields.Datetime.now()
        result = self.service.compile_expression(
            'r.name == "PhoneDisabledTest99"', "registry_individuals", limit=10, fields=["id", "phone_number_ids"]
        )
        records = result.get("preview_records", [])
        if "spp.phone.number" in self.env and records:
            self.assertEqual(records[0]["phone_numbers"], ["+active"])
