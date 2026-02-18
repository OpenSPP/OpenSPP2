# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.tests.common import TransactionCase


class TestPrivacyEnforcement(TransactionCase):
    """Tests for spp.metrics.privacy service."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.metrics.privacy"]

    def test_enforce_empty_result(self):
        """Test enforcement on empty result."""
        result = {"total_count": 0, "statistics": {}}
        enforced = self.service.enforce(result)
        self.assertEqual(enforced["total_count"], 0)

    def test_enforce_strips_ids_for_aggregate(self):
        """Test that IDs are stripped for aggregate access."""
        result = {
            "total_count": 100,
            "registrant_ids": [1, 2, 3, 4, 5],
            "partner_ids": [1, 2, 3, 4, 5],
        }
        enforced = self.service.enforce(result, access_level="aggregate")

        self.assertNotIn("registrant_ids", enforced)
        self.assertNotIn("partner_ids", enforced)

    def test_enforce_keeps_ids_for_individual(self):
        """Test that IDs are kept for individual access."""
        result = {
            "total_count": 100,
            "registrant_ids": [1, 2, 3, 4, 5],
        }
        enforced = self.service.enforce(result, access_level="individual")

        self.assertIn("registrant_ids", enforced)

    def test_k_anonymity_suppresses_small_cells(self):
        """Test that cells below k-threshold are suppressed."""
        result = {
            "total_count": 100,
            "breakdown": {
                "male|urban": {"count": 50, "statistics": {}},
                "male|rural": {"count": 3, "statistics": {}},  # Below k=5
                "female|urban": {"count": 47, "statistics": {}},
            },
        }
        enforced = self.service.enforce(result, k_threshold=5)

        # male|rural should be suppressed
        self.assertTrue(enforced["breakdown"]["male|rural"]["suppressed"])
        self.assertEqual(enforced["breakdown"]["male|rural"]["count"], "<5")

    def test_complementary_suppression(self):
        """Test that sibling cells are suppressed to prevent derivation."""
        result = {
            "total_count": 100,
            "breakdown": {
                "male": {"count": 97, "statistics": {}},
                "female": {"count": 3, "statistics": {}},  # Below k=5
            },
        }
        enforced = self.service.enforce(result, k_threshold=5)

        # Both should be suppressed to prevent derivation
        self.assertTrue(enforced["breakdown"]["female"]["suppressed"])
        self.assertTrue(enforced["breakdown"]["male"]["suppressed"])

    def test_no_suppression_above_threshold(self):
        """Test that cells above threshold are not suppressed."""
        result = {
            "total_count": 100,
            "breakdown": {
                "male": {"count": 60, "statistics": {}},
                "female": {"count": 40, "statistics": {}},
            },
        }
        enforced = self.service.enforce(result, k_threshold=5)

        self.assertFalse(enforced["breakdown"]["male"].get("suppressed", False))
        self.assertFalse(enforced["breakdown"]["female"].get("suppressed", False))

    def test_is_count_suppressed(self):
        """Test count suppression check."""
        self.assertTrue(self.service.is_count_suppressed(3, k_threshold=5))
        self.assertTrue(self.service.is_count_suppressed(4, k_threshold=5))
        self.assertFalse(self.service.is_count_suppressed(5, k_threshold=5))
        self.assertFalse(self.service.is_count_suppressed(10, k_threshold=5))

    def test_format_suppressed_count_less_than(self):
        """Test formatting suppressed count with less_than mode."""
        result = self.service.format_suppressed_count(3, k_threshold=5, display_mode="less_than")
        self.assertEqual(result, "<5")

    def test_format_suppressed_count_asterisk(self):
        """Test formatting suppressed count with asterisk mode."""
        result = self.service.format_suppressed_count(3, k_threshold=5, display_mode="asterisk")
        self.assertEqual(result, "*")

    def test_format_suppressed_count_null(self):
        """Test formatting suppressed count with null mode."""
        result = self.service.format_suppressed_count(3, k_threshold=5, display_mode="null")
        self.assertIsNone(result)

    def test_format_non_suppressed_count(self):
        """Test formatting non-suppressed count."""
        result = self.service.format_suppressed_count(10, k_threshold=5)
        self.assertEqual(result, "10")

    def test_find_siblings(self):
        """Test finding sibling cells."""
        breakdown = {
            "male|urban": {},
            "male|rural": {},
            "female|urban": {},
            "female|rural": {},
        }
        siblings = self.service._find_siblings("male|urban", breakdown)

        # Siblings differ by exactly one dimension
        self.assertIn("female|urban", siblings)  # Same location, different gender
        self.assertIn("male|rural", siblings)  # Same gender, different location
        self.assertNotIn("female|rural", siblings)  # Different by 2

    def test_get_smallest_sibling(self):
        """Test getting smallest sibling cell."""
        breakdown = {
            "male": {"count": 100},
            "female": {"count": 50},
            "other": {"count": 10},
        }
        smallest = self.service._get_smallest_sibling(["male", "female", "other"], breakdown)
        self.assertEqual(smallest, "other")

    def test_default_k_threshold(self):
        """Test default k-anonymity threshold."""
        result = {"total_count": 10, "breakdown": {"a": {"count": 4}}}
        enforced = self.service.enforce(result)  # No k_threshold specified

        # Should use default (5), so count of 4 should be suppressed
        self.assertTrue(enforced["breakdown"]["a"]["suppressed"])


class TestPrivacyKAnonymityAttacks(TransactionCase):
    """Tests for k-anonymity differencing attack prevention."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.metrics.privacy"]

    def test_differencing_attack_prevention_single_sibling(self):
        """
        Test prevention of differencing attack when only one sibling exists.

        Scenario:
        - Area A total = 1000 (known from parent)
        - Area A, Male = 995
        - Area A, Female = 5 (below k)

        Without complementary suppression:
        - Female is suppressed, shows "<5"
        - Attacker derives: Female = 1000 - 995 = 5 (exact count!)

        With complementary suppression:
        - Both Male and Female are suppressed
        - No derivation possible
        """
        result = {
            "total_count": 1000,
            "breakdown": {
                "male": {"count": 995, "statistics": {}},
                "female": {"count": 5, "statistics": {}},
            },
        }

        # Use k=6 so female (5) is below threshold
        enforced = self.service.enforce(result, k_threshold=6)

        # Both must be suppressed
        self.assertTrue(enforced["breakdown"]["female"]["suppressed"])
        self.assertTrue(enforced["breakdown"]["male"]["suppressed"])

    def test_differencing_attack_multiple_siblings(self):
        """
        Test that smallest sibling is suppressed with multiple siblings.

        Scenario:
        - Gender: male=500, female=497, other=3
        - other is below k, must suppress
        - Need to suppress at least one sibling to prevent derivation from total
        """
        result = {
            "total_count": 1000,
            "breakdown": {
                "male": {"count": 500, "statistics": {}},
                "female": {"count": 497, "statistics": {}},
                "other": {"count": 3, "statistics": {}},
            },
        }

        enforced = self.service.enforce(result, k_threshold=5)

        # other must be suppressed
        self.assertTrue(enforced["breakdown"]["other"]["suppressed"])

        # At least one sibling should also be suppressed
        siblings_suppressed = sum(1 for k in ["male", "female"] if enforced["breakdown"][k].get("suppressed", False))
        self.assertGreaterEqual(siblings_suppressed, 1)

    def test_multi_dimensional_differencing(self):
        """
        Test differencing attack with multiple dimensions.

        Scenario:
        - gender|location breakdown
        - If male|urban=3 is suppressed but we know:
          - total male = 100
          - male|rural = 97
        - Attacker derives: male|urban = 100 - 97 = 3
        """
        result = {
            "total_count": 200,
            "breakdown": {
                "male|urban": {"count": 3, "statistics": {}},
                "male|rural": {"count": 97, "statistics": {}},
                "female|urban": {"count": 50, "statistics": {}},
                "female|rural": {"count": 50, "statistics": {}},
            },
        }

        enforced = self.service.enforce(result, k_threshold=5)

        # male|urban should be suppressed
        self.assertTrue(enforced["breakdown"]["male|urban"]["suppressed"])

        # male|rural should also be suppressed (only sibling in male category)
        self.assertTrue(enforced["breakdown"]["male|rural"]["suppressed"])
