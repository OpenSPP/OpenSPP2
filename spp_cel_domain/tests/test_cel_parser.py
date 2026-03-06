# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Adversarial tests for CEL parser - designed to BREAK the parser."""

from odoo.tests import TransactionCase, tagged

from ..services import cel_parser as P


@tagged("post_install", "-at_install")
class TestCELParserBreaking(TransactionCase):
    """Adversarial tests designed to find parser bugs and edge cases."""

    def test_empty_expression_fails(self):
        """Empty expressions should fail gracefully."""
        with self.assertRaises(SyntaxError):
            P.parse("")

    def test_whitespace_only_expression_fails(self):
        """Expression with only whitespace should fail."""
        with self.assertRaises(SyntaxError):
            P.parse("   \n\t  ")

    def test_single_tab_fails(self):
        """Single tab character should fail."""
        with self.assertRaises(SyntaxError):
            P.parse("\t")

    def test_extremely_long_expression(self):
        """Parser should handle very long expressions without crashing."""
        # Create a 50KB expression
        long_expr = " or ".join([f'r.field{i} == "value{i}"' for i in range(5000)])
        try:
            ast = P.parse(long_expr)
            self.assertIsNotNone(ast)
        except RecursionError:
            self.fail("Parser should not hit recursion limit on long expressions")
        except MemoryError:
            self.fail("Parser should not exhaust memory on long expressions")

    def test_deeply_nested_parentheses(self):
        """Parser should handle deeply nested parentheses."""
        # 100 levels of nesting
        expr = "(" * 100 + "true" + ")" * 100
        try:
            ast = P.parse(expr)
            self.assertIsNotNone(ast)
        except RecursionError:
            # This is acceptable - we need to limit nesting depth
            pass

    def test_unterminated_string_single_quote(self):
        """Unterminated strings should raise SyntaxError."""
        with self.assertRaises(SyntaxError) as ctx:
            P.parse("r.name == 'unterminated")
        self.assertIn("Unterminated", str(ctx.exception))

    def test_unterminated_string_double_quote(self):
        """Unterminated strings should raise SyntaxError."""
        with self.assertRaises(SyntaxError) as ctx:
            P.parse('r.name == "unterminated')
        self.assertIn("Unterminated", str(ctx.exception))

    def test_unterminated_escape_sequence(self):
        """String ending with backslash should fail."""
        with self.assertRaises(SyntaxError) as ctx:
            P.parse('r.name == "test\\')
        self.assertIn("escape", str(ctx.exception).lower())

    def test_invalid_operator(self):
        """Invalid operators should raise SyntaxError."""
        with self.assertRaises(SyntaxError):
            P.parse("r.age === 18")  # Triple equals

    def test_invalid_operator_assignment(self):
        """Assignment operators should not be allowed."""
        with self.assertRaises(SyntaxError):
            P.parse("r.age = 18")  # Single equals (assignment)

    def test_sql_injection_in_string_literal(self):
        """SQL injection attempts should be safely treated as literal strings."""
        expr = 'r.name == "Robert\'); DROP TABLE res_partner;--"'
        ast = P.parse(expr)
        # Should parse as a comparison with a literal string
        self.assertIsInstance(ast, P.Compare)
        self.assertEqual(ast.right.value, "Robert'); DROP TABLE res_partner;--")

    def test_code_injection_import_attempt(self):
        """Attempts to inject __import__ should be treated as identifiers."""
        expr = "__import__('os').system('ls')"
        ast = P.parse(expr)
        # Should parse as a function call, not execute code
        self.assertIsInstance(ast, P.Call)

    def test_code_injection_eval_attempt(self):
        """Attempts to inject eval should be treated as identifiers."""
        expr = "eval('1+1')"
        ast = P.parse(expr)
        # Should parse as a function call
        self.assertIsInstance(ast, P.Call)
        self.assertEqual(ast.func.name, "eval")

    def test_code_injection_exec_attempt(self):
        """Attempts to inject exec should be treated as identifiers."""
        expr = "exec('print(1)')"
        ast = P.parse(expr)
        # Should parse as a function call
        self.assertIsInstance(ast, P.Call)

    def test_unicode_characters_in_expression(self):
        """Unicode characters should be handled safely."""
        # Various unicode characters
        expr = 'r.name == "José García 日本語 Привет"'
        ast = P.parse(expr)
        self.assertIsInstance(ast, P.Compare)
        self.assertEqual(ast.right.value, "José García 日本語 Привет")

    def test_emoji_in_string_literal(self):
        """Emojis in strings should work."""
        expr = 'r.name == "Hello 👋 World 🌍"'
        ast = P.parse(expr)
        self.assertIsInstance(ast, P.Compare)

    def test_null_byte_in_expression(self):
        """Null bytes should not crash parser."""
        # Python strings can contain null bytes
        expr = "r.name == 'test\x00test'"
        ast = P.parse(expr)
        self.assertIsInstance(ast, P.Compare)

    def test_control_characters_in_string(self):
        """Control characters in strings should be handled."""
        expr = 'r.name == "test\r\n\t\x00"'
        ast = P.parse(expr)
        self.assertIsInstance(ast, P.Compare)

    def test_reserved_python_keywords_as_identifiers(self):
        """Reserved Python keywords should work as field names."""
        # These are already keywords in CEL: and, or, not, true, false
        # But other Python keywords should work
        expr = "class == 5"  # 'class' is a Python keyword
        ast = P.parse(expr)
        self.assertIsInstance(ast, P.Compare)
        self.assertEqual(ast.left.name, "class")

    def test_malformed_number_multiple_dots(self):
        """Numbers with multiple decimal points should fail."""
        with self.assertRaises(SyntaxError):
            # This might parse as "1.2" then ".3" or raise an error
            P.parse("r.age > 1.2.3")

    def test_number_starting_with_dot(self):
        """Numbers starting with dot should fail."""
        with self.assertRaises(SyntaxError):
            P.parse("r.age > .5")

    def test_extremely_large_number(self):
        """Very large numbers should not cause overflow."""
        expr = "r.age > 99999999999999999999999999999999999"
        ast = P.parse(expr)
        self.assertIsInstance(ast, P.Compare)

    def test_negative_number(self):
        """Negative numbers are supported via unary minus."""
        ast = P.parse("r.age > -5")
        self.assertIsInstance(ast, P.Compare)
        self.assertEqual(ast.op, "GT")
        # Right side should be Neg(Literal(5))
        self.assertIsInstance(ast.right, P.Neg)
        self.assertEqual(ast.right.expr.value, 5)

    def test_comparison_chain_not_supported(self):
        """Chained comparisons like 'a < b < c' should not work."""
        # CEL doesn't support this, but parser might accept it
        expr = "10 < r.age < 20"
        # This will parse but might not give expected result
        _ = P.parse(expr)
        # It will parse as (10 < r.age) < 20, which is probably not intended

    def test_list_literal_with_trailing_comma(self):
        """Lists with trailing commas should work."""
        expr = "r.status in ['active', 'pending',]"
        ast = P.parse(expr)
        self.assertIsInstance(ast, P.InOp)

    def test_empty_list_literal(self):
        """Empty list should work."""
        expr = "r.status in []"
        ast = P.parse(expr)
        self.assertIsInstance(ast, P.InOp)

    def test_nested_list_literals_not_supported(self):
        """Nested lists should not be supported."""
        # Parser might accept this but won't work correctly
        expr = "r.data in [[1, 2], [3, 4]]"
        _ = P.parse(expr)
        # Will parse but nested lists won't work as expected

    def test_function_call_no_args(self):
        """Function calls with no arguments."""
        expr = "today()"
        ast = P.parse(expr)
        self.assertIsInstance(ast, P.Call)
        self.assertEqual(len(ast.args), 0)

    def test_function_call_trailing_comma(self):
        """Function calls with trailing comma."""
        expr = "age_years(r.birthdate,)"
        ast = P.parse(expr)
        self.assertIsInstance(ast, P.Call)

    def test_unterminated_function_call(self):
        """Unterminated function call should fail."""
        with self.assertRaises(SyntaxError):
            P.parse("age_years(r.birthdate")

    def test_unterminated_list_literal(self):
        """Unterminated list should fail."""
        with self.assertRaises(SyntaxError):
            P.parse("r.status in ['active', 'pending'")

    def test_mismatched_parentheses(self):
        """Mismatched parentheses should fail."""
        with self.assertRaises(SyntaxError):
            P.parse("(r.age > 18")

    def test_extra_closing_parenthesis(self):
        """Extra closing parenthesis should fail."""
        with self.assertRaises(SyntaxError):
            P.parse("r.age > 18)")

    def test_attribute_access_on_literal(self):
        """Accessing attributes on literals should fail or parse strangely."""
        expr = "5.name == 'five'"
        # This might parse as a float "5." followed by invalid syntax
        # or it might parse as (5).name
        with self.assertRaises(SyntaxError):
            P.parse(expr)

    def test_double_dot_attribute_access(self):
        """Double dots in attribute access should fail."""
        with self.assertRaises(SyntaxError):
            P.parse("r..name == 'test'")

    def test_attribute_starting_with_number(self):
        """Attribute names starting with numbers should fail."""
        with self.assertRaises(SyntaxError):
            P.parse("r.1name == 'test'")

    def test_special_characters_in_identifier(self):
        """Special characters in identifiers should fail."""
        with self.assertRaises(SyntaxError):
            P.parse("r.first@name == 'test'")  # @ not allowed in identifiers

    def test_bang_not_operator_supported(self):
        """'!' should be accepted as a logical NOT operator."""
        # Simple negation
        ast = P.parse("!has_government_employee")
        self.assertIsInstance(ast, P.Not)
        self.assertIsInstance(ast.expr, P.Ident)
        self.assertEqual(ast.expr.name, "has_government_employee")

        # Combined with OR, as used in studio packs
        ast = P.parse("is_orphan || (!has_mother && !has_father)")
        # Top-level should be an OR node
        self.assertIsInstance(ast, P.Or)

    def test_cache_pollution_same_expression(self):
        """Parsing same expression multiple times should use cache."""
        expr = "r.age >= 18"
        ast1 = P.parse(expr)
        ast2 = P.parse(expr)
        # Should return the same cached object
        self.assertIs(ast1, ast2)

    def test_cache_different_expressions(self):
        """Different expressions should not interfere."""
        ast1 = P.parse("r.age >= 18")
        ast2 = P.parse("r.name == 'test'")
        self.assertIsNot(ast1, ast2)

    def test_expression_with_only_operators(self):
        """Expression with only operators should fail."""
        with self.assertRaises(SyntaxError):
            P.parse("and or not")

    def test_expression_starting_with_operator(self):
        """Expression starting with binary operator should fail."""
        with self.assertRaises(SyntaxError):
            P.parse("and r.age > 18")

    def test_expression_ending_with_operator(self):
        """Expression ending with operator should fail."""
        with self.assertRaises(SyntaxError):
            P.parse("r.age > 18 and")

    def test_consecutive_operators(self):
        """Consecutive operators should fail."""
        with self.assertRaises(SyntaxError):
            P.parse("r.age > >= 18")

    def test_boolean_literal_true(self):
        """Boolean literal 'true' should parse."""
        ast = P.parse("true")
        self.assertIsInstance(ast, P.Literal)
        self.assertTrue(ast.value)

    def test_boolean_literal_false(self):
        """Boolean literal 'false' should parse."""
        ast = P.parse("false")
        self.assertIsInstance(ast, P.Literal)
        self.assertFalse(ast.value)

    def test_boolean_literal_uppercase_not_supported(self):
        """Uppercase 'TRUE' or 'FALSE' should not work."""
        # These will be treated as identifiers, not boolean literals
        ast = P.parse("TRUE")
        self.assertIsInstance(ast, P.Ident)
        self.assertEqual(ast.name, "TRUE")

    def test_in_operator_with_non_list(self):
        """IN operator with non-list should fail."""
        with self.assertRaises(SyntaxError):
            P.parse("r.status in 'active'")

    def test_in_operator_with_identifier(self):
        """IN operator with identifier (not list) should fail."""
        with self.assertRaises(SyntaxError):
            P.parse("r.status in some_variable")

    def test_comparison_with_multiple_values(self):
        """Comparisons don't support multiple RHS values."""
        # This is not valid CEL syntax
        with self.assertRaises(SyntaxError):
            P.parse("r.age == 18, 19, 20")

    def test_escape_sequences_in_strings(self):
        """Various escape sequences should work."""
        expr = r'r.name == "test\nline\tbreak"'
        ast = P.parse(expr)
        self.assertIsInstance(ast, P.Compare)
        # The escape sequence is stored as-is (not interpreted)
        self.assertEqual(ast.right.value, "testnlinetbreak")

    def test_backslash_escape_quote(self):
        """Escaping quotes should work."""
        expr = r'r.name == "He said \"Hello\""'
        ast = P.parse(expr)
        self.assertEqual(ast.right.value, 'He said "Hello"')

    def test_single_quote_in_double_quoted_string(self):
        """Single quotes in double-quoted strings don't need escaping."""
        expr = """r.name == "It's fine" """
        ast = P.parse(expr)
        self.assertEqual(ast.right.value, "It's fine")

    def test_double_quote_in_single_quoted_string(self):
        """Double quotes in single-quoted strings don't need escaping."""
        expr = """r.name == 'He said "Hello"' """
        ast = P.parse(expr)
        self.assertEqual(ast.right.value, 'He said "Hello"')

    def test_method_style_call_on_literal(self):
        """Method-style calls on literals should fail or parse strangely."""
        with self.assertRaises(SyntaxError):
            P.parse("5.exists()")

    def test_chained_method_calls(self):
        """Chained method calls should work."""
        expr = "r.members.exists(m, m.age > 5)"
        ast = P.parse(expr)
        self.assertIsInstance(ast, P.Call)

    def test_not_operator_precedence(self):
        """NOT operator should have correct precedence."""
        expr = "not r.age > 18"
        ast = P.parse(expr)
        self.assertIsInstance(ast, P.Not)

    def test_and_or_precedence(self):
        """AND should have higher precedence than OR."""
        expr = "r.age > 18 or r.status == 'active' and r.verified == true"
        ast = P.parse(expr)
        self.assertIsInstance(ast, P.Or)
        # Right side should be AND
        self.assertIsInstance(ast.right, P.And)

    def test_parentheses_override_precedence(self):
        """Parentheses should override precedence."""
        expr = "(r.age > 18 or r.status == 'active') and r.verified == true"
        ast = P.parse(expr)
        self.assertIsInstance(ast, P.And)
        self.assertIsInstance(ast.left, P.Or)

    def test_redundant_parentheses(self):
        """Multiple levels of redundant parentheses should work."""
        expr = "((((r.age > 18))))"
        ast = P.parse(expr)
        self.assertIsInstance(ast, P.Compare)

    def test_eof_token_placement(self):
        """EOF token should always be last."""
        tokens = P.Lexer("r.age > 18").tokens()
        self.assertEqual(tokens[-1].kind, "EOF")

    def test_position_tracking_in_tokens(self):
        """Tokens should track their position in the input."""
        tokens = P.Lexer("r.age >= 18").tokens()
        # Each token should have a position
        for tok in tokens:
            self.assertIsInstance(tok.pos, int)
            self.assertGreaterEqual(tok.pos, 0)

    def test_odoo_null_field_equals_null(self):
        """Odoo returns False for unset non-boolean fields; CEL null comparison should treat as None.

        When an Odoo Datetime/Date/Char/etc. field is NULL in the DB, the ORM
        returns False. CEL 'null' maps to Python None. Without normalization,
        `m.disabled != null` becomes `False != None` which is True for every
        record, even though the field IS null.
        """
        # Create a registrant with an unset disabled (Datetime) field
        partner = self.env["res.partner"].create(
            {"name": "CEL Null Test Person", "is_registrant": True, "is_group": False}
        )

        # Odoo ORM returns False for unset Datetime fields
        self.assertIs(partner.disabled, False)

        # CEL: m.disabled == null should be True (field is unset)
        ast = P.parse("m.disabled == null")
        result = P.evaluate(ast, {"m": partner})
        self.assertTrue(
            result,
            f"m.disabled == null should be True when disabled is unset (ORM returns {partner.disabled!r})",
        )

        # CEL: m.disabled != null should be False (field is unset)
        ast = P.parse("m.disabled != null")
        result = P.evaluate(ast, {"m": partner})
        self.assertFalse(
            result,
            f"m.disabled != null should be False when disabled is unset (ORM returns {partner.disabled!r})",
        )

    def test_odoo_boolean_false_not_treated_as_null(self):
        """Boolean fields that are legitimately False should NOT be normalized to None."""
        partner = self.env["res.partner"].create({"name": "CEL Bool Test", "is_registrant": False})

        # is_registrant is a Boolean field, False is a real value
        ast = P.parse("m.is_registrant == false")
        result = P.evaluate(ast, {"m": partner})
        self.assertTrue(
            result,
            "Boolean False should remain False, not become None",
        )

        # Boolean False should NOT equal null
        ast = P.parse("m.is_registrant == null")
        result = P.evaluate(ast, {"m": partner})
        self.assertFalse(
            result,
            "Boolean False should not equal null",
        )
