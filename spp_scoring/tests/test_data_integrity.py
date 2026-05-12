from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestScoringModelIntegrity(TransactionCase):
    """Test data integrity for scoring models."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ScoringModel = cls.env["spp.scoring.model"]
        cls.ScoringIndicator = cls.env["spp.scoring.indicator"]
        cls.ScoringThreshold = cls.env["spp.scoring.threshold"]

    def test_model_code_uniqueness(self):
        """Test that model codes must be unique."""
        self.ScoringModel.create(
            {
                "name": "Model 1",
                "code": "UNIQUE_CODE",
            }
        )

        with self.assertRaises(ValidationError):
            self.ScoringModel.create(
                {
                    "name": "Model 2",
                    "code": "UNIQUE_CODE",
                }
            )

    def test_indicator_code_unique_within_model(self):
        """Test that indicator codes are unique within a model."""
        model = self.ScoringModel.create(
            {
                "name": "Indicator Test Model",
                "code": "IND_TEST",
            }
        )

        self.ScoringIndicator.create(
            {
                "model_id": model.id,
                "name": "Indicator 1",
                "code": "IND_CODE",
                "field_path": "id",
                "calculation_type": "direct",
                "weight": 1.0,
            }
        )

        with self.assertRaises(ValidationError):
            self.ScoringIndicator.create(
                {
                    "model_id": model.id,
                    "name": "Indicator 2",
                    "code": "IND_CODE",  # Duplicate
                    "field_path": "name",
                    "calculation_type": "direct",
                    "weight": 1.0,
                }
            )

    def test_indicator_code_unique_across_models(self):
        """Test that same indicator code can be used in different models."""
        model1 = self.ScoringModel.create(
            {
                "name": "Model 1",
                "code": "MODEL_1",
            }
        )
        model2 = self.ScoringModel.create(
            {
                "name": "Model 2",
                "code": "MODEL_2",
            }
        )

        # Should succeed - same code in different models
        self.ScoringIndicator.create(
            {
                "model_id": model1.id,
                "name": "Indicator",
                "code": "SAME_CODE",
                "field_path": "id",
                "calculation_type": "direct",
                "weight": 1.0,
            }
        )
        self.ScoringIndicator.create(
            {
                "model_id": model2.id,
                "name": "Indicator",
                "code": "SAME_CODE",
                "field_path": "id",
                "calculation_type": "direct",
                "weight": 1.0,
            }
        )

    def test_cascade_delete_indicators(self):
        """Test that deleting a model deletes its indicators."""
        model = self.ScoringModel.create(
            {
                "name": "Cascade Test Model",
                "code": "CASCADE_TEST",
            }
        )
        indicator = self.ScoringIndicator.create(
            {
                "model_id": model.id,
                "name": "Cascade Indicator",
                "code": "CASCADE_IND",
                "field_path": "id",
                "calculation_type": "direct",
                "weight": 1.0,
            }
        )
        indicator_id = indicator.id

        model.unlink()

        # Indicator should be deleted
        self.assertFalse(self.ScoringIndicator.search([("id", "=", indicator_id)]))

    def test_cascade_delete_thresholds(self):
        """Test that deleting a model deletes its thresholds."""
        model = self.ScoringModel.create(
            {
                "name": "Threshold Cascade Model",
                "code": "THRESH_CASCADE",
            }
        )
        threshold = self.ScoringThreshold.create(
            {
                "model_id": model.id,
                "name": "Cascade Threshold",
                "min_score": 0,
                "max_score": 100,
                "classification_code": "CASCADE",
                "classification_label": "Cascade",
            }
        )
        threshold_id = threshold.id

        model.unlink()

        self.assertFalse(self.ScoringThreshold.search([("id", "=", threshold_id)]))

    def test_threshold_min_max_validation(self):
        """Test that threshold min cannot exceed max."""
        model = self.ScoringModel.create(
            {
                "name": "Validation Model",
                "code": "VALIDATE",
            }
        )

        with self.assertRaises(ValidationError):
            self.ScoringThreshold.create(
                {
                    "model_id": model.id,
                    "name": "Invalid Threshold",
                    "min_score": 100,
                    "max_score": 50,  # Invalid: min > max
                    "classification_code": "INVALID",
                    "classification_label": "Invalid",
                }
            )


@tagged("post_install", "-at_install")
class TestScoringResultIntegrity(TransactionCase):
    """Test data integrity for scoring results."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ScoringModel = cls.env["spp.scoring.model"]
        cls.ScoringIndicator = cls.env["spp.scoring.indicator"]
        cls.ScoringResult = cls.env["spp.scoring.result"]
        cls.ScoringEngine = cls.env["spp.scoring.engine"]
        cls.Partner = cls.env["res.partner"]

        cls.model = cls.ScoringModel.create(
            {
                "name": "Result Integrity Model",
                "code": "RESULT_INT",
                "is_active": True,
            }
        )
        cls.ScoringIndicator.create(
            {
                "model_id": cls.model.id,
                "name": "Test Indicator",
                "code": "TEST_IND",
                "field_path": "id",
                "calculation_type": "direct",
                "weight": 1.0,
                "max_score": 100,  # Cap to 100
            }
        )

        cls.registrant = cls.Partner.create(
            {
                "name": "Integrity Test Registrant",
                "is_registrant": True,
            }
        )

    def test_result_stores_model_version(self):
        """Test that result captures model version at creation."""
        self.model.version = "1.0"

        result = self.ScoringEngine.calculate_score(self.registrant, self.model)

        self.assertEqual(result.model_version, "1.0")

    def test_result_restrict_model_delete(self):
        """Test that model with results cannot be deleted."""
        self.ScoringEngine.calculate_score(self.registrant, self.model)  # noqa: F841

        # Model has results, should not be deletable due to restrict
        # The exact exception type may vary (psycopg2.errors.ForeignKeyViolation
        # or Odoo wrapper), so we catch the most common exceptions
        with self.assertRaises(Exception) as ctx:
            self.model.unlink()

        # Verify it's a foreign key / restrict error (not some other error)
        error_msg = str(ctx.exception).lower()
        self.assertTrue(
            any(x in error_msg for x in ["foreign key", "restrict", "violates", "constraint"]),
            f"Expected foreign key/restrict error, got: {ctx.exception}",
        )

    def test_result_cascade_registrant_delete(self):
        """Test that deleting registrant cascades to results."""
        new_registrant = self.Partner.create(
            {
                "name": "Delete Test",
                "is_registrant": True,
            }
        )
        result = self.ScoringEngine.calculate_score(new_registrant, self.model)
        result_id = result.id

        new_registrant.unlink()

        # Result should be deleted
        self.assertFalse(self.ScoringResult.search([("id", "=", result_id)]))

    def test_result_details_cascade(self):
        """Test that result details are deleted with result."""
        new_registrant = self.Partner.create(
            {
                "name": "Detail Cascade Test",
                "is_registrant": True,
            }
        )
        result = self.ScoringEngine.calculate_score(new_registrant, self.model)
        detail_ids = result.detail_ids.ids

        self.assertTrue(len(detail_ids) > 0)

        new_registrant.unlink()

        # Details should be deleted
        remaining = self.env["spp.scoring.result.detail"].search([("id", "in", detail_ids)])
        self.assertEqual(len(remaining), 0)

    def test_result_breakdown_json_valid(self):
        """Test that breakdown JSON is valid and parseable."""
        result = self.ScoringEngine.calculate_score(self.registrant, self.model)

        breakdown = result.get_breakdown()

        self.assertIsInstance(breakdown, list)
        if breakdown:
            self.assertIn("indicator_code", breakdown[0])
            self.assertIn("weighted_score", breakdown[0])

    def test_result_inputs_snapshot_valid(self):
        """Test that inputs snapshot is valid JSON."""
        result = self.ScoringEngine.calculate_score(self.registrant, self.model)

        inputs = result.get_inputs()

        self.assertIsInstance(inputs, dict)

    def test_multiple_results_for_same_registrant(self):
        """Test that multiple results can exist for same registrant."""
        result1 = self.ScoringEngine.calculate_score(self.registrant, self.model)
        result2 = self.ScoringEngine.calculate_score(self.registrant, self.model)

        self.assertNotEqual(result1.id, result2.id)

        # Both should exist
        results = self.ScoringResult.search(
            [
                ("registrant_id", "=", self.registrant.id),
                ("model_id", "=", self.model.id),
            ]
        )
        self.assertGreaterEqual(len(results), 2)


