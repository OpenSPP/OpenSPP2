# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for CEL Variable extension for Farmer Registry.

Tests cover:
- Extended aggregate_target Selection with farm-specific targets
- CEL expression generation for farm aggregates
- Integration with CEL service
"""

import time

from odoo.tests import TransactionCase, tagged

from .common import FarmerTestDataMixin


def _unique(base):
    """Generate unique name for test isolation."""
    return f"{base}_{int(time.time() * 1000)}"


@tagged("post_install", "-at_install")
class TestCELVariableFarmerExtension(TransactionCase, FarmerTestDataMixin):
    """Test CEL Variable farmer-specific aggregate targets."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)

        # Create test category
        cls.category = cls.env["spp.cel.variable.category"].create({
            "name": f"Farmer Test Category {cls._test_id}",
            "code": f"farmer_test_{cls._test_id}",
        })

    def test_aggregate_target_selection_extended(self):
        """Test that aggregate_target Selection includes farm targets."""
        Variable = self.env["spp.cel.variable"]

        # Get the selection field options
        selection = Variable._fields["aggregate_target"].selection
        if callable(selection):
            selection = Variable._fields["aggregate_target"].get_description(self.env)["selection"]

        selection_keys = [s[0] for s in selection]

        self.assertIn("farm_crop_activities", selection_keys)
        self.assertIn("farm_livestock_activities", selection_keys)
        self.assertIn("farm_aquaculture_activities", selection_keys)
        self.assertIn("land_parcels", selection_keys)

    def test_create_crop_count_variable(self):
        """Test creating aggregate variable for crop activities count."""
        Variable = self.env["spp.cel.variable"]

        var = Variable.create({
            "name": _unique("crop_count"),
            "cel_accessor": _unique("crop_count"),
            "source_type": "aggregate",
            "value_type": "number",
            "aggregate_type": "count",
            "aggregate_target": "farm_crop_activities",
            "aggregate_filter": "true",
            "category_id": self.category.id,
            "applies_to": "group",
        })

        self.assertEqual(var.source_type, "aggregate")
        self.assertEqual(var.aggregate_target, "farm_crop_activities")

        # Check generated CEL expression
        cel_expr = var.get_cel_expression()
        self.assertIn("farm_crop_act_ids", cel_expr)
        self.assertIn("count", cel_expr)

    def test_create_livestock_count_variable(self):
        """Test creating aggregate variable for livestock activities count."""
        Variable = self.env["spp.cel.variable"]

        var = Variable.create({
            "name": _unique("livestock_count"),
            "cel_accessor": _unique("livestock_count"),
            "source_type": "aggregate",
            "value_type": "number",
            "aggregate_type": "count",
            "aggregate_target": "farm_livestock_activities",
            "aggregate_filter": "true",
            "category_id": self.category.id,
            "applies_to": "group",
        })

        cel_expr = var.get_cel_expression()
        self.assertIn("farm_livestock_act_ids", cel_expr)

    def test_create_aquaculture_count_variable(self):
        """Test creating aggregate variable for aquaculture activities count."""
        Variable = self.env["spp.cel.variable"]

        var = Variable.create({
            "name": _unique("aquaculture_count"),
            "cel_accessor": _unique("aquaculture_count"),
            "source_type": "aggregate",
            "value_type": "number",
            "aggregate_type": "count",
            "aggregate_target": "farm_aquaculture_activities",
            "aggregate_filter": "true",
            "category_id": self.category.id,
            "applies_to": "group",
        })

        cel_expr = var.get_cel_expression()
        self.assertIn("farm_aquaculture_act_ids", cel_expr)

    def test_create_land_parcel_count_variable(self):
        """Test creating aggregate variable for land parcels count."""
        Variable = self.env["spp.cel.variable"]

        var = Variable.create({
            "name": _unique("parcel_count"),
            "cel_accessor": _unique("parcel_count"),
            "source_type": "aggregate",
            "value_type": "number",
            "aggregate_type": "count",
            "aggregate_target": "land_parcels",
            "aggregate_filter": "true",
            "category_id": self.category.id,
            "applies_to": "group",
        })

        cel_expr = var.get_cel_expression()
        self.assertIn("farm_land_rec_ids", cel_expr)

    def test_aggregate_exists_for_farm_target(self):
        """Test aggregate exists type for farm target."""
        Variable = self.env["spp.cel.variable"]

        var = Variable.create({
            "name": _unique("has_crops"),
            "cel_accessor": _unique("has_crops"),
            "source_type": "aggregate",
            "value_type": "boolean",
            "aggregate_type": "exists",
            "aggregate_target": "farm_crop_activities",
            "aggregate_filter": "true",
            "category_id": self.category.id,
            "applies_to": "group",
        })

        cel_expr = var.get_cel_expression()
        self.assertIn("farm_crop_act_ids", cel_expr)
        self.assertIn("exists", cel_expr)

    def test_aggregate_sum_for_farm_target(self):
        """Test aggregate sum type for farm target with field."""
        Variable = self.env["spp.cel.variable"]

        var = Variable.create({
            "name": _unique("total_livestock"),
            "cel_accessor": _unique("total_livestock"),
            "source_type": "aggregate",
            "value_type": "number",
            "aggregate_type": "sum",
            "aggregate_target": "farm_livestock_activities",
            "aggregate_field": "quantity",
            "aggregate_filter": "true",
            "category_id": self.category.id,
            "applies_to": "group",
        })

        cel_expr = var.get_cel_expression()
        self.assertIn("farm_livestock_act_ids", cel_expr)
        self.assertIn("sum", cel_expr)
        self.assertIn("quantity", cel_expr)

    def test_aggregate_avg_for_farm_target(self):
        """Test aggregate avg type for farm target."""
        Variable = self.env["spp.cel.variable"]

        var = Variable.create({
            "name": _unique("avg_yield"),
            "cel_accessor": _unique("avg_yield"),
            "source_type": "aggregate",
            "value_type": "number",
            "aggregate_type": "avg",
            "aggregate_target": "farm_crop_activities",
            "aggregate_field": "actual_yield",
            "aggregate_filter": "true",
            "category_id": self.category.id,
            "applies_to": "group",
        })

        cel_expr = var.get_cel_expression()
        self.assertIn("farm_crop_act_ids", cel_expr)
        self.assertIn("avg", cel_expr)

    def test_aggregate_with_filter(self):
        """Test aggregate with filter expression."""
        Variable = self.env["spp.cel.variable"]

        var = Variable.create({
            "name": _unique("rice_count"),
            "cel_accessor": _unique("rice_count"),
            "source_type": "aggregate",
            "value_type": "number",
            "aggregate_type": "count",
            "aggregate_target": "farm_crop_activities",
            "aggregate_filter": "a.species_id.code == '0113'",
            "category_id": self.category.id,
            "applies_to": "group",
        })

        cel_expr = var.get_cel_expression()
        self.assertIn("a.species_id.code == '0113'", cel_expr)

    def test_standard_members_target_still_works(self):
        """Test that standard members aggregate target still works."""
        Variable = self.env["spp.cel.variable"]

        var = Variable.create({
            "name": _unique("hh_size"),
            "cel_accessor": _unique("hh_size"),
            "source_type": "aggregate",
            "value_type": "number",
            "aggregate_type": "count",
            "aggregate_target": "members",
            "aggregate_filter": "true",
            "category_id": self.category.id,
            "applies_to": "group",
        })

        cel_expr = var.get_cel_expression()
        self.assertIn("members.count", cel_expr)


