# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for aggregation API schemas and endpoint logic."""

from odoo.tests import tagged

from .common import SimulationApiTestCase


@tagged("-at_install", "post_install")
class TestAggregationApi(SimulationApiTestCase):
    """Test aggregation endpoint schemas and logic."""

    def test_aggregation_scope_request_defaults(self):
        """Test AggregationScopeRequest schema defaults."""
        from ..schemas.aggregation import AggregationScopeRequest

        scope = AggregationScopeRequest()
        self.assertEqual(scope.target_type, "group")
        self.assertIsNone(scope.cel_expression)
        self.assertIsNone(scope.area_id)

    def test_aggregation_scope_request_with_values(self):
        """Test AggregationScopeRequest with explicit values."""
        from ..schemas.aggregation import AggregationScopeRequest

        scope = AggregationScopeRequest(
            target_type="individual",
            cel_expression="r.age >= 18",
            area_id=42,
        )
        self.assertEqual(scope.target_type, "individual")
        self.assertEqual(scope.cel_expression, "r.age >= 18")
        self.assertEqual(scope.area_id, 42)

    def test_compute_aggregation_request_minimal(self):
        """Test ComputeAggregationRequest with minimal fields."""
        from ..schemas.aggregation import (
            AggregationScopeRequest,
            ComputeAggregationRequest,
        )

        request = ComputeAggregationRequest(
            scope=AggregationScopeRequest(),
        )
        self.assertEqual(request.scope.target_type, "group")
        self.assertIsNone(request.statistics)
        self.assertIsNone(request.group_by)

    def test_compute_aggregation_request_full(self):
        """Test ComputeAggregationRequest with all fields."""
        from ..schemas.aggregation import (
            AggregationScopeRequest,
            ComputeAggregationRequest,
        )

        request = ComputeAggregationRequest(
            scope=AggregationScopeRequest(
                target_type="individual",
                cel_expression="r.age >= 60",
            ),
            statistics=["count", "average_age"],
            group_by=["gender", "area"],
        )
        self.assertEqual(request.scope.target_type, "individual")
        self.assertEqual(len(request.statistics), 2)
        self.assertEqual(len(request.group_by), 2)

    def test_aggregation_response_schema(self):
        """Test AggregationResponse schema."""
        from ..schemas.aggregation import AggregationResponse

        response = AggregationResponse(
            total_count=150,
            statistics={"average_age": 45.2, "count": 150},
            breakdown={"gender": {"male": 70, "female": 80}},
            from_cache=False,
            computed_at="2024-01-01T12:00:00Z",
            access_level="aggregate",
        )
        self.assertEqual(response.total_count, 150)
        self.assertEqual(response.statistics["average_age"], 45.2)
        self.assertIn("gender", response.breakdown)
        self.assertFalse(response.from_cache)

    def test_aggregation_response_no_breakdown(self):
        """Test AggregationResponse without breakdown."""
        from ..schemas.aggregation import AggregationResponse

        response = AggregationResponse(
            total_count=100,
            statistics={},
            from_cache=True,
            computed_at="2024-01-01T12:00:00Z",
            access_level="aggregate",
        )
        self.assertIsNone(response.breakdown)
        self.assertTrue(response.from_cache)

    def test_dimension_info_schema(self):
        """Test DimensionInfo schema."""
        from ..schemas.aggregation import DimensionInfo

        dim = DimensionInfo(
            name="gender",
            label="Gender",
            description="Biological sex",
            dimension_type="field",
            applies_to="all",
            value_labels={"male": "Male", "female": "Female"},
        )
        self.assertEqual(dim.name, "gender")
        self.assertEqual(dim.label, "Gender")
        self.assertEqual(dim.dimension_type, "field")
        self.assertEqual(dim.applies_to, "all")
        self.assertIn("male", dim.value_labels)

    def test_dimension_info_minimal(self):
        """Test DimensionInfo with no optional fields."""
        from ..schemas.aggregation import DimensionInfo

        dim = DimensionInfo(
            name="custom_dim",
            label="Custom",
            dimension_type="expression",
            applies_to="individuals",
        )
        self.assertIsNone(dim.description)
        self.assertIsNone(dim.value_labels)

    def test_dimensions_list_response_schema(self):
        """Test DimensionsListResponse schema."""
        from ..schemas.aggregation import DimensionInfo, DimensionsListResponse

        dims = [
            DimensionInfo(
                name="gender",
                label="Gender",
                dimension_type="field",
                applies_to="all",
            ),
            DimensionInfo(
                name="age_group",
                label="Age Group",
                dimension_type="expression",
                applies_to="individuals",
            ),
        ]
        response = DimensionsListResponse(dimensions=dims)
        self.assertEqual(len(response.dimensions), 2)
        self.assertEqual(response.dimensions[0].name, "gender")
        self.assertEqual(response.dimensions[1].name, "age_group")

    def test_scope_model_dump(self):
        """Test that scope model_dump produces the expected dict."""
        from ..schemas.aggregation import AggregationScopeRequest

        scope = AggregationScopeRequest(
            target_type="group",
            cel_expression="r.area_id != false",
            area_id=5,
        )
        dumped = scope.model_dump()
        self.assertEqual(dumped["target_type"], "group")
        self.assertEqual(dumped["cel_expression"], "r.area_id != false")
        self.assertEqual(dumped["area_id"], 5)
