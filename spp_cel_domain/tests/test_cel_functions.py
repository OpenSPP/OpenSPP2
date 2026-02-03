# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for CEL functions including size, has, matches, and parser extensions."""

from odoo.tests import TransactionCase, tagged

from ..services import cel_functions as F
from ..services import cel_parser as P


@tagged("post_install", "-at_install")
class TestCELFunctionsSize(TransactionCase):
    """Test cases for the size() function."""

    def test_size_list(self):
        """Size of a list."""
        self.assertEqual(F.size([1, 2, 3]), 3)

    def test_size_empty_list(self):
        """Size of an empty list."""
        self.assertEqual(F.size([]), 0)

    def test_size_string(self):
        """Size of a string."""
        self.assertEqual(F.size("hello"), 5)

    def test_size_empty_string(self):
        """Size of an empty string."""
        self.assertEqual(F.size(""), 0)

    def test_size_dict(self):
        """Size of a dict."""
        self.assertEqual(F.size({"a": 1, "b": 2}), 2)

    def test_size_none(self):
        """Size of None should be 0."""
        self.assertEqual(F.size(None), 0)

    def test_size_odoo_recordset_dict_with_ids(self):
        """Size of dict with 'ids' key (Odoo recordset representation)."""
        self.assertEqual(F.size({"ids": [1, 2, 3, 4, 5]}), 5)

    def test_size_odoo_recordset_dict_with_count(self):
        """Size of dict with 'count' key (Odoo recordset representation)."""
        self.assertEqual(F.size({"count": 10, "ids": [1, 2]}), 10)

    def test_size_in_expression(self):
        """Test size() used in CEL expression."""
        context = {
            "size": F.size,
            "items": [1, 2, 3, 4, 5],
        }
        ast = P.parse("size(items) > 3")
        result = P.evaluate(ast, context)
        self.assertTrue(result)

    def test_size_of_record_field(self):
        """Test size() on a record's collection field."""
        context = {
            "size": F.size,
            "record": {
                "line_ids": {"ids": [1, 2, 3], "count": 3},
            },
        }
        ast = P.parse("size(record.line_ids) > 2")
        result = P.evaluate(ast, context)
        self.assertTrue(result)


@tagged("post_install", "-at_install")
class TestCELFunctionsHas(TransactionCase):
    """Test cases for the has() function."""

    def test_has_single_arg_truthy(self):
        """has(value) returns True for truthy value."""
        self.assertTrue(F.has("non-empty"))
        self.assertTrue(F.has(1))
        self.assertTrue(F.has([1, 2, 3]))

    def test_has_single_arg_falsy(self):
        """has(value) returns False for falsy value."""
        self.assertFalse(F.has(None))
        self.assertFalse(F.has(""))
        self.assertFalse(F.has(0))
        self.assertFalse(F.has([]))

    def test_has_dict_field_present(self):
        """has(obj, field) with dict and present field."""
        obj = {"name": "John", "email": "john@example.com"}
        self.assertTrue(F.has(obj, "name"))
        self.assertTrue(F.has(obj, "email"))

    def test_has_dict_field_empty(self):
        """has(obj, field) with dict and empty field."""
        obj = {"name": "", "email": None}
        self.assertFalse(F.has(obj, "name"))
        self.assertFalse(F.has(obj, "email"))

    def test_has_dict_field_missing(self):
        """has(obj, field) with dict and missing field."""
        obj = {"name": "John"}
        self.assertFalse(F.has(obj, "email"))

    def test_has_none_object(self):
        """has(None, field) returns False."""
        self.assertFalse(F.has(None, "name"))

    def test_has_in_expression(self):
        """Test has() used in CEL expression."""
        context = {
            "has": F.has,
            "record": {"name": "Test", "email": ""},
        }
        ast = P.parse('has(record, "name")')
        self.assertTrue(P.evaluate(ast, context))

        ast = P.parse('has(record, "email")')
        self.assertFalse(P.evaluate(ast, context))


@tagged("post_install", "-at_install")
class TestCELFunctionsMatches(TransactionCase):
    """Test cases for the matches() function."""

    def test_matches_simple(self):
        """Simple regex matching."""
        self.assertTrue(F.matches("hello world", r"world"))
        self.assertTrue(F.matches("hello world", r"hello"))

    def test_matches_anchor_start(self):
        """Regex with start anchor."""
        self.assertTrue(F.matches("hello world", r"^hello"))
        self.assertFalse(F.matches("hello world", r"^world"))

    def test_matches_anchor_end(self):
        """Regex with end anchor."""
        self.assertTrue(F.matches("hello world", r"world$"))
        self.assertFalse(F.matches("hello world", r"hello$"))

    def test_matches_pattern_groups(self):
        """Regex with pattern groups."""
        self.assertTrue(F.matches("test@example.com", r"^\w+@\w+\.\w+$"))

    def test_matches_none_string(self):
        """matches(None, pattern) returns False."""
        self.assertFalse(F.matches(None, r"test"))

    def test_matches_non_string(self):
        """matches() converts non-string to string."""
        self.assertTrue(F.matches(12345, r"234"))

    def test_matches_invalid_regex(self):
        """Invalid regex returns False (no exception)."""
        self.assertFalse(F.matches("test", r"[invalid"))

    def test_matches_in_expression(self):
        """Test matches() used in CEL expression."""
        context = {
            "matches": F.matches,
            "record": {"email": "john@example.com"},
        }
        ast = P.parse(r'matches(record.email, "^\\w+@")')
        result = P.evaluate(ast, context)
        self.assertTrue(result)


