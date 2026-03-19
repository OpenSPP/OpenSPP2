from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestScoringEngine(TransactionCase):
    """Test cases for spp.scoring.engine."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ScoringModel = cls.env["spp.scoring.model"]
        cls.ScoringIndicator = cls.env["spp.scoring.indicator"]
        cls.ScoringThreshold = cls.env["spp.scoring.threshold"]
        cls.ValueMapping = cls.env["spp.scoring.value_mapping"]
        cls.ScoringEngine = cls.env["spp.scoring.engine"]
        cls.Partner = cls.env["res.partner"]

        # Create a test registrant
        cls.registrant = cls.Partner.create(
            {
                "name": "Test Registrant",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create a complete scoring model
        cls.model = cls.ScoringModel.create(
            {
                "name": "Test Scoring Model",
                "code": "TEST_ENGINE",
                "calculation_method": "weighted_sum",
                "expected_total_weight": 1.0,
                "is_active": True,
            }
        )

        # Create indicators
        cls.indicator1 = cls.ScoringIndicator.create(
            {
                "model_id": cls.model.id,
                "name": "ID Score",
                "code": "ID_SCORE",
                "field_path": "id",
                "calculation_type": "direct",
                "weight": 0.5,
                "min_score": 0,
                "max_score": 100,
            }
        )

        cls.indicator2 = cls.ScoringIndicator.create(
            {
                "model_id": cls.model.id,
                "name": "Is Group",
                "code": "IS_GROUP",
                "field_path": "is_group",
                "calculation_type": "direct",
                "weight": 0.5,
            }
        )

        # Create thresholds
        cls.ScoringThreshold.create(
            {
                "model_id": cls.model.id,
                "name": "Low",
                "min_score": 0,
                "max_score": 25,
                "classification_code": "LOW",
                "classification_label": "Low Risk",
                "display_color": "green",
            }
        )
        cls.ScoringThreshold.create(
            {
                "model_id": cls.model.id,
                "name": "Medium",
                "min_score": 25.01,
                "max_score": 50,
                "classification_code": "MEDIUM",
                "classification_label": "Medium Risk",
                "display_color": "yellow",
            }
        )
        cls.ScoringThreshold.create(
            {
                "model_id": cls.model.id,
                "name": "High",
                "min_score": 50.01,
                "max_score": 100,
                "classification_code": "HIGH",
                "classification_label": "High Risk",
                "display_color": "red",
            }
        )

    def test_calculate_score_basic(self):
        """Test basic score calculation."""
        result = self.ScoringEngine.calculate_score(
            self.registrant,
            self.model,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.registrant_id, self.registrant)
        self.assertEqual(result.model_id, self.model)
        self.assertGreaterEqual(result.score, 0)
        self.assertTrue(result.is_complete)

    def test_calculate_score_creates_details(self):
        """Test that score calculation creates detail records."""
        result = self.ScoringEngine.calculate_score(
            self.registrant,
            self.model,
        )

        self.assertEqual(len(result.detail_ids), 2)
        indicator_codes = result.detail_ids.mapped("indicator_code")
        self.assertIn("ID_SCORE", indicator_codes)
        self.assertIn("IS_GROUP", indicator_codes)

    def test_calculate_score_classification(self):
        """Test that scores are classified correctly."""
        result = self.ScoringEngine.calculate_score(
            self.registrant,
            self.model,
        )

        # Classification should be set
        self.assertIsNotNone(result.classification_code)
        self.assertIsNotNone(result.classification_label)

    def test_calculate_score_stores_snapshot(self):
        """Test that inputs are stored in snapshot."""
        result = self.ScoringEngine.calculate_score(
            self.registrant,
            self.model,
        )

        inputs = result.get_inputs()
        self.assertIn("ID_SCORE", inputs)
        self.assertIn("IS_GROUP", inputs)

    def test_calculate_score_stores_breakdown(self):
        """Test that breakdown is stored."""
        result = self.ScoringEngine.calculate_score(
            self.registrant,
            self.model,
        )

        breakdown = result.get_breakdown()
        self.assertIsInstance(breakdown, list)
        self.assertEqual(len(breakdown), 2)

    def test_calculate_score_inactive_model_fails(self):
        """Test that scoring with inactive model fails."""
        inactive_model = self.ScoringModel.create(
            {
                "name": "Inactive Model",
                "code": "INACTIVE",
                "is_active": False,
            }
        )

        with self.assertRaises(UserError):
            self.ScoringEngine.calculate_score(
                self.registrant,
                inactive_model,
            )

    def test_calculate_score_without_registrant_fails(self):
        """Test that scoring without registrant fails."""
        with self.assertRaises(ValidationError):
            self.ScoringEngine.calculate_score(
                None,
                self.model,
            )

    def test_calculate_score_without_model_fails(self):
        """Test that scoring without model fails."""
        with self.assertRaises(ValidationError):
            self.ScoringEngine.calculate_score(
                self.registrant,
                None,
            )

    def test_batch_scoring(self):
        """Test batch scoring multiple registrants."""
        # Create more registrants
        registrant2 = self.Partner.create(
            {
                "name": "Registrant 2",
                "is_registrant": True,
            }
        )
        registrant3 = self.Partner.create(
            {
                "name": "Registrant 3",
                "is_registrant": True,
            }
        )

        registrants = self.registrant | registrant2 | registrant3

        result = self.ScoringEngine.batch_score(
            registrants,
            self.model,
        )

        self.assertEqual(result["summary"]["total"], 3)
        self.assertEqual(result["summary"]["successful"], 3)
        self.assertEqual(result["summary"]["failed"], 0)
        self.assertEqual(len(result["results"]), 3)

    def test_batch_scoring_with_errors(self):
        """Test batch scoring handles errors gracefully."""
        # Create a model with a required indicator that will fail
        strict_model = self.ScoringModel.create(
            {
                "name": "Strict Model",
                "code": "STRICT",
                "is_active": True,
                "is_strict_mode": True,
            }
        )
        self.ScoringIndicator.create(
            {
                "model_id": strict_model.id,
                "name": "Missing Field",
                "code": "MISSING",
                "field_path": "nonexistent_field",
                "calculation_type": "direct",
                "is_required": True,
            }
        )
        self.ScoringThreshold.create(
            {
                "model_id": strict_model.id,
                "name": "All",
                "min_score": 0,
                "max_score": 1000,
                "classification_code": "ALL",
                "classification_label": "All",
            }
        )

        # Batch scoring should continue despite errors (default behavior)
        result = self.ScoringEngine.batch_score(
            self.registrant,
            strict_model,
        )

        # Should have 1 result but marked as incomplete
        self.assertEqual(result["summary"]["total"], 1)

    def test_get_or_calculate_score_caches(self):
        """Test get_or_calculate_score returns cached score."""
        # First calculation
        result1 = self.ScoringEngine.get_or_calculate_score(
            self.registrant,
            self.model,
            max_age_days=30,
        )

        # Second call should return the same result
        result2 = self.ScoringEngine.get_or_calculate_score(
            self.registrant,
            self.model,
            max_age_days=30,
        )

        self.assertEqual(result1.id, result2.id)

    def test_get_or_calculate_score_recalculates_when_stale(self):
        """Test that stale scores trigger recalculation."""
        # First calculation
        result1 = self.ScoringEngine.get_or_calculate_score(
            self.registrant,
            self.model,
            max_age_days=None,  # Always recalculate
        )

        # Second call with max_age=None should create new result
        result2 = self.ScoringEngine.get_or_calculate_score(
            self.registrant,
            self.model,
            max_age_days=None,
        )

        self.assertNotEqual(result1.id, result2.id)

    def test_compare_scores(self):
        """Test score comparison between model versions."""
        # Create a second model version
        model2 = self.ScoringModel.create(
            {
                "name": "Test Model V2",
                "code": "TEST_ENGINE_V2",
                "version": "2.0",
                "calculation_method": "weighted_sum",
                "is_active": True,
            }
        )
        self.ScoringIndicator.create(
            {
                "model_id": model2.id,
                "name": "ID Score",
                "code": "ID_SCORE",
                "field_path": "id",
                "calculation_type": "direct",
                "weight": 1.0,  # Different weight
                "min_score": 0,
                "max_score": 100,
            }
        )
        self.ScoringThreshold.create(
            {
                "model_id": model2.id,
                "name": "All",
                "min_score": 0,
                "max_score": 1000,
                "classification_code": "ALL",
                "classification_label": "All",
            }
        )

        comparison = self.ScoringEngine.compare_scores(
            self.registrant,
            self.model,
            model2,
        )

        self.assertIn("old_score", comparison)
        self.assertIn("new_score", comparison)
        self.assertIn("score_change", comparison)
        self.assertIn("classification_changed", comparison)
