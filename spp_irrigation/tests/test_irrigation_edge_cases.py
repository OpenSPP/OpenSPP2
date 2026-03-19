# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Irrigation Asset edge cases and comprehensive coverage."""

import json
import time

from odoo.tests import TransactionCase, tagged


def _unique(base):
    """Generate unique name for test isolation."""
    return f"{base}_{int(time.time() * 1000)}"


@tagged("post_install", "-at_install")
class TestIrrigationAssetAllFields(TransactionCase):
    """Test irrigation asset creation with all possible fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.asset_type_reservoir = cls.env.ref("spp_farmer_registry_vocabularies.code_irrigation_reservoir")
        cls.asset_type_canal = cls.env.ref("spp_farmer_registry_vocabularies.code_irrigation_canal")
        cls.asset_type_pump = cls.env.ref("spp_farmer_registry_vocabularies.code_irrigation_pump_station")
        cls.asset_type_well = cls.env.ref("spp_farmer_registry_vocabularies.code_irrigation_well")

        cls.farm = cls.env["res.partner"].create(
            {
                "name": _unique("Full Field Farm"),
                "is_registrant": True,
                "is_group": True,
            }
        )

    def test_create_with_all_fields(self):
        """Create irrigation asset with every field populated."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Full Asset"),
                "asset_type_id": self.asset_type_reservoir.id,
                "farm_id": self.farm.id,
                "total_capacity": 7500.0,
                "coordinates": json.dumps({"type": "Point", "coordinates": [125.5, 8.5]}),
                "geo_polygon": json.dumps(
                    {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [125.4, 8.4],
                                [125.6, 8.4],
                                [125.6, 8.6],
                                [125.4, 8.6],
                                [125.4, 8.4],
                            ]
                        ],
                    }
                ),
            }
        )
        self.assertTrue(asset.name)
        self.assertEqual(asset.asset_type_id, self.asset_type_reservoir)
        self.assertEqual(asset.farm_id, self.farm)
        self.assertEqual(asset.total_capacity, 7500.0)
        self.assertTrue(asset.coordinates)
        self.assertTrue(asset.geo_polygon)
        self.assertEqual(asset.category, "reservoir")

    def test_create_minimal_asset(self):
        """Create irrigation asset with only name."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Minimal Asset"),
            }
        )
        self.assertTrue(asset.name)
        self.assertFalse(asset.asset_type_id)
        self.assertFalse(asset.farm_id)
        self.assertEqual(asset.total_capacity, 0.0)
        self.assertFalse(asset.coordinates)
        self.assertFalse(asset.geo_polygon)
        self.assertFalse(asset.category)

    def test_total_capacity_zero(self):
        """Asset can have zero capacity."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Zero Cap"),
                "total_capacity": 0.0,
            }
        )
        self.assertEqual(asset.total_capacity, 0.0)

    def test_total_capacity_large_value(self):
        """Asset can have very large capacity."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Large Cap"),
                "total_capacity": 999999999.99,
            }
        )
        self.assertAlmostEqual(asset.total_capacity, 999999999.99, places=2)


@tagged("post_install", "-at_install")
class TestIrrigationM2MRelationships(TransactionCase):
    """Test Many2many source/destination relationships in depth."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.asset_type_reservoir = cls.env.ref("spp_farmer_registry_vocabularies.code_irrigation_reservoir")
        cls.asset_type_canal = cls.env.ref("spp_farmer_registry_vocabularies.code_irrigation_canal")
        cls.asset_type_pump = cls.env.ref("spp_farmer_registry_vocabularies.code_irrigation_pump_station")

    def test_empty_source_and_destination(self):
        """New asset has no sources or destinations."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Isolated"),
                "asset_type_id": self.asset_type_reservoir.id,
            }
        )
        self.assertEqual(len(asset.irrigation_source_ids), 0)
        self.assertEqual(len(asset.irrigation_destination_ids), 0)

    def test_multiple_destinations(self):
        """One source can feed multiple destinations."""
        source = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Main Reservoir"),
                "asset_type_id": self.asset_type_reservoir.id,
                "total_capacity": 10000.0,
            }
        )
        dest1 = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Canal A"),
                "asset_type_id": self.asset_type_canal.id,
            }
        )
        dest2 = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Canal B"),
                "asset_type_id": self.asset_type_canal.id,
            }
        )
        dest3 = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Canal C"),
                "asset_type_id": self.asset_type_canal.id,
            }
        )

        source.irrigation_destination_ids = [
            (4, dest1.id),
            (4, dest2.id),
            (4, dest3.id),
        ]

        self.assertEqual(len(source.irrigation_destination_ids), 3)
        self.assertIn(dest1, source.irrigation_destination_ids)
        self.assertIn(dest2, source.irrigation_destination_ids)
        self.assertIn(dest3, source.irrigation_destination_ids)

    def test_multiple_sources(self):
        """One destination can receive from multiple sources."""
        dest = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Collection Canal"),
                "asset_type_id": self.asset_type_canal.id,
            }
        )
        src1 = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Reservoir 1"),
                "asset_type_id": self.asset_type_reservoir.id,
            }
        )
        src2 = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Reservoir 2"),
                "asset_type_id": self.asset_type_reservoir.id,
            }
        )

        dest.irrigation_source_ids = [
            (4, src1.id),
            (4, src2.id),
        ]

        self.assertEqual(len(dest.irrigation_source_ids), 2)
        self.assertIn(src1, dest.irrigation_source_ids)
        self.assertIn(src2, dest.irrigation_source_ids)

    def test_remove_destination(self):
        """Removing a destination relationship works correctly."""
        source = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Source Remove"),
                "asset_type_id": self.asset_type_reservoir.id,
            }
        )
        dest = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Dest Remove"),
                "asset_type_id": self.asset_type_canal.id,
            }
        )

        # Add then remove
        source.irrigation_destination_ids = [(4, dest.id)]
        self.assertEqual(len(source.irrigation_destination_ids), 1)

        source.irrigation_destination_ids = [(3, dest.id)]
        self.assertEqual(len(source.irrigation_destination_ids), 0)

    def test_remove_source(self):
        """Removing a source relationship works correctly."""
        dest = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Dest Remove Src"),
                "asset_type_id": self.asset_type_canal.id,
            }
        )
        src = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Src Remove"),
                "asset_type_id": self.asset_type_reservoir.id,
            }
        )

        dest.irrigation_source_ids = [(4, src.id)]
        self.assertEqual(len(dest.irrigation_source_ids), 1)

        dest.irrigation_source_ids = [(3, src.id)]
        self.assertEqual(len(dest.irrigation_source_ids), 0)

    def test_source_destination_independent(self):
        """Source and destination relations use separate tables and are independent."""
        asset_a = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Asset A"),
                "asset_type_id": self.asset_type_pump.id,
            }
        )
        asset_b = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Asset B"),
                "asset_type_id": self.asset_type_canal.id,
            }
        )

        # A has B as destination
        asset_a.irrigation_destination_ids = [(4, asset_b.id)]
        # B does NOT automatically have A as source (separate tables)
        self.assertNotIn(asset_a, asset_b.irrigation_source_ids)

        # Manually add A as source of B
        asset_b.irrigation_source_ids = [(4, asset_a.id)]
        self.assertIn(asset_a, asset_b.irrigation_source_ids)
        self.assertIn(asset_b, asset_a.irrigation_destination_ids)

    def test_replace_all_destinations(self):
        """Replace all destinations at once using (6, 0, ids)."""
        source = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Replace Source"),
                "asset_type_id": self.asset_type_reservoir.id,
            }
        )
        dest1 = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Old Dest"),
                "asset_type_id": self.asset_type_canal.id,
            }
        )
        dest2 = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("New Dest"),
                "asset_type_id": self.asset_type_canal.id,
            }
        )

        source.irrigation_destination_ids = [(4, dest1.id)]
        self.assertIn(dest1, source.irrigation_destination_ids)

        # Replace all with just dest2
        source.irrigation_destination_ids = [(6, 0, [dest2.id])]
        self.assertEqual(len(source.irrigation_destination_ids), 1)
        self.assertIn(dest2, source.irrigation_destination_ids)
        self.assertNotIn(dest1, source.irrigation_destination_ids)


@tagged("post_install", "-at_install")
class TestIrrigationCategoryComputed(TransactionCase):
    """Test category computed field edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.asset_type_reservoir = cls.env.ref("spp_farmer_registry_vocabularies.code_irrigation_reservoir")
        cls.asset_type_canal = cls.env.ref("spp_farmer_registry_vocabularies.code_irrigation_canal")
        cls.asset_type_pump = cls.env.ref("spp_farmer_registry_vocabularies.code_irrigation_pump_station")
        cls.asset_type_well = cls.env.ref("spp_farmer_registry_vocabularies.code_irrigation_well")

    def test_category_matches_reservoir_code(self):
        """Category is 'reservoir' for reservoir asset type."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Cat Reservoir"),
                "asset_type_id": self.asset_type_reservoir.id,
            }
        )
        self.assertEqual(asset.category, "reservoir")

    def test_category_matches_canal_code(self):
        """Category is 'canal' for canal asset type."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Cat Canal"),
                "asset_type_id": self.asset_type_canal.id,
            }
        )
        self.assertEqual(asset.category, "canal")

    def test_category_matches_pump_code(self):
        """Category is 'pump_station' for pump station asset type."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Cat Pump"),
                "asset_type_id": self.asset_type_pump.id,
            }
        )
        self.assertEqual(asset.category, "pump_station")

    def test_category_matches_well_code(self):
        """Category is 'well' for well asset type."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Cat Well"),
                "asset_type_id": self.asset_type_well.id,
            }
        )
        self.assertEqual(asset.category, "well")

    def test_category_cleared_when_type_removed(self):
        """Category becomes False when asset_type_id is cleared."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Clear Cat"),
                "asset_type_id": self.asset_type_reservoir.id,
            }
        )
        self.assertEqual(asset.category, "reservoir")
        asset.asset_type_id = False
        self.assertFalse(asset.category)

    def test_category_updates_on_type_change(self):
        """Category updates when asset type changes across all types."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Change Cat"),
                "asset_type_id": self.asset_type_reservoir.id,
            }
        )
        self.assertEqual(asset.category, "reservoir")

        asset.asset_type_id = self.asset_type_canal.id
        self.assertEqual(asset.category, "canal")

        asset.asset_type_id = self.asset_type_pump.id
        self.assertEqual(asset.category, "pump_station")

        asset.asset_type_id = self.asset_type_well.id
        self.assertEqual(asset.category, "well")


