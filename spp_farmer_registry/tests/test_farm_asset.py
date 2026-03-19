# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Farm Asset models.

Tests cover:
- FarmAsset creation and fields
- _onchange_farm_id() clears land_id
- AssetType, MachineryType, FarmExtension models
"""

import time

from odoo.tests import TransactionCase, tagged

from .common import FarmerTestDataMixin


def _unique(base):
    """Generate unique name for test isolation."""
    return f"{base}_{int(time.time() * 1000)}"


@tagged("post_install", "-at_install")
class TestFarmAsset(TransactionCase, FarmerTestDataMixin):
    """Test spp.farm.asset model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.farm = cls._create_test_farm(name=f"Asset Test Farm {cls._test_id}")

    def test_create_asset_with_farm(self):
        """Test creating a farm asset linked to a farm."""
        asset_type = self.env["spp.asset.type"].create({"name": _unique("Tractor Type")})

        asset = self.env["spp.farm.asset"].create(
            {
                "asset_farm_id": self.farm.id,
                "asset_type_id": asset_type.id,
                "quantity": 2,
                "technology_used": "Diesel-powered",
            }
        )

        self.assertEqual(asset.asset_farm_id, self.farm)
        self.assertEqual(asset.quantity, 2)
        self.assertEqual(asset.technology_used, "Diesel-powered")

    def test_create_machinery_asset(self):
        """Test creating a machinery asset linked to a farm."""
        machinery_type = self.env["spp.machinery.type"].create({"name": _unique("Harvester")})

        asset = self.env["spp.farm.asset"].create(
            {
                "machinery_farm_id": self.farm.id,
                "machinery_type_id": machinery_type.id,
                "quantity": 1,
                "machine_working_status": "operational",
            }
        )

        self.assertEqual(asset.machinery_farm_id, self.farm)
        self.assertEqual(asset.machine_working_status, "operational")

    def test_onchange_farm_id_clears_land(self):
        """Test that changing asset_farm_id clears land_id."""
        land = self.env["spp.land.record"].create(
            {
                "land_farm_id": self.farm.id,
                "land_name": _unique("Parcel"),
                "land_acreage": 5.0,
            }
        )

        asset = self.env["spp.farm.asset"].new(
            {
                "asset_farm_id": self.farm.id,
                "land_id": land.id,
            }
        )

        # Simulate changing farm
        another_farm = self._create_test_farm(name=_unique("Other Farm"))
        asset.asset_farm_id = another_farm
        asset._onchange_farm_id()

        self.assertFalse(asset.land_id)

    def test_create_asset_without_farm(self):
        """Test creating a farm asset without a farm link."""
        asset = self.env["spp.farm.asset"].create(
            {
                "quantity": 5,
                "technology_used": "Manual",
            }
        )

        self.assertFalse(asset.asset_farm_id)
        self.assertEqual(asset.quantity, 5)


@tagged("post_install", "-at_install")
class TestAssetType(TransactionCase):
    """Test spp.asset.type model."""

    def test_create_asset_type(self):
        """Test creating an asset type."""
        asset_type = self.env["spp.asset.type"].create(
            {
                "name": "Irrigation Pump",
            }
        )

        self.assertEqual(asset_type.name, "Irrigation Pump")

    def test_create_multiple_asset_types(self):
        """Test creating multiple asset types."""
        types = self.env["spp.asset.type"].create(
            [
                {"name": "Tractor"},
                {"name": "Sprayer"},
                {"name": "Plow"},
            ]
        )

        self.assertEqual(len(types), 3)


@tagged("post_install", "-at_install")
class TestMachineryType(TransactionCase):
    """Test spp.machinery.type model."""

    def test_create_machinery_type(self):
        """Test creating a machinery type."""
        machinery_type = self.env["spp.machinery.type"].create(
            {
                "name": "Combine Harvester",
            }
        )

        self.assertEqual(machinery_type.name, "Combine Harvester")


@tagged("post_install", "-at_install")
class TestFarmExtension(TransactionCase, FarmerTestDataMixin):
    """Test spp.farm.extension model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.farm = cls._create_test_farm(name=f"Extension Test Farm {cls._test_id}")

    def test_create_extension_service(self):
        """Test creating an extension service record."""
        from datetime import date

        extension = self.env["spp.farm.extension"].create(
            {
                "farm_id": self.farm.id,
                "service_type": "Pest Management Training",
                "provider": "Ministry of Agriculture",
                "date": date.today(),
                "notes": "Quarterly training session",
            }
        )

        self.assertEqual(extension.farm_id, self.farm)
        self.assertEqual(extension.service_type, "Pest Management Training")
        self.assertEqual(extension.provider, "Ministry of Agriculture")

    def test_create_extension_service_minimal(self):
        """Test creating an extension service with minimal fields."""
        extension = self.env["spp.farm.extension"].create(
            {
                "farm_id": self.farm.id,
            }
        )

        self.assertEqual(extension.farm_id, self.farm)
        self.assertFalse(extension.service_type)

    def test_farm_extension_ids_relation(self):
        """Test that farm.farm_extension_ids One2many works correctly."""
        self.env["spp.farm.extension"].create(
            {
                "farm_id": self.farm.id,
                "service_type": "Soil Testing",
            }
        )
        self.env["spp.farm.extension"].create(
            {
                "farm_id": self.farm.id,
                "service_type": "Seed Distribution",
            }
        )

        self.farm.invalidate_recordset()
        self.assertEqual(len(self.farm.farm_extension_ids), 2)
