from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestChangeRequestBase(TransactionCase):
    """Base test class for change request tests.

    Provides common setup for registrants, groups, and CR types.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cr_model = cls.env["spp.change.request"]
        cls.cr_type_model = cls.env["spp.change.request.type"]
        cls.partner_model = cls.env["res.partner"]

        # Create test registrant
        cls.registrant = cls.partner_model.create(
            {
                "name": "Test Registrant",
                "is_registrant": True,
                "is_group": False,
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

        # Get CR types by code (they may be in different modules)
        cls.cr_type_add_member = cls.cr_type_model.search([("code", "=", "add_member")], limit=1)
        if not cls.cr_type_add_member:
            # Create a minimal test type if not installed
            cls.cr_type_add_member = cls.cr_type_model.create(
                {
                    "name": "Test Add Member",
                    "code": "test_add_member",
                    "target_type": "group",
                    "detail_model": "spp.cr.detail.add_member",
                    "apply_strategy": "custom",
                    "apply_model": "spp.cr.apply.add_member",
                }
            )

        cls.cr_type_edit_individual = cls.cr_type_model.search([("code", "=", "edit_individual")], limit=1)
        if not cls.cr_type_edit_individual:
            # Create a minimal test type if not installed
            cls.cr_type_edit_individual = cls.cr_type_model.create(
                {
                    "name": "Test Edit Individual",
                    "code": "test_edit_individual",
                    "target_type": "individual",
                    "detail_model": "spp.cr.detail.edit_individual",
                    "apply_strategy": "field_mapping",
                }
            )


class TestChangeRequest(TestChangeRequestBase):
    """Tests for spp.change.request model."""

    def test_create_change_request(self):
        """Test creating a change request."""
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_add_member.id,
                "registrant_id": self.group.id,
            }
        )
        self.assertTrue(cr.id)
        self.assertTrue(cr.name.startswith("CR/"))
        self.assertEqual(cr.approval_state, "draft")
        self.assertFalse(cr.is_applied)

    def test_auto_create_detail(self):
        """Test that detail record is auto-created."""
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_add_member.id,
                "registrant_id": self.group.id,
            }
        )
        self.assertTrue(cr.detail_res_id)
        detail = cr.get_detail()
        self.assertTrue(detail)
        self.assertEqual(detail._name, "spp.cr.detail.add_member")

    def test_cannot_apply_unapproved(self):
        """Test that unapproved CR cannot be applied."""
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_add_member.id,
                "registrant_id": self.group.id,
            }
        )
        with self.assertRaises(UserError):
            cr.action_apply()

    def test_cannot_apply_twice(self):
        """Test that CR cannot be applied twice."""
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_add_member.id,
                "registrant_id": self.group.id,
            }
        )
        # Set to approved and applied state manually for test
        cr.write({"approval_state": "approved", "is_applied": True})
        with self.assertRaises(UserError):
            cr.action_apply()

    def test_display_state_computed(self):
        """Test display_state is computed correctly."""
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_add_member.id,
                "registrant_id": self.group.id,
            }
        )
        self.assertEqual(cr.display_state, "draft")

        cr.approval_state = "pending"
        self.assertEqual(cr.display_state, "pending")

        cr.approval_state = "approved"
        self.assertEqual(cr.display_state, "approved")

        cr.is_applied = True
        self.assertEqual(cr.display_state, "applied")
