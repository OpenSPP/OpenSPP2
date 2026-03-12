# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMetricsServices(TransactionCase):
    """Test that all metrics services are accessible and functional."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test registrants
        cls.partner_model = cls.env["res.partner"]
        cls.registrant1 = cls.partner_model.create(
            {
                "name": "Test Registrant 1",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.registrant2 = cls.partner_model.create(
            {
                "name": "Test Registrant 2",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.registrant3 = cls.partner_model.create(
            {
                "name": "Test Registrant 3",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cls.registrant_ids = [cls.registrant1.id, cls.registrant2.id, cls.registrant3.id]

    def test_fairness_service_exists(self):
        """Test that fairness service is accessible."""
        fairness_service = self.env.get("spp.metric.fairness")
        self.assertIsNotNone(fairness_service, "Fairness service should be accessible")

    def test_distribution_service_exists(self):
        """Test that distribution service is accessible."""
        distribution_service = self.env.get("spp.metric.distribution")
        self.assertIsNotNone(distribution_service, "Distribution service should be accessible")

    def test_privacy_service_exists(self):
        """Test that privacy service is accessible."""
        privacy_service = self.env.get("spp.metric.privacy")
        self.assertIsNotNone(privacy_service, "Privacy service should be accessible")

    def test_breakdown_service_exists(self):
        """Test that breakdown service is accessible."""
        breakdown_service = self.env.get("spp.metric.breakdown")
        self.assertIsNotNone(breakdown_service, "Breakdown service should be accessible")

    def test_fairness_service_compute(self):
        """Test fairness computation works."""
        fairness_service = self.env["spp.metric.fairness"]
        result = fairness_service.compute_fairness(
            self.registrant_ids,
            base_domain=[("is_registrant", "=", True)],
        )

        self.assertIn("equity_score", result)
        self.assertIn("has_disparity", result)
        self.assertIn("total_beneficiaries", result)
        self.assertEqual(result["total_beneficiaries"], 3)

    def test_distribution_service_compute(self):
        """Test distribution computation works."""
        distribution_service = self.env["spp.metric.distribution"]
        amounts = [100, 200, 300, 400, 500]
        result = distribution_service.compute_distribution(amounts)

        self.assertIn("count", result)
        self.assertIn("mean", result)
        self.assertIn("median", result)
        self.assertIn("gini_coefficient", result)
        self.assertEqual(result["count"], 5)
        self.assertEqual(result["mean"], 300)

    def test_privacy_service_enforce(self):
        """Test privacy enforcement works."""
        privacy_service = self.env["spp.metric.privacy"]
        test_result = {
            "total_count": 10,
            "breakdown": {
                "male": {"count": 2},
                "female": {"count": 8},
            },
        }

        protected_result = privacy_service.enforce(test_result, k_threshold=5)

        self.assertIn("breakdown", protected_result)
        # Cell with count=2 should be suppressed
        self.assertTrue(protected_result["breakdown"]["male"].get("suppressed", False))

    def test_breakdown_service_compute(self):
        """Test breakdown computation works."""
        breakdown_service = self.env["spp.metric.breakdown"]

        # Create a simple dimension (if spp.demographic.dimension exists)
        dimension_model = self.env.get("spp.demographic.dimension")
        if dimension_model:
            # For now, test with empty group_by
            result = breakdown_service.compute_breakdown(self.registrant_ids, [])
            self.assertEqual(result, {}, "Empty group_by should return empty breakdown")

    def test_empty_inputs(self):
        """Test services handle empty inputs gracefully."""
        fairness_service = self.env["spp.metric.fairness"]
        distribution_service = self.env["spp.metric.distribution"]
        breakdown_service = self.env["spp.metric.breakdown"]

        # Test fairness with empty registrants
        fairness_result = fairness_service.compute_fairness([])
        self.assertEqual(fairness_result["total_beneficiaries"], 0)
        self.assertEqual(fairness_result["equity_score"], 100.0)

        # Test distribution with empty amounts
        dist_result = distribution_service.compute_distribution([])
        self.assertEqual(dist_result["count"], 0)

        # Test breakdown with empty registrants
        breakdown_result = breakdown_service.compute_breakdown([], ["gender"])
        self.assertEqual(breakdown_result, {})


@tagged("post_install", "-at_install")
class TestPrivacySuppressionUnified(TransactionCase):
    """Test unified suppression logic in privacy service."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.privacy_service = cls.env["spp.metric.privacy"]

    def test_suppress_value_no_suppression_default_threshold(self):
        """Test suppress_value with count above default threshold (5)."""
        value = 100
        count = 10
        result_value, is_suppressed = self.privacy_service.suppress_value(value, count)

        self.assertEqual(result_value, 100)
        self.assertFalse(is_suppressed)

    def test_suppress_value_with_suppression_default_threshold(self):
        """Test suppress_value with count below default threshold (5)."""
        value = 50
        count = 3
        result_value, is_suppressed = self.privacy_service.suppress_value(value, count)

        self.assertEqual(result_value, "<5")
        self.assertTrue(is_suppressed)

    def test_suppress_value_with_user_threshold(self):
        """Test suppress_value with user-level k-anonymity threshold."""
        value = 100
        count = 8
        result_value, is_suppressed = self.privacy_service.suppress_value(value, count, k_threshold=10)

        self.assertEqual(result_value, "<10")
        self.assertTrue(is_suppressed)

    def test_suppress_value_with_stat_config_raising_threshold(self):
        """Test suppress_value with stat config raising threshold above user threshold."""
        value = 100
        count = 7
        stat_config = {"minimum_count": 10, "suppression_display": "asterisk"}

        result_value, is_suppressed = self.privacy_service.suppress_value(
            value, count, k_threshold=5, stat_config=stat_config
        )

        # Effective threshold = max(5, 10) = 10, so count=7 is suppressed
        self.assertEqual(result_value, "*")
        self.assertTrue(is_suppressed)

    def test_suppress_value_precedence_max(self):
        """Test precedence: effective_threshold = max(user, stat)."""
        value = 100

        # Case 1: stat threshold higher (10) than user (5)
        count_7 = 7
        stat_config = {"minimum_count": 10, "suppression_display": "less_than"}
        result_value, is_suppressed = self.privacy_service.suppress_value(
            value, count_7, k_threshold=5, stat_config=stat_config
        )
        self.assertEqual(result_value, "<10")
        self.assertTrue(is_suppressed)

        # Case 2: user threshold higher (15) than stat (10)
        count_12 = 12
        result_value2, is_suppressed2 = self.privacy_service.suppress_value(
            value, count_12, k_threshold=15, stat_config=stat_config
        )
        self.assertEqual(result_value2, "<15")
        self.assertTrue(is_suppressed2)

    def test_suppress_value_display_mode_null(self):
        """Test suppress_value with null display mode."""
        value = 50
        count = 3
        stat_config = {"minimum_count": 5, "suppression_display": "null"}

        result_value, is_suppressed = self.privacy_service.suppress_value(value, count, stat_config=stat_config)

        self.assertIsNone(result_value)
        self.assertTrue(is_suppressed)

    def test_suppress_value_display_mode_asterisk(self):
        """Test suppress_value with asterisk display mode."""
        value = 50
        count = 3
        stat_config = {"minimum_count": 5, "suppression_display": "asterisk"}

        result_value, is_suppressed = self.privacy_service.suppress_value(value, count, stat_config=stat_config)

        self.assertEqual(result_value, "*")
        self.assertTrue(is_suppressed)

    def test_suppress_value_display_mode_less_than(self):
        """Test suppress_value with less_than display mode."""
        value = 50
        count = 3
        stat_config = {"minimum_count": 8, "suppression_display": "less_than"}

        result_value, is_suppressed = self.privacy_service.suppress_value(value, count, stat_config=stat_config)

        self.assertEqual(result_value, "<8")
        self.assertTrue(is_suppressed)

    def test_suppress_value_none_value_passes_through(self):
        """Test suppress_value with None value passes through unsuppressed."""
        value = None
        count = 3

        result_value, is_suppressed = self.privacy_service.suppress_value(value, count)

        self.assertIsNone(result_value)
        self.assertFalse(is_suppressed)
