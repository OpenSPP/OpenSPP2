# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.tests.common import TransactionCase


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
