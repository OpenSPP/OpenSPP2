"""Tests for Change Request UX Improvement Wizards.

Tests cover:
- Creation wizard (spp.cr.create.wizard)
- Batch approval wizard (spp.cr.batch.approval.wizard)
- Conflict comparison wizard (spp.cr.conflict.comparison.wizard)
"""

from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_change_request import TestChangeRequestBase


@tagged("post_install", "-at_install", "cr_ux")
class TestCreateWizard(TestChangeRequestBase):
    """Tests for the creation wizard."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

    def test_wizard_type_selection(self):
        """Test wizard type selection field."""
        wizard = self.env["spp.cr.create.wizard"].create({})

        # Initial state - no type selected
        self.assertFalse(wizard.request_type_id)
        self.assertFalse(wizard.show_registrant)

        # Select a type
        cr_type = self.env["spp.change.request.type"].search([], limit=1)
        wizard.request_type_id = cr_type

        # Now registrant field should be visible
        self.assertTrue(wizard.show_registrant)

    def test_wizard_registrant_selection(self):
        """Test wizard registrant selection."""
        cr_type = self.env["spp.change.request.type"].search([], limit=1)
        wizard = self.env["spp.cr.create.wizard"].create(
            {
                "request_type_id": cr_type.id,
            }
        )

        self.assertTrue(wizard.show_registrant)

        # Select a registrant
        wizard.registrant_id = self.group

        # Should have registrant info computed
        self.assertTrue(wizard.registrant_info_html)

    def test_wizard_create_draft_requires_type(self):
        """Test create draft requires type selection."""
        wizard = self.env["spp.cr.create.wizard"].create(
            {
                "registrant_id": self.group.id,
            }
        )

        with self.assertRaises(UserError):
            wizard.action_create_draft()

    def test_wizard_create_draft_requires_registrant(self):
        """Test create draft requires registrant selection."""
        cr_type = self.env["spp.change.request.type"].search([], limit=1)
        wizard = self.env["spp.cr.create.wizard"].create(
            {
                "request_type_id": cr_type.id,
            }
        )

        with self.assertRaises(UserError):
            wizard.action_create_draft()

    def test_wizard_create_draft_success(self):
        """Test successful draft creation from wizard."""
        cr_type = self.env["spp.change.request.type"].search([], limit=1)
        wizard = self.env["spp.cr.create.wizard"].create(
            {
                "request_type_id": cr_type.id,
                "registrant_id": self.group.id,
            }
        )

        result = wizard.action_create_draft()

        # Should return client action that closes modal then opens form
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "open_cr_close_modal")
        params = result["params"]
        self.assertTrue(params["res_id"])

        # If CR type has a detail model, wizard opens detail form directly
        # Otherwise, it falls back to CR form
        if cr_type.detail_model:
            # Opened detail form
            self.assertEqual(params["res_model"], cr_type.detail_model)
            detail = self.env[cr_type.detail_model].browse(params["res_id"])
            self.assertTrue(detail.exists())
            # Verify the CR was created and linked
            cr = detail.change_request_id
            self.assertTrue(cr.exists())
            self.assertEqual(cr.request_type_id, cr_type)
            self.assertEqual(cr.registrant_id, self.group)
            self.assertEqual(cr.approval_state, "draft")
        else:
            # Opened CR form (fallback)
            self.assertEqual(params["res_model"], "spp.change.request")
            cr = self.env["spp.change.request"].browse(params["res_id"])
            self.assertTrue(cr.exists())
            self.assertEqual(cr.request_type_id, cr_type)
            self.assertEqual(cr.registrant_id, self.group)
            self.assertEqual(cr.approval_state, "draft")

    def test_wizard_registrant_domain_filter_group(self):
        """Test registrant domain is computed correctly for group target type."""
        cr_type_group = self.env["spp.change.request.type"].search([("target_type", "=", "group")], limit=1)

        if cr_type_group:
            wizard = self.env["spp.cr.create.wizard"].create(
                {
                    "request_type_id": cr_type_group.id,
                }
            )
            self.assertIn("is_group", wizard.registrant_domain)
            self.assertIn("True", wizard.registrant_domain)

    def test_wizard_registrant_domain_filter_individual(self):
        """Test registrant domain is computed correctly for individual target type."""
        cr_type_individual = self.env["spp.change.request.type"].search([("target_type", "=", "individual")], limit=1)

        if cr_type_individual:
            wizard = self.env["spp.cr.create.wizard"].create(
                {
                    "request_type_id": cr_type_individual.id,
                }
            )
            self.assertIn("is_group", wizard.registrant_domain)
            self.assertIn("False", wizard.registrant_domain)

    def test_wizard_validates_target_type_group(self):
        """Test wizard validates registrant matches group target type."""
        cr_type_group = self.env["spp.change.request.type"].search([("target_type", "=", "group")], limit=1)

        if not cr_type_group:
            self.skipTest("No CR type with group target")

        # Try to create with individual registrant for group type
        individual = self.env["res.partner"].search(
            [
                ("is_registrant", "=", True),
                ("is_group", "=", False),
            ],
            limit=1,
        )

        if not individual:
            self.skipTest("No individual registrant found")

        wizard = self.env["spp.cr.create.wizard"].create(
            {
                "request_type_id": cr_type_group.id,
                "registrant_id": individual.id,
            }
        )

        with self.assertRaises(UserError):
            wizard.action_create_draft()

    def test_wizard_validates_target_type_individual(self):
        """Test wizard validates registrant matches individual target type."""
        cr_type_individual = self.env["spp.change.request.type"].search([("target_type", "=", "individual")], limit=1)

        if not cr_type_individual:
            self.skipTest("No CR type with individual target")

        # Try to create with group registrant for individual type
        wizard = self.env["spp.cr.create.wizard"].create(
            {
                "request_type_id": cr_type_individual.id,
                "registrant_id": self.group.id,
            }
        )

        with self.assertRaises(UserError):
            wizard.action_create_draft()

    def test_wizard_prefills_from_context(self):
        """Test wizard pre-fills registrant from context."""
        wizard = (
            self.env["spp.cr.create.wizard"]
            .with_context(
                active_model="res.partner",
                active_id=self.group.id,
            )
            .create({})
        )

        self.assertEqual(wizard.registrant_id, self.group)

    def test_wizard_onchange_clears_mismatched_registrant(self):
        """Test onchange clears registrant when type target doesn't match."""
        cr_type_group = self.env["spp.change.request.type"].search([("target_type", "=", "group")], limit=1)
        cr_type_individual = self.env["spp.change.request.type"].search([("target_type", "=", "individual")], limit=1)

        if not cr_type_group or not cr_type_individual:
            self.skipTest("Need both group and individual CR types")

        wizard = self.env["spp.cr.create.wizard"].create(
            {
                "request_type_id": cr_type_group.id,
                "registrant_id": self.group.id,
            }
        )

        # Change to individual type
        wizard.request_type_id = cr_type_individual
        wizard._onchange_request_type()

        # Group registrant should be cleared
        self.assertFalse(wizard.registrant_id)


