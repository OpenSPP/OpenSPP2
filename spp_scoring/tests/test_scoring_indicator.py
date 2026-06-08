from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestScoringIndicator(TransactionCase):
    """Test cases for spp.scoring.indicator."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ScoringModel = cls.env["spp.scoring.model"]
        cls.ScoringIndicator = cls.env["spp.scoring.indicator"]
        cls.ValueMapping = cls.env["spp.scoring.value_mapping"]

        # Create a test model
        cls.model = cls.ScoringModel.create(
            {
                "name": "Test Model",
                "code": "TEST_IND_MODEL",
            }
        )

    def test_create_direct_indicator(self):
        """Test creating a direct calculation indicator."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Age Indicator",
                "code": "AGE",
                "field_path": "id",
                "calculation_type": "direct",
                "weight": 0.5,
            }
        )

        self.assertEqual(indicator.calculation_type, "direct")
        self.assertEqual(indicator.weight, 0.5)

    def test_mapped_indicator_without_mappings_uses_default(self):
        """Test that mapped indicators without mappings use default_score."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Mapped Without Mappings",
                "code": "MAPPED_NO_MAP",
                "field_path": "id",
                "calculation_type": "mapped",
                "default_score": 5.0,
            }
        )
        # With no mappings, any value returns default_score
        self.assertEqual(indicator.calculate_score("anything"), 5.0)

    def test_range_indicator_without_mappings_uses_default(self):
        """Test that range indicators without mappings use default_score."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Range Without Mappings",
                "code": "RANGE_NO_MAP",
                "field_path": "id",
                "calculation_type": "range",
                "default_score": 3.0,
            }
        )
        # With no mappings, any value returns default_score
        self.assertEqual(indicator.calculate_score(100), 3.0)

    def test_formula_indicator_requires_expression(self):
        """Test that formula indicators require CEL expression."""
        with self.assertRaises(ValidationError):
            self.ScoringIndicator.create(
                {
                    "model_id": self.model.id,
                    "name": "Formula Without Expression",
                    "code": "FORMULA_NO_EXPR",
                    "calculation_type": "formula",
                }
            )

    def test_calculate_direct_score(self):
        """Test direct score calculation."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Direct",
                "code": "DIRECT",
                "field_path": "id",
                "calculation_type": "direct",
                "weight": 1.0,
            }
        )

        score = indicator.calculate_score(10)
        self.assertEqual(score, 10.0)

        # Boolean handling
        score = indicator.calculate_score(True)
        self.assertEqual(score, 1.0)

        score = indicator.calculate_score(False)
        self.assertEqual(score, 0.0)

    def test_calculate_mapped_score(self):
        """Test mapped score calculation."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Roof Material",
                "code": "ROOF",
                "field_path": "name",
                "calculation_type": "mapped",
                "weight": 1.0,
            }
        )
        self.ValueMapping.create(
            {
                "indicator_id": indicator.id,
                "input_value": "concrete",
                "output_score": 0,
            }
        )
        self.ValueMapping.create(
            {
                "indicator_id": indicator.id,
                "input_value": "wood",
                "output_score": 5,
            }
        )
        self.ValueMapping.create(
            {
                "indicator_id": indicator.id,
                "input_value": "thatch",
                "output_score": 10,
            }
        )

        self.assertEqual(indicator.calculate_score("concrete"), 0)
        self.assertEqual(indicator.calculate_score("wood"), 5)
        self.assertEqual(indicator.calculate_score("thatch"), 10)
        self.assertEqual(indicator.calculate_score("unknown"), 0)  # default

    def test_calculate_range_score(self):
        """Test range score calculation."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Income Range",
                "code": "INCOME",
                "field_path": "id",
                "calculation_type": "range",
                "weight": 1.0,
                "default_score": 0,
            }
        )
        self.ValueMapping.create(
            {
                "indicator_id": indicator.id,
                "range_min": 0,
                "range_max": 1000,
                "output_score": 10,
            }
        )
        self.ValueMapping.create(
            {
                "indicator_id": indicator.id,
                "range_min": 1001,
                "range_max": 5000,
                "output_score": 5,
            }
        )
        self.ValueMapping.create(
            {
                "indicator_id": indicator.id,
                "range_min": 5001,
                "range_max": 100000,
                "output_score": 0,
            }
        )

        self.assertEqual(indicator.calculate_score(500), 10)
        self.assertEqual(indicator.calculate_score(2500), 5)
        self.assertEqual(indicator.calculate_score(10000), 0)

    def test_default_value_handling(self):
        """Test default value when field is None."""
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "With Default",
                "code": "DEFAULT",
                "field_path": "id",
                "calculation_type": "direct",
                "default_value": "5",
                "default_score": 0,
            }
        )

        score = indicator.calculate_score(None)
        self.assertEqual(score, 5.0)

    def test_min_max_constraints(self):
        """Test min/max score constraints.

        Note: min_score=0 is treated as "no constraint" since Float fields
        default to 0.0. Use non-zero values for actual constraints.
        """
        indicator = self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "Constrained",
                "code": "CONSTRAINED",
                "field_path": "id",
                "calculation_type": "direct",
                "min_score": 1,  # Non-zero to enforce minimum
                "max_score": 10,
            }
        )

        # Within range
        self.assertEqual(indicator.calculate_score(5), 5)

        # Below min - clamped to min_score
        self.assertEqual(indicator.calculate_score(-5), 1)
        self.assertEqual(indicator.calculate_score(0), 1)

        # Above max - clamped to max_score
        self.assertEqual(indicator.calculate_score(15), 10)

    def test_indicator_code_uniqueness_per_model(self):
        """Test that indicator codes are unique within a model."""
        self.ScoringIndicator.create(
            {
                "model_id": self.model.id,
                "name": "First",
                "code": "UNIQUE",
                "field_path": "id",
                "calculation_type": "direct",
            }
        )

        with self.assertRaises(ValidationError):
            self.ScoringIndicator.create(
                {
                    "model_id": self.model.id,
                    "name": "Second",
                    "code": "UNIQUE",
                    "field_path": "name",
                    "calculation_type": "direct",
                }
            )
