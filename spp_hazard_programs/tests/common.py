# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase


class HazardProgramsTestCase(TransactionCase):
    """Base test case for hazard programs integration tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                queue_job__no_delay=True,
                tracking_disable=True,
            )
        )

        # Create test area
        cls.area = cls.env["spp.area"].create(
            {
                "draft_name": "Test Area",
                "code": "HP-TEST-AREA-001",
            }
        )

        # Create hazard category
        cls.category = cls.env["spp.hazard.category"].create(
            {
                "name": "Typhoon",
                "code": "HP-TYPHOON-TEST",
            }
        )

        # Create impact type
        cls.impact_type = cls.env["spp.hazard.impact.type"].create(
            {
                "name": "Property Damage",
                "code": "HP-PROPERTY-TEST",
                "category": "physical",
            }
        )

        # Create test registrants
        cls.registrant_1 = cls.env["res.partner"].create(
            {
                "name": "Test Registrant 1",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area.id,
            }
        )
        cls.registrant_2 = cls.env["res.partner"].create(
            {
                "name": "Test Registrant 2",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area.id,
            }
        )
        cls.registrant_3 = cls.env["res.partner"].create(
            {
                "name": "Test Registrant 3",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area.id,
            }
        )

        # Create test incidents
        cls.incident_active = cls.env["spp.hazard.incident"].create(
            {
                "name": "Active Typhoon",
                "code": "HP-INC-ACTIVE",
                "category_id": cls.category.id,
                "start_date": "2024-01-01",
                "status": "active",
            }
        )
        cls.incident_closed = cls.env["spp.hazard.incident"].create(
            {
                "name": "Closed Typhoon",
                "code": "HP-INC-CLOSED",
                "category_id": cls.category.id,
                "start_date": "2024-01-01",
                "end_date": "2024-02-01",
                "status": "closed",
            }
        )

        # Create test program
        cls.program = cls.env["spp.program"].create(
            {
                "name": "Emergency Relief Program",
            }
        )

        # Create impacts with varying damage levels and verification statuses
        cls.impact_verified_critical = cls.env["spp.hazard.impact"].create(
            {
                "incident_id": cls.incident_active.id,
                "registrant_id": cls.registrant_1.id,
                "impact_type_id": cls.impact_type.id,
                "impact_date": "2024-01-02",
                "damage_level": "critical",
                "verification_status": "verified",
            }
        )
        cls.impact_verified_moderate = cls.env["spp.hazard.impact"].create(
            {
                "incident_id": cls.incident_active.id,
                "registrant_id": cls.registrant_2.id,
                "impact_type_id": cls.impact_type.id,
                "impact_date": "2024-01-02",
                "damage_level": "moderate",
                "verification_status": "verified",
            }
        )
        cls.impact_unverified = cls.env["spp.hazard.impact"].create(
            {
                "incident_id": cls.incident_active.id,
                "registrant_id": cls.registrant_3.id,
                "impact_type_id": cls.impact_type.id,
                "impact_date": "2024-01-02",
                "damage_level": "severe",
                "verification_status": "reported",
            }
        )
