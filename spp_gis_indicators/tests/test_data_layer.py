# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestDataLayerIndicators(TransactionCase):
    """Test GIS Data Layer extension for indicator visualization."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.DataLayer = cls.env["spp.gis.data.layer"]
        cls.ColorScale = cls.env["spp.gis.color.scale"]
        cls.IndicatorLayer = cls.env["spp.gis.indicator.layer"]
        cls.Variable = cls.env["spp.cel.variable"]

        # Create test color scale
        cls.color_scale = cls.ColorScale.create(
            {
                "name": "Test Blues",
                "scale_type": "sequential",
                "colors_json": json.dumps(["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]),
            }
        )

        # Create test variable
        # Required fields: name, cel_accessor, value_type, source_type
        cls.variable = cls.Variable.create(
            {
                "name": "test_pop",
                "cel_accessor": "test_pop",
                "label": "Test Population",
                "value_type": "number",
                "source_type": "constant",
            }
        )

        # Create test indicator layer
        cls.indicator_layer = cls.IndicatorLayer.create(
            {
                "name": "Population Indicator",
                "variable_id": cls.variable.id,
                "color_scale_id": cls.color_scale.id,
                "classification_method": "quantile",
                "num_classes": 5,
            }
        )

        # Find or create a geo field for testing
        geo_field = cls.env["ir.model.fields"].search(
            [
                ("model", "=", "spp.area"),
                ("ttype", "=", "geo_polygon"),
            ],
            limit=1,
        )

        if not geo_field:
            # Create a mock data layer without geo_field
            cls.geo_field_id = False
        else:
            cls.geo_field_id = geo_field.id

    def test_geo_repr_choropleth_option(self):
        """Test that choropleth is available as geo_repr option."""
        # Get the selection options for geo_repr
        field_info = self.DataLayer.fields_get(["geo_repr"])
        selection = field_info["geo_repr"]["selection"]

        # Find choropleth in selection
        choropleth_found = any(opt[0] == "choropleth" for opt in selection)
        self.assertTrue(choropleth_found, "choropleth should be available in geo_repr selection")

    def test_create_data_layer_with_choropleth(self):
        """Test creating a data layer with choropleth representation."""
        # Get any available GIS view
        gis_view = self.env["ir.ui.view"].search(
            [
                ("type", "=", "spp_gis"),
            ],
            limit=1,
        )

        if not gis_view:
            self.skipTest("No GIS view available for testing")

        # Try to create data layer
        layer = self.DataLayer.create(
            {
                "name": "Test Choropleth Layer",
                "view_id": gis_view.id,
                "geo_repr": "choropleth",
                "indicator_layer_id": self.indicator_layer.id,
            }
        )

        self.assertEqual(layer.name, "Test Choropleth Layer")
        self.assertEqual(layer.geo_repr, "choropleth")
        self.assertEqual(layer.indicator_layer_id, self.indicator_layer)

    def test_indicator_layer_field_exists(self):
        """Test that indicator_layer_id field exists on data layer."""
        field_info = self.DataLayer.fields_get(["indicator_layer_id"])
        self.assertIn("indicator_layer_id", field_info)
        self.assertEqual(field_info["indicator_layer_id"]["relation"], "spp.gis.indicator.layer")

    def test_data_layer_without_indicator(self):
        """Test that data layer can be created without indicator."""
        gis_view = self.env["ir.ui.view"].search(
            [
                ("type", "=", "spp_gis"),
            ],
            limit=1,
        )

        if not gis_view:
            self.skipTest("No GIS view available for testing")

        # Create without indicator_layer_id
        layer = self.DataLayer.create(
            {
                "name": "Non-Choropleth Layer",
                "view_id": gis_view.id,
                "geo_repr": "basic",
            }
        )

        self.assertEqual(layer.name, "Non-Choropleth Layer")
        self.assertFalse(layer.indicator_layer_id)

    def test_change_geo_repr_to_choropleth(self):
        """Test changing geo_repr to choropleth after creation."""
        gis_view = self.env["ir.ui.view"].search(
            [
                ("type", "=", "spp_gis"),
            ],
            limit=1,
        )

        if not gis_view:
            self.skipTest("No GIS view available for testing")

        layer = self.DataLayer.create(
            {
                "name": "Changeable Layer",
                "view_id": gis_view.id,
            }
        )

        # Change to choropleth
        layer.write(
            {
                "geo_repr": "choropleth",
                "indicator_layer_id": self.indicator_layer.id,
            }
        )

        self.assertEqual(layer.geo_repr, "choropleth")
        self.assertEqual(layer.indicator_layer_id, self.indicator_layer)