@tagged("post_install", "-at_install")
class TestIrrigationFarmLinking(TransactionCase):
    """Test farm linking via farm_id field."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.asset_type_reservoir = cls.env.ref("spp_farmer_registry_vocabularies.code_irrigation_reservoir")

        cls.farm1 = cls.env["res.partner"].create(
            {
                "name": _unique("Farm Alpha"),
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.farm2 = cls.env["res.partner"].create(
            {
                "name": _unique("Farm Beta"),
                "is_registrant": True,
                "is_group": True,
            }
        )

    def test_change_farm(self):
        """Asset farm can be changed after creation."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Reassign Asset"),
                "asset_type_id": self.asset_type_reservoir.id,
                "farm_id": self.farm1.id,
            }
        )
        self.assertEqual(asset.farm_id, self.farm1)

        asset.farm_id = self.farm2.id
        self.assertEqual(asset.farm_id, self.farm2)

    def test_clear_farm(self):
        """Asset farm can be cleared (make it shared/unassigned)."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Unassign Asset"),
                "asset_type_id": self.asset_type_reservoir.id,
                "farm_id": self.farm1.id,
            }
        )
        asset.farm_id = False
        self.assertFalse(asset.farm_id)

    def test_multiple_assets_same_farm(self):
        """Multiple assets can belong to the same farm."""
        asset1 = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Farm Asset 1"),
                "farm_id": self.farm1.id,
            }
        )
        asset2 = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Farm Asset 2"),
                "farm_id": self.farm1.id,
            }
        )
        asset3 = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Farm Asset 3"),
                "farm_id": self.farm1.id,
            }
        )

        self.assertEqual(asset1.farm_id, self.farm1)
        self.assertEqual(asset2.farm_id, self.farm1)
        self.assertEqual(asset3.farm_id, self.farm1)

    def test_write_farm_id(self):
        """Farm can be set via write() method."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Write Farm"),
            }
        )
        self.assertFalse(asset.farm_id)

        asset.write({"farm_id": self.farm1.id})
        self.assertEqual(asset.farm_id, self.farm1)


