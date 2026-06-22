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

    # ─── threshold gap / overlap detection (#835 r3) ──────────────────

    def _model_with_one_indicator(self, code):
        model = self.ScoringModel.create({"name": code, "code": code, "expected_total_weight": 1.0})
        self.ScoringIndicator.create(
            {
                "model_id": model.id,
                "name": "Indicator",
                "code": f"{code}_IND",
                "weight": 1.0,
                "calculation_type": "direct",
                "field_path": "id",
            }
        )
        return model

    def test_threshold_gap_blocks_activation(self):
        """Gap between thresholds (e.g. 0–20 / 21–40) blocks activation."""
        model = self._model_with_one_indicator("GAP_MODEL")
        self.ScoringThreshold.create(
            {
                "model_id": model.id,
                "name": "Low",
                "min_score": 0,
                "max_score": 20,
                "classification_code": "LOW",
                "classification_label": "Low",
            }
        )
        self.ScoringThreshold.create(
            {
                "model_id": model.id,
                "name": "High",
                "min_score": 21,
                "max_score": 40,
                "classification_code": "HIGH",
                "classification_label": "High",
            }
        )
        with self.assertRaises(ValidationError) as ctx:
            model.action_activate()
        self.assertIn("Gap detected", str(ctx.exception))

    def test_threshold_overlap_blocks_activation(self):
        """Shared boundary thresholds (e.g. 0–20 / 20–40) blocks activation.

        matches_score uses inclusive bounds on both ends, so the shared value
        at the boundary belongs to both thresholds — that's a real overlap.
        """
        model = self._model_with_one_indicator("OVL_MODEL")
        self.ScoringThreshold.create(
            {
                "model_id": model.id,
                "name": "Low",
                "min_score": 0,
                "max_score": 20,
                "classification_code": "LOW",
                "classification_label": "Low",
            }
        )
        self.ScoringThreshold.create(
            {
                "model_id": model.id,
                "name": "High",
                "min_score": 20,
                "max_score": 40,
                "classification_code": "HIGH",
                "classification_label": "High",
            }
        )
        with self.assertRaises(ValidationError) as ctx:
            model.action_activate()
        self.assertIn("Overlap detected", str(ctx.exception))

    def test_threshold_contiguous_passes(self):
        """Properly contiguous thresholds (0–20 / 20.01–40) activate cleanly."""
        model = self._model_with_one_indicator("OK_MODEL")
        self.ScoringThreshold.create(
            {
                "model_id": model.id,
                "name": "Low",
                "min_score": 0,
                "max_score": 20,
                "classification_code": "LOW",
                "classification_label": "Low",
            }
        )
        self.ScoringThreshold.create(
            {
                "model_id": model.id,
                "name": "High",
                "min_score": 20.01,
                "max_score": 40,
                "classification_code": "HIGH",
                "classification_label": "High",
            }
        )
        model.action_activate()
        self.assertTrue(model.is_active)

    # ─── copy=True on indicator_ids / threshold_ids ──────────────────

    def test_copy_duplicates_indicators_and_thresholds(self):
        """Copying a scoring model now duplicates its indicators + thresholds
        instead of leaving the copy empty (#839)."""
        model = self._model_with_one_indicator("COPY_SRC")
        self.ScoringThreshold.create(
            {
                "model_id": model.id,
                "name": "Low",
                "min_score": 0,
                "max_score": 100,
                "classification_code": "LOW",
                "classification_label": "Low",
            }
        )

        clone = model.copy()
        self.assertEqual(len(clone.indicator_ids), 1)
        self.assertEqual(len(clone.threshold_ids), 1)
        # Copied indicator/threshold must point at the new model
        self.assertEqual(clone.indicator_ids[0].model_id, clone)
        self.assertEqual(clone.threshold_ids[0].model_id, clone)
        # Source model unchanged
        self.assertEqual(len(model.indicator_ids), 1)
        self.assertEqual(len(model.threshold_ids), 1)
