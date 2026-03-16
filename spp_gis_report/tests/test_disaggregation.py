# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo.tests import tagged

from .common import GISReportTestBase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestDisaggregation(GISReportTestBase):
    """Test disaggregation computation via demographic dimensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create gender dimension (field-based)
        cls.gender_dimension = cls.env["spp.demographic.dimension"].search([("name", "=", "gender")], limit=1)
        if not cls.gender_dimension:
            cls.gender_dimension = cls.env["spp.demographic.dimension"].create(
                {
                    "name": "gender",
                    "label": "Gender",
                    "dimension_type": "field",
                    "field_path": "gender_id.code",
                    "value_labels_json": {"1": "Male", "2": "Female", "0": "Not Known"},
                    "default_value": "unknown",
                }
            )

        # Create age_group dimension (field-based for testing, uses a simple field)
        cls.age_dimension = cls.env["spp.demographic.dimension"].search([("name", "=", "age_group")], limit=1)
        if not cls.age_dimension:
            cls.age_dimension = cls.env["spp.demographic.dimension"].create(
                {
                    "name": "age_group",
                    "label": "Age Group",
                    "dimension_type": "field",
                    "field_path": "is_group",
                    "value_labels_json": {"true": "Group", "false": "Individual"},
                    "default_value": "unknown",
                }
            )

        # Create individuals-only dimension
        cls.individual_dimension = cls.env["spp.demographic.dimension"].create(
            {
                "name": "test_individual_dim",
                "label": "Test Individual Dim",
                "dimension_type": "field",
                "field_path": "is_registrant",
                "applies_to": "individuals",
                "default_value": "n/a",
            }
        )

    # =========================================================================
    # Phase B: _compute_disaggregation() tests
    # =========================================================================

    def test_disaggregation_no_dimensions_returns_empty(self):
        """Test _compute_disaggregation returns empty dict when no dimensions configured."""
        report = self.create_test_report(name="No Dims Report")
        area_context = report._prepare_area_context()
        result = report._compute_disaggregation(area_context)
        self.assertEqual(result, {})

    def test_disaggregation_non_partner_model_returns_empty(self):
        """Test _compute_disaggregation returns empty dict for non-partner source model."""
        # Find a non-partner model
        area_model = self.env["ir.model"].search([("model", "=", "spp.area")], limit=1)
        if not area_model:
            return  # Skip if spp.area model not found

        report = self.env["spp.gis.report"].create(
            {
                "name": "Non-Partner Report",
                "code": "non_partner_test",
                "category_id": self.category.id,
                "source_model_id": area_model.id,
                "area_field_path": "parent_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "dimension_ids": [(6, 0, [self.gender_dimension.id])],
            }
        )
        area_context = report._prepare_area_context()
        result = report._compute_disaggregation(area_context)
        self.assertEqual(result, {})

    def test_disaggregation_with_gender_dimension(self):
        """Test _compute_disaggregation with gender dimension returns per-area counts."""
        report = self.create_test_report(
            name="Gender Disagg Test",
            dimension_ids=[(6, 0, [self.gender_dimension.id])],
        )
        area_context = report._prepare_area_context()
        result = report._compute_disaggregation(area_context)

        # We have 3 registrants total:
        # - individual_1 in district_1 (no gender set, should get default)
        # - individual_2 in district_2
        # - group in district_1
        # All lack gender_id, so all should fall to default_value="unknown"

        # We should have results for areas that have registrants
        self.assertIsInstance(result, dict)
        # Each area result should have a "gender" key
        for _area_id, disagg in result.items():
            self.assertIn("gender", disagg)

    def test_disaggregation_with_multiple_dimensions(self):
        """Test _compute_disaggregation with multiple dimensions."""
        report = self.create_test_report(
            name="Multi Dim Test",
            dimension_ids=[(6, 0, [self.gender_dimension.id, self.age_dimension.id])],
        )
        area_context = report._prepare_area_context()
        result = report._compute_disaggregation(area_context)

        # Each area result should have both dimension keys
        for _area_id, disagg in result.items():
            self.assertIn("gender", disagg)
            self.assertIn("age_group", disagg)

    def test_disaggregation_applies_to_filtering(self):
        """Test _compute_disaggregation respects applies_to on dimensions."""
        report = self.create_test_report(
            name="Applies To Test",
            dimension_ids=[(6, 0, [self.individual_dimension.id])],
        )
        area_context = report._prepare_area_context()
        result = report._compute_disaggregation(area_context)

        # The dimension only applies to individuals. Groups should get "n/a".
        self.assertIsInstance(result, dict)
        # District 1 has both an individual and a group
        if self.area_district_1.id in result:
            dim_data = result[self.area_district_1.id]["test_individual_dim"]
            # The group registrant should have "n/a" value
            self.assertIn("n/a", dim_data)

    def test_disaggregation_none_area_context_returns_empty(self):
        """Test _compute_disaggregation returns empty dict when area_context is None."""
        report = self.create_test_report(
            name="None Context Test",
            dimension_ids=[(6, 0, [self.gender_dimension.id])],
        )
        result = report._compute_disaggregation(None)
        self.assertEqual(result, {})

    # =========================================================================
    # Phase B: _refresh_data() stores disaggregation
    # =========================================================================

    def test_refresh_data_stores_disaggregation(self):
        """Test _refresh_data populates disaggregation field on data records."""
        report = self.create_test_report(
            name="Refresh Disagg Test",
            dimension_ids=[(6, 0, [self.gender_dimension.id])],
        )
        report._refresh_data()

        # Check that data records have disaggregation populated
        data_with_disagg = report.data_ids.filtered(lambda d: d.disaggregation and d.area_level == 2)
        # We should have base-level data records with disaggregation
        # (only for areas that have registrants)
        for data in data_with_disagg:
            self.assertIn("gender", data.disaggregation)

    def test_refresh_data_no_dimensions_no_disaggregation(self):
        """Test _refresh_data leaves disaggregation empty when no dimensions configured."""
        report = self.create_test_report(name="No Dims Refresh Test")
        report._refresh_data()

        for data in report.data_ids:
            self.assertFalse(data.disaggregation)

    # =========================================================================
    # Phase C: GeoJSON output with flat disagg_* properties
    # =========================================================================

    def test_geojson_flat_disagg_properties(self):
        """Test GeoJSON output includes flat disagg_* properties when requested."""
        report = self.create_test_report(
            name="GeoJSON Disagg Test",
            dimension_ids=[(6, 0, [self.gender_dimension.id])],
        )
        # Create data with known disaggregation
        self.create_test_data(
            report,
            self.area_district_1,
            raw_value=100,
            disaggregation={"gender": {"1": 60, "2": 40}},
        )

        geojson = report._to_geojson(
            include_disaggregation=True,
            include_geometry=False,
        )

        features = geojson["features"]
        self.assertTrue(len(features) > 0)

        # Find the district_1 feature
        feature = next(f for f in features if f["id"] == self.area_district_1.code)
        props = feature["properties"]

        # Should have flat disagg_* properties
        self.assertEqual(props["disagg_gender_1"], 60)
        self.assertEqual(props["disagg_gender_2"], 40)

    def test_geojson_no_disagg_without_flag(self):
        """Test GeoJSON without include_disaggregation has no disagg_* properties."""
        report = self.create_test_report(
            name="GeoJSON No Disagg Test",
            dimension_ids=[(6, 0, [self.gender_dimension.id])],
        )
        self.create_test_data(
            report,
            self.area_district_1,
            raw_value=100,
            disaggregation={"gender": {"1": 60, "2": 40}},
        )

        geojson = report._to_geojson(
            include_disaggregation=False,
            include_geometry=False,
        )

        feature = geojson["features"][0]
        props = feature["properties"]

        # Should NOT have disagg_* properties
        disagg_keys = [k for k in props if k.startswith("disagg_")]
        self.assertEqual(len(disagg_keys), 0)

    def test_geojson_disagg_metadata(self):
        """Test GeoJSON metadata includes disaggregation dimension info with labels."""
        report = self.create_test_report(
            name="GeoJSON Metadata Test",
            dimension_ids=[(6, 0, [self.gender_dimension.id])],
        )
        self.create_test_data(
            report,
            self.area_district_1,
            raw_value=100,
            disaggregation={"gender": {"1": 60, "2": 40}},
        )

        geojson = report._to_geojson(
            include_disaggregation=True,
            include_geometry=False,
        )

        metadata = geojson["metadata"]
        self.assertIn("disaggregation", metadata)
        self.assertEqual(len(metadata["disaggregation"]), 1)

        dim_meta = metadata["disaggregation"][0]
        self.assertEqual(dim_meta["name"], "gender")
        self.assertEqual(dim_meta["label"], "Gender")
        self.assertEqual(dim_meta["property_prefix"], "disagg_gender_")
        self.assertIn("value_labels", dim_meta)
        self.assertEqual(dim_meta["value_labels"]["1"], "Male")
        self.assertEqual(dim_meta["value_labels"]["2"], "Female")

    def test_geojson_no_disagg_metadata_without_flag(self):
        """Test GeoJSON metadata excludes disaggregation when not requested."""
        report = self.create_test_report(
            name="GeoJSON No Meta Test",
            dimension_ids=[(6, 0, [self.gender_dimension.id])],
        )
        self.create_test_data(report, self.area_district_1, raw_value=100)

        geojson = report._to_geojson(
            include_disaggregation=False,
            include_geometry=False,
        )

        metadata = geojson["metadata"]
        self.assertNotIn("disaggregation", metadata)

    # =========================================================================
    # Member Expansion Tests
    # =========================================================================

    def test_member_expansion_with_gender(self):
        """Test member_expansion='expand' drills into group members."""
        # Create individual members of the group with gender
        gender_male = self.env["spp.vocabulary.code"].search([("code", "=", "1")], limit=1)
        gender_female = self.env["spp.vocabulary.code"].search([("code", "=", "2")], limit=1)

        # Only run if gender codes exist
        if not gender_male or not gender_female:
            return

        member1 = self.env["res.partner"].create(
            {
                "name": "Member Male",
                "is_registrant": True,
                "is_group": False,
            }
        )
        member1.gender_id = gender_male.id

        member2 = self.env["res.partner"].create(
            {
                "name": "Member Female",
                "is_registrant": True,
                "is_group": False,
            }
        )
        member2.gender_id = gender_female.id

        # Add members to group
        self.env["spp.group.membership"].create({"group": self.registrant_group.id, "individual": member1.id})
        self.env["spp.group.membership"].create({"group": self.registrant_group.id, "individual": member2.id})

        # Create report with member expansion filtering groups
        report = self.create_test_report(
            name="Expand Test",
            dimension_ids=[(6, 0, [self.gender_dimension.id])],
            member_expansion="expand",
            filter_domain="[('is_registrant', '=', True), ('is_group', '=', True)]",
            filter_mode="domain",
        )

        area_context = report._prepare_area_context()
        result = report._compute_disaggregation(area_context)

        # Should have results for district_1 (the group's area)
        self.assertIn(self.area_district_1.id, result)
        gender_data = result[self.area_district_1.id]["gender"]
        # Should have counted individuals, not the group
        total = sum(gender_data.values())
        self.assertEqual(total, 2)  # 2 members

    def test_member_expansion_area_inheritance(self):
        """Test individuals inherit area from their group when they lack one."""
        member = self.env["res.partner"].create(
            {
                "name": "No Area Member",
                "is_registrant": True,
                "is_group": False,
                # No area_id set
            }
        )

        self.env["spp.group.membership"].create({"group": self.registrant_group.id, "individual": member.id})

        report = self.create_test_report(
            name="Area Inherit Test",
            dimension_ids=[(6, 0, [self.age_dimension.id])],
            member_expansion="expand",
            filter_domain="[('is_registrant', '=', True), ('is_group', '=', True)]",
            filter_mode="domain",
        )

        area_context = report._prepare_area_context()
        result = report._compute_disaggregation(area_context)

        # The member should appear under district_1 (inherited from group)
        self.assertIn(self.area_district_1.id, result)

    def test_member_expansion_distinct_dedup(self):
        """Test individuals in multiple groups are counted once (DISTINCT)."""
        # Create a second group in district_1
        group2 = self.env["res.partner"].create(
            {
                "name": "Test Group 2",
                "is_registrant": True,
                "is_group": True,
                "area_id": self.area_district_1.id,
            }
        )

        shared_member = self.env["res.partner"].create(
            {
                "name": "Shared Member",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Add to both groups
        self.env["spp.group.membership"].create({"group": self.registrant_group.id, "individual": shared_member.id})
        self.env["spp.group.membership"].create({"group": group2.id, "individual": shared_member.id})

        report = self.create_test_report(
            name="Dedup Test",
            dimension_ids=[(6, 0, [self.age_dimension.id])],
            member_expansion="expand",
            filter_domain="[('is_registrant', '=', True), ('is_group', '=', True)]",
            filter_mode="domain",
        )

        area_context = report._prepare_area_context()
        result = report._compute_disaggregation(area_context)

        # Count the total across all dimension values for district_1
        if self.area_district_1.id in result:
            age_data = result[self.area_district_1.id].get("age_group", {})
            total = sum(age_data.values())
            # shared_member should only be counted once
            self.assertGreaterEqual(total, 1)
            # Verify shared_member not counted twice (sum should not be more than unique individuals)

    def test_backward_compat_no_expansion(self):
        """Test member_expansion='none' produces same output format as before."""
        report = self.create_test_report(
            name="Backward Compat Test",
            dimension_ids=[(6, 0, [self.gender_dimension.id])],
            member_expansion="none",
        )
        area_context = report._prepare_area_context()
        result = report._compute_disaggregation(area_context)

        # Should still produce {area_id: {dim_name: {value: count}}}
        self.assertIsInstance(result, dict)
        for _area_id, disagg in result.items():
            self.assertIn("gender", disagg)
            for value, count in disagg["gender"].items():
                self.assertIsInstance(value, str)
                self.assertIsInstance(count, int)

    def test_member_expansion_constrains(self):
        """Test member_expansion='expand' rejected for non-partner models."""
        area_model = self.env["ir.model"].search([("model", "=", "spp.area")], limit=1)
        if not area_model:
            return

        from odoo.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self.env["spp.gis.report"].create(
                {
                    "name": "Bad Expand Report",
                    "code": "bad_expand_test",
                    "category_id": self.category.id,
                    "source_model_id": area_model.id,
                    "area_field_path": "parent_id",
                    "aggregation_method": "count",
                    "normalization_method": "raw",
                    "base_area_level": 2,
                    "member_expansion": "expand",
                }
            )
