# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .common import SimulationTestCommon


@tagged("-at_install", "post_install")
class TestDistributionService(SimulationTestCommon):
    """Tests for distribution statistics computation.

    NOTE: These tests now use spp.metrics.distribution directly.
    The old spp.simulation.distribution.service has been removed (Phase 6 cleanup).
    """

    def _get_service(self):
        return self.env["spp.metrics.distribution"]

    def test_empty_distribution(self):
        """Test distribution with empty amounts list."""
        service = self._get_service()
        result = service.compute_distribution([])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["gini_coefficient"], 0)

    def test_uniform_distribution(self):
        """Test distribution where all amounts are equal."""
        service = self._get_service()
        amounts = [100.0] * 10
        result = service.compute_distribution(amounts)
        self.assertEqual(result["count"], 10)
        self.assertEqual(result["total"], 1000.0)
        self.assertEqual(result["minimum"], 100.0)
        self.assertEqual(result["maximum"], 100.0)
        self.assertEqual(result["mean"], 100.0)
        self.assertEqual(result["median"], 100.0)
        self.assertEqual(result["standard_deviation"], 0.0)
        # Gini should be 0 for perfectly equal distribution
        self.assertAlmostEqual(result["gini_coefficient"], 0.0, places=2)

    def test_known_gini(self):
        """Test Gini coefficient against a known value.

        For amounts [1, 2, 3, 4, 5], Gini = 0.2667
        Formula: G = (2*sum(i*y_i) - (n+1)*sum(y_i)) / (n*sum(y_i))
        = (2*(1+4+9+16+25) - 6*15) / (5*15)
        = (2*55 - 90) / 75
        = 20 / 75
        = 0.2667
        """
        service = self._get_service()
        amounts = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = service.compute_distribution(amounts)
        self.assertAlmostEqual(result["gini_coefficient"], 0.2667, places=3)

    def test_extreme_inequality(self):
        """Test distribution with extreme inequality."""
        service = self._get_service()
        amounts = [0.0, 0.0, 0.0, 0.0, 1000.0]
        result = service.compute_distribution(amounts)
        # Gini should be close to 1 for extreme inequality
        self.assertGreater(result["gini_coefficient"], 0.7)

    def test_percentiles(self):
        """Test percentile computation."""
        service = self._get_service()
        amounts = list(range(1, 101))  # 1 to 100
        result = service.compute_distribution(amounts)
        percentiles = result["percentiles"]
        # p50 should be approximately 50
        self.assertAlmostEqual(percentiles["p50"], 50.5, places=0)
        # p10 should be approximately 10
        self.assertAlmostEqual(percentiles["p10"], 10.9, places=0)
        # p90 should be approximately 90
        self.assertAlmostEqual(percentiles["p90"], 90.1, places=0)

    def test_lorenz_deciles(self):
        """Test Lorenz curve decile computation."""
        service = self._get_service()
        # Equal distribution: Lorenz should be on the diagonal
        amounts = [100.0] * 10
        result = service.compute_distribution(amounts)
        lorenz = result["lorenz_deciles"]
        self.assertEqual(len(lorenz), 10)
        # For equal distribution, each decile's income_share should equal population_share
        for decile in lorenz:
            self.assertAlmostEqual(
                decile["income_share"],
                decile["population_share"],
                places=0,
            )

    def test_single_amount(self):
        """Test distribution with a single amount."""
        service = self._get_service()
        result = service.compute_distribution([500.0])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["total"], 500.0)
        self.assertEqual(result["minimum"], 500.0)
        self.assertEqual(result["maximum"], 500.0)
        self.assertEqual(result["mean"], 500.0)
        self.assertEqual(result["median"], 500.0)

    def test_standard_deviation(self):
        """Test standard deviation computation."""
        service = self._get_service()
        amounts = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        result = service.compute_distribution(amounts)
        # Known stddev for this data = 2.0
        self.assertAlmostEqual(result["standard_deviation"], 2.0, places=1)
