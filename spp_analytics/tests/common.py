# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.tests.common import TransactionCase


class AnalyticsTestCase(TransactionCase):
    """Base test case for aggregation module tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test areas
        cls.area_country = cls.env["spp.area"].create(
            {
                "draft_name": "Test Country",
                "code": "TC",
            }
        )
        cls.area_region = cls.env["spp.area"].create(
            {
                "draft_name": "Test Region",
                "code": "TR",
                "parent_id": cls.area_country.id,
            }
        )
        cls.area_district = cls.env["spp.area"].create(
            {
                "draft_name": "Test District",
                "code": "TD",
                "parent_id": cls.area_region.id,
            }
        )

        # Get or create area tags (may already exist from demo data)
        cls.tag_urban = cls.env["spp.area.tag"].search([("code", "=", "URBAN")], limit=1)
        if not cls.tag_urban:
            cls.tag_urban = cls.env["spp.area.tag"].create(
                {
                    "name": "Urban",
                    "code": "URBAN",
                }
            )
        cls.tag_rural = cls.env["spp.area.tag"].search([("code", "=", "RURAL")], limit=1)
        if not cls.tag_rural:
            cls.tag_rural = cls.env["spp.area.tag"].create(
                {
                    "name": "Rural",
                    "code": "RURAL",
                }
            )
        cls.area_district.tag_ids = [(4, cls.tag_urban.id)]

        # Create test registrants
        cls.registrants = cls._create_test_registrants()

    @classmethod
    def _create_test_registrants(cls):
        """Create a set of test registrants with various attributes."""
        Partner = cls.env["res.partner"]
        registrants = Partner.browse()

        # Create 20 test registrants with varied attributes
        for i in range(20):
            vals = {
                "name": f"Test Registrant {i}",
                "is_registrant": True,
                "is_group": i >= 15,  # Last 5 are groups
                "area_id": cls.area_district.id if i < 10 else cls.area_region.id,
            }
            registrants |= Partner.create(vals)

        return registrants

    def create_scope(self, scope_type, **kwargs):
        """Helper to create aggregation scopes."""
        vals = {
            "name": f"Test {scope_type} Scope",
            "scope_type": scope_type,
        }
        vals.update(kwargs)
        return self.env["spp.analytics.scope"].create(vals)

    def create_access_rule(self, access_level, **kwargs):
        """Helper to create access rules."""
        vals = {
            "name": f"Test {access_level} Rule",
            "access_level": access_level,
            "group_id": self.env.ref("base.group_user").id,
        }
        vals.update(kwargs)
        return self.env["spp.analytics.access.rule"].create(vals)