@tagged("post_install", "-at_install")
class TestCELVariableFarmerFieldTargetMapping(TransactionCase, FarmerTestDataMixin):
    """Test the target-to-field mapping in _build_aggregate_cel."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)

        cls.category = cls.env["spp.cel.variable.category"].create({
            "name": f"Mapping Test Category {cls._test_id}",
            "code": f"mapping_test_{cls._test_id}",
        })

    def test_target_field_mapping_crop(self):
        """Test farm_crop_activities maps to farm_crop_act_ids."""
        Variable = self.env["spp.cel.variable"]

        var = Variable.create({
            "name": _unique("crop_var"),
            "cel_accessor": _unique("crop_var"),
            "source_type": "aggregate",
            "value_type": "number",
            "aggregate_type": "count",
            "aggregate_target": "farm_crop_activities",
            "category_id": self.category.id,
            "applies_to": "group",
        })

        cel_expr = var.get_cel_expression()
        self.assertIn("r.farm_crop_act_ids", cel_expr)

    def test_target_field_mapping_livestock(self):
        """Test farm_livestock_activities maps to farm_livestock_act_ids."""
        Variable = self.env["spp.cel.variable"]

        var = Variable.create({
            "name": _unique("livestock_var"),
            "cel_accessor": _unique("livestock_var"),
            "source_type": "aggregate",
            "value_type": "number",
            "aggregate_type": "count",
            "aggregate_target": "farm_livestock_activities",
            "category_id": self.category.id,
            "applies_to": "group",
        })

        cel_expr = var.get_cel_expression()
        self.assertIn("r.farm_livestock_act_ids", cel_expr)

    def test_target_field_mapping_aquaculture(self):
        """Test farm_aquaculture_activities maps to farm_aquaculture_act_ids."""
        Variable = self.env["spp.cel.variable"]

        var = Variable.create({
            "name": _unique("aqua_var"),
            "cel_accessor": _unique("aqua_var"),
            "source_type": "aggregate",
            "value_type": "number",
            "aggregate_type": "count",
            "aggregate_target": "farm_aquaculture_activities",
            "category_id": self.category.id,
            "applies_to": "group",
        })

        cel_expr = var.get_cel_expression()
        self.assertIn("r.farm_aquaculture_act_ids", cel_expr)

    def test_target_field_mapping_land(self):
        """Test land_parcels maps to farm_land_rec_ids."""
        Variable = self.env["spp.cel.variable"]

        var = Variable.create({
            "name": _unique("land_var"),
            "cel_accessor": _unique("land_var"),
            "source_type": "aggregate",
            "value_type": "number",
            "aggregate_type": "count",
            "aggregate_target": "land_parcels",
            "category_id": self.category.id,
            "applies_to": "group",
        })

        cel_expr = var.get_cel_expression()
        self.assertIn("r.farm_land_rec_ids", cel_expr)
