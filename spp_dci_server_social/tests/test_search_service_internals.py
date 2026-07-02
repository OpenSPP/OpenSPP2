# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Unit tests for DCISocialSearchService internal helpers.

test_search_service.py covers execute_search end-to-end; this file
targets the standalone helpers that the e2e path doesn't exercise:
_parse_predicate, _condition_to_domain, _to_dci_member, and the
_map_gender hardcoded-fallback branches.
"""

from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.spp_cel_domain.exceptions import CELValidationError

from ..services.search_service import DCISocialSearchService
from .common import DCISocialServerCommon

CEL_SERVICE = "odoo.addons.spp_cel_domain.models.cel_service.CELService.compile_expression"


@tagged("post_install", "-at_install")
class TestSearchServiceInternals(DCISocialServerCommon):
    def setUp(self):
        super().setUp()
        self.service = DCISocialSearchService(self.env)

    # --- _condition_to_domain ------------------------------------------------

    def test_condition_attribute_mapping(self):
        cases = {
            "surname": "family_name",
            "sex": "gender",
            "locality": "city",
            "region": "state_id.name",
            "country": "country_id.code",
            "birth_date": "birthdate",
        }
        for dci_attr, odoo_field in cases.items():
            field, _op, _val = self.service._condition_to_domain(dci_attr, "=", "x")
            self.assertEqual(field, odoo_field)

    def test_condition_unknown_attribute_rejected(self):
        # Default-deny: an attribute outside the safe person-field allowlist is
        # rejected (previously it passed through as a raw field name, which let
        # expression searches oracle sensitive partner fields).
        with self.assertRaises(ValueError):
            self.service._condition_to_domain("custom_field", "=", "x")

    def test_condition_rejects_sensitive_partner_fields(self):
        for attribute in (
            "disability_severity_id",
            "has_disability",
            "disability_review_category",
            "has_unmet_device_need",
        ):
            with self.assertRaises(ValueError):
                self.service._condition_to_domain(attribute, "=", "x")

    def test_condition_operator_mapping(self):
        cases = {"==": "=", "contains": "ilike", "like": "ilike", ">=": ">="}
        for dci_op, odoo_op in cases.items():
            _f, op, _v = self.service._condition_to_domain("name", dci_op, "x")
            self.assertEqual(op, odoo_op)

    def test_condition_unknown_operator_passthrough(self):
        _f, op, _v = self.service._condition_to_domain("name", "!=", "x")
        self.assertEqual(op, "!=")

    # --- _parse_predicate ----------------------------------------------------

    def test_parse_predicate_empty_returns_empty(self):
        self.assertEqual(self.service._parse_predicate(None), [])
        self.assertEqual(self.service._parse_predicate(""), [])
        self.assertEqual(self.service._parse_predicate({"expression": "   "}), [])

    def test_parse_predicate_invalid_type_raises(self):
        with self.assertRaises(ValueError):
            self.service._parse_predicate(12345)

    def test_parse_predicate_extracts_expression_from_shapes(self):
        """dict.expression / dict.value / obj.expression / obj.value / str
        all resolve to the same CEL string and compile to the same domain."""
        domain = [("age", ">=", 18)]
        shapes = [
            {"expression": "r.age >= 18"},
            {"value": "r.age >= 18"},
            SimpleNamespace(expression="r.age >= 18"),
            "r.age >= 18",
        ]
        for shape in shapes:
            with patch(CEL_SERVICE, return_value={"valid": True, "domain": domain}):
                self.assertEqual(self.service._parse_predicate(shape), domain)

    def test_parse_predicate_compile_failure_raises(self):
        with patch(CEL_SERVICE, return_value={"valid": False, "error": "bad syntax"}):
            with self.assertRaises(ValueError) as ctx:
                self.service._parse_predicate("r.broken ==")
        self.assertIn("bad syntax", str(ctx.exception))

    def test_parse_predicate_rejects_sensitive_dci_method_metrics(self):
        blocked = [
            # Parameterized methods (accessor-call + metric() forms, incl. spaced dots)
            "r.dci.dr.severity('Vision') >= 3",
            "r . dci . dr . severity('Vision') >= 3",
            "r.dci.crvs.has_event('death') == true",
            "metric('r.dci.dr.severity', me, arg='Vision') >= 3",
            'metric("r.dci.crvs.has_event", me, arg="death") == true',
            # Backslash-escaped dots: the lexer decodes \. -> . so the metric
            # still resolves; the AST guard sees the decoded name (the regex
            # denylist this replaced did not).
            r"metric('r\.dci\.dr\.severity', me, arg='Vision') >= 3",
            # Non-parameterized disability flags (boolean oracles)
            "r.dci.dr.has_disability == true",
            "r.dci.dr.vision_severe == true",
            "metric('r.dci.dr.mobility_severe', me) == true",
            # Non-parameterized CRVS vital/civil status (boolean oracles)
            "r.dci.crvs.is_alive == false",
            "r.dci.crvs.is_married == true",
            "metric('r.dci.crvs.birth_verified', me) == true",
        ]
        for expression in blocked:
            # Through _parse_predicate so the test also pins that the guard is
            # wired in ahead of CEL execution (it rejects before the query runs).
            with self.assertRaises(ValueError) as ctx:
                self.service._parse_predicate(expression)
            self.assertIn("not permitted in external searches", str(ctx.exception))

    def test_parse_predicate_rejects_sensitive_partner_fields(self):
        # The disability data is also reachable via plain partner field paths
        # (stored on res.partner) and disability CEL functions -- not just DCI
        # metrics. Default-deny rejects these too.
        blocked = [
            "r.disability_severity_id == 5",
            "r.has_disability == true",
            "r.disability_review_category == 'high'",
            "r.has_unmet_device_need == true",
            "disability_severity(r) == 2",
            "is_severe_disability(r) == true",
            # Relation traversal that navigates back to the root partner's
            # disability via a child predicate.
            "enrollments.exists(m, m.partner_id.disability_severity_id == 5)",
        ]
        for expression in blocked:
            with self.assertRaises(ValueError) as ctx:
                self.service._parse_predicate(expression)
            self.assertIn("not permitted in external searches", str(ctx.exception))

    def test_external_predicate_policy_allows_benign_and_lower_risk_metrics(self):
        # The allowlist must permit benign person predicates, safe scalar
        # functions, and the intentionally-allowed lower-risk SR/IBR metrics.
        policy = self.service._external_predicate_policy()
        cel = self.env["spp.cel.service"]
        allowed = [
            "r.gender == 'female'",
            "r.name == 'John'",
            "age_years(r.birthdate) >= 18",
            "r.dci.sr.household_size >= 5",
            "r.dci.ibr.has_duplicate == true",
        ]
        for expression in allowed:
            # Should not raise.
            cel._enforce_predicate_policy(expression, policy)

    def test_external_predicate_policy_denies_disability_namespace_and_fields(self):
        # Behaviour change vs the old regex: anything in the disability metric
        # namespace, and any non-allowlisted partner field, is now denied.
        policy = self.service._external_predicate_policy()
        cel = self.env["spp.cel.service"]
        for expression in (
            "r.dci.dr.severity_score >= 3",  # disability namespace
            "r.poverty_score >= 50",  # arbitrary non-allowlisted field
        ):
            with self.assertRaises(CELValidationError):
                cel._enforce_predicate_policy(expression, policy)

    # --- _to_dci_member ------------------------------------------------------

    def test_to_dci_member_with_identifier_and_demographics(self):
        member = self.service._to_dci_member(self.individual_1)
        self.assertIsNotNone(member.member_identifier)
        self.assertIsNotNone(member.demographic_info)

    def test_to_dci_member_demographics_failure_is_tolerated(self):
        """If _to_dci_person raises (e.g. no identifier), the member is
        still returned with demographic_info=None."""
        bare = self.env["res.partner"].create({"name": "No Ident Member", "is_registrant": True})
        with patch.object(DCISocialSearchService, "_to_dci_person", side_effect=ValueError("no id")):
            member = self.service._to_dci_member(bare)
        self.assertIsNone(member.demographic_info)

    # --- _map_gender hardcoded fallback (no vocabulary adapter) ---------------

    def _service_without_vocab(self):
        svc = DCISocialSearchService(self.env)
        # Force the lazy property to report "no adapter" so the hardcoded
        # fallback branch runs.
        patcher = patch.object(DCISocialSearchService, "vocabulary_adapter", None)
        patcher.start()
        self.addCleanup(patcher.stop)
        return svc

    def test_map_gender_fallback_string_values(self):
        svc = self._service_without_vocab()
        for value, expected in [
            ("male", "male"),
            ("F", "female"),
            ("3", "other"),
            ("weird", "unknown"),
        ]:
            partner = SimpleNamespace(gender=value)
            self.assertEqual(svc._map_gender(partner), expected)

    def test_map_gender_fallback_gender_id_code(self):
        svc = self._service_without_vocab()
        partner = SimpleNamespace(
            gender=None,
            gender_id=SimpleNamespace(code="M"),
        )
        self.assertEqual(svc._map_gender(partner), "male")

    def test_map_gender_fallback_none(self):
        svc = self._service_without_vocab()
        partner = SimpleNamespace(gender=None, gender_id=None)
        self.assertIsNone(svc._map_gender(partner))
