# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase


class TestAreaTags(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                queue_job__no_delay=True,
            )
        )

    def test_create_area_tag_and_assign_to_area(self):
        """Area tags can be created and linked to areas."""
        Area = self.env["spp.area"]
        Tag = self.env["spp.area.tag"]

        area = Area.create({"draft_name": "Tagged Area"})
        # Search before create to avoid unique constraint violation
        tag = Tag.search([("code", "=", "REMOTE")], limit=1)
        if not tag:
            tag = Tag.create(
                {
                    "name": "Remote",
                    "code": "REMOTE",
                }
            )

        area.tag_ids = [(4, tag.id)]
        self.assertIn(tag, area.tag_ids)
        self.assertIn(area, tag.area_ids)

    def test_area_tag_code_is_unique(self):
        """Tag code must be unique across tags."""
        Tag = self.env["spp.area.tag"]

        # Use a unique test code to avoid conflicts with demo data
        test_code = "TEST_UNIQUE_CODE"

        # Ensure the test code doesn't exist yet
        existing = Tag.search([("code", "=", test_code)], limit=1)
        if existing:
            existing.unlink()

        Tag.create(
            {
                "name": "Test Unique Tag",
                "code": test_code,
            }
        )

        with self.assertRaises(IntegrityError):
            # Duplicate code should violate SQL constraint
            Tag.create(
                {
                    "name": "Test Unique Tag Duplicate",
                    "code": test_code,
                }
            )
