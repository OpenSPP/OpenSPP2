# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from unittest import SkipTest

from odoo.tests.common import TransactionCase


class TestCelAreaHelpers(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "spp.area" not in cls.env:
            raise SkipTest("spp_area not installed; skipping CEL area helper tests")

        cls.service = cls.env["spp.cel.service"]

        Area = cls.env["spp.area"]
        Tag = cls.env["spp.area.tag"]
        Partner = cls.env["res.partner"]

        # Areas: Region A -> District A1, Region B
        cls.region_a = Area.create({"draft_name": "Region A", "code": "REGION_A"})
        cls.district_a1 = Area.create(
            {
                "draft_name": "District A1",
                "code": "REGION_A_1",
                "parent_id": cls.region_a.id,
            }
        )
        cls.region_b = Area.create({"draft_name": "Region B", "code": "REGION_B"})

        # Tags - search first to avoid duplicates from demo data
        cls.tag_remote = Tag.search([("code", "=", "REMOTE")], limit=1)
        if not cls.tag_remote:
            cls.tag_remote = Tag.create({"name": "Remote", "code": "REMOTE"})
        cls.tag_urban = Tag.search([("code", "=", "URBAN")], limit=1)
        if not cls.tag_urban:
            cls.tag_urban = Tag.create({"name": "Urban", "code": "URBAN"})

        cls.region_a.tag_ids = [(4, cls.tag_remote.id)]
        cls.region_b.tag_ids = [(4, cls.tag_urban.id)]

        # Individual registrants
        cls.individual_a = Partner.create(
            {
                "name": "Individual A",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.district_a1.id,
            }
        )
        cls.individual_b = Partner.create(
            {
                "name": "Individual B",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.region_b.id,
            }
        )

        # Group registrants (households)
        cls.group_a = Partner.create(
            {
                "name": "Household A",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.district_a1.id,
            }
        )
        cls.group_b = Partner.create(
            {
                "name": "Household B",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.region_b.id,
            }
        )

    def test_in_area_tree_filters_individuals_by_hierarchy(self):
        """in_area_tree(code) should include descendants of the specified area."""
        result = self.service.compile_expression(
            "in_area_tree('REGION_A')",
            "registry_individuals",
            limit=0,
        )
        self.assertTrue(result["valid"])
        self.assertIn(self.individual_a.id, result["ids"])
        self.assertNotIn(self.individual_b.id, result["ids"])

    def test_in_area_tree_filters_groups_by_hierarchy(self):
        """in_area_tree(code) should work for registry_groups as well."""
        result = self.service.compile_expression(
            "in_area_tree('REGION_A')",
            "registry_groups",
            limit=0,
        )
        self.assertTrue(result["valid"])
        self.assertIn(self.group_a.id, result["ids"])
        self.assertNotIn(self.group_b.id, result["ids"])

    def test_has_area_tag_uses_area_tags(self):
        """has_area_tag(code) should filter registrants by area tags."""
        result_remote = self.service.compile_expression(
            "has_area_tag('REMOTE')",
            "registry_individuals",
            limit=0,
        )
        self.assertTrue(result_remote["valid"])
        self.assertIn(self.individual_a.id, result_remote["ids"])
        self.assertNotIn(self.individual_b.id, result_remote["ids"])

        result_urban = self.service.compile_expression(
            "has_area_tag('URBAN')",
            "registry_individuals",
            limit=0,
        )
        self.assertTrue(result_urban["valid"])
        self.assertIn(self.individual_b.id, result_urban["ids"])
        self.assertNotIn(self.individual_a.id, result_urban["ids"])

    def test_has_any_area_tag_accepts_list(self):
        """has_any_area_tag([...]) should match when any tag is present."""
        result = self.service.compile_expression(
            "has_any_area_tag(['REMOTE', 'UNKNOWN'])",
            "registry_groups",
            limit=0,
        )
        self.assertTrue(result["valid"])
        self.assertIn(self.group_a.id, result["ids"])
        self.assertNotIn(self.group_b.id, result["ids"])
