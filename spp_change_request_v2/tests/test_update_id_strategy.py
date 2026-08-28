# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Update ID Document strategy."""

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase

from .common import get_or_create_cr_type


class TestUpdateIDStrategy(TransactionCase):
    """Tests for Update ID Document custom strategy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.id_model = cls.env["spp.registry.id"]
        cls.id_type_model = cls.env["spp.id.type"]
        cls.cr_model = cls.env["spp.change.request"]

        # Get or create ID types
        cls.national_id_type = cls.id_type_model.search([("name", "=", "Test National ID")], limit=1)
        if not cls.national_id_type:
            cls.national_id_type = cls.id_type_model.create(
                {
                    "name": "Test National ID",
                    "namespace_uri": "urn:test:national-id",
                }
            )

        cls.passport_type = cls.id_type_model.search([("name", "=", "Test Passport")], limit=1)
        if not cls.passport_type:
            cls.passport_type = cls.id_type_model.create(
                {
                    "name": "Test Passport",
                    "namespace_uri": "urn:test:passport",
                }
            )

        # Create test individual
        cls.individual = cls.partner_model.create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create existing ID
        cls.existing_id = cls.id_model.create(
            {
                "partner_id": cls.individual.id,
                "id_type_id": cls.national_id_type.id,
                "value": "NID-12345",
                "status": "valid",
            }
        )

        # Get or create CR type
        cls.cr_type = get_or_create_cr_type(cls.env, "update_id")

    def test_add_new_id(self):
        """Test adding new ID document."""

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.individual.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "operation": "add",
                "id_type_id": self.passport_type.id,
                "id_value": "PP-67890",
                "expiry_date": fields.Date.today(),
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify new ID created
        self.assertTrue(cr.is_applied)

        new_id = self.id_model.search(
            [
                ("partner_id", "=", self.individual.id),
                ("id_type_id", "=", self.passport_type.id),
            ]
        )
        self.assertTrue(new_id)
        self.assertEqual(new_id.value, "PP-67890")
        self.assertEqual(new_id.status, "valid")

    def test_add_duplicate_id_type_fails(self):
        """Test adding duplicate ID type fails."""

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.individual.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "operation": "add",
                "id_type_id": self.national_id_type.id,  # Already exists
                "id_value": "NID-99999",
            }
        )

        cr.approval_state = "approved"

        with self.assertRaises(UserError) as cm:
            cr.action_apply()

        self.assertIn("already", str(cm.exception).lower())

    def test_update_existing_id(self):
        """Test updating existing ID document."""

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.individual.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "operation": "update",
                "existing_id_record_id": self.existing_id.id,
                "id_type_id": self.national_id_type.id,
                "id_value": "NID-UPDATED",
                "expiry_date": fields.Date.today(),
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify ID updated
        self.assertTrue(cr.is_applied)
        self.assertEqual(self.existing_id.value, "NID-UPDATED")

    def test_remove_id(self):
        """Test removing (invalidating) ID document."""

        # Create ID to remove
        id_to_remove = self.id_model.create(
            {
                "partner_id": self.individual.id,
                "id_type_id": self.passport_type.id,
                "value": "PP-REMOVE",
                "status": "valid",
            }
        )

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.individual.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "operation": "remove",
                "existing_id_record_id": id_to_remove.id,
                "id_type_id": self.passport_type.id,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify ID invalidated
        self.assertTrue(cr.is_applied)
        self.assertEqual(id_to_remove.status, "invalid")

    def test_readd_same_type_after_removal(self):
        """OP#1136: removing an ID must free its type for a replacement.

        The reported bug end to end — a removed ID is kept and marked Invalid,
        and both the duplicate check here and the uniqueness rule on
        spp.registry.id counted that dead row, so the registrant was left with
        an Invalid ID and no way to add a valid one of the same type.
        """
        original = self.id_model.create(
            {
                "partner_id": self.individual.id,
                "id_type_id": self.passport_type.id,
                "value": "PP-ORIGINAL",
                "status": "valid",
            }
        )

        removal = self.cr_model.create({"request_type_id": self.cr_type.id, "registrant_id": self.individual.id})
        removal.get_detail().write(
            {
                "operation": "remove",
                "existing_id_record_id": original.id,
                "id_type_id": self.passport_type.id,
            }
        )
        removal.approval_state = "approved"
        removal.action_apply()
        self.assertEqual(original.status, "invalid")

        # The replacement, through the same change-request route.
        replacement = self.cr_model.create({"request_type_id": self.cr_type.id, "registrant_id": self.individual.id})
        replacement.get_detail().write(
            {
                "operation": "add",
                "id_type_id": self.passport_type.id,
                "id_value": "PP-REPLACEMENT",
            }
        )
        replacement.approval_state = "approved"
        replacement.action_apply()

        self.assertTrue(replacement.is_applied)
        live = self.id_model.search(
            [
                ("partner_id", "=", self.individual.id),
                ("id_type_id", "=", self.passport_type.id),
                ("status", "!=", "invalid"),
            ]
        )
        self.assertEqual(len(live), 1, "exactly one live ID of that type should remain")
        self.assertEqual(live.value, "PP-REPLACEMENT")
        self.assertEqual(original.status, "invalid", "the removed ID stays on file as Invalid")

    def test_update_without_existing_id_fails(self):
        """Test update operation requires existing ID."""

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.individual.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "operation": "update",
                # No existing_id_record_id
                "id_type_id": self.national_id_type.id,
                "id_value": "NEW-VALUE",
            }
        )

        cr.approval_state = "approved"

        with self.assertRaises(UserError) as cm:
            cr.action_apply()

        self.assertIn("existing", str(cm.exception).lower())

    def test_add_requires_value(self):
        """Test add operation requires ID value."""

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.individual.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "operation": "add",
                "id_type_id": self.passport_type.id,
                # No id_value
            }
        )

        cr.approval_state = "approved"

        with self.assertRaises(UserError) as cm:
            cr.action_apply()

        self.assertIn("value", str(cm.exception).lower())

    def test_update_id_preview(self):
        """Test preview returns expected structure."""

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.individual.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "operation": "add",
                "id_type_id": self.passport_type.id,
                "id_value": "PP-PREVIEW",
            }
        )

        preview = cr.action_preview_changes()

        self.assertIn("_action", preview)
        self.assertEqual(preview["_action"], "add_id")
        self.assertIn("_header", preview)
        self.assertEqual(preview["_header"], "Add New ID")
