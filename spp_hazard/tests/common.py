# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

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

        # Resolve CAP vocabulary codes (loaded from data/vocabulary_cap.xml)
        VocabCode = cls.env["spp.vocabulary.code"]
        cls.severity_extreme = VocabCode.get_code("urn:oasis:names:tc:cap:severity", "extreme")
        cls.severity_severe = VocabCode.get_code("urn:oasis:names:tc:cap:severity", "severe")
        cls.severity_moderate = VocabCode.get_code("urn:oasis:names:tc:cap:severity", "moderate")
        cls.severity_minor = VocabCode.get_code("urn:oasis:names:tc:cap:severity", "minor")
        cls.urgency_immediate = VocabCode.get_code("urn:oasis:names:tc:cap:urgency", "immediate")
        cls.certainty_observed = VocabCode.get_code("urn:oasis:names:tc:cap:certainty", "observed")
        cls.msg_type_alert = VocabCode.get_code("urn:oasis:names:tc:cap:msg-type", "alert")
        cls.msg_type_cancel = VocabCode.get_code("urn:oasis:names:tc:cap:msg-type", "cancel")

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
