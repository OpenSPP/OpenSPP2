# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from unittest.mock import patch

from odoo.api import Environment
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

_PATTERN_LOGGER = "odoo.addons.spp_data_classification.models.classification_pattern"


class _RaisingCelService:
    """Stand-in CEL service whose evaluation blows up unexpectedly."""

    def evaluate_expression(self, expression, context):
        raise RuntimeError("boom")


class _RecordingCelService:
    """Stand-in CEL service that records its call and returns a fixed result."""

    def __init__(self, result):
        self.result = result
        self.calls = []

    def evaluate_expression(self, expression, context):
        self.calls.append((expression, context))
        return self.result


class TestClassificationPattern(TransactionCase):
    """Tests for spp.classification.pattern model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Pattern = cls.env["spp.classification.pattern"]
        cls.Classification = cls.env["spp.field.classification"]

        cls.level_restricted = cls.env.ref("spp_data_classification.level_restricted")
        cls.level_confidential = cls.env.ref("spp_data_classification.level_confidential")

    def test_pattern_matches_field(self):
        """Test pattern matching against field names."""
        pattern = self.Pattern.create(
            {
                "name": "Test National ID",
                "pattern": "(national|passport).*id",
                "classification_id": self.level_restricted.id,
                "pii_category": "direct_id",
                "priority": 90,
            }
        )

        self.assertTrue(pattern.matches_field("national_id"))
        self.assertTrue(pattern.matches_field("passport_id"))
        self.assertTrue(pattern.matches_field("national_identity_id"))
        self.assertFalse(pattern.matches_field("name"))
        self.assertFalse(pattern.matches_field("email"))

    def test_pattern_with_model_scope(self):
        """Test pattern matching with model scope."""
        pattern = self.Pattern.create(
            {
                "name": "SPP Models Only",
                "pattern": ".*_id",
                "classification_id": self.level_confidential.id,
                "apply_to_model_pattern": r"spp\..*",
                "priority": 50,
            }
        )

        # Should match SPP models
        self.assertTrue(pattern.matches_field("partner_id", "spp.registry.id"))

        # Should not match non-SPP models
        self.assertFalse(pattern.matches_field("partner_id", "res.partner"))

    def test_find_matching_pattern(self):
        """Test finding best matching pattern."""
        # Create patterns with different priorities
        self.Pattern.create(
            {
                "name": "Low Priority",
                "pattern": ".*name",
                "classification_id": self.level_confidential.id,
                "priority": 10,
            }
        )
        high_priority = self.Pattern.create(
            {
                "name": "High Priority - Family Name",
                "pattern": "family.*name",
                "classification_id": self.level_restricted.id,
                "priority": 90,
            }
        )

        # family_name should match high priority pattern
        result = self.Pattern.find_matching_pattern("family_name")
        self.assertEqual(result, high_priority)

    def test_auto_classify_field(self):
        """Test auto-classification of a field."""
        self.Pattern.create(
            {
                "name": "Test Phone",
                "pattern": "phone|mobile",
                "classification_id": self.level_confidential.id,
                "pii_category": "contact",
                "default_mask_pattern": "***-***-####",
                "default_search_strategy": "partial_index",
                "priority": 70,
            }
        )

        # Auto-classify phone field on res.partner
        classification = self.Pattern.auto_classify_field("res.partner", "phone")

        self.assertTrue(classification)
        self.assertEqual(classification.source, "auto")
        self.assertEqual(classification.pii_category, "contact")
        self.assertEqual(classification.mask_pattern, "***-***-####")

    def test_default_patterns_exist(self):
        """Test that default detection patterns are loaded."""
        patterns = self.Pattern.search([])
        self.assertGreater(len(patterns), 0)

        # Check for some expected patterns
        national_id = self.Pattern.search([("name", "ilike", "national")])
        self.assertTrue(national_id)

        phone = self.Pattern.search([("name", "ilike", "phone")])
        self.assertTrue(phone)

    def test_pattern_requires_expression_for_mode(self):
        """Each match mode requires its own expression field."""
        with self.assertRaises(ValidationError):
            self.Pattern.create(
                {
                    "name": "Regex without pattern",
                    "match_mode": "regex",
                    "classification_id": self.level_restricted.id,
                }
            )
        with self.assertRaises(ValidationError):
            self.Pattern.create(
                {
                    "name": "CEL without expression",
                    "match_mode": "cel",
                    "classification_id": self.level_restricted.id,
                }
            )

    def test_invalid_regex_rejected_on_save(self):
        """An uncompilable regex must be rejected at save time, not silently
        disable matching at scan time."""
        with self.assertRaises(ValidationError):
            self.Pattern.create(
                {
                    "name": "Broken regex",
                    "pattern": "(unclosed",
                    "classification_id": self.level_restricted.id,
                }
            )
        with self.assertRaises(ValidationError):
            self.Pattern.create(
                {
                    "name": "Broken model scope",
                    "pattern": "phone",
                    "apply_to_model_pattern": "(unclosed",
                    "classification_id": self.level_restricted.id,
                }
            )

    def _create_cel_pattern(self):
        return self.Pattern.create(
            {
                "name": "CEL char fields",
                "match_mode": "cel",
                "cel_expression": "field.type == 'char'",
                "classification_id": self.level_confidential.id,
                "pii_category": "quasi_id",
                "priority": 60,
            }
        )

    def test_cel_pattern_degrades_without_service(self):
        """Without spp_cel_domain installed, CEL patterns must not match and
        must not crash - they log a warning and return False."""
        pattern = self._create_cel_pattern()
        # Guard: the CEL service is genuinely absent in this module's test DB
        self.assertNotIn("spp.cel.service", self.env)

        with self.assertLogs(_PATTERN_LOGGER, level="WARNING") as capture:
            self.assertFalse(pattern.matches_field("phone", "res.partner"))
        self.assertIn("CEL service not available", capture.output[0])

    def test_cel_pattern_matches_via_service(self):
        """With a CEL service present, the expression result decides the match
        and the service receives the field/model metadata context."""
        pattern = self._create_cel_pattern()
        model = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        field = self.env["ir.model.fields"].search(
            [("model_id", "=", model.id), ("name", "=", "phone")],
            limit=1,
        )

        service = _RecordingCelService(result=True)
        with patch.object(Environment, "get", return_value=service):
            self.assertTrue(pattern.matches_field("phone", "res.partner", field, model))

        expression, context = service.calls[0]
        self.assertEqual(expression, "field.type == 'char'")
        self.assertEqual(context["field"].name, "phone")
        self.assertEqual(context["field"].type, "char")
        self.assertEqual(context["model"].model, "res.partner")

        service_false = _RecordingCelService(result=False)
        with patch.object(Environment, "get", return_value=service_false):
            self.assertFalse(pattern.matches_field("phone", "res.partner", field, model))

    def test_cel_evaluation_error_returns_false(self):
        """An unexpected evaluation error in one pattern must not crash the
        caller (a registry scan) - it logs a warning and reports no match."""
        pattern = self._create_cel_pattern()
        with patch.object(Environment, "get", return_value=_RaisingCelService()):
            with self.assertLogs(_PATTERN_LOGGER, level="WARNING") as capture:
                self.assertFalse(pattern.matches_field("phone", "res.partner"))
        self.assertIn("CEL evaluation failed", capture.output[0])

    def test_build_cel_context(self):
        """The CEL context carries field/model metadata, with safe defaults
        when the ir.model(.fields) records are not provided."""
        pattern = self._create_cel_pattern()
        model = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        field = self.env["ir.model.fields"].search(
            [("model_id", "=", model.id), ("name", "=", "phone")],
            limit=1,
        )

        context = pattern._build_cel_context("phone", "res.partner", field, model)
        self.assertEqual(context["field"].name, "phone")
        self.assertEqual(context["field"].type, "char")
        self.assertTrue(context["field"].store)
        self.assertEqual(context["model"].model, "res.partner")
        self.assertFalse(context["model"].transient)

        defaults = pattern._build_cel_context("some_field")
        self.assertEqual(defaults["field"].name, "some_field")
        self.assertEqual(defaults["field"].type, "unknown")
        self.assertEqual(defaults["model"].model, "")

    def test_find_matching_pattern_no_match(self):
        """No matching pattern yields an empty recordset, and auto-classify
        creates nothing."""
        result = self.Pattern.find_matching_pattern("zzz_nothing_matches_this")
        self.assertFalse(result)

        classification = self.Pattern.auto_classify_field("res.partner", "zzz_nothing_matches_this")
        self.assertFalse(classification)

    def test_scan_model_fields(self):
        """Scanning a model classifies matching fields and skips the ones
        already classified on the next run."""
        results = self.Pattern.scan_model_fields("res.partner")
        matched_fields = [field_name for field_name, _classification in results]
        self.assertIn("phone", matched_fields)

        classification = self.Classification.get_classification("res.partner", "phone")
        self.assertEqual(classification.source, "auto")
        self.assertTrue(classification.pattern_id)

        rescan = self.Pattern.scan_model_fields("res.partner")
        self.assertNotIn("phone", [field_name for field_name, _classification in rescan])

        # skip_classified=False reports already-classified fields again
        # (ensure_classification returns the existing record, creates nothing)
        full_rescan = self.Pattern.scan_model_fields("res.partner", skip_classified=False)
        self.assertIn("phone", [field_name for field_name, _classification in full_rescan])
        self.assertEqual(
            self.Classification.search_count([("model_name", "=", "res.partner"), ("field_name", "=", "phone")]),
            1,
        )

    def test_scan_model_fields_unknown_model(self):
        """Scanning an unknown model warns and returns an empty list."""
        with self.assertLogs(_PATTERN_LOGGER, level="WARNING") as capture:
            self.assertEqual(self.Pattern.scan_model_fields("no.such.model"), [])
        self.assertIn("Model not found", capture.output[0])

    def test_scan_all_models_with_pattern(self):
        """The model_pattern filter restricts the scan to matching models."""
        results = self.Pattern.scan_all_models(model_pattern=r"^res\.bank$")
        self.assertTrue(results, "res.bank has fields matching the seeded patterns")
        self.assertEqual(list(results.keys()), ["res.bank"])

    def test_action_test_pattern(self):
        """The Test Pattern button reports matches against res.partner."""
        pattern = self.Pattern.create(
            {
                "name": "Test Phone Button",
                "pattern": "phone",
                "classification_id": self.level_confidential.id,
            }
        )
        action = pattern.action_test_pattern()
        self.assertEqual(action["params"]["type"], "success")
        self.assertIn("phone", action["params"]["message"])

        no_match = self.Pattern.create(
            {
                "name": "Never Matches",
                "pattern": "zzz_nothing_matches_this",
                "classification_id": self.level_confidential.id,
            }
        )
        action = no_match.action_test_pattern()
        self.assertEqual(action["params"]["type"], "warning")

        # More than 20 matches truncates the field list in the message
        match_all = self.Pattern.create(
            {
                "name": "Matches Everything",
                "pattern": ".",
                "classification_id": self.level_confidential.id,
            }
        )
        action = match_all.action_test_pattern()
        self.assertEqual(action["params"]["type"], "success")
        self.assertIn("more", action["params"]["message"])