@tagged("post_install", "-at_install")
class TestValueMappingIntegrity(TransactionCase):
    """Test data integrity for value mappings."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ScoringModel = cls.env["spp.scoring.model"]
        cls.ScoringIndicator = cls.env["spp.scoring.indicator"]
        cls.ValueMapping = cls.env["spp.scoring.value_mapping"]

        cls.model = cls.ScoringModel.create(
            {
                "name": "Mapping Test Model",
                "code": "MAP_TEST",
            }
        )

    def test_mapping_cascade_indicator_delete(self):
        """Test that mappings are deleted when indicator is deleted."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Mapping Indicator",
                "code": "MAP_IND",
                "field_path": "name",
                "calculation_type": "mapped",
                "weight": 1.0,
            }
        )
        mapping = self.ValueMapping.create(
            {
                "indicator_id": indicator.id,
                "input_value": "test",
                "output_score": 10.0,
            }
        )
        mapping_id = mapping.id

        indicator.unlink()

        self.assertFalse(self.ValueMapping.search([("id", "=", mapping_id)]))

    def test_mapped_requires_field_path(self):
        """Test that mapped indicator requires field_path."""
        with self.assertRaises(ValidationError):
            self.ScoringIndicator.create(
                {
                    "model_id": self.model.id,
                    "name": "No Path Mapped",
                    "code": "NO_PATH",
                    "field_path": "",  # Empty
                    "calculation_type": "mapped",
                    "weight": 1.0,
                }
            )

    def test_formula_requires_cel_expression(self):
        """Test that formula indicator requires CEL expression."""
        with self.assertRaises(ValidationError):
            self.ScoringIndicator.create(
                {
                    "model_id": self.model.id,
                    "name": "No CEL Formula",
                    "code": "NO_CEL",
                    "calculation_type": "formula",
                    "cel_expression": "",  # Empty
                    "weight": 1.0,
                }
            )
