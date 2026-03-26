# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging
from datetime import date
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestRejectionWizards(TransactionCase):
    """Tests for reject/reset-to-pending wizard models.

    Covers:
    - spp.reject.entitlement.wizard
    - spp.reject.inkind.entitlement.wizard
    - spp.reset.pending.entitlement.wizard
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Registrant Wizard Test [TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )

        cls.program = cls.env["spp.program"].create(
            {
                "name": "Program Wizard Test [TEST]",
                "program_membership_ids": [
                    (
                        0,
                        0,
                        {
                            "partner_id": cls.registrant.id,
                            "state": "enrolled",
                        },
                    ),
                ],
            }
        )
        cls.program.create_journal()

        cls.cycle = cls.env["spp.cycle"].create(
            {
                "name": "Cycle Wizard Test [TEST]",
                "program_id": cls.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )

        # Set up approval definition for cash entitlements
        entitlement_model = cls.env["ir.model"].search([("model", "=", "spp.entitlement")], limit=1)
        cls._approval_definition = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Entitlement Approval Wizards [TEST]",
                "model_id": entitlement_model.id,
                "approval_type": "group",
                "approval_group_id": cls.env.ref("base.group_user").id,
            }
        )
        cls._cash_entitlement_manager = cls.env["spp.program.entitlement.manager.cash"].create(
            {
                "name": "Cash Entitlement Manager Wizard Test [TEST]",
                "program_id": cls.program.id,
                "approval_definition_id": cls._approval_definition.id,
            }
        )
        entitlement_manager_junction = cls.env["spp.program.entitlement.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": (f"spp.program.entitlement.manager.cash,{cls._cash_entitlement_manager.id}"),
            }
        )
        cls.program.write({"entitlement_manager_ids": [(4, entitlement_manager_junction.id)]})

        # Set up a separate program for in-kind entitlements (one manager per program)
        cls.inkind_program = cls.env["spp.program"].create(
            {
                "name": "Program Inkind Wizard Test [TEST]",
                "program_membership_ids": [
                    (
                        0,
                        0,
                        {
                            "partner_id": cls.registrant.id,
                            "state": "enrolled",
                        },
                    ),
                ],
            }
        )
        cls.inkind_cycle = cls.env["spp.cycle"].create(
            {
                "name": "Cycle Inkind Wizard Test [TEST]",
                "program_id": cls.inkind_program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )

        inkind_model = cls.env["ir.model"].search([("model", "=", "spp.entitlement.inkind")], limit=1)
        cls._inkind_approval_definition = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Inkind Entitlement Approval Wizards [TEST]",
                "model_id": inkind_model.id,
                "approval_type": "group",
                "approval_group_id": cls.env.ref("base.group_user").id,
            }
        )
        cls._inkind_entitlement_manager = cls.env["spp.program.entitlement.manager.inkind"].create(
            {
                "name": "Inkind Entitlement Manager Wizard Test [TEST]",
                "program_id": cls.inkind_program.id,
                "warehouse_id": cls.env.ref("stock.warehouse0").id,
                "approval_definition_id": cls._inkind_approval_definition.id,
            }
        )
        inkind_manager_junction = cls.env["spp.program.entitlement.manager"].create(
            {
                "program_id": cls.inkind_program.id,
                "manager_ref_id": (f"spp.program.entitlement.manager.inkind,{cls._inkind_entitlement_manager.id}"),
            }
        )
        cls.inkind_program.write({"entitlement_manager_ids": [(4, inkind_manager_junction.id)]})

    def _create_cash_entitlement(self, state="draft"):
        entitlement = self.env["spp.entitlement"].create(
            {
                "partner_id": self.registrant.id,
                "cycle_id": self.cycle.id,
                "valid_from": fields.Date.today(),
                "initial_amount": 50.0,
            }
        )
        if state != "draft":
            entitlement.write({"state": state})
        return entitlement

    def _create_inkind_entitlement(self, state="draft"):
        entitlement = self.env["spp.entitlement.inkind"].create(
            {
                "partner_id": self.registrant.id,
                "cycle_id": self.inkind_cycle.id,
                "valid_from": fields.Date.today(),
            }
        )
        if state != "draft":
            entitlement.write({"state": state})
        return entitlement

    # ------------------------------------------------------------------
    # spp.reject.entitlement.wizard
    # ------------------------------------------------------------------

    def test_01_reject_entitlement_wizard_default_get_filters_by_state(self):
        """default_get only includes entitlements in rejectable states."""
        draft_entitlement = self._create_cash_entitlement(state="draft")
        pending_entitlement = self._create_cash_entitlement(state="pending_validation")
        approved_entitlement = self._create_cash_entitlement(state="approved")

        wizard = (
            self.env["spp.reject.entitlement.wizard"]
            .with_context(
                active_ids=[
                    draft_entitlement.id,
                    pending_entitlement.id,
                    approved_entitlement.id,
                ]
            )
            .create({})
        )

        entitlement_ids_in_wizard = wizard.entitlement_ids.mapped("entitlement_id")
        self.assertIn(
            draft_entitlement,
            entitlement_ids_in_wizard,
            "Draft entitlement should be included in the wizard.",
        )
        self.assertIn(
            pending_entitlement,
            entitlement_ids_in_wizard,
            "Pending entitlement should be included in the wizard.",
        )
        self.assertNotIn(
            approved_entitlement,
            entitlement_ids_in_wizard,
            "Approved entitlement must not be included in the wizard.",
        )

    def test_02_reject_entitlement_wizard_computes_beneficiary_count(self):
        """number_of_beneficiaries reflects the number of entitlement lines."""
        entitlement_1 = self._create_cash_entitlement(state="draft")
        entitlement_2 = self._create_cash_entitlement(state="pending_validation")

        wizard = (
            self.env["spp.reject.entitlement.wizard"]
            .with_context(active_ids=[entitlement_1.id, entitlement_2.id])
            .create({})
        )

        self.assertEqual(
            wizard.number_of_beneficiaries,
            2,
            "number_of_beneficiaries should equal the count of entitlement lines.",
        )

    @patch("odoo.fields.Date.today")
    def test_03_reject_entitlement_wizard_rejects_draft_entitlement(self, mock_today):
        """Executing the wizard transitions a draft entitlement to 'reject'."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 6, 1)

        entitlement = self._create_cash_entitlement(state="draft")
        reason = "Insufficient documentation."

        wizard = (
            self.env["spp.reject.entitlement.wizard"]
            .with_context(active_ids=[entitlement.id])
            .create({"reject_reason": reason})
        )
        wizard.reject_entitlements()

        self.assertEqual(
            entitlement.state,
            "reject",
            "Entitlement state should be 'reject' after wizard execution.",
        )
        self.assertEqual(
            entitlement.rejected_reason,
            reason,
            "rejected_reason should be saved on the entitlement.",
        )
        self.assertEqual(
            entitlement.date_rejected,
            date(2024, 6, 1),
            "date_rejected should be set to today.",
        )

    @patch("odoo.fields.Date.today")
    def test_04_reject_entitlement_wizard_rejects_pending_entitlement(self, mock_today):
        """Executing the wizard transitions a pending entitlement to 'reject'."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 6, 2)

        entitlement = self._create_cash_entitlement(state="pending_validation")
        reason = "Duplicate record detected."

        wizard = (
            self.env["spp.reject.entitlement.wizard"]
            .with_context(active_ids=[entitlement.id])
            .create({"reject_reason": reason})
        )
        wizard.reject_entitlements()

        self.assertEqual(entitlement.state, "reject")
        self.assertEqual(entitlement.rejected_reason, reason)

    def test_05_reject_entitlement_wizard_skips_approved_entitlement(self):
        """Approved entitlements are silently skipped by the rejection logic."""
        entitlement = self._create_cash_entitlement(state="approved")

        wizard = self.env["spp.reject.entitlement.wizard"].with_context(active_ids=[entitlement.id]).create({})
        # default_get excludes the approved entitlement, so wizard has no lines
        self.assertEqual(
            len(wizard.entitlement_ids),
            0,
            "No lines should be loaded for an approved entitlement.",
        )

    def test_06_reject_entitlement_wizard_returns_notification(self):
        """reject_entitlements() returns a display_notification action."""
        entitlement = self._create_cash_entitlement(state="draft")

        wizard = self.env["spp.reject.entitlement.wizard"].with_context(active_ids=[entitlement.id]).create({})
        result = wizard.reject_entitlements()

        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "danger")

    def test_07_reject_entitlement_wizard_default_to_state(self):
        """The wizard defaults to_state to 'reject'."""
        entitlement = self._create_cash_entitlement(state="draft")

        wizard = self.env["spp.reject.entitlement.wizard"].with_context(active_ids=[entitlement.id]).create({})
        self.assertEqual(
            wizard.to_state,
            "reject",
            "to_state should default to 'reject'.",
        )

    def test_08_reject_entitlement_wizard_open_wizard_returns_action(self):
        """open_wizard() returns a valid act_window action dictionary."""
        wizard = self.env["spp.reject.entitlement.wizard"].create({})
        action = wizard.open_wizard()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.reject.entitlement.wizard")
        self.assertEqual(action["target"], "new")

    def test_09_reject_entitlement_wizard_close_wizard_returns_action(self):
        """close_wizard() returns an act_window_close action."""
        wizard = self.env["spp.reject.entitlement.wizard"].create({})
        action = wizard.close_wizard()

        self.assertEqual(action["type"], "ir.actions.act_window_close")

    # ------------------------------------------------------------------
    # spp.reject.inkind.entitlement.wizard
    # ------------------------------------------------------------------

    def test_10_reject_inkind_wizard_default_get_filters_by_state(self):
        """default_get for in-kind wizard only includes rejectable states."""
        draft_entitlement = self._create_inkind_entitlement(state="draft")
        pending_entitlement = self._create_inkind_entitlement(state="pending_validation")
        approved_entitlement = self._create_inkind_entitlement(state="approved")

        wizard = (
            self.env["spp.reject.inkind.entitlement.wizard"]
            .with_context(
                active_ids=[
                    draft_entitlement.id,
                    pending_entitlement.id,
                    approved_entitlement.id,
                ]
            )
            .create({})
        )

        entitlement_ids_in_wizard = wizard.entitlement_ids.mapped("entitlement_id")
        self.assertIn(draft_entitlement, entitlement_ids_in_wizard)
        self.assertIn(pending_entitlement, entitlement_ids_in_wizard)
        self.assertNotIn(
            approved_entitlement,
            entitlement_ids_in_wizard,
            "Approved in-kind entitlement must not be loaded into the wizard.",
        )

    def test_11_reject_inkind_wizard_computes_beneficiary_count(self):
        """number_of_beneficiaries reflects the in-kind entitlement line count."""
        entitlement = self._create_inkind_entitlement(state="draft")

        wizard = self.env["spp.reject.inkind.entitlement.wizard"].with_context(active_ids=[entitlement.id]).create({})

        self.assertEqual(wizard.number_of_beneficiaries, 1)

    @patch("odoo.fields.Date.today")
    def test_12_reject_inkind_wizard_rejects_draft_entitlement(self, mock_today):
        """Executing the in-kind wizard transitions a draft entitlement to 'reject'."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 7, 1)

        entitlement = self._create_inkind_entitlement(state="draft")
        reason = "Product not available in warehouse."

        wizard = (
            self.env["spp.reject.inkind.entitlement.wizard"]
            .with_context(active_ids=[entitlement.id])
            .create({"reject_reason": reason})
        )
        wizard.reject_entitlements()

        self.assertEqual(entitlement.state, "reject")
        self.assertEqual(entitlement.rejected_reason, reason)
        self.assertEqual(entitlement.date_rejected, date(2024, 7, 1))

    @patch("odoo.fields.Date.today")
    def test_13_reject_inkind_wizard_rejects_pending_entitlement(self, mock_today):
        """Executing the in-kind wizard transitions a pending entitlement to 'reject'."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 7, 2)

        entitlement = self._create_inkind_entitlement(state="pending_validation")
        reason = "Criteria not met."

        wizard = (
            self.env["spp.reject.inkind.entitlement.wizard"]
            .with_context(active_ids=[entitlement.id])
            .create({"reject_reason": reason})
        )
        wizard.reject_entitlements()

        self.assertEqual(entitlement.state, "reject")
        self.assertEqual(entitlement.rejected_reason, reason)

    def test_14_reject_inkind_wizard_returns_notification(self):
        """reject_entitlements() on in-kind wizard returns a display_notification action."""
        entitlement = self._create_inkind_entitlement(state="draft")

        wizard = self.env["spp.reject.inkind.entitlement.wizard"].with_context(active_ids=[entitlement.id]).create({})
        result = wizard.reject_entitlements()

        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "danger")

    def test_15_reject_inkind_wizard_default_to_state(self):
        """The in-kind wizard defaults to_state to 'reject'."""
        wizard = self.env["spp.reject.inkind.entitlement.wizard"].create({})
        self.assertEqual(wizard.to_state, "reject")

    def test_16_reject_inkind_wizard_open_wizard_returns_action(self):
        """open_wizard() on the in-kind wizard returns a valid act_window action."""
        wizard = self.env["spp.reject.inkind.entitlement.wizard"].create({})
        action = wizard.open_wizard()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.reject.inkind.entitlement.wizard")
        self.assertEqual(action["target"], "new")

    def test_17_reject_inkind_wizard_close_wizard_returns_action(self):
        """close_wizard() on the in-kind wizard returns an act_window_close action."""
        wizard = self.env["spp.reject.inkind.entitlement.wizard"].create({})
        action = wizard.close_wizard()

        self.assertEqual(action["type"], "ir.actions.act_window_close")

    # ------------------------------------------------------------------
    # spp.reset.pending.entitlement.wizard
    # ------------------------------------------------------------------

    def test_18_reset_pending_wizard_default_get_only_includes_rejected(self):
        """default_get for reset wizard only includes entitlements in 'reject' state."""
        rejected_entitlement = self._create_cash_entitlement(state="reject")
        draft_entitlement = self._create_cash_entitlement(state="draft")

        wizard = (
            self.env["spp.reset.pending.entitlement.wizard"]
            .with_context(active_ids=[rejected_entitlement.id, draft_entitlement.id])
            .create({})
        )

        entitlement_ids_in_wizard = wizard.entitlement_ids.mapped("entitlement_id")
        self.assertIn(
            rejected_entitlement,
            entitlement_ids_in_wizard,
            "Rejected entitlement should be included in the reset wizard.",
        )
        self.assertNotIn(
            draft_entitlement,
            entitlement_ids_in_wizard,
            "Draft entitlement must not be included in the reset wizard.",
        )

    def test_19_reset_pending_wizard_resets_rejected_entitlement(self):
        """reset_to_pending() transitions a rejected entitlement to 'pending_validation'."""
        entitlement = self._create_cash_entitlement(state="reject")

        wizard = self.env["spp.reset.pending.entitlement.wizard"].with_context(active_ids=[entitlement.id]).create({})
        wizard.reset_to_pending()

        self.assertEqual(
            entitlement.state,
            "pending_validation",
            "Entitlement should be in 'pending_validation' after reset.",
        )

    def test_20_reset_pending_wizard_returns_notification(self):
        """reset_to_pending() returns a success display_notification action."""
        entitlement = self._create_cash_entitlement(state="reject")

        wizard = self.env["spp.reset.pending.entitlement.wizard"].with_context(active_ids=[entitlement.id]).create({})
        result = wizard.reset_to_pending()

        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "success")
        self.assertEqual(result["params"]["message"], "Entitlement Reset to Pending")

    def test_21_reset_pending_wizard_no_lines_when_no_rejected(self):
        """When no rejected entitlements are in context, wizard has no lines."""
        draft_entitlement = self._create_cash_entitlement(state="draft")

        wizard = (
            self.env["spp.reset.pending.entitlement.wizard"].with_context(active_ids=[draft_entitlement.id]).create({})
        )

        self.assertEqual(
            len(wizard.entitlement_ids),
            0,
            "No lines should be loaded when context has no rejected entitlements.",
        )

    def test_22_reset_pending_wizard_open_wizard_returns_action(self):
        """open_wizard() on the reset wizard returns a valid act_window action."""
        wizard = self.env["spp.reset.pending.entitlement.wizard"].create({})
        action = wizard.open_wizard()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.reset.pending.entitlement.wizard")
        self.assertEqual(action["target"], "new")

    def test_23_reset_pending_wizard_close_wizard_returns_action(self):
        """close_wizard() on the reset wizard returns an act_window_close action."""
        wizard = self.env["spp.reset.pending.entitlement.wizard"].create({})
        action = wizard.close_wizard()

        self.assertEqual(action["type"], "ir.actions.act_window_close")

    def test_24_reset_pending_wizard_empty_entitlement_ids_returns_none(self):
        """reset_to_pending() with no entitlement lines returns None."""
        wizard = self.env["spp.reset.pending.entitlement.wizard"].create({})
        result = wizard.reset_to_pending()

        self.assertIsNone(
            result,
            "reset_to_pending() should return None when there are no entitlement lines.",
        )

    def test_25_reject_entitlement_wizard_empty_entitlement_ids_returns_none(self):
        """reject_entitlements() with no entitlement lines returns None."""
        wizard = self.env["spp.reject.entitlement.wizard"].create({})
        result = wizard.reject_entitlements()

        self.assertIsNone(
            result,
            "reject_entitlements() should return None when there are no entitlement lines.",
        )

    def test_26_reject_inkind_wizard_empty_entitlement_ids_returns_none(self):
        """reject_entitlements() on in-kind wizard with no lines returns None."""
        wizard = self.env["spp.reject.inkind.entitlement.wizard"].create({})
        result = wizard.reject_entitlements()

        self.assertIsNone(
            result,
            "reject_entitlements() on in-kind wizard should return None when there are no entitlement lines.",
        )
