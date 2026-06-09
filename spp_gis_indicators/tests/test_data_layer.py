# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json

from odoo.exceptions import ValidationError
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

        # Find a geo field for testing
        geo_field = cls.env["ir.model.fields"].search(
            [
                ("model", "=", "spp.area"),
                ("ttype", "=", "geo_polygon"),
            ],
            limit=1,
        )

        cls.geo_field_id = geo_field.id if geo_field else False

        # Find a GIS view for testing
        cls.gis_view = cls.env["ir.ui.view"].search(
            [("type", "=", "spp_gis")],
            limit=1,
        )

    def _skip_if_no_gis_prereqs(self):
        """Skip test if GIS prerequisites are missing."""
        if not self.gis_view:
            self.skipTest("No GIS view available for testing")
        if not self.geo_field_id:
            self.skipTest("No geo_polygon field available for testing")

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
        self._skip_if_no_gis_prereqs()

        # Try to create data layer
        layer = self.DataLayer.create(
            {
                "name": "Test Choropleth Layer",
                "view_id": self.gis_view.id,
                "geo_field_id": self.geo_field_id,
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
        self._skip_if_no_gis_prereqs()

        # Create without indicator_layer_id
        layer = self.DataLayer.create(
            {
                "name": "Non-Choropleth Layer",
                "view_id": self.gis_view.id,
                "geo_field_id": self.geo_field_id,
                "geo_repr": "basic",
            }
        )

        self.assertEqual(layer.name, "Non-Choropleth Layer")
        self.assertFalse(layer.indicator_layer_id)

    def test_change_geo_repr_to_choropleth(self):
        """Test changing geo_repr to choropleth after creation."""
        self._skip_if_no_gis_prereqs()

        layer = self.DataLayer.create(
            {
                "name": "Changeable Layer",
                "view_id": self.gis_view.id,
                "geo_field_id": self.geo_field_id,
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

    def test_choropleth_requires_config(self):
        """Test that choropleth without any config raises ValidationError."""
        self._skip_if_no_gis_prereqs()

        with self.assertRaises(ValidationError):
            self.DataLayer.create(
                {
                    "name": "Invalid Choropleth",
                    "view_id": self.gis_view.id,
                    "geo_field_id": self.geo_field_id,
                    "geo_repr": "choropleth",
                }
            )

    def test_get_choropleth_config_indicator(self):
        """Test _get_choropleth_config returns indicator config."""
        self._skip_if_no_gis_prereqs()

        layer = self.DataLayer.create(
            {
                "name": "Indicator Choropleth",
                "view_id": self.gis_view.id,
                "geo_field_id": self.geo_field_id,
                "geo_repr": "choropleth",
                "indicator_layer_id": self.indicator_layer.id,
            }
        )

        config = layer._get_choropleth_config()
        self.assertIsNotNone(config)
        self.assertEqual(config["type"], "indicator")
        self.assertEqual(config["classification"], "quantile")
        self.assertEqual(config["class_count"], 5)

    def test_get_choropleth_config_basic(self):
        """Test _get_choropleth_config returns None for basic layers."""
        self._skip_if_no_gis_prereqs()

        layer = self.DataLayer.create(
            {
                "name": "Basic Layer",
                "view_id": self.gis_view.id,
                "geo_field_id": self.geo_field_id,
                "geo_repr": "basic",
            }
        )

        config = layer._get_choropleth_config()
        self.assertIsNone(config)
