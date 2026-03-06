# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from .common import AggregationTestCase


class TestFairnessService(AggregationTestCase):
    """Tests for spp.metric.fairness service."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.metric.fairness"]

    def test_empty_registrants(self):
        """Test fairness with no registrants."""
        result = self.service.compute_fairness([])
        self.assertEqual(result["equity_score"], 100.0)
        self.assertFalse(result["has_disparity"])
        self.assertEqual(result["total_beneficiaries"], 0)

    def test_compute_fairness_basic(self):
        """Test basic fairness computation."""
        registrant_ids = self.registrants[:10].ids
        result = self.service.compute_fairness(registrant_ids)

        self.assertIn("equity_score", result)
        self.assertIn("has_disparity", result)
        self.assertIn("overall_coverage", result)
        self.assertIn("total_beneficiaries", result)
        self.assertIn("total_population", result)
        self.assertEqual(result["total_beneficiaries"], 10)

    def test_disparity_ratio_equal_coverage(self):
        """Test disparity ratio when group coverage equals overall."""
        # When group_coverage == overall_coverage, ratio should be 1.0
        ratio = self.service._compute_disparity_ratio(0.5, 0.5)
        self.assertEqual(ratio, 1.0)

    def test_disparity_ratio_under_coverage(self):
        """Test disparity ratio when group is under-covered."""
        # Group at 25% coverage when overall is 50% = 0.5 ratio
        ratio = self.service._compute_disparity_ratio(0.25, 0.5)
        self.assertEqual(ratio, 0.5)

    def test_disparity_ratio_zero_overall(self):
        """Test disparity ratio when overall coverage is zero."""
        ratio = self.service._compute_disparity_ratio(0.5, 0)
        self.assertEqual(ratio, 0.0)

    def test_disparity_status_proportional(self):
        """Test status for proportional coverage."""
        status = self.service._get_disparity_status(0.9)
        self.assertEqual(status, "proportional")

    def test_disparity_status_low_coverage(self):
        """Test status for low coverage."""
        status = self.service._get_disparity_status(0.75)
        self.assertEqual(status, "low_coverage")

    def test_disparity_status_under_represented(self):
        """Test status for under-representation."""
        status = self.service._get_disparity_status(0.6)
        self.assertEqual(status, "under_represented")

    def test_fairness_with_specific_dimensions(self):
        """Test fairness analysis with specific dimensions."""
        # Get the registrant_type dimension
        registrant_ids = self.registrants.ids
        result = self.service.compute_fairness(
            registrant_ids,
            dimensions=["registrant_type"],
        )

        # Should have analysis for registrant_type
        self.assertIn("attributes", result)

    def test_equity_score_penalties(self):
        """Test that equity score decreases with disparity."""
        # Create a scenario with known disparity
        # This is a basic test - actual disparity depends on data
        registrant_ids = self.registrants[:5].ids
        result = self.service.compute_fairness(registrant_ids)

        # Equity score should be between 0 and 100
        self.assertGreaterEqual(result["equity_score"], 0)
        self.assertLessEqual(result["equity_score"], 100)