@tagged("post_install", "-at_install")
class TestIrrigationGeoFields(TransactionCase):
    """Test geo point and polygon field edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.asset_type_pump = cls.env.ref("spp_farmer_registry_vocabularies.code_irrigation_pump_station")

    def test_only_coordinates_set(self):
        """Asset can have only point coordinates."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Point Only"),
                "asset_type_id": self.asset_type_pump.id,
                "coordinates": json.dumps({"type": "Point", "coordinates": [126.0, 9.0]}),
            }
        )
        self.assertTrue(asset.coordinates)
        self.assertFalse(asset.geo_polygon)

    def test_only_polygon_set(self):
        """Asset can have only polygon geometry."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("Polygon Only"),
                "asset_type_id": self.asset_type_pump.id,
                "geo_polygon": json.dumps(
                    {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [125.0, 8.0],
                                [125.1, 8.0],
                                [125.1, 8.1],
                                [125.0, 8.1],
                                [125.0, 8.0],
                            ]
                        ],
                    }
                ),
            }
        )
        self.assertFalse(asset.coordinates)
        self.assertTrue(asset.geo_polygon)

    def test_no_geo_fields(self):
        """Asset can exist with no geographic data."""
        asset = self.env["spp.irrigation.asset"].create(
            {
                "name": _unique("No Geo"),
                "asset_type_id": self.asset_type_pump.id,
            }
        )
        self.assertFalse(asset.coordinates)
        self.assertFalse(asset.geo_polygon)
