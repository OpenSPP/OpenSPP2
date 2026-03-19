from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestScoringModel(TransactionCase):
    """Test cases for spp.scoring.model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ScoringModel = cls.env["spp.scoring.model"]
        cls.ScoringIndicator = cls.env["spp.scoring.indicator"]
        cls.ScoringThreshold = cls.env["spp.scoring.threshold"]

    def test_create_scoring_model(self):
        """Test creating a basic scoring model."""
        model = self.ScoringModel.create(
            {
                "name": "Test PMT Model",
                "code": "TEST_PMT_001",
                "version": "1.0",
                "category": "poverty",
                "calculation_method": "weighted_sum",
            }
        )

        self.assertEqual(model.name, "Test PMT Model")
        self.assertEqual(model.code, "TEST_PMT_001")
        self.assertEqual(model.category, "poverty")
        self.assertFalse(model.is_active)

    def test_code_uniqueness(self):
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

    def test_date_validation(self):
        """Test that effective_date must be before end_date."""
        with self.assertRaises(ValidationError):
            self.ScoringModel.create(
                {
                    "name": "Invalid Dates Model",
                    "code": "INVALID_DATES",
                    "effective_date": date.today(),
                    "end_date": date.today() - timedelta(days=10),
                }
            )

    def test_is_active_on_date(self):
        """Test the is_active_on_date method."""
        today = date.today()
        model = self.ScoringModel.create(
            {
                "name": "Date Test Model",
                "code": "DATE_TEST",
                "effective_date": today - timedelta(days=10),
                "end_date": today + timedelta(days=10),
                "is_active": True,
            }
        )

        # Within range
        self.assertTrue(model.is_active_on_date(today))

        # Before effective date
        self.assertFalse(model.is_active_on_date(today - timedelta(days=20)))

        # After end date
        self.assertFalse(model.is_active_on_date(today + timedelta(days=20)))

        # When not active
        model.is_active = False
        self.assertFalse(model.is_active_on_date(today))

    def test_compute_total_weight(self):
        """Test that total weight is computed from indicators."""
        model = self.ScoringModel.create(
            {
                "name": "Weight Test Model",
                "code": "WEIGHT_TEST",
            }
        )

        self.ScoringIndicator.create(
            {
                "model_id": model.id,
                "name": "Indicator 1",
                "code": "IND1",
                "weight": 0.3,
                "calculation_type": "direct",
                "field_path": "id",
            }
        )
        self.ScoringIndicator.create(
            {
                "model_id": model.id,
                "name": "Indicator 2",
                "code": "IND2",
                "weight": 0.7,
                "calculation_type": "direct",
                "field_path": "id",
            }
        )

        model.invalidate_recordset()
        self.assertAlmostEqual(model.total_weight, 1.0, places=2)

    def test_activation_requires_indicators(self):
        """Test that activation fails without indicators."""
        model = self.ScoringModel.create(
            {
                "name": "No Indicators Model",
                "code": "NO_IND",
            }
        )

        with self.assertRaises(ValidationError):
            model.action_activate()

    def test_activation_requires_thresholds(self):
        """Test that activation fails without thresholds."""
        model = self.ScoringModel.create(
            {
                "name": "No Thresholds Model",
                "code": "NO_THRESH",
            }
        )
        self.ScoringIndicator.create(
            {
                "model_id": model.id,
                "name": "Indicator",
                "code": "IND",
                "weight": 1.0,
                "calculation_type": "direct",
                "field_path": "id",
            }
        )

        with self.assertRaises(ValidationError):
            model.action_activate()

    def test_successful_activation(self):
        """Test successful model activation."""
        model = self.ScoringModel.create(
            {
                "name": "Complete Model",
                "code": "COMPLETE",
                "expected_total_weight": 1.0,
            }
        )
        self.ScoringIndicator.create(
            {
                "model_id": model.id,
                "name": "Indicator",
                "code": "IND",
                "weight": 1.0,
                "calculation_type": "direct",
                "field_path": "id",
            }
        )
        self.ScoringThreshold.create(
            {
                "model_id": model.id,
                "name": "Low",
                "min_score": 0,
                "max_score": 100,
                "classification_code": "LOW",
                "classification_label": "Low Score",
            }
        )

        model.action_activate()
        self.assertTrue(model.is_active)

    def test_copy_creates_inactive_model(self):
        """Test that copying a model creates an inactive copy."""
        model = self.ScoringModel.create(
            {
                "name": "Original Model",
                "code": "ORIGINAL",
                "is_active": True,
            }
        )

        copy = model.copy()
        self.assertFalse(copy.is_active)
        self.assertIn("copy", copy.code)

    def test_cel_formula_requires_expression(self):
        """Test that CEL formula method requires an expression."""
        with self.assertRaises(ValidationError):
            self.ScoringModel.create(
                {
                    "name": "CEL Without Expression",
                    "code": "CEL_NO_EXPR",
                    "calculation_method": "cel_formula",
                    "cel_expression": False,
                }
            )