@tagged("post_install", "-at_install")
class TestCELParserUnaryMinus(TransactionCase):
    """Test cases for unary minus (negative numbers) in parser."""

    def test_parse_negative_number(self):
        """Parse negative number literal."""
        ast = P.parse("-5")
        self.assertIsInstance(ast, P.Neg)

    def test_evaluate_negative_number(self):
        """Evaluate negative number."""
        ast = P.parse("-5")
        result = P.evaluate(ast, {})
        self.assertEqual(result, -5)

    def test_evaluate_negative_float(self):
        """Evaluate negative float."""
        ast = P.parse("-3.14")
        result = P.evaluate(ast, {})
        self.assertAlmostEqual(result, -3.14)

    def test_compare_with_negative_number(self):
        """Compare value with negative number."""
        ast = P.parse("x > -5")
        self.assertTrue(P.evaluate(ast, {"x": 0}))
        self.assertFalse(P.evaluate(ast, {"x": -10}))

    def test_negative_field_value(self):
        """Negate a field value."""
        ast = P.parse("-record.amount")
        result = P.evaluate(ast, {"record": {"amount": 100}})
        self.assertEqual(result, -100)

    def test_negative_in_arithmetic_context(self):
        """Negative number in comparison."""
        context = {"temperature": -15}
        ast = P.parse("temperature < -10")
        self.assertTrue(P.evaluate(ast, context))

    def test_double_negative(self):
        """Double negative should work."""
        ast = P.parse("--5")
        result = P.evaluate(ast, {})
        self.assertEqual(result, 5)

    def test_negative_none_returns_none(self):
        """Negating None returns None."""
        ast = P.parse("-x")
        result = P.evaluate(ast, {"x": None})
        self.assertIsNone(result)


@tagged("post_install", "-at_install")
class TestCELApprovalExpressions(TransactionCase):
    """Test CEL expressions typical for approval workflows."""

    def test_amount_threshold(self):
        """Test amount > threshold expression."""
        context = {"record": {"amount": 15000}}
        ast = P.parse("record.amount > 10000")
        self.assertTrue(P.evaluate(ast, context))

    def test_state_check(self):
        """Test state == value expression."""
        context = {"record": {"state": "draft"}}
        ast = P.parse('record.state == "draft"')
        self.assertTrue(P.evaluate(ast, context))

    def test_combined_conditions_and(self):
        """Test combined conditions with 'and'."""
        context = {
            "record": {"state": "draft", "amount": 15000},
        }
        ast = P.parse('record.state == "draft" and record.amount > 10000')
        self.assertTrue(P.evaluate(ast, context))

    def test_combined_conditions_or(self):
        """Test combined conditions with 'or'."""
        context = {
            "record": {"amount": 5000, "category": "high_risk"},
        }
        ast = P.parse('record.amount > 10000 or record.category == "high_risk"')
        self.assertTrue(P.evaluate(ast, context))

    def test_nested_field_access(self):
        """Test accessing nested fields (Many2one simulation)."""
        context = {
            "record": {
                "partner_id": {"id": 123, "name": "Test Partner"},
            },
        }
        ast = P.parse("record.partner_id.id != 0")
        self.assertTrue(P.evaluate(ast, context))

    def test_collection_size_check(self):
        """Test size() on collection field."""
        context = {
            "size": F.size,
            "record": {"line_ids": {"ids": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11], "count": 11}},
        }
        ast = P.parse("size(record.line_ids) > 10")
        self.assertTrue(P.evaluate(ast, context))

    def test_user_context(self):
        """Test user variable in context."""
        context = {
            "user": {"id": 2, "name": "Admin"},
        }
        ast = P.parse("user.id > 0")
        self.assertTrue(P.evaluate(ast, context))

    def test_company_context(self):
        """Test company variable in context."""
        context = {
            "company": {"id": 1, "name": "My Company"},
        }
        ast = P.parse("company.id > 0")
        self.assertTrue(P.evaluate(ast, context))

    def test_not_operator(self):
        """Test 'not' operator."""
        context = {"record": {"is_company": False}}
        ast = P.parse("not record.is_company")
        self.assertTrue(P.evaluate(ast, context))

    def test_in_operator(self):
        """Test 'in' operator."""
        context = {"record": {"state": "pending"}}
        ast = P.parse("record.state in ['pending', 'approved']")
        self.assertTrue(P.evaluate(ast, context))