@tagged("post_install", "-at_install", "cr_ux")
class TestBatchApprovalWizard(TestChangeRequestBase):
    """Tests for the batch approval wizard."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls._pending_crs_type = None

    def setUp(self):
        super().setUp()
        # Create multiple pending CRs for batch testing
        cr_type = self.env["spp.change.request.type"].search([("approval_definition_id", "!=", False)], limit=1)

        if not cr_type:
            self.skipTest("No CR type with approval definition")

        self.pending_crs = self.env["spp.change.request"]
        for _i in range(3):
            cr = self.env["spp.change.request"].create(
                {
                    "request_type_id": cr_type.id,
                    "registrant_id": self.group.id,
                }
            )
            cr.action_submit_for_approval()
            self.pending_crs |= cr

    def test_batch_wizard_initialization(self):
        """Test batch wizard initializes with selected CRs."""
        wizard = self.env["spp.cr.batch.approval.wizard"].with_context(active_ids=self.pending_crs.ids).create({})

        self.assertEqual(wizard.total_count, 3)
        self.assertEqual(len(wizard.line_ids), 3)

    def test_batch_wizard_counts(self):
        """Test batch wizard computes valid/invalid counts correctly."""
        wizard = self.env["spp.cr.batch.approval.wizard"].with_context(active_ids=self.pending_crs.ids).create({})

        # All should be valid if user can approve
        self.assertEqual(wizard.total_count, wizard.valid_count + wizard.invalid_count)

    def test_batch_approve_requires_valid_crs(self):
        """Test batch approve fails if no valid CRs."""
        # Create wizard with draft CR (cannot be approved)
        cr_type = self.env["spp.change.request.type"].search([], limit=1)
        draft_cr = self.env["spp.change.request"].create(
            {
                "request_type_id": cr_type.id,
                "registrant_id": self.group.id,
            }
        )

        wizard = self.env["spp.cr.batch.approval.wizard"].with_context(active_ids=[draft_cr.id]).create({})

        # Should have 0 valid CRs
        self.assertEqual(wizard.valid_count, 0)

        with self.assertRaises(UserError):
            wizard.action_confirm()

    def test_batch_reject_requires_comment(self):
        """Test batch reject requires a reason."""
        wizard = (
            self.env["spp.cr.batch.approval.wizard"]
            .with_context(active_ids=self.pending_crs.ids)
            .create(
                {
                    "action_type": "reject",
                    "comment": "",
                }
            )
        )

        # Should fail without comment
        with self.assertRaises(UserError):
            wizard.action_confirm()


@tagged("post_install", "-at_install", "cr_ux")
class TestConflictComparisonWizard(TestChangeRequestBase):
    """Tests for the conflict comparison wizard."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

    def test_wizard_initialization(self):
        """Test conflict comparison wizard initializes correctly."""
        cr_type = self.env["spp.change.request.type"].search([], limit=1)
        primary_cr = self.env["spp.change.request"].create(
            {
                "request_type_id": cr_type.id,
                "registrant_id": self.group.id,
            }
        )

        wizard = self.env["spp.cr.conflict.comparison.wizard"].with_context(active_id=primary_cr.id).create({})

        self.assertEqual(wizard.primary_cr_id, primary_cr)
        # Should have at least the primary CR in lines
        self.assertTrue(len(wizard.line_ids) >= 1)

    def test_wizard_quick_actions(self):
        """Test quick action buttons work correctly."""
        cr_type = self.env["spp.change.request.type"].search([("approval_definition_id", "!=", False)], limit=1)

        if not cr_type:
            self.skipTest("No CR type with approval definition")

        # Create two conflicting CRs
        cr1 = self.env["spp.change.request"].create(
            {
                "request_type_id": cr_type.id,
                "registrant_id": self.group.id,
            }
        )
        cr1.action_submit_for_approval()

        cr2 = self.env["spp.change.request"].create(
            {
                "request_type_id": cr_type.id,
                "registrant_id": self.group.id,
            }
        )
        cr2.action_submit_for_approval()

        # Create wizard manually since we don't have conflict records
        wizard = self.env["spp.cr.conflict.comparison.wizard"].create(
            {
                "primary_cr_id": cr1.id,
                "line_ids": [
                    (0, 0, {"change_request_id": cr1.id, "is_primary": True}),
                    (0, 0, {"change_request_id": cr2.id, "is_primary": False}),
                ],
            }
        )

        # Test approve latest action
        wizard.action_approve_latest_decline_others()

        # Check decisions were set
        latest_line = wizard.line_ids.sorted(key=lambda line: line.change_request_id.create_date, reverse=True)[0]
        self.assertEqual(latest_line.decision, "approve")

    def test_wizard_line_decision(self):
        """Test setting individual line decisions."""
        cr_type = self.env["spp.change.request.type"].search([], limit=1)
        cr = self.env["spp.change.request"].create(
            {
                "request_type_id": cr_type.id,
                "registrant_id": self.group.id,
            }
        )

        line = self.env["spp.cr.conflict.comparison.line"].create(
            {
                "wizard_id": self.env["spp.cr.conflict.comparison.wizard"]
                .create(
                    {
                        "primary_cr_id": cr.id,
                    }
                )
                .id,
                "change_request_id": cr.id,
                "decision": "none",
            }
        )

        # Change decision
        line.decision = "approve"
        self.assertEqual(line.decision, "approve")
