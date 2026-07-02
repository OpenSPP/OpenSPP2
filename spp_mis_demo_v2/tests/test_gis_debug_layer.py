# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for MIS demo household-points debug GIS layer."""

from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_mis_demo_v2.models.indicator_providers import (
    DEBUG_HH_POINTS_LAYER_DOMAIN,
    DEBUG_HH_POINTS_LAYER_NAME,
    _ensure_household_points_debug_layer,
)


@tagged("post_install", "-at_install")
class TestGISDebugLayer(TransactionCase):
    """Validate HH points debug layer creation and defaults."""

    def test_household_points_debug_layer_exists_and_disabled_on_startup(self):
        """Post-init should provide HH points debug layer in a safe default state."""
        layer = self.env["spp.gis.data.layer"].search(
            [("name", "=", DEBUG_HH_POINTS_LAYER_NAME)],
            limit=1,
        )
        self.assertTrue(layer, "Expected HH points debug layer to be created")
        self.assertEqual(layer.geo_field_id.model, "res.partner")
        self.assertEqual(layer.geo_field_id.name, "coordinates")
        self.assertFalse(layer.active_on_startup, "Debug layer must be disabled by default")
        self.assertEqual(layer.domain, DEBUG_HH_POINTS_LAYER_DOMAIN)

    def test_household_points_debug_layer_setup_is_idempotent(self):
        """Running helper repeatedly should update existing layer, not duplicate it."""
        layer_model = self.env["spp.gis.data.layer"]
        before_count = layer_model.search_count([("name", "=", DEBUG_HH_POINTS_LAYER_NAME)])

        _ensure_household_points_debug_layer(self.env)

        after_count = layer_model.search_count([("name", "=", DEBUG_HH_POINTS_LAYER_NAME)])
        self.assertEqual(before_count, after_count)

    def test_generator_reensures_household_points_debug_layer(self):
        """Generator flow should re-ensure debug layer for --generate workflows."""
        layer_model = self.env["spp.gis.data.layer"]
        layer_model.search([("name", "=", DEBUG_HH_POINTS_LAYER_NAME)]).unlink()

        generator = self.env["spp.mis.demo.generator"].create({"name": "GIS Debug Layer Ensure"})
        stats = {}
        generator._ensure_debug_gis_layers(stats)

        layer = layer_model.search([("name", "=", DEBUG_HH_POINTS_LAYER_NAME)], limit=1)
        self.assertTrue(layer)
        self.assertFalse(layer.active_on_startup)
        self.assertTrue(stats.get("debug_hh_points_layer_ready"))
