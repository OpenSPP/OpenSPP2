# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Farm Details model - V2 with vocabulary integration.

Tests cover:
- Vocabulary-based field creation and domains
- Computed fields (farm_size_hectares, is_smallholder, has_productive_land)
- Configurable smallholder threshold
- Helper methods for vocabulary code access
"""

import time

from odoo.tests import TransactionCase, tagged

from .common import FarmerTestDataMixin


def _unique(base):
    """Generate unique name for test isolation."""
    return f"{base}_{int(time.time() * 1000)}"


@tagged("post_install", "-at_install")
class TestFarmDetails(TransactionCase, FarmerTestDataMixin):
    """Test spp.farm.details model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)

        # Create test vocabularies
        cls.farm_types = cls._create_farm_type_vocabulary()
        cls.land_tenures = cls._create_land_tenure_vocabulary()

        # Create test farm
        cls.farm = cls._create_test_farm(name=f"Details Test Farm {cls._test_id}")

    def test_create_farm_details_with_vocabulary(self):
        """Test creating farm details with vocabulary-based fields."""
        FarmDetails = self.env["spp.farm.details"]

        details = FarmDetails.create(
            {
                "farm_type_id": self.farm_types["crop"].id,
                "land_tenure_id": self.land_tenures["self"].id,
                "farm_total_size": 2.5,
            }
        )

        self.assertEqual(details.farm_type_id.code, "crop")
        self.assertEqual(details.land_tenure_id.code, "self")
        self.assertEqual(details.farm_total_size, 2.5)

    def test_farm_size_hectares_computed(self):
        """Test farm_size_hectares is computed from farm_total_size on partner."""
        farm = self._create_test_farm(name=_unique("Hectares Farm"), farm_total_size=3.5)
        self.assertEqual(farm.farm_size_hectares, 3.5)

        farm.farm_total_size = 5.0
        self.assertEqual(farm.farm_size_hectares, 5.0)

    def test_is_smallholder_default_threshold(self):
        """Test is_smallholder with default 5ha threshold."""
        small = self._create_test_farm(name=_unique("Small Farm"), farm_total_size=2.0)
        self.assertTrue(small.is_smallholder)

        at_threshold = self._create_test_farm(name=_unique("Threshold Farm"), farm_total_size=5.0)
        self.assertTrue(at_threshold.is_smallholder)

        large = self._create_test_farm(name=_unique("Large Farm"), farm_total_size=10.0)
        self.assertFalse(large.is_smallholder)

    def test_is_smallholder_configurable_threshold(self):
        """Test is_smallholder with configurable threshold."""
        self.env["ir.config_parameter"].sudo().set_param("spp.farmer.smallholder_threshold", "3.0")

        above = self._create_test_farm(name=_unique("Above Farm"), farm_total_size=3.5)
        self.assertFalse(above.is_smallholder)

        below = self._create_test_farm(name=_unique("Below Farm"), farm_total_size=2.5)
        self.assertTrue(below.is_smallholder)

        self.env["ir.config_parameter"].sudo().set_param("spp.farmer.smallholder_threshold", "5.0")

    def test_has_productive_land_crops(self):
        """Test has_productive_land when farm has crops."""
        farm = self._create_test_farm(name=_unique("Crop Farm"), farm_total_size=5.0, farm_size_under_crops=3.0)
        self.assertTrue(farm.has_productive_land)

    def test_has_productive_land_livestock(self):
        """Test has_productive_land when farm has livestock."""
        farm = self._create_test_farm(
            name=_unique("Livestock Farm"), farm_total_size=5.0, farm_size_under_livestock=2.0
        )
        self.assertTrue(farm.has_productive_land)

    def test_has_productive_land_aquaculture(self):
        """Test has_productive_land when farm has aquaculture."""
        farm = self._create_test_farm(name=_unique("Aqua Farm"), farm_total_size=1.0, farm_size_under_aquaculture=0.5)
        self.assertTrue(farm.has_productive_land)

    def test_has_productive_land_idle_only(self):
        """Test has_productive_land is false when all land is idle."""
        farm = self._create_test_farm(name=_unique("Idle Farm"), farm_total_size=5.0, farm_size_idle=5.0)
        self.assertFalse(farm.has_productive_land)

    def test_get_farm_type_code(self):
        """Test get_farm_type_code helper method."""
        FarmDetails = self.env["spp.farm.details"]

        details = FarmDetails.create(
            {
                "farm_type_id": self.farm_types["mixed"].id,
            }
        )
        self.assertEqual(details.get_farm_type_code(), "mixed")

    def test_get_farm_type_code_none(self):
        """Test get_farm_type_code returns None when not set."""
        FarmDetails = self.env["spp.farm.details"]

        details = FarmDetails.create({})
        self.assertIsNone(details.get_farm_type_code())

    def test_get_land_tenure_code(self):
        """Test get_land_tenure_code helper method."""
        FarmDetails = self.env["spp.farm.details"]

        details = FarmDetails.create(
            {
                "land_tenure_id": self.land_tenures["leased"].id,
            }
        )
        self.assertEqual(details.get_land_tenure_code(), "leased")

    def test_is_farm_type(self):
        """Test is_farm_type helper method."""
        FarmDetails = self.env["spp.farm.details"]

        details = FarmDetails.create(
            {
                "farm_type_id": self.farm_types["livestock"].id,
            }
        )

        self.assertTrue(details.is_farm_type("livestock"))
        self.assertFalse(details.is_farm_type("crop"))
        self.assertFalse(details.is_farm_type("mixed"))

    def test_farm_details_on_partner(self):
        """Test farm detail fields via _inherits delegation on partner.

        Farm detail fields are stored in spp.farm.details but accessible
        directly on res.partner via _inherits delegation.
        """
        # Create farm with detail fields via _inherits
        farm = self._create_test_farm(
            name=_unique("Farm"),
            farm_type_id=self.farm_types["crop"].id,
            farm_total_size=2.0,
        )

        # Access fields directly on partner
        self.assertEqual(farm.farm_total_size, 2.0)
        self.assertEqual(farm.farm_type_id.code, "crop")
        # Computed field should also work
        self.assertEqual(farm.farm_size_hectares, 2.0)

        # Verify data is actually in farm_details
        self.assertEqual(farm.farm_details_id.farm_total_size, 2.0)

    def test_zero_size_farm(self):
        """Test edge case with zero farm size."""
        farm = self._create_test_farm(name=_unique("Zero Farm"), farm_total_size=0.0)

        self.assertEqual(farm.farm_size_hectares, 0.0)
        self.assertTrue(farm.is_smallholder)  # 0 <= 5
        self.assertFalse(farm.has_productive_land)

    def test_multiple_productive_land_types(self):
        """Test has_productive_land with mixed use."""
        farm = self._create_test_farm(
            name=_unique("Mixed Farm"),
            farm_total_size=10.0,
            farm_size_under_crops=3.0,
            farm_size_under_livestock=2.0,
            farm_size_under_aquaculture=0.5,
            farm_size_idle=4.5,
        )

        self.assertTrue(farm.has_productive_land)
