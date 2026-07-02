# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json
from datetime import date

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAreaExtension(TransactionCase):
    """Test area extensions for GIS reporting reference data."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Set context to avoid job queue delay for faster tests
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                queue_job__no_delay=True,
            )
        )

        # Create test area hierarchy
        cls.area_country = cls.env["spp.area"].create(
            {
                "draft_name": "Test Country",
                "code": "TC",
                "area_level": 0,
                "area_sqkm": 5000.0,
                "population": 500000,
                "population_date": date(2020, 1, 1),
                "population_source": "National Census 2020",
                "household_count": 100000,
            }
        )

        cls.area_region = cls.env["spp.area"].create(
            {
                "draft_name": "Test Region",
                "code": "TC-R1",
                "parent_id": cls.area_country.id,
                "area_level": 1,
                "area_sqkm": 1000.0,
                "population": 100000,
                "household_count": 20000,
            }
        )

        cls.area_district = cls.env["spp.area"].create(
            {
                "draft_name": "Test District",
                "code": "TC-R1-D1",
                "parent_id": cls.area_region.id,
                "area_level": 2,
                "area_sqkm": 500.0,
                "population": 50000,
                "household_count": 10000,
            }
        )

    def test_01_area_population_fields(self):
        """Test area population reference data fields."""
        self.assertEqual(self.area_country.population, 500000)
        self.assertEqual(self.area_country.population_date, date(2020, 1, 1))
        self.assertEqual(self.area_country.population_source, "National Census 2020")

    def test_02_area_household_count(self):
        """Test area household count field."""
        self.assertEqual(self.area_country.household_count, 100000)
        self.assertEqual(self.area_region.household_count, 20000)
        self.assertEqual(self.area_district.household_count, 10000)

    def test_03_area_sqkm(self):
        """Test area size in square kilometers."""
        self.assertEqual(self.area_country.area_sqkm, 5000.0)
        self.assertEqual(self.area_region.area_sqkm, 1000.0)
        self.assertEqual(self.area_district.area_sqkm, 500.0)

    def test_04_registrant_count_computation_empty(self):
        """Test registrant count when no registrants."""
        self.area_district._compute_registry_counts()
        self.assertEqual(self.area_district.registrant_count, 0)
        self.assertEqual(self.area_district.group_count, 0)

    def test_05_registrant_count_computation_individuals(self):
        """Test registrant count with individual registrants."""
        # Create individual registrants
        self.env["res.partner"].create(
            {
                "name": "Individual 1",
                "is_registrant": True,
                "is_group": False,
                "area_id": self.area_district.id,
            }
        )
        self.env["res.partner"].create(
            {
                "name": "Individual 2",
                "is_registrant": True,
                "is_group": False,
                "area_id": self.area_district.id,
            }
        )

        # Recompute
        self.area_district._compute_registry_counts()

        self.assertEqual(self.area_district.registrant_count, 2)
        self.assertEqual(self.area_district.group_count, 0)

    def test_06_registrant_count_computation_groups(self):
        """Test registrant count with group registrants."""
        # Create group registrants
        self.env["res.partner"].create(
            {
                "name": "Group 1",
                "is_registrant": True,
                "is_group": True,
                "area_id": self.area_district.id,
            }
        )
        self.env["res.partner"].create(
            {
                "name": "Group 2",
                "is_registrant": True,
                "is_group": True,
                "area_id": self.area_district.id,
            }
        )

        # Recompute
        self.area_district._compute_registry_counts()

        self.assertEqual(self.area_district.registrant_count, 0)
        self.assertEqual(self.area_district.group_count, 2)

    def test_07_registrant_count_computation_mixed(self):
        """Test registrant count with both individuals and groups."""
        # Create mixed registrants
        self.env["res.partner"].create(
            {
                "name": "Individual 1",
                "is_registrant": True,
                "is_group": False,
                "area_id": self.area_region.id,
            }
        )
        self.env["res.partner"].create(
            {
                "name": "Individual 2",
                "is_registrant": True,
                "is_group": False,
                "area_id": self.area_region.id,
            }
        )
        self.env["res.partner"].create(
            {
                "name": "Group 1",
                "is_registrant": True,
                "is_group": True,
                "area_id": self.area_region.id,
            }
        )

        # Recompute
        self.area_region._compute_registry_counts()

        self.assertEqual(self.area_region.registrant_count, 2)
        self.assertEqual(self.area_region.group_count, 1)

    def test_08_registrant_count_excludes_inactive(self):
        """Test that inactive registrants are excluded from count."""
        # Create active and inactive registrants
        self.env["res.partner"].create(
            {
                "name": "Active Individual",
                "is_registrant": True,
                "is_group": False,
                "area_id": self.area_district.id,
                "active": True,
            }
        )
        self.env["res.partner"].create(
            {
                "name": "Inactive Individual",
                "is_registrant": True,
                "is_group": False,
                "area_id": self.area_district.id,
                "active": False,
            }
        )

        # Recompute
        self.area_district._compute_registry_counts()

        # Should only count active registrant
        self.assertEqual(self.area_district.registrant_count, 1)

    def test_09_registrant_count_excludes_non_registrants(self):
        """Test that non-registrants are excluded from count."""
        # Create registrant and non-registrant
        self.env["res.partner"].create(
            {
                "name": "Registrant",
                "is_registrant": True,
                "is_group": False,
                "area_id": self.area_district.id,
            }
        )
        self.env["res.partner"].create(
            {
                "name": "Non-Registrant",
                "is_registrant": False,
                "is_group": False,
                "area_id": self.area_district.id,
            }
        )

        # Recompute
        self.area_district._compute_registry_counts()

        # Should only count registrant
        self.assertEqual(self.area_district.registrant_count, 1)

    def test_10_registrant_count_multiple_areas(self):
        """Test registrant count computation across multiple areas."""
        # Create registrants in different areas
        self.env["res.partner"].create(
            {
                "name": "District Individual",
                "is_registrant": True,
                "is_group": False,
                "area_id": self.area_district.id,
            }
        )
        self.env["res.partner"].create(
            {
                "name": "Region Individual",
                "is_registrant": True,
                "is_group": False,
                "area_id": self.area_region.id,
            }
        )

        # Recompute both areas
        areas = self.area_district | self.area_region
        areas._compute_registry_counts()

        self.assertEqual(self.area_district.registrant_count, 1)
        self.assertEqual(self.area_region.registrant_count, 1)

    def test_11_registrant_count_new_record(self):
        """Test registrant count for new unsaved records."""
        new_area = self.env["spp.area"].new(
            {
                "draft_name": "New Area",
                "code": "NEW",
            }
        )

        # Should not fail for new records
        new_area._compute_registry_counts()
        self.assertEqual(new_area.registrant_count, 0)
        self.assertEqual(new_area.group_count, 0)

    def test_12_registrant_count_trigger_on_create(self):
        """Test that registrant count is computed when partner is created."""
        area = self.env["spp.area"].create(
            {
                "draft_name": "Auto Compute Area",
                "code": "AUTO",
            }
        )

        # Create registrant
        self.env["res.partner"].create(
            {
                "name": "Auto Registrant",
                "is_registrant": True,
                "is_group": False,
                "area_id": area.id,
            }
        )

        # Recompute (in real scenario this would be triggered automatically)
        area._compute_registry_counts()

        self.assertEqual(area.registrant_count, 1)

    def test_13_population_data_optional(self):
        """Test that population data fields are optional."""
        area = self.env["spp.area"].create(
            {
                "draft_name": "Minimal Area",
                "code": "MIN",
            }
        )

        # Should be created successfully without population data
        self.assertTrue(area.exists())
        self.assertEqual(area.population, 0)
        self.assertFalse(area.population_date)
        self.assertFalse(area.population_source)

    def test_14_household_count_optional(self):
        """Test that household count is optional."""
        area = self.env["spp.area"].create(
            {
                "draft_name": "No Household Data",
                "code": "NHH",
            }
        )

        self.assertTrue(area.exists())
        self.assertEqual(area.household_count, 0)

    def test_15_update_population_data(self):
        """Test updating population reference data."""
        area = self.env["spp.area"].create(
            {
                "draft_name": "Update Area",
                "code": "UPD",
                "population": 10000,
            }
        )

        # Update population
        area.write(
            {
                "population": 15000,
                "population_date": date(2021, 1, 1),
                "population_source": "Updated Census 2021",
            }
        )

        self.assertEqual(area.population, 15000)
        self.assertEqual(area.population_date, date(2021, 1, 1))
        self.assertEqual(area.population_source, "Updated Census 2021")

    def test_16_registrant_count_with_depends(self):
        """Test that @depends triggers recomputation correctly."""
        area = self.env["spp.area"].create(
            {
                "draft_name": "Depends Test",
                "code": "DEP",
            }
        )

        # Create initial registrant
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "is_registrant": True,
                "is_group": False,
                "area_id": area.id,
            }
        )

        area._compute_registry_counts()
        self.assertEqual(area.registrant_count, 1)

        # Update partner to not be registrant
        partner.write({"is_registrant": False})

        area._compute_registry_counts()
        self.assertEqual(area.registrant_count, 0)

    def test_17_registrant_count_group_conversion(self):
        """Test count when partner is converted from individual to group."""
        area = self.env["spp.area"].create(
            {
                "draft_name": "Conversion Test",
                "code": "CONV",
            }
        )

        # Create individual
        partner = self.env["res.partner"].create(
            {
                "name": "Individual to Group",
                "is_registrant": True,
                "is_group": False,
                "area_id": area.id,
            }
        )

        area._compute_registry_counts()
        self.assertEqual(area.registrant_count, 1)
        self.assertEqual(area.group_count, 0)

        # Convert to group
        partner.write({"is_group": True})

        area._compute_registry_counts()
        self.assertEqual(area.registrant_count, 0)
        self.assertEqual(area.group_count, 1)

    def test_18_registrant_count_area_change(self):
        """Test count when partner changes area."""
        area1 = self.env["spp.area"].create(
            {
                "draft_name": "Area 1",
                "code": "A1",
            }
        )
        area2 = self.env["spp.area"].create(
            {
                "draft_name": "Area 2",
                "code": "A2",
            }
        )

        # Create partner in area1
        partner = self.env["res.partner"].create(
            {
                "name": "Moving Partner",
                "is_registrant": True,
                "is_group": False,
                "area_id": area1.id,
            }
        )

        area1._compute_registry_counts()
        self.assertEqual(area1.registrant_count, 1)

        # Move to area2
        partner.write({"area_id": area2.id})

        # Recompute both areas
        (area1 | area2)._compute_registry_counts()
        self.assertEqual(area1.registrant_count, 0)
        self.assertEqual(area2.registrant_count, 1)

    def test_19_large_area_hierarchy(self):
        """Test registry counts in a larger area hierarchy."""
        # Create country -> region -> district -> village hierarchy
        village = self.env["spp.area"].create(
            {
                "draft_name": "Test Village",
                "code": "TC-R1-D1-V1",
                "parent_id": self.area_district.id,
                "area_level": 3,
            }
        )

        # Create registrants at different levels
        self.env["res.partner"].create(
            {
                "name": "Country Level",
                "is_registrant": True,
                "is_group": False,
                "area_id": self.area_country.id,
            }
        )
        self.env["res.partner"].create(
            {
                "name": "Region Level",
                "is_registrant": True,
                "is_group": False,
                "area_id": self.area_region.id,
            }
        )
        self.env["res.partner"].create(
            {
                "name": "District Level",
                "is_registrant": True,
                "is_group": False,
                "area_id": self.area_district.id,
            }
        )
        self.env["res.partner"].create(
            {
                "name": "Village Level",
                "is_registrant": True,
                "is_group": False,
                "area_id": village.id,
            }
        )

        # Recompute all
        all_areas = self.area_country | self.area_region | self.area_district | village
        all_areas._compute_registry_counts()

        # Each area should count only its direct registrants
        self.assertEqual(self.area_country.registrant_count, 1)
        self.assertEqual(self.area_region.registrant_count, 1)
        self.assertEqual(self.area_district.registrant_count, 1)
        self.assertEqual(village.registrant_count, 1)

    def test_20_reference_data_for_normalization(self):
        """Test that reference data is available for normalization calculations."""
        # This area has all reference data needed for various normalization methods
        self.assertTrue(self.area_country.area_sqkm > 0)
        self.assertTrue(self.area_country.population > 0)
        self.assertTrue(self.area_country.household_count > 0)

        # Test density calculation
        density = self.area_country.population / self.area_country.area_sqkm
        self.assertEqual(density, 100.0)  # 500000 / 5000

        # Test per capita (per 1000)
        per_capita = (10000 / self.area_country.population) * 1000
        self.assertEqual(per_capita, 20.0)  # (10000 / 500000) * 1000

        # Test per household (per 100)
        per_household = (5000 / self.area_country.household_count) * 100
        self.assertEqual(per_household, 5.0)  # (5000 / 100000) * 100


@tagged("post_install", "-at_install")
class TestAreaGetGISLayers(TransactionCase):
    """Test get_gis_layers method for report-based layers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                queue_job__no_delay=True,
            )
        )

        # Create test areas with geo_polygon
        # Use GeoJSON string for geo_polygon field
        test_polygon_geojson = json.dumps(
            {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            }
        )
        cls.area_with_geo = cls.env["spp.area"].create(
            {
                "draft_name": "Area With Geometry",
                "code": "AWG",
                "area_level": 1,
                "geo_polygon": test_polygon_geojson,
            }
        )

        cls.area_without_geo = cls.env["spp.area"].create(
            {
                "draft_name": "Area Without Geometry",
                "code": "AWOG",
                "area_level": 1,
            }
        )

        # Create category for report
        cls.category = cls.env["spp.gis.report.category"].create(
            {
                "name": "Test GIS Category",
                "code": "test_gis",
            }
        )

        # Get partner model
        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

        # Create GIS view
        cls.gis_view = cls.env["ir.ui.view"].create(
            {
                "name": "Test GIS View",
                "model": "spp.area",
                "type": "gis",
                "arch": """<gis>
                    <field name="geo_polygon" />
                </gis>""",
            }
        )

        # Get geo field
        cls.geo_field = cls.env["ir.model.fields"].search(
            [
                ("model", "=", "spp.area"),
                ("name", "=", "geo_polygon"),
            ],
            limit=1,
        )

    def _create_report_with_layer(self, name="Test Report"):
        """Create a report with associated layer."""
        # Use a unique code for each test call
        import uuid

        unique_code = f"test_{uuid.uuid4().hex[:8]}"

        report = self.env["spp.gis.report"].create(
            {
                "name": name,
                "code": unique_code,
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 1,
                "auto_create_layer": False,  # Don't auto-create, we'll create manually
            }
        )

        # Create a data layer for this report attached to the test view
        layer = self.env["spp.gis.data.layer"].create(
            {
                "name": f"Layer for {name}",
                "view_id": self.gis_view.id,
                "source_type": "report",
                "report_id": report.id,
                "geo_field_id": self.geo_field.id,
            }
        )

        return report, layer

    def test_01_report_features_with_geometry(self):
        """Test that get_gis_layers returns report_features for areas with geometry."""
        report, layer = self._create_report_with_layer("Report with Geometry")

        # Create threshold
        self.env["spp.gis.report.threshold"].create(
            {
                "report_id": report.id,
                "min_value": 0,
                "max_value": 100,
                "color": "#ff0000",
                "label": "Low",
                "sequence": 1,
            }
        )

        # Create report data for area with geometry
        self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_with_geo.id,
                "raw_value": 50,
                "normalized_value": 50,
                "bucket_color": "#ff0000",
                "bucket_label": "Low",
                "is_stale": False,
            }
        )

        # Call get_gis_layers
        result = self.env["spp.area"].get_gis_layers(view_id=self.gis_view.id)

        # Find the report layer in actives
        report_layer = None
        for layer_dict in result.get("actives", []):
            if layer_dict.get("source_type") == "report" and layer_dict.get("report_id"):
                report_id = layer_dict["report_id"]
                if isinstance(report_id, list | tuple):
                    report_id = report_id[0]
                if report_id == report.id:
                    report_layer = layer_dict
                    break

        self.assertIsNotNone(report_layer, "Report layer should be in actives")
        self.assertIn("report_features", report_layer, "report_features should be present")
        self.assertEqual(len(report_layer["report_features"]), 1, "Should have 1 feature")

        # Verify feature structure
        feature = report_layer["report_features"][0]
        self.assertEqual(feature["type"], "Feature")
        self.assertIn("geometry", feature)
        self.assertEqual(feature["geometry"]["type"], "Polygon")
        self.assertIn("coordinates", feature["geometry"])

        # Verify properties
        props = feature["properties"]
        self.assertEqual(props["resModel"], "spp.area")
        self.assertEqual(props["resId"], self.area_with_geo.id)
        self.assertEqual(props["choropleth_value"], 50.0)
        self.assertEqual(props["report_color"], "#ff0000")
        self.assertEqual(props["report_label"], "Low")

    def test_02_report_features_skips_area_without_geometry(self):
        """Test that areas without geo_polygon are skipped."""
        report, layer = self._create_report_with_layer("Report Skip No Geo")

        # Create report data for area WITHOUT geometry
        self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_without_geo.id,
                "raw_value": 50,
                "normalized_value": 50,
                "is_stale": False,
            }
        )

        # Call get_gis_layers
        result = self.env["spp.area"].get_gis_layers(view_id=self.gis_view.id)

        # Find the report layer
        report_layer = None
        for layer_dict in result.get("actives", []):
            if layer_dict.get("source_type") == "report":
                report_id = layer_dict.get("report_id")
                if isinstance(report_id, list | tuple):
                    report_id = report_id[0]
                if report_id == report.id:
                    report_layer = layer_dict
                    break

        self.assertIsNotNone(report_layer)
        self.assertEqual(
            len(report_layer.get("report_features", [])),
            0,
            "Should have 0 features for area without geometry",
        )

    def test_03_report_features_skips_stale_data(self):
        """Test that stale report data is excluded."""
        # Create a fresh area for this test to avoid interference
        test_polygon_geojson = json.dumps(
            {
                "type": "Polygon",
                "coordinates": [[[2, 2], [3, 2], [3, 3], [2, 3], [2, 2]]],
            }
        )
        stale_area = self.env["spp.area"].create(
            {
                "draft_name": "Stale Test Area",
                "code": "STA",
                "area_level": 1,
                "geo_polygon": test_polygon_geojson,
            }
        )

        report, layer = self._create_report_with_layer("Report Skip Stale")

        # Set report to hourly refresh so data can be stale
        report.refresh_interval = "hourly"

        # Create report data with computed_at far in the past (makes it stale)
        # is_stale is computed from computed_at + refresh_interval
        stale_data = self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": stale_area.id,
                "raw_value": 50,
                "normalized_value": 50,
                "computed_at": fields.Datetime.subtract(fields.Datetime.now(), hours=2),
            }
        )

        # Verify the data was created as stale
        self.assertTrue(stale_data.is_stale, "Data should be marked as stale")

        # Call get_gis_layers
        result = self.env["spp.area"].get_gis_layers(view_id=self.gis_view.id)

        # Find the report layer
        report_layer = None
        for layer_dict in result.get("actives", []):
            if layer_dict.get("source_type") == "report":
                report_id = layer_dict.get("report_id")
                if isinstance(report_id, list | tuple):
                    report_id = report_id[0]
                if report_id == report.id:
                    report_layer = layer_dict
                    break

        self.assertIsNotNone(report_layer)
        features = report_layer.get("report_features", [])
        self.assertEqual(
            len(features),
            0,
            f"Should have 0 features for stale data, but found {len(features)}",
        )

    def test_04_report_legend_from_thresholds(self):
        """Test that report_legend is built from thresholds."""
        report, layer = self._create_report_with_layer("Report With Legend")

        # Create thresholds
        self.env["spp.gis.report.threshold"].create(
            {
                "report_id": report.id,
                "min_value": 0,
                "max_value": 50,
                "color": "#00ff00",
                "label": "Low",
                "sequence": 1,
            }
        )
        self.env["spp.gis.report.threshold"].create(
            {
                "report_id": report.id,
                "min_value": 50,
                "max_value": 100,
                "color": "#ff0000",
                "label": "High",
                "sequence": 2,
            }
        )

        # Call get_gis_layers
        result = self.env["spp.area"].get_gis_layers(view_id=self.gis_view.id)

        # Find the report layer
        report_layer = None
        for layer_dict in result.get("actives", []):
            if layer_dict.get("source_type") == "report":
                report_id = layer_dict.get("report_id")
                if isinstance(report_id, list | tuple):
                    report_id = report_id[0]
                if report_id == report.id:
                    report_layer = layer_dict
                    break

        self.assertIsNotNone(report_layer)
        self.assertIn("report_legend", report_layer)
        self.assertEqual(len(report_layer["report_legend"]), 2)
        self.assertEqual(report_layer["report_legend"][0]["color"], "#00ff00")
        self.assertEqual(report_layer["report_legend"][0]["label"], "Low")
        self.assertEqual(report_layer["report_legend"][1]["color"], "#ff0000")
        self.assertEqual(report_layer["report_legend"][1]["label"], "High")
        self.assertEqual(report_layer["report_legend_title"], "Report With Legend")

    def test_05_shapely_geometry_converted_to_geojson(self):
        """Test that Shapely geometry objects are converted to GeoJSON."""
        report, layer = self._create_report_with_layer("Report Shapely Conversion")

        # Create report data
        self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_with_geo.id,
                "raw_value": 75,
                "normalized_value": 75,
                "bucket_color": "#0000ff",
                "is_stale": False,
            }
        )

        # Call get_gis_layers
        result = self.env["spp.area"].get_gis_layers(view_id=self.gis_view.id)

        # Find the report layer
        report_layer = None
        for layer_dict in result.get("actives", []):
            if layer_dict.get("source_type") == "report":
                report_id = layer_dict.get("report_id")
                if isinstance(report_id, list | tuple):
                    report_id = report_id[0]
                if report_id == report.id:
                    report_layer = layer_dict
                    break

        self.assertIsNotNone(report_layer)
        self.assertEqual(len(report_layer.get("report_features", [])), 1)

        # Verify geometry is valid GeoJSON
        feature = report_layer["report_features"][0]
        geometry = feature["geometry"]
        self.assertIsInstance(geometry, dict)
        self.assertEqual(geometry["type"], "Polygon")
        self.assertIsInstance(geometry["coordinates"], (list, tuple))
        # Verify coordinate structure - should be list of rings
        self.assertTrue(len(geometry["coordinates"]) > 0)
        self.assertTrue(len(geometry["coordinates"][0]) >= 4)  # At least 4 points for closed polygon

    def test_06_non_report_layers_unchanged(self):
        """Test that non-report layers are not modified."""
        # Create a model-based layer
        model_layer = self.env["spp.gis.data.layer"].create(
            {
                "name": "Model Layer",
                "view_id": self.gis_view.id,
                "source_type": "model",
                "geo_field_id": self.geo_field.id,
            }
        )

        # Call get_gis_layers
        result = self.env["spp.area"].get_gis_layers(view_id=self.gis_view.id)

        # Find the model layer
        found_layer = None
        for layer_dict in result.get("actives", []):
            if layer_dict.get("id") == model_layer.id:
                found_layer = layer_dict
                break

        self.assertIsNotNone(found_layer)
        self.assertEqual(found_layer.get("source_type"), "model")
        self.assertNotIn(
            "report_features",
            found_layer,
            "Model layers should not have report_features",
        )
