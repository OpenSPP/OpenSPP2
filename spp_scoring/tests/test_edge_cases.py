from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIndicatorEdgeCases(TransactionCase):
    """Test edge cases for indicator calculations."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ScoringModel = cls.env["spp.scoring.model"]
        cls.ScoringIndicator = cls.env["spp.scoring.indicator"]
        cls.ValueMapping = cls.env["spp.scoring.value_mapping"]
        cls.ScoringEngine = cls.env["spp.scoring.engine"]
        cls.Partner = cls.env["res.partner"]

        cls.model = cls.ScoringModel.create(
            {
                "name": "Edge Case Model",
                "code": "EDGE_TEST",
                "is_active": True,
            }
        )

    def test_direct_with_none_value(self):
        """Test direct calculation with None value."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "None Test",
                "code": "NONE_TEST",
                "field_path": "ref",  # Often None
                "calculation_type": "direct",
                "weight": 1.0,
                "default_score": 5.0,
            }
        )

        self.Partner.create(
            {
                "name": "No Ref Registrant",
                "is_registrant": True,
                "ref": None,
            }
        )

        score = indicator.calculate_score(None)
        self.assertEqual(score, 5.0)

    def test_direct_with_boolean_true(self):
        """Test direct calculation with boolean True."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Bool True Test",
                "code": "BOOL_TRUE",
                "field_path": "is_group",
                "calculation_type": "direct",
                "weight": 1.0,
            }
        )

        score = indicator.calculate_score(True)
        self.assertEqual(score, 1.0)

    def test_direct_with_boolean_false(self):
        """Test direct calculation with boolean False."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Bool False Test",
                "code": "BOOL_FALSE",
                "field_path": "is_group",
                "calculation_type": "direct",
                "weight": 1.0,
            }
        )

        score = indicator.calculate_score(False)
        self.assertEqual(score, 0.0)

    def test_direct_with_negative_value(self):
        """Test direct calculation with negative value.

        Note: min_score=0 is treated as "no constraint" since Float fields
        default to 0.0. Use non-zero values for actual constraints.
        """
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Negative Test",
                "code": "NEGATIVE",
                "field_path": "id",
                "calculation_type": "direct",
                "weight": 1.0,
                "min_score": 1,  # Non-zero to enforce minimum
            }
        )

        # Negative value should be clamped to min_score
        score = indicator.calculate_score(-10)
        self.assertEqual(score, 1.0)

    def test_direct_exceeds_max(self):
        """Test direct calculation exceeding max score."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Max Test",
                "code": "MAX_TEST",
                "field_path": "id",
                "calculation_type": "direct",
                "weight": 1.0,
                "max_score": 10,
            }
        )

        score = indicator.calculate_score(999)
        self.assertEqual(score, 10.0)

    def test_mapped_with_empty_string(self):
        """Test mapped calculation with empty string."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Empty Map Test",
                "code": "EMPTY_MAP",
                "field_path": "ref",
                "calculation_type": "mapped",
                "weight": 1.0,
                "default_score": 3.0,
            }
        )
        self.ValueMapping.create(
            {
                "indicator_id": indicator.id,
                "input_value": "",
                "output_score": 0.0,
            }
        )

        score = indicator.calculate_score("")
        self.assertEqual(score, 0.0)

    def test_mapped_with_none_returns_default(self):
        """Test that mapped with None returns default score."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "None Map Test",
                "code": "NONE_MAP",
                "field_path": "ref",
                "calculation_type": "mapped",
                "weight": 1.0,
                "default_score": 7.0,
            }
        )
        self.ValueMapping.create(
            {
                "indicator_id": indicator.id,
                "input_value": "test",
                "output_score": 10.0,
            }
        )

        score = indicator.calculate_score(None)
        self.assertEqual(score, 7.0)

    def test_range_with_boundary_value(self):
        """Test range calculation at exact boundary."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Boundary Test",
                "code": "BOUNDARY",
                "field_path": "id",
                "calculation_type": "range",
                "weight": 1.0,
            }
        )
        self.ValueMapping.create(
            [
                {"indicator_id": indicator.id, "range_min": 0, "range_max": 10, "output_score": 1.0},
                {"indicator_id": indicator.id, "range_min": 10, "range_max": 20, "output_score": 2.0},
            ]
        )

        # Value at exact boundary (10) should match the first range that contains it
        score = indicator.calculate_score(10)
        self.assertIn(score, [1.0, 2.0])  # Either is acceptable

    def test_range_with_float_value(self):
        """Test range calculation with float value."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Float Range Test",
                "code": "FLOAT_RANGE",
                "field_path": "id",
                "calculation_type": "range",
                "weight": 1.0,
            }
        )
        self.ValueMapping.create(
            {
                "indicator_id": indicator.id,
                "range_min": 0.0,
                "range_max": 10.5,
                "output_score": 5.0,
            }
        )

        score = indicator.calculate_score(5.25)
        self.assertEqual(score, 5.0)

    def test_range_with_string_number(self):
        """Test range calculation with string number."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "String Number Test",
                "code": "STR_NUM",
                "field_path": "id",
                "calculation_type": "range",
                "weight": 1.0,
            }
        )
        self.ValueMapping.create(
            {
                "indicator_id": indicator.id,
                "range_min": 0,
                "range_max": 100,
                "output_score": 8.0,
            }
        )

        # String "50" should be converted to float
        score = indicator.calculate_score("50")
        self.assertEqual(score, 8.0)

    def test_range_with_non_numeric_string(self):
        """Test range calculation with non-numeric string returns default."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Non-Num Test",
                "code": "NON_NUM",
                "field_path": "name",
                "calculation_type": "range",
                "weight": 1.0,
                "default_score": 2.0,
            }
        )
        self.ValueMapping.create(
            {
                "indicator_id": indicator.id,
                "range_min": 0,
                "range_max": 100,
                "output_score": 8.0,
            }
        )

        score = indicator.calculate_score("not a number")
        self.assertEqual(score, 2.0)

    def test_zero_weight_indicator(self):
        """Test indicator with zero weight."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Zero Weight",
                "code": "ZERO_WEIGHT",
                "field_path": "id",
                "calculation_type": "direct",
                "weight": 0.0,
            }
        )

        score = indicator.calculate_score(100)
        # Score should be calculated but weight is 0
        self.assertEqual(score, 100.0)


