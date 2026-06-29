# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the external-predicate allowlist guard.

Covers the AST symbol collector (cel_predicate_guard) and the CEL service
enforcement entry point (_enforce_predicate_policy) used to keep sender-supplied
DCI predicates from filtering on sensitive fields/metrics.
"""

from odoo.tests import TransactionCase, tagged

from ..exceptions import CELValidationError
from ..services.cel_parser import parse
from ..services.cel_predicate_guard import DYNAMIC_METRIC, collect_referenced_symbols


def _syms(expression):
    return collect_referenced_symbols(parse(expression))


@tagged("post_install", "-at_install")
class TestCelPredicateGuardCollector(TransactionCase):
    """Unit tests for collect_referenced_symbols (pure AST walk)."""

    def test_metric_call_collects_decoded_name(self):
        syms = _syms("metric('r.dci.dr.severity', me, arg='Vision') >= 3")
        self.assertEqual(syms.metrics, {"r.dci.dr.severity"})

    def test_metric_call_escaped_dots_decode_to_same_name(self):
        # The lexer drops the backslash and keeps the next char, so the escaped
        # literal decodes to the real accessor -- the bypass the regex missed.
        syms = _syms(r"metric('r\.dci\.dr\.severity', me, arg='Vision') >= 3")
        self.assertEqual(syms.metrics, {"r.dci.dr.severity"})

    def test_raw_called_dotted_accessor_is_a_metric(self):
        syms = _syms("r.dci.dr.severity('Vision') >= 3")
        self.assertEqual(syms.metrics, {"r.dci.dr.severity"})

    def test_raw_bare_dotted_accessor_is_a_metric(self):
        syms = _syms("r.dci.sr.household_size >= 5")
        self.assertEqual(syms.metrics, {"r.dci.sr.household_size"})

    def test_me_rooted_accessor_canonicalised_to_r(self):
        syms = _syms("me.dci.dr.severity('Vision') >= 3")
        self.assertEqual(syms.metrics, {"r.dci.dr.severity"})

    def test_fields_and_functions(self):
        syms = _syms("r.gender == 'female' && age_years(r.birthdate) >= 18")
        self.assertEqual(syms.fields, {"gender", "birthdate"})
        self.assertEqual(syms.functions, {"age_years"})
        self.assertFalse(syms.metrics)
        self.assertFalse(syms.methods)

    def test_bare_identifier_is_a_field(self):
        syms = _syms("gender == 'female'")
        self.assertEqual(syms.fields, {"gender"})

    def test_relation_method_and_child_navigation(self):
        syms = _syms("enrollments.exists(m, m.partner_id.disability_severity_id == 5)")
        self.assertIn("enrollments.exists", syms.methods)
        # The child navigation (rooted at the lambda var, not r/me) is recorded
        # as a non-allowlisted field path.
        self.assertIn("m.partner_id.disability_severity_id", syms.fields)

    def test_rhs_field_reference_is_collected(self):
        syms = _syms("metric('r.dci.sr.x', me) == r.disability_severity_id")
        self.assertEqual(syms.metrics, {"r.dci.sr.x"})
        self.assertEqual(syms.fields, {"disability_severity_id"})

    def test_non_literal_metric_name_is_dynamic(self):
        syms = _syms("metric('r.dci.dr' + '.severity', me) == 2")
        self.assertIn(DYNAMIC_METRIC, syms.metrics)


@tagged("post_install", "-at_install")
class TestEnforcePredicatePolicy(TransactionCase):
    """The CEL service default-deny enforcement entry point."""

    def setUp(self):
        super().setUp()
        self.cel = self.env["spp.cel.service"]
        self.policy = {
            "allowed_fields": {"gender", "birthdate", "name"},
            "allowed_functions": {"age_years"},
            "allowed_metric_prefixes": ("r.dci.sr.", "r.dci.ibr."),
            "allow_relations": False,
        }

    def _assert_denied(self, expression, needle=None):
        with self.assertRaises(CELValidationError) as ctx:
            self.cel._enforce_predicate_policy(expression, self.policy)
        if needle:
            self.assertIn(needle, str(ctx.exception))

    def test_allows_safe_fields_functions_and_metrics(self):
        # Should not raise.
        self.cel._enforce_predicate_policy(
            "r.gender == 'female' && age_years(r.birthdate) >= 18 && r.dci.sr.household_size >= 5",
            self.policy,
        )

    def test_denies_sensitive_field(self):
        self._assert_denied("r.disability_severity_id == 5", "disability_severity_id")

    def test_denies_sensitive_metric_even_escaped(self):
        self._assert_denied(r"metric('r\.dci\.dr\.severity', me, arg='Vision') >= 3", "r.dci.dr.severity")

    def test_denies_relation_traversal(self):
        self._assert_denied(
            "enrollments.exists(m, m.partner_id.disability_severity_id == 5)",
            "enrollments.exists",
        )

    def test_denies_unknown_function(self):
        self._assert_denied("disability_severity(r) == 2", "disability_severity")

    def test_denies_dynamic_metric(self):
        self._assert_denied("metric('r.dci.dr' + '.severity', me) == 2")

    def test_empty_expression_is_noop(self):
        # Should not raise.
        self.cel._enforce_predicate_policy("", self.policy)
        self.cel._enforce_predicate_policy("   ", self.policy)
