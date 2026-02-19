# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Merge Registrants strategy."""

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase

from .common import get_or_create_cr_type


class TestMergeRegistrantsStrategy(TransactionCase):
    """Tests for Merge Registrants custom strategy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.membership_model = cls.env["spp.group.membership"]
        cls.id_model = cls.env["spp.registry.id"]
        cls.id_type_model = cls.env["spp.id.type"]
        cls.cr_model = cls.env["spp.change.request"]

        # Create ID type
        cls.id_type = cls.id_type_model.create(
            {
                "name": "Test ID",
                "namespace_uri": "urn:test:merge-id",
            }
        )

        # Create test group
        cls.group = cls.partner_model.create(
            {
                "name": "Test Group",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create primary individual
        cls.primary = cls.partner_model.create(
            {
                "name": "Primary Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create duplicate individuals
        cls.duplicate1 = cls.partner_model.create(
            {
                "name": "Duplicate 1",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.duplicate2 = cls.partner_model.create(
            {
                "name": "Duplicate 2",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create membership for duplicate (to test merge)
        cls.dup_membership = cls.membership_model.create(
            {
                "group": cls.group.id,
                "individual": cls.duplicate1.id,
                "start_date": fields.Datetime.now(),
            }
        )

        # Create ID for duplicate (to test merge)
        cls.dup_id = cls.id_model.create(
            {
                "partner_id": cls.duplicate1.id,
                "id_type_id": cls.id_type.id,
                "value": "DUP-ID-123",
                "status": "valid",
            }
        )

        # Get or create CR type
        cls.cr_type = get_or_create_cr_type(cls.env, "merge_registrants")

    def test_merge_deactivates_duplicates(self):
        """Test merging deactivates duplicate registrants."""

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.primary.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "duplicate_registrant_ids": [(6, 0, [self.duplicate2.id])],
                "reason": "duplicate_entry",
                "merge_strategy": "keep_primary",
                "is_deactivate_duplicates": True,
                "is_merge_memberships": False,
                "is_merge_ids": False,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify duplicate deactivated
        self.assertTrue(cr.is_applied)
        self.assertTrue(self.duplicate2.disabled)

    def test_merge_transfers_memberships(self):
        """Test merging transfers memberships to primary."""

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.primary.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "duplicate_registrant_ids": [(6, 0, [self.duplicate1.id])],
                "reason": "duplicate_entry",
                "merge_strategy": "keep_primary",
                "is_merge_memberships": True,
                "is_merge_ids": False,
                "is_deactivate_duplicates": True,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify membership transferred
        self.assertTrue(cr.is_applied)
        self.assertEqual(self.dup_membership.individual.id, self.primary.id)

    def test_merge_transfers_ids(self):
        """Test merging transfers IDs to primary."""

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.primary.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "duplicate_registrant_ids": [(6, 0, [self.duplicate1.id])],
                "reason": "data_quality",
                "merge_strategy": "keep_primary",
                "is_merge_memberships": False,
                "is_merge_ids": True,
                "is_deactivate_duplicates": True,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify ID transferred
        self.assertTrue(cr.is_applied)
        self.assertEqual(self.dup_id.partner_id.id, self.primary.id)

    def test_merge_multiple_duplicates(self):
        """Test merging multiple duplicates at once."""

        # Create more duplicates
        dup3 = self.partner_model.create(
            {
                "name": "Duplicate 3",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.primary.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "duplicate_registrant_ids": [(6, 0, [self.duplicate2.id, dup3.id])],
                "reason": "system_migration",
                "merge_strategy": "keep_primary",
                "is_deactivate_duplicates": True,
                "is_merge_memberships": False,
                "is_merge_ids": False,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify all duplicates deactivated
        self.assertTrue(cr.is_applied)
        self.assertTrue(self.duplicate2.disabled)
        self.assertTrue(dup3.disabled)

    def test_merge_same_type_only(self):
        """Test cannot merge individuals with groups."""

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.primary.id,  # Individual
            }
        )

        detail = cr.get_detail()

        with self.assertRaises(ValidationError):
            detail.write(
                {
                    "duplicate_registrant_ids": [(6, 0, [self.group.id])],  # Group
                    "reason": "other",
                    "merge_strategy": "keep_primary",
                }
            )

    def test_merge_cannot_include_primary(self):
        """Test cannot include primary in duplicates list."""

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.primary.id,
            }
        )

        detail = cr.get_detail()

        with self.assertRaises(ValidationError):
            detail.write(
                {
                    "duplicate_registrant_ids": [(6, 0, [self.primary.id])],  # Same as primary
                    "reason": "other",
                    "merge_strategy": "keep_primary",
                }
            )

    def test_merge_all_reasons(self):
        """Test all merge reasons work."""

        reasons = [
            "duplicate_entry",
            "system_migration",
            "household_merge",
            "data_quality",
            "other",
        ]

        for reason in reasons:
            primary = self.partner_model.create(
                {
                    "name": f"Primary {reason}",
                    "is_registrant": True,
                    "is_group": False,
                }
            )
            duplicate = self.partner_model.create(
                {
                    "name": f"Duplicate {reason}",
                    "is_registrant": True,
                    "is_group": False,
                }
            )

            cr = self.cr_model.create(
                {
                    "request_type_id": self.cr_type.id,
                    "registrant_id": primary.id,
                }
            )

            detail = cr.get_detail()
            detail.write(
                {
                    "duplicate_registrant_ids": [(6, 0, [duplicate.id])],
                    "reason": reason,
                    "merge_strategy": "keep_primary",
                    "is_deactivate_duplicates": True,
                    "is_merge_memberships": False,
                    "is_merge_ids": False,
                }
            )

            cr.approval_state = "approved"
            cr.action_apply()

            self.assertTrue(cr.is_applied, f"Failed for reason: {reason}")

    def test_merge_preview(self):
        """Test preview returns expected structure."""

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.primary.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "duplicate_registrant_ids": [(6, 0, [self.duplicate2.id])],
                "reason": "duplicate_entry",
                "merge_strategy": "keep_primary",
                "is_merge_memberships": True,
                "is_merge_ids": True,
                "is_deactivate_duplicates": True,
            }
        )

        preview = cr.action_preview_changes()

        self.assertIn("_action", preview)
        self.assertEqual(preview["_action"], "merge_registrants")
        self.assertEqual(preview["duplicate_count"], 1)
