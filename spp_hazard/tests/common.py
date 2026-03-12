# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests.common import TransactionCase


class HazardTestCase(TransactionCase):
    """Base test case for hazard module tests with common setup."""

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

        # Create test area
        cls.area = cls.env["spp.area"].create(
            {
                "draft_name": "Test Area",
                "code": "TEST-AREA-001",
            }
        )

        # Create test registrant
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Test Registrant",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area.id,
            }
        )

        # Create parent hazard category
        cls.category_natural = cls.env["spp.hazard.category"].create(
            {
                "name": "Natural Disaster",
                "code": "NATURAL_TEST",
            }
        )

        # Create child hazard category
        cls.category_typhoon = cls.env["spp.hazard.category"].create(
            {
                "name": "Typhoon",
                "code": "TYPHOON_TEST",
                "parent_id": cls.category_natural.id,
            }
        )

        # Create impact type
        cls.impact_type_displacement = cls.env["spp.hazard.impact.type"].create(
            {
                "name": "Displacement",
                "code": "DISPLACEMENT_TEST",
                "category": "physical",
            }
        )

        cls.impact_type_property = cls.env["spp.hazard.impact.type"].create(
            {
                "name": "Property Damage",
                "code": "PROPERTY_TEST",
                "category": "physical",
            }
        )

        # Create test users for security tests
        base_group = Command.link(cls.env.ref("base.group_user").id)
        cls.hazard_viewer = cls.env["res.users"].create(
            {
                "name": "Hazard Viewer",
                "login": "hazard_viewer_test",
                "group_ids": [
                    base_group,
                    Command.link(cls.env.ref("spp_hazard.group_hazard_viewer").id),
                ],
            }
        )
        cls.hazard_officer = cls.env["res.users"].create(
            {
                "name": "Hazard Officer",
                "login": "hazard_officer_test",
                "group_ids": [
                    base_group,
                    Command.link(cls.env.ref("spp_hazard.group_hazard_officer").id),
                ],
            }
        )
        cls.hazard_manager = cls.env["res.users"].create(
            {
                "name": "Hazard Manager",
                "login": "hazard_manager_test",
                "group_ids": [
                    base_group,
                    Command.link(cls.env.ref("spp_hazard.group_hazard_manager").id),
                ],
            }
        )