@tagged("post_install", "-at_install")
class TestThresholdEdgeCases(TransactionCase):
    """Test edge cases for threshold classification."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ScoringModel = cls.env["spp.scoring.model"]
        cls.ScoringThreshold = cls.env["spp.scoring.threshold"]

        cls.model = cls.ScoringModel.create(
            {
                "name": "Threshold Edge Model",
                "code": "THRESH_EDGE",
            }
        )

    def test_threshold_exact_min_boundary(self):
        """Test score exactly at threshold min."""
        threshold = self.ScoringThreshold.create(
            {
                "model_id": self.model.id,
                "name": "Test Threshold",
                "min_score": 50.0,
                "max_score": 100.0,
                "classification_code": "TEST",
                "classification_label": "Test",
            }
        )

        self.assertTrue(threshold.matches_score(50.0))

    def test_threshold_exact_max_boundary(self):
        """Test score exactly at threshold max."""
        threshold = self.ScoringThreshold.create(
            {
                "model_id": self.model.id,
                "name": "Test Threshold",
                "min_score": 0.0,
                "max_score": 50.0,
                "classification_code": "TEST",
                "classification_label": "Test",
            }
        )

        self.assertTrue(threshold.matches_score(50.0))

    def test_threshold_just_below_min(self):
        """Test score just below threshold min."""
        threshold = self.ScoringThreshold.create(
            {
                "model_id": self.model.id,
                "name": "Test Threshold",
                "min_score": 50.0,
                "max_score": 100.0,
                "classification_code": "TEST",
                "classification_label": "Test",
            }
        )

        self.assertFalse(threshold.matches_score(49.99))

    def test_threshold_just_above_max(self):
        """Test score just above threshold max."""
        threshold = self.ScoringThreshold.create(
            {
                "model_id": self.model.id,
                "name": "Test Threshold",
                "min_score": 0.0,
                "max_score": 50.0,
                "classification_code": "TEST",
                "classification_label": "Test",
            }
        )

        self.assertFalse(threshold.matches_score(50.01))

    def test_threshold_negative_score(self):
        """Test classification with negative score."""
        threshold = self.ScoringThreshold.create(
            {
                "model_id": self.model.id,
                "name": "Negative Threshold",
                "min_score": -100.0,
                "max_score": 0.0,
                "classification_code": "NEGATIVE",
                "classification_label": "Negative",
            }
        )

        self.assertTrue(threshold.matches_score(-50.0))

    def test_threshold_zero_range(self):
        """Test threshold with zero-width range (min == max)."""
        threshold = self.ScoringThreshold.create(
            {
                "model_id": self.model.id,
                "name": "Point Threshold",
                "min_score": 50.0,
                "max_score": 50.0,
                "classification_code": "POINT",
                "classification_label": "Exact Point",
            }
        )

        self.assertTrue(threshold.matches_score(50.0))
        self.assertFalse(threshold.matches_score(50.001))


@tagged("post_install", "-at_install")
class TestFieldPathEdgeCases(TransactionCase):
    """Test edge cases for field path resolution."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ScoringModel = cls.env["spp.scoring.model"]
        cls.ScoringIndicator = cls.env["spp.scoring.indicator"]
        cls.Partner = cls.env["res.partner"]

        cls.model = cls.ScoringModel.create(
            {
                "name": "Field Path Model",
                "code": "FIELD_PATH",
                "is_active": True,
            }
        )

    def test_nested_field_path(self):
        """Test accessing nested field via path."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Nested Field",
                "code": "NESTED",
                "field_path": "parent_id.name",
                "calculation_type": "direct",
                "weight": 1.0,
                "default_score": 0.0,
            }
        )

        parent = self.Partner.create(
            {
                "name": "Parent Company",
                "is_company": True,
            }
        )
        child = self.Partner.create(
            {
                "name": "Child Registrant",
                "is_registrant": True,
                "parent_id": parent.id,
            }
        )

        value = indicator.get_field_value(child)
        self.assertEqual(value, "Parent Company")

    def test_field_path_none_in_chain(self):
        """Test field path when intermediate value is None."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "None Chain",
                "code": "NONE_CHAIN",
                "field_path": "parent_id.name",
                "calculation_type": "direct",
                "weight": 1.0,
            }
        )

        orphan = self.Partner.create(
            {
                "name": "Orphan Registrant",
                "is_registrant": True,
                "parent_id": False,
            }
        )

        value = indicator.get_field_value(orphan)
        self.assertIsNone(value)

    def test_invalid_field_path_validation(self):
        """Test that invalid field path is detected."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Invalid Path",
                "code": "INVALID_PATH",
                "field_path": "nonexistent_field",
                "calculation_type": "direct",
                "weight": 1.0,
            }
        )

        self.assertFalse(indicator._is_valid_field_path())

    def test_empty_field_path_is_valid(self):
        """Test that empty field path is considered valid."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Empty Path",
                "code": "EMPTY_PATH",
                "field_path": "",
                "calculation_type": "formula",
                "cel_expression": "1 + 1",
                "weight": 1.0,
            }
        )

        self.assertTrue(indicator._is_valid_field_path())
