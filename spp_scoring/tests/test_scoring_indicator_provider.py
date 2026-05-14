"""Tests for ScoringIndicatorProvider integration with spp_indicators."""

from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestScoringIndicatorProvider(TransactionCase):
    """Test cases for scoring indicator provider integration."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ScoringModel = cls.env["spp.scoring.model"]
        cls.ScoringIndicator = cls.env["spp.scoring.indicator"]
        cls.ScoringThreshold = cls.env["spp.scoring.threshold"]
        cls.ScoringResult = cls.env["spp.scoring.result"]
        cls.Partner = cls.env["res.partner"]
        cls.Bridge = cls.env["spp.scoring.indicator.bridge"]

        # Create a test registrant
        cls.registrant = cls.Partner.create(
            {
                "name": "Test Registrant",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create a complete scoring model
        cls.scoring_model = cls.ScoringModel.create(
            {
                "name": "Test PMT Model",
                "code": "test_pmt",
                "version": "1.0",
                "category": "poverty",
                "calculation_method": "weighted_sum",
                "expected_total_weight": 1.0,
            }
        )
        cls.ScoringIndicator.create(
            {
                "model_id": cls.scoring_model.id,
                "name": "Test Indicator",
                "code": "test_ind",
                "weight": 1.0,
                "calculation_type": "direct",
                "field_path": "id",
            }
        )
        cls.ScoringThreshold.create(
            {
                "model_id": cls.scoring_model.id,
                "name": "Low",
                "min_score": 0,
                "max_score": 49.99,
                "classification_code": "LOW",
                "classification_label": "Low Score",
            }
        )
        cls.ScoringThreshold.create(
            {
                "model_id": cls.scoring_model.id,
                "name": "High",
                "min_score": 50,
                "max_score": 100,
                "classification_code": "HIGH",
                "classification_label": "High Score",
            }
        )

    def test_bridge_model_exists(self):
        """Test that the bridge model is available."""
        self.assertIn("spp.scoring.indicator.bridge", self.env)

    def test_register_scoring_model_without_indicators(self):
        """Test registration when spp_indicators is not installed."""
        # When spp_indicators is not installed, registration should be silent
        with patch.object(type(self.Bridge), "_get_indicator_registry", return_value=None):
            # Should not raise an error
            self.Bridge.register_scoring_model("test_pmt")

    def test_register_scoring_model_with_mock_registry(self):
        """Test provider registration with a mock indicator registry."""
        mock_registry = MagicMock()

        with patch.object(type(self.Bridge), "_get_indicator_registry", return_value=mock_registry):
            self.Bridge.register_scoring_model("test_pmt")

            # Verify register was called with correct arguments
            mock_registry.register.assert_called_once()
            call_kwargs = mock_registry.register.call_args.kwargs
            self.assertEqual(call_kwargs["name"], "scoring.test_pmt")
            self.assertEqual(call_kwargs["return_type"], "number")
            self.assertEqual(call_kwargs["subject_model"], "res.partner")

    def test_register_all_scoring_models(self):
        """Test registering all active scoring models."""
        # Activate the model
        self.scoring_model.action_activate()
        self.assertTrue(self.scoring_model.is_active)

        mock_registry = MagicMock()

        with patch.object(type(self.Bridge), "_get_indicator_registry", return_value=mock_registry):
            self.Bridge.register_all_scoring_models()

            # Should have registered at least our test model
            self.assertTrue(mock_registry.register.called)

    def test_provider_compute_batch_with_results(self):
        """Test compute_batch returns correct scores."""
        from odoo.addons.spp_scoring.models.scoring_indicator_provider import (
            ScoringIndicatorProvider,
        )

        # Create a scoring result
        self.ScoringResult.create(
            {
                "model_id": self.scoring_model.id,
                "registrant_id": self.registrant.id,
                "score": 75.5,
                "classification_code": "HIGH",
                "classification_label": "High Score",
            }
        )

        provider = ScoringIndicatorProvider("test_pmt")
        result = provider.compute_batch(self.env, {}, [self.registrant.id])

        self.assertIn(self.registrant.id, result)
        self.assertAlmostEqual(result[self.registrant.id], 75.5, places=1)

    def test_provider_compute_batch_empty_ids(self):
        """Test compute_batch with empty subject_ids list."""
        from odoo.addons.spp_scoring.models.scoring_indicator_provider import (
            ScoringIndicatorProvider,
        )

        provider = ScoringIndicatorProvider("test_pmt")
        result = provider.compute_batch(self.env, {}, [])

        self.assertEqual(result, {})

    def test_provider_compute_batch_missing_model(self):
        """Test compute_batch with non-existent model code."""
        from odoo.addons.spp_scoring.models.scoring_indicator_provider import (
            ScoringIndicatorProvider,
        )

        provider = ScoringIndicatorProvider("nonexistent_model")
        result = provider.compute_batch(self.env, {}, [self.registrant.id])

        self.assertEqual(result, {})

    def test_provider_compute_batch_no_results(self):
        """Test compute_batch when no scoring results exist."""
        from odoo.addons.spp_scoring.models.scoring_indicator_provider import (
            ScoringIndicatorProvider,
        )

        # Create a new registrant with no scores
        new_registrant = self.Partner.create(
            {
                "name": "No Scores Registrant",
                "is_registrant": True,
                "is_group": True,
            }
        )

        provider = ScoringIndicatorProvider("test_pmt")
        result = provider.compute_batch(self.env, {}, [new_registrant.id])

        # Should not include the registrant (no score)
        self.assertNotIn(new_registrant.id, result)

    def test_provider_returns_latest_score(self):
        """Test that compute_batch returns the most recent score."""
        from odoo.addons.spp_scoring.models.scoring_indicator_provider import (
            ScoringIndicatorProvider,
        )

        # Create older score
        self.ScoringResult.create(
            {
                "model_id": self.scoring_model.id,
                "registrant_id": self.registrant.id,
                "score": 50.0,
                "classification_code": "LOW",
                "classification_label": "Low Score",
            }
        )

        # Create newer score
        self.ScoringResult.create(
            {
                "model_id": self.scoring_model.id,
                "registrant_id": self.registrant.id,
                "score": 85.0,
                "classification_code": "HIGH",
                "classification_label": "High Score",
            }
        )

        provider = ScoringIndicatorProvider("test_pmt")
        result = provider.compute_batch(self.env, {}, [self.registrant.id])

        # Should return the latest score (85.0)
        self.assertAlmostEqual(result[self.registrant.id], 85.0, places=1)

    def test_mixin_registers_on_activate(self):
        """Test that activating a model triggers registration."""
        # Create a new model
        new_model = self.ScoringModel.create(
            {
                "name": "Auto Register Model",
                "code": "auto_register",
                "expected_total_weight": 1.0,
            }
        )
        self.ScoringIndicator.create(
            {
                "model_id": new_model.id,
                "name": "Indicator",
                "code": "ind",
                "weight": 1.0,
                "calculation_type": "direct",
                "field_path": "id",
            }
        )
        self.ScoringThreshold.create(
            {
                "model_id": new_model.id,
                "name": "Threshold",
                "min_score": 0,
                "max_score": 100,
                "classification_code": "ALL",
                "classification_label": "All",
            }
        )

        mock_registry = MagicMock()

        with patch.object(type(self.Bridge), "_get_indicator_registry", return_value=mock_registry):
            new_model.action_activate()

            # Should have called register
            mock_registry.register.assert_called()
            call_kwargs = mock_registry.register.call_args.kwargs
            self.assertEqual(call_kwargs["name"], "scoring.auto_register")


@tagged("post_install", "-at_install")
class TestScoringIndicatorProviderCompanyScoping(TransactionCase):
    """Test company scoping for scoring indicator provider."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ScoringModel = cls.env["spp.scoring.model"]
        cls.ScoringIndicator = cls.env["spp.scoring.indicator"]
        cls.ScoringThreshold = cls.env["spp.scoring.threshold"]
        cls.ScoringResult = cls.env["spp.scoring.result"]
        cls.Partner = cls.env["res.partner"]

    def test_compute_batch_respects_company(self):
        """Test that compute_batch filters by company if applicable."""
        from odoo.addons.spp_scoring.models.scoring_indicator_provider import (
            ScoringIndicatorProvider,
        )

        # Create scoring model
        model = self.ScoringModel.create(
            {
                "name": "Company Test Model",
                "code": "company_test",
            }
        )

        registrant = self.Partner.create(
            {
                "name": "Test Registrant",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create a result (company_id comes from spp.scoring.result model)
        self.ScoringResult.create(
            {
                "model_id": model.id,
                "registrant_id": registrant.id,
                "score": 60.0,
                "classification_code": "MED",
                "classification_label": "Medium",
            }
        )

        provider = ScoringIndicatorProvider("company_test")
        result = provider.compute_batch(self.env, {}, [registrant.id])

        # Should return the score for this company
        self.assertIn(registrant.id, result)
        self.assertAlmostEqual(result[registrant.id], 60.0, places=1)
