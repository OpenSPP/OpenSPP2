# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DemographicDimension.to_sql_column() SQL compilation."""

from odoo.tests import TransactionCase, tagged
from odoo.tools.sql import SQL

from ..models.demographic_dimension import SQLColumnResult


@tagged("post_install", "-at_install")
class TestDimensionSqlColumn(TransactionCase):
    """Test to_sql_column() for field-based and expression-based dimensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Dim = cls.env["spp.demographic.dimension"]

        # Simple boolean field
        cls.dim_is_group = Dim.create(
            {
                "name": "test_is_group",
                "label": "Is Group",
                "dimension_type": "field",
                "field_path": "is_group",
                "default_value": "unknown",
            }
        )

        # Many2one with .code path (gender_id.code)
        cls.dim_gender_code = Dim.create(
            {
                "name": "test_gender_code",
                "label": "Gender Code",
                "dimension_type": "field",
                "field_path": "gender_id.code",
                "default_value": "unknown",
            }
        )

        # Many2one direct (gender_id)
        cls.dim_gender_direct = Dim.create(
            {
                "name": "test_gender_direct",
                "label": "Gender Direct",
                "dimension_type": "field",
                "field_path": "gender_id",
                "default_value": "unknown",
            }
        )

        # CEL expression dimension
        cls.dim_age_group = Dim.create(
            {
                "name": "test_age_group",
                "label": "Age Group",
                "dimension_type": "expression",
                "cel_expression": (
                    'r.birthdate == null ? "unknown" : '
                    'age_years(r.birthdate) < 18 ? "child" : '
                    'age_years(r.birthdate) < 60 ? "adult" : "elderly"'
                ),
                "default_value": "unknown",
            }
        )

    def test_field_simple_returns_sql(self):
        """Test simple field produces CAST + COALESCE SQL."""
        result = self.dim_is_group.to_sql_column("p", 0)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQLColumnResult)
        self.assertIsInstance(result.expression, SQL)
        self.assertEqual(result.joins, [])
        sql_str = str(result.expression)
        self.assertIn("COALESCE", sql_str)
        self.assertIn("CAST", sql_str)
        self.assertIn("is_group", sql_str)

    def test_field_m2o_code_path_produces_join(self):
        """Test M2O dotted path (gender_id.code) produces LEFT JOIN."""
        result = self.dim_gender_code.to_sql_column("ind", 0)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.joins), 1)
        join_str = str(result.joins[0])
        self.assertIn("LEFT JOIN", join_str)
        sql_str = str(result.expression)
        self.assertIn("code", sql_str)
        # alias_counter should be incremented
        self.assertEqual(result.alias_counter, 1)

    def test_field_m2o_direct_produces_join(self):
        """Test direct M2O field (gender_id) produces LEFT JOIN with code lookup."""
        result = self.dim_gender_direct.to_sql_column("ind", 0)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.joins), 1)
        join_str = str(result.joins[0])
        self.assertIn("LEFT JOIN", join_str)

    def test_expression_produces_case_when(self):
        """Test CEL expression dimension compiles to CASE WHEN SQL."""
        result = self.dim_age_group.to_sql_column("ind", 0)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQLColumnResult)
        sql_str = str(result.expression)
        self.assertIn("CASE WHEN", sql_str)
        self.assertIn("COALESCE", sql_str)

    def test_unsupported_expression_returns_none(self):
        """Test unsupported CEL expression returns None for fallback."""
        dim = self.env["spp.demographic.dimension"].create(
            {
                "name": "test_unsupported",
                "label": "Unsupported",
                "dimension_type": "expression",
                "cel_expression": "r.income + r.bonus",
                "default_value": "n/a",
            }
        )
        result = dim.to_sql_column("ind", 0)
        self.assertIsNone(result)

    def test_invalid_field_path_returns_none(self):
        """Test invalid field path returns None."""
        dim = self.env["spp.demographic.dimension"].create(
            {
                "name": "test_invalid_field",
                "label": "Invalid Field",
                "dimension_type": "field",
                "field_path": "nonexistent_field",
                "default_value": "n/a",
            }
        )
        result = dim.to_sql_column("ind", 0)
        self.assertIsNone(result)

    def test_alias_counter_increments(self):
        """Test multiple dimensions get unique join aliases."""
        r1 = self.dim_gender_code.to_sql_column("ind", 0)
        r2 = self.dim_gender_direct.to_sql_column("ind", r1.alias_counter)
        self.assertNotEqual(r1.alias_counter, r2.alias_counter)
        # Join aliases should differ
        join1_str = str(r1.joins[0])
        join2_str = str(r2.joins[0])
        self.assertIn("_dim0", join1_str)
        self.assertIn("_dim1", join2_str)

    def test_cross_module_cel_call(self):
        """Test to_sql_column works cross-module (spp_metrics_services calling spp_cel_domain)."""
        # This is the key cross-module integration test
        result = self.dim_age_group.to_sql_column("t", 5)
        self.assertIsNotNone(result)
        sql_str = str(result.expression)
        # Should reference the correct alias
        self.assertIn("t", sql_str)
        self.assertIn("birthdate", sql_str)
