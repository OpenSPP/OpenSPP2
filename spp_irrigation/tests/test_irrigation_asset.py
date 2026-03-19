# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Irrigation Asset model."""

import json
import time

from odoo.tests import TransactionCase, tagged


def _unique(base):
    """Generate unique name for test isolation."""
    return f"{base}_{int(time.time() * 1000)}"


@tagged("post_install", "-at_install")
class TestIrrigationAsset(TransactionCase):
    """Test spp.irrigation.asset model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)

        # Get vocabulary codes
        cls.asset_type_reservoir = cls.env.ref(
            "spp_farmer_registry_vocabularies.code_irrigation_reservoir"
        )
        cls.asset_type_canal = cls.env.ref(
            "spp_farmer_registry_vocabularies.code_irrigation_canal"
        )
        cls.asset_type_pump = cls.env.ref(
            "spp_farmer_registry_vocabularies.code_irrigation_pump_station"
        )

        # Create test farm
        cls.test_farm = cls.env["res.partner"].create(
            {
                "name": f"Test Farm {cls._test_id}",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create test irrigation asset
        cls.test_asset = cls.env["spp.irrigation.asset"].create(
            {
                "name": f"Test Reservoir {cls._test_id}",
                "asset_type_id": cls.asset_type_reservoir.id,
                "farm_id": cls.test_farm.id,
                "total_capacity": 1000.0,
            }
        )

    def test_create_irrigation_asset(self):
        """Test creating an irrigation asset with vocabulary-based type."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Canal"),
                "asset_type_id": self.asset_type_canal.id,
                "total_capacity": 500.0,
            }
        )

        self.assertEqual(asset.asset_type_id.code, "canal")
        self.assertEqual(asset.asset_type_id.display, "Canal")
        self.assertEqual(asset.total_capacity, 500.0)

    def test_farm_relationship(self):
        """Test that irrigation asset can be linked to a farm."""
        self.assertEqual(self.test_asset.farm_id, self.test_farm)
        self.assertEqual(self.test_asset.farm_id.name, f"Test Farm {self._test_id}")

    def test_category_computed_field(self):
        """Test that category computed field derives from asset_type_id."""
        self.assertEqual(self.test_asset.category, "reservoir")

        # Change asset type
        self.test_asset.asset_type_id = self.asset_type_canal.id
        self.assertEqual(self.test_asset.category, "canal")

    def test_category_empty(self):
        """Test category when no asset_type_id is set."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("No Type Asset"),
            }
        )
        self.assertFalse(asset.category)
        self.assertFalse(asset.asset_type_id)

    def test_irrigation_source_destination(self):
        """Test water flow relationships between irrigation assets.

        Note: irrigation_source_ids and irrigation_destination_ids use
        separate relation tables, so they are independent (not inverses).
        This allows modeling complex water networks where the same asset
        can be both a source and destination in different relationships.
        """
        # Create source and destination assets
        source = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Water Source"),
                "asset_type_id": self.asset_type_reservoir.id,
                "total_capacity": 5000.0,
            }
        )

        destination = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Water Destination"),
                "asset_type_id": self.asset_type_canal.id,
            }
        )

        # Set water flow relationship - source feeds to destination
        source.irrigation_destination_ids = [(4, destination.id)]

        # Verify destination relationship on source
        self.assertIn(destination, source.irrigation_destination_ids)

        # Set the inverse manually (destination receives from source)
        destination.irrigation_source_ids = [(4, source.id)]

        # Verify source relationship on destination
        self.assertIn(source, destination.irrigation_source_ids)

    def test_geo_fields(self):
        """Test that geo fields can be set."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Geo Asset"),
                "asset_type_id": self.asset_type_pump.id,
                "coordinates": json.dumps(
                    {
                        "type": "Point",
                        "coordinates": [125.0, 8.0],
                    }
                ),
                "geo_polygon": json.dumps(
                    {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [124.9, 7.9],
                                [125.1, 7.9],
                                [125.1, 8.1],
                                [124.9, 8.1],
                                [124.9, 7.9],
                            ]
                        ],
                    }
                ),
            }
        )

        self.assertTrue(asset.coordinates)
        self.assertTrue(asset.geo_polygon)

    def test_multiple_farms_with_assets(self):
        """Test multiple farms can have different irrigation assets."""
        farm2 = self.env["res.partner"].create(
            {
                "name": _unique("Farm 2"),
                "is_registrant": True,
                "is_group": True,
            }
        )

        asset2 = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Farm 2 Well"),
                "asset_type_id": self.env.ref(
                    "spp_farmer_registry_vocabularies.code_irrigation_well"
                ).id,
                "farm_id": farm2.id,
            }
        )

        self.assertEqual(self.test_asset.farm_id, self.test_farm)
        self.assertEqual(asset2.farm_id, farm2)
        self.assertNotEqual(self.test_asset.farm_id, asset2.farm_id)

    def test_asset_without_farm(self):
        """Test irrigation asset can exist without a farm (shared infrastructure)."""
        shared_asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Community Reservoir"),
                "asset_type_id": self.asset_type_reservoir.id,
                "total_capacity": 10000.0,
            }
        )

        self.assertFalse(shared_asset.farm_id)
        self.assertEqual(shared_asset.asset_type_id.code, "reservoir")
