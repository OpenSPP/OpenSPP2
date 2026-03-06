# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for aggregation API service."""

import logging

from odoo.tests import tagged

from .common import SimulationApiTestCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestAggregationApiService(SimulationApiTestCommon):
    """Test aggregation API service functionality."""

    def _get_service(self):
        """Import and create the service."""
        from ..services.aggregation_api_service import AggregationApiService

        return AggregationApiService(self.env)

    def test_compute_aggregation_basic(self):
        """Test basic aggregation compute with inline scope."""
        service = self._get_service()
        scope_dict = {
            "target_type": "group",
        }
        result = service.compute_aggregation(scope_dict)

        self.assertIn("total_count", result)
        self.assertIn("computed_at", result)
        self.assertIn("access_level", result)
        self.assertIsInstance(result["total_count"], int)

    def test_compute_aggregation_with_statistics(self):
        """Test aggregation compute with statistics requested."""
        service = self._get_service()
        scope_dict = {
            "target_type": "group",
        }
        result = service.compute_aggregation(
            scope_dict,
            statistics=["total_count"],
        )

        self.assertIn("total_count", result)
        self.assertIn("statistics", result)

    def test_compute_aggregation_with_group_by(self):
        """Test aggregation compute with group_by dimension."""
        service = self._get_service()
        scope_dict = {
            "target_type": "group",
        }

        # Create a dimension for testing if none exist
        if not self.env["spp.demographic.dimension"].search([], limit=1):
            self.env["spp.demographic.dimension"].create(
                {
                    "name": "test_gender",
                    "label": "Test Gender",
                    "dimension_type": "field",
                    "field_path": "gender",
                    "applies_to": "all",
                    "active": True,
                }
            )

        dimensions = self.env["spp.demographic.dimension"].search([("active", "=", True)], limit=1)
        if dimensions:
            result = service.compute_aggregation(
                scope_dict,
                group_by=[dimensions[0].name],
            )
            self.assertIn("total_count", result)

    def test_list_dimensions(self):
        """Test listing active dimensions."""
        service = self._get_service()

        # Ensure at least one dimension exists
        self.env["spp.demographic.dimension"].create(
            {
                "name": "test_dim_for_listing",
                "label": "Test Dimension",
                "dimension_type": "field",
                "field_path": "name",
                "applies_to": "all",
                "active": True,
            }
        )

        result = service.list_dimensions()

        self.assertIsInstance(result, list)
        self.assertGreaterEqual(len(result), 1)

        # Check structure of first dimension
        dimension = result[0]
        self.assertIn("name", dimension)
        self.assertIn("label", dimension)
        self.assertIn("dimension_type", dimension)
        self.assertIn("applies_to", dimension)

    def test_list_dimensions_filtered_by_applies_to(self):
        """Test that list_dimensions can filter by applies_to."""
        service = self._get_service()

        # Create individual-only dimension
        self.env["spp.demographic.dimension"].create(
            {
                "name": "test_individual_dim",
                "label": "Individual Only",
                "dimension_type": "field",
                "field_path": "name",
                "applies_to": "individuals",
                "active": True,
            }
        )

        result_all = service.list_dimensions()
        result_individuals = service.list_dimensions(applies_to="individuals")

        # Individual filter should include individual + all dims
        self.assertIsInstance(result_individuals, list)
        # All dims should be >= individual dims
        self.assertGreaterEqual(len(result_all), len(result_individuals))
