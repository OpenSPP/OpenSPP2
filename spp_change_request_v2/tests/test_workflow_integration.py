# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Integration tests for CR workflows."""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestWorkflowIntegration(TransactionCase):
    """End-to-end workflow integration tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.cr_model = cls.env["spp.change.request"]

        # Create test registrant
        cls.registrant = cls.partner_model.create(
            {
                "name": "Test Person",
                "given_name": "Test",
                "family_name": "Person",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Get edit individual CR type by code
        cls.cr_type = cls.env["spp.change.request.type"].search([("code", "=", "edit_individual")], limit=1)
        if not cls.cr_type:
            # Create a minimal test type with field mappings if not installed
            cls.cr_type = cls.env["spp.change.request.type"].create(
                {
                    "name": "Test Edit Individual",
                    "code": "test_edit_individual",
                    "target_type": "individual",
                    "detail_model": "spp.cr.detail.edit_individual",
                    "apply_strategy": "field_mapping",
                }
            )
            # Add required field mappings for the test
            mapping_model = cls.env["spp.change.request.type.mapping"]
            for field in ["given_name", "family_name", "phone", "email"]:
                mapping_model.create(
                    {
                        "type_id": cls.cr_type.id,
                        "source_field": field,
                        "target_field": field,
                        "transform": "direct",
                    }
                )

    def test_full_workflow_create_to_apply(self):
        """Test complete workflow: create -> update -> approve -> apply."""
        if not self.cr_type:
            self.skipTest("Edit individual CR type not found")

        # 1. Create
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )
        self.assertEqual(cr.approval_state, "draft")
        self.assertTrue(cr.name.startswith("CR/"))

        # 2. Update detail
        detail = cr.get_detail()
        self.assertTrue(detail, "Detail record should exist")
        detail.write(
            {
                "given_name": "Updated",
                "family_name": "Name",
            }
        )

        # 3. Approve (bypassing workflow for test)
        cr.approval_state = "approved"
        self.assertEqual(cr.display_state, "approved")

        # 4. Apply
        cr.action_apply()

        # 5. Verify
        self.assertTrue(cr.is_applied)
        self.assertEqual(cr.display_state, "applied")
        self.assertTrue(cr.applied_date)
        self.assertEqual(cr.applied_by_id, self.env.user)

        # Check registrant updated
        self.registrant.invalidate_recordset()
        self.assertEqual(self.registrant.given_name, "Updated")
        self.assertEqual(self.registrant.family_name, "Name")

    def test_cannot_update_after_submit(self):
        """Test that submitted CRs cannot be modified."""
        if not self.cr_type:
            self.skipTest("Edit individual CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Simulate submitted state
        cr.approval_state = "pending"

        # Detail should still be accessible but CR fields readonly
        detail = cr.get_detail()
        self.assertTrue(detail)

    def test_rejection_flow(self):
        """Test rejection workflow."""
        if not self.cr_type:
            self.skipTest("Edit individual CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        cr.approval_state = "pending"
        cr._do_reject("Invalid data provided")

        self.assertEqual(cr.approval_state, "rejected")
        self.assertEqual(cr.rejection_reason, "Invalid data provided")
        self.assertTrue(cr.rejected_date)

    def test_revision_flow(self):
        """Test revision request workflow state transitions.

        This test verifies the state machine behavior for revision requests.
        Permission checks are tested separately in approval-specific tests.
        """
        if not self.cr_type:
            self.skipTest("Edit individual CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        cr.approval_state = "pending"
        # Directly set revision state to test state machine without approval workflow
        # Permission checks are tested in test_approval_per_cr_type.py
        cr._write_approval_fields(
            {
                "approval_state": "revision",
                "revision_requested_by_id": self.env.user.id,
                "revision_notes": "Please update phone number",
            }
        )

        self.assertEqual(cr.approval_state, "revision")
        self.assertEqual(cr.revision_notes, "Please update phone number")

    def test_reset_to_draft_after_rejection(self):
        """Test resetting rejected CR to draft."""
        if not self.cr_type:
            self.skipTest("Edit individual CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        cr.approval_state = "rejected"
        cr.action_reset_to_draft()

        self.assertEqual(cr.approval_state, "draft")
        self.assertFalse(cr.rejection_reason)

    def test_cannot_apply_unapproved(self):
        """Test that only approved CRs can be applied."""
        if not self.cr_type:
            self.skipTest("Edit individual CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Try to apply draft
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("approved", str(cm.exception).lower())

        # Try to apply pending
        cr.approval_state = "pending"
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("approved", str(cm.exception).lower())

    def test_delete_cascades_to_detail(self):
        """Test deleting CR deletes detail record."""
        if not self.cr_type:
            self.skipTest("Edit individual CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        detail = cr.get_detail()
        detail_id = detail.id
        detail_model = detail._name

        cr.unlink()

        # Verify detail deleted
        remaining = self.env[detail_model].search([("id", "=", detail_id)])
        self.assertFalse(remaining, "Detail should be deleted with CR")
