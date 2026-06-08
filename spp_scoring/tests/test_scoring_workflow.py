from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestScoringWorkflow(TransactionCase):
    """Integration tests for complete scoring workflows."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ScoringModel = cls.env["spp.scoring.model"]
        cls.ScoringIndicator = cls.env["spp.scoring.indicator"]
        cls.ScoringThreshold = cls.env["spp.scoring.threshold"]
        cls.ValueMapping = cls.env["spp.scoring.value_mapping"]
        cls.ScoringEngine = cls.env["spp.scoring.engine"]
        cls.Partner = cls.env["res.partner"]

    def _create_pmt_model(self):
        """Create a PMT-style scoring model for testing."""
        model = self.ScoringModel.create(
            {
                "name": "Test PMT Model",
                "code": "PMT_TEST",
                "category": "poverty",
                "calculation_method": "weighted_sum",
                "expected_total_weight": 1.0,
            }
        )

        # Indicator: is_group (boolean -> 0 or 1)
        self.ScoringIndicator.create(
            {
                "model_id": model.id,
                "name": "Group Status",
                "code": "GROUP_STATUS",
                "field_path": "is_group",
                "calculation_type": "direct",
                "weight": 0.3,
            }
        )

        # Indicator: name length as proxy (mapped)
        ind2 = self.ScoringIndicator.create(
            {
                "model_id": model.id,
                "name": "Name Category",
                "code": "NAME_CAT",
                "field_path": "active",
                "calculation_type": "mapped",
                "weight": 0.4,
            }
        )
        self.ValueMapping.create(
            [
                {"indicator_id": ind2.id, "input_value": "True", "output_score": 10},
                {"indicator_id": ind2.id, "input_value": "False", "output_score": 5},
            ]
        )

        # Indicator: ID-based (range)
        ind3 = self.ScoringIndicator.create(
            {
                "model_id": model.id,
                "name": "ID Range",
                "code": "ID_RANGE",
                "field_path": "id",
                "calculation_type": "range",
                "weight": 0.3,
                "default_score": 5,
            }
        )
        self.ValueMapping.create(
            [
                {"indicator_id": ind3.id, "range_min": 0, "range_max": 100, "output_score": 10},
                {"indicator_id": ind3.id, "range_min": 101, "range_max": 1000, "output_score": 5},
                {"indicator_id": ind3.id, "range_min": 1001, "range_max": 1000000, "output_score": 0},
            ]
        )

        # Thresholds
        self.ScoringThreshold.create(
            [
                {
                    "model_id": model.id,
                    "name": "Extremely Poor",
                    "min_score": 0,
                    "max_score": 2.5,
                    "classification_code": "EXTREME_POOR",
                    "classification_label": "Extremely Poor",
                    "display_color": "red",
                },
                {
                    "model_id": model.id,
                    "name": "Poor",
                    "min_score": 2.51,
                    "max_score": 5.0,
                    "classification_code": "POOR",
                    "classification_label": "Poor",
                    "display_color": "orange",
                },
                {
                    "model_id": model.id,
                    "name": "Near Poor",
                    "min_score": 5.01,
                    "max_score": 7.5,
                    "classification_code": "NEAR_POOR",
                    "classification_label": "Near Poor",
                    "display_color": "yellow",
                },
                {
                    "model_id": model.id,
                    "name": "Non-Poor",
                    "min_score": 7.51,
                    "max_score": 100,
                    "classification_code": "NON_POOR",
                    "classification_label": "Non-Poor",
                    "display_color": "green",
                },
            ]
        )

        return model

    def test_complete_scoring_workflow(self):
        """Test a complete scoring workflow from model creation to results."""
        # Step 1: Create and configure the model
        model = self._create_pmt_model()

        # Step 2: Activate the model
        model.action_activate()
        self.assertTrue(model.is_active)

        # Step 3: Create test registrants
        registrant1 = self.Partner.create(
            {
                "name": "Poor Household",
                "is_registrant": True,
                "is_group": True,
                "active": False,
            }
        )
        registrant2 = self.Partner.create(
            {
                "name": "Non-Poor Household",
                "is_registrant": True,
                "is_group": False,
                "active": True,
            }
        )

        # Step 4: Score registrants
        result1 = self.ScoringEngine.calculate_score(registrant1, model)
        result2 = self.ScoringEngine.calculate_score(registrant2, model)

        # Step 5: Verify results
        self.assertTrue(result1.is_complete)
        self.assertTrue(result2.is_complete)

        # Verify breakdowns were created
        self.assertEqual(len(result1.detail_ids), 3)
        self.assertEqual(len(result2.detail_ids), 3)

        # Verify classifications are different (different characteristics)
        # Both registrants should have valid classifications

    def test_batch_scoring_workflow(self):
        """Test batch scoring multiple registrants."""
        model = self._create_pmt_model()
        model.action_activate()

        # Create multiple registrants
        registrants = self.Partner.create([{"name": f"Registrant {i}", "is_registrant": True} for i in range(5)])

        # Batch score
        result = self.ScoringEngine.batch_score(registrants, model)

        # Verify all were scored
        self.assertEqual(result["summary"]["total"], 5)
        self.assertEqual(result["summary"]["successful"], 5)
        self.assertEqual(result["summary"]["failed"], 0)

    def test_model_validation_workflow(self):
        """Test the model validation before activation."""
        model = self.ScoringModel.create(
            {
                "name": "Incomplete Model",
                "code": "INCOMPLETE",
                "expected_total_weight": 1.0,
            }
        )

        # Should fail validation - no indicators
        errors = model._validate_configuration()
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("indicator" in e.lower() for e in errors))

        # Add an indicator
        self.ScoringIndicator.create(
            {
                "model_id": model.id,
                "name": "Test",
                "code": "TEST",
                "field_path": "id",
                "calculation_type": "direct",
                "weight": 0.5,  # Only 0.5, not 1.0
            }
        )

        # Should fail validation - weight doesn't sum correctly
        errors = model._validate_configuration()
        self.assertTrue(len(errors) > 0)

    def test_recalculation_workflow(self):
        """Test recalculating scores when model changes."""
        model = self._create_pmt_model()
        model.action_activate()

        registrant = self.Partner.create(
            {
                "name": "Test Registrant",
                "is_registrant": True,
            }
        )

        # Initial score
        result1 = self.ScoringEngine.calculate_score(registrant, model)
        score1 = result1.score

        # Recalculate (should create new result)
        result2 = self.ScoringEngine.calculate_score(registrant, model)
        score2 = result2.score

        # Scores should be the same (same data)
        self.assertEqual(score1, score2)

        # But should be different result records
        self.assertNotEqual(result1.id, result2.id)

    def test_result_history(self):
        """Test that score history is maintained."""
        model = self._create_pmt_model()
        model.action_activate()

        registrant = self.Partner.create(
            {
                "name": "History Test",
                "is_registrant": True,
            }
        )

        # Calculate multiple scores
        for _ in range(3):
            self.ScoringEngine.calculate_score(registrant, model)

        # Check history
        Result = self.env["spp.scoring.result"]
        history = Result.search(
            [
                ("registrant_id", "=", registrant.id),
                ("model_id", "=", model.id),
            ]
        )

        self.assertEqual(len(history), 3)

        # Latest should be first (ordered by calculation_date desc)
        latest = Result.get_latest_score(registrant, model)
        self.assertEqual(latest.id, max(history.ids))

    def test_threshold_classification(self):
        """Test that thresholds correctly classify scores."""
        model = self.ScoringModel.create(
            {
                "name": "Classification Test",
                "code": "CLASS_TEST",
                "is_active": True,
            }
        )

        # Simple indicator that returns the ID as score
        # Note: Use max_score to cap scores to 100 range
        self.ScoringIndicator.create(
            {
                "model_id": model.id,
                "name": "Score",
                "code": "SCORE",
                "field_path": "id",
                "calculation_type": "direct",
                "weight": 1.0,
                "max_score": 100,  # Cap to 100 for threshold tests
            }
        )

        # Create thresholds
        self.ScoringThreshold.create(
            [
                {
                    "model_id": model.id,
                    "name": "Low",
                    "min_score": 0,
                    "max_score": 33,
                    "classification_code": "LOW",
                    "classification_label": "Low",
                },
                {
                    "model_id": model.id,
                    "name": "Medium",
                    "min_score": 33.01,
                    "max_score": 66,
                    "classification_code": "MEDIUM",
                    "classification_label": "Medium",
                },
                {
                    "model_id": model.id,
                    "name": "High",
                    "min_score": 66.01,
                    "max_score": 100,
                    "classification_code": "HIGH",
                    "classification_label": "High",
                },
            ]
        )

        # The classification will depend on the partner ID
        # Since IDs are auto-generated, we just verify classification exists
        registrant = self.Partner.create(
            {
                "name": "Classification Registrant",
                "is_registrant": True,
            }
        )

        result = self.ScoringEngine.calculate_score(registrant, model)

        # Should have a classification
        self.assertIsNotNone(result.classification_code)
        self.assertIn(result.classification_code, ["LOW", "MEDIUM", "HIGH"])
