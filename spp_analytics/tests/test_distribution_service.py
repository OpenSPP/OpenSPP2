# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.tests.common import TransactionCase


class TestDistributionService(TransactionCase):
    """Tests for spp.metric.distribution service."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.metric.distribution"]

    def test_empty_amounts(self):
        """Test distribution with empty list."""
        result = self.service.compute_distribution([])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["gini_coefficient"], 0)
        self.assertEqual(result["lorenz_deciles"], [])

    def test_single_amount(self):
        """Test distribution with single value."""
        result = self.service.compute_distribution([100])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["total"], 100)
        self.assertEqual(result["mean"], 100)
        self.assertEqual(result["median"], 100)

    def test_uniform_distribution(self):
        """Test uniform distribution has Gini close to 0."""
        # All equal values = perfect equality
        amounts = [100] * 100
        result = self.service.compute_distribution(amounts)
        self.assertEqual(result["count"], 100)
        self.assertEqual(result["total"], 10000)
        self.assertEqual(result["mean"], 100)
        self.assertEqual(result["gini_coefficient"], 0.0)

    def test_skewed_distribution(self):
        """Test skewed distribution has higher Gini."""
        # One person has everything = high inequality
        amounts = [0] * 99 + [10000]
        result = self.service.compute_distribution(amounts)
        self.assertEqual(result["count"], 100)
        self.assertGreater(result["gini_coefficient"], 0.9)

    def test_percentiles(self):
        """Test percentile calculation."""
        amounts = list(range(1, 101))  # 1 to 100
        result = self.service.compute_distribution(amounts)

        self.assertAlmostEqual(result["percentiles"]["p50"], 50.5, places=1)
        self.assertAlmostEqual(result["percentiles"]["p25"], 25.75, places=1)
        self.assertAlmostEqual(result["percentiles"]["p75"], 75.25, places=1)

    def test_median_odd_count(self):
        """Test median with odd number of values."""
        amounts = [1, 2, 3, 4, 5]
        result = self.service.compute_distribution(amounts)
        self.assertEqual(result["median"], 3)

    def test_median_even_count(self):
        """Test median with even number of values."""
        amounts = [1, 2, 3, 4]
        result = self.service.compute_distribution(amounts)
        self.assertEqual(result["median"], 2.5)

    def test_standard_deviation(self):
        """Test standard deviation calculation."""
        amounts = [2, 4, 4, 4, 5, 5, 7, 9]
        result = self.service.compute_distribution(amounts)
        # Mean = 5, variance = 4, std = 2
        self.assertAlmostEqual(result["standard_deviation"], 2, places=5)

    def test_lorenz_deciles(self):
        """Test Lorenz curve decile points."""
        amounts = list(range(1, 11))  # 1 to 10
        result = self.service.compute_distribution(amounts)

        lorenz = result["lorenz_deciles"]
        self.assertEqual(len(lorenz), 10)

        # 10% of population (1 person) has 1/55 of total
        self.assertEqual(lorenz[0]["population_share"], 10)

        # 100% of population has 100% of income
        self.assertEqual(lorenz[9]["population_share"], 100)
        self.assertEqual(lorenz[9]["income_share"], 100)

    def test_gini_clamped(self):
        """Test Gini coefficient is clamped between 0 and 1."""
        # Normal case
        amounts = [10, 20, 30, 40]
        result = self.service.compute_distribution(amounts)
        self.assertGreaterEqual(result["gini_coefficient"], 0)
        self.assertLessEqual(result["gini_coefficient"], 1)

    def test_zero_total(self):
        """Test distribution with all zero values."""
        amounts = [0, 0, 0, 0]
        result = self.service.compute_distribution(amounts)
        self.assertEqual(result["gini_coefficient"], 0)
        self.assertEqual(result["lorenz_deciles"], [])

    def test_negative_values(self):
        """Test distribution handles negative values."""
        amounts = [-10, 0, 10, 20]
        result = self.service.compute_distribution(amounts)
        self.assertEqual(result["count"], 4)
        self.assertEqual(result["minimum"], -10)
        self.assertEqual(result["maximum"], 20)
