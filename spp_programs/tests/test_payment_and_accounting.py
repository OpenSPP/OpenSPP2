# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestPaymentAndAccounting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Test Registrant [TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )

        cls.program = cls.env["spp.program"].create(
            {
                "name": "Test Program [TEST]",
                "program_membership_ids": [
                    (
                        0,
                        0,
                        {
                            "partner_id": cls.registrant.id,
                            "state": "enrolled",
                        },
                    )
                ],
            }
        )
        cls.program.create_journal()

        cls.cycle = cls.env["spp.cycle"].create(
            {
                "name": "Test Cycle [TEST]",
                "program_id": cls.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )

        cls.entitlement = cls.env["spp.entitlement"].create(
            {
                "partner_id": cls.registrant.id,
                "cycle_id": cls.cycle.id,
                "valid_from": fields.Date.today(),
                "initial_amount": 100.0,
            }
        )

    # -------------------------------------------------------------------------
    # spp.payment tests
    # -------------------------------------------------------------------------

    def test_payment_creation_with_required_fields(self):
        """A payment can be created given a valid entitlement."""
        payment = self.env["spp.payment"].create(
            {
                "entitlement_id": self.entitlement.id,
                "cycle_id": self.cycle.id,
                "amount_issued": 100.0,
            }
        )
        self.assertTrue(payment.id, "Payment record should have been created.")
        self.assertEqual(payment.state, "issued", "New payment should default to 'issued' state.")
        self.assertFalse(payment.is_status_final, "New payment should not be in final status by default.")

    def test_payment_state_default(self):
        """Payment state defaults to 'issued'."""
        payment = self.env["spp.payment"].create(
            {
                "entitlement_id": self.entitlement.id,
                "cycle_id": self.cycle.id,
                "amount_issued": 50.0,
            }
        )
        self.assertEqual(payment.state, "issued")

    def test_payment_status_field(self):
        """Payment status can be set to 'paid' or 'failed'."""
        payment = self.env["spp.payment"].create(
            {
                "entitlement_id": self.entitlement.id,
                "cycle_id": self.cycle.id,
                "amount_issued": 75.0,
                "status": "paid",
            }
        )
        self.assertEqual(payment.status, "paid")

        payment.write({"status": "failed"})
        self.assertEqual(payment.status, "failed")

    def test_payment_journal_computed_from_program(self):
        """Payment journal is computed from the entitlement's program journal."""
        payment = self.env["spp.payment"].create(
            {
                "entitlement_id": self.entitlement.id,
                "cycle_id": self.cycle.id,
                "amount_issued": 100.0,
            }
        )
        # The program has a journal created by create_journal()
        self.assertTrue(
            payment.journal_id,
            "Payment should inherit the journal from the program via entitlement.",
        )
        self.assertEqual(
            payment.journal_id,
            self.program.journal_id,
            "Payment journal should match the program's journal.",
        )

    def test_payment_partner_related_to_entitlement(self):
        """Payment partner is the related beneficiary from the entitlement."""
        payment = self.env["spp.payment"].create(
            {
                "entitlement_id": self.entitlement.id,
                "cycle_id": self.cycle.id,
                "amount_issued": 100.0,
            }
        )
        self.assertEqual(
            payment.partner_id,
            self.registrant,
            "Payment partner should match the entitlement's partner.",
        )

    def test_payment_program_related_to_cycle(self):
        """Payment program is the related program from the cycle."""
        payment = self.env["spp.payment"].create(
            {
                "entitlement_id": self.entitlement.id,
                "cycle_id": self.cycle.id,
                "amount_issued": 100.0,
            }
        )
        self.assertEqual(
            payment.program_id,
            self.program,
            "Payment program should match the cycle's program.",
        )

    def test_payment_batch_linking(self):
        """A payment can be linked to a payment batch via the batch's Many2many."""
        payment = self.env["spp.payment"].create(
            {
                "entitlement_id": self.entitlement.id,
                "cycle_id": self.cycle.id,
                "amount_issued": 100.0,
            }
        )
        batch = self.env["spp.payment.batch"].create(
            {
                "cycle_id": self.cycle.id,
                "payment_ids": [(4, payment.id)],
            }
        )
        self.assertIn(payment, batch.payment_ids, "Batch should include the linked payment.")

    def test_payment_issuance_date_defaults_to_now(self):
        """Payment issuance_date defaults to the current datetime."""
        payment = self.env["spp.payment"].create(
            {
                "entitlement_id": self.entitlement.id,
                "cycle_id": self.cycle.id,
                "amount_issued": 100.0,
            }
        )
        self.assertTrue(payment.issuance_date, "Payment issuance_date should be set by default.")

    def test_payment_delete_in_issued_state(self):
        """A payment in 'issued' state can be deleted."""
        payment = self.env["spp.payment"].create(
            {
                "entitlement_id": self.entitlement.id,
                "cycle_id": self.cycle.id,
                "amount_issued": 100.0,
            }
        )
        payment_id = payment.id
        payment.unlink()
        self.assertFalse(
            self.env["spp.payment"].browse(payment_id).exists(),
            "Payment in 'issued' state should be deletable.",
        )

    def test_payment_delete_blocked_when_not_issued(self):
        """Deleting a payment in 'sent' or 'reconciled' state raises ValidationError."""
        payment = self.env["spp.payment"].create(
            {
                "entitlement_id": self.entitlement.id,
                "cycle_id": self.cycle.id,
                "amount_issued": 100.0,
                "state": "sent",
            }
        )
        with self.assertRaises(ValidationError):
            payment.unlink()

    # -------------------------------------------------------------------------
    # spp.payment.batch tests
    # -------------------------------------------------------------------------

    def test_payment_batch_creation(self):
        """A payment batch can be created linked to a cycle."""
        batch = self.env["spp.payment.batch"].create(
            {
                "cycle_id": self.cycle.id,
            }
        )
        self.assertTrue(batch.id, "Payment batch should be created.")
        self.assertFalse(batch.has_batch_started, "Batch should not have started by default.")
        self.assertFalse(batch.has_batch_completed, "Batch should not be completed by default.")

    def test_payment_batch_program_related_to_cycle(self):
        """Payment batch program is related to the cycle's program."""
        batch = self.env["spp.payment.batch"].create(
            {
                "cycle_id": self.cycle.id,
            }
        )
        self.assertEqual(
            batch.program_id,
            self.program,
            "Batch program should match the cycle's program.",
        )

    def test_payment_batch_delete_before_start(self):
        """A batch that has not started can be deleted."""
        payment = self.env["spp.payment"].create(
            {
                "entitlement_id": self.entitlement.id,
                "cycle_id": self.cycle.id,
                "amount_issued": 100.0,
            }
        )
        batch = self.env["spp.payment.batch"].create(
            {
                "cycle_id": self.cycle.id,
                "payment_ids": [(4, payment.id)],
            }
        )
        batch_id = batch.id
        batch.unlink()
        self.assertFalse(
            self.env["spp.payment.batch"].browse(batch_id).exists(),
            "Batch that has not started should be deletable.",
        )

    def test_payment_batch_delete_blocked_after_start(self):
        """A batch that has started cannot be deleted."""
        batch = self.env["spp.payment.batch"].create(
            {
                "cycle_id": self.cycle.id,
                "has_batch_started": True,
            }
        )
        with self.assertRaises(ValidationError):
            batch.unlink()

    # -------------------------------------------------------------------------
    # spp.program.fund tests
    # -------------------------------------------------------------------------

    def test_fund_creation(self):
        """A program fund can be created in draft state."""
        fund = self.env["spp.program.fund"].create(
            {
                "name": "Test Fund [TEST]",
                "program_id": self.program.id,
                "amount": 10_000.0,
                "date_posted": fields.Date.today(),
            }
        )
        self.assertTrue(fund.id, "Fund should be created.")
        self.assertEqual(fund.state, "draft", "Fund should default to 'draft' state.")

    def test_fund_journal_related_to_program(self):
        """Fund journal is related to the program's journal."""
        fund = self.env["spp.program.fund"].create(
            {
                "name": "Test Fund Journal [TEST]",
                "program_id": self.program.id,
                "amount": 5_000.0,
                "date_posted": fields.Date.today(),
            }
        )
        self.assertEqual(
            fund.journal_id,
            self.program.journal_id,
            "Fund journal should match the program's disbursement journal.",
        )

    def test_fund_post_transitions_from_draft(self):
        """Posting a draft fund transitions it to 'posted' state."""
        fund = self.env["spp.program.fund"].create(
            {
                "program_id": self.program.id,
                "amount": 20_000.0,
                "date_posted": fields.Date.today(),
            }
        )
        self.assertEqual(fund.state, "draft")
        fund.post_fund()
        self.assertEqual(fund.state, "posted", "Fund should be in 'posted' state after posting.")

    def test_fund_post_assigns_reference_number(self):
        """Posting a fund with default name assigns a sequence-based reference number."""
        fund = self.env["spp.program.fund"].create(
            {
                "program_id": self.program.id,
                "amount": 15_000.0,
                "date_posted": fields.Date.today(),
            }
        )
        # Default name is "Draft"
        self.assertEqual(fund.name, "Draft")
        fund.post_fund()
        self.assertNotEqual(
            fund.name,
            "Draft",
            "Fund name should be updated from 'Draft' after posting.",
        )

    def test_fund_post_preserves_custom_reference(self):
        """Posting a fund with a custom name does not overwrite that name."""
        fund = self.env["spp.program.fund"].create(
            {
                "name": "CUSTOM-REF-001",
                "program_id": self.program.id,
                "amount": 5_000.0,
                "date_posted": fields.Date.today(),
            }
        )
        fund.post_fund()
        self.assertEqual(
            fund.name,
            "CUSTOM-REF-001",
            "Custom reference number should not be overwritten when posting.",
        )

    def test_fund_post_non_draft_returns_notification(self):
        """Attempting to post a non-draft fund returns a danger notification."""
        fund = self.env["spp.program.fund"].create(
            {
                "name": "Already Posted [TEST]",
                "program_id": self.program.id,
                "amount": 1_000.0,
                "state": "posted",
                "date_posted": fields.Date.today(),
            }
        )
        result = fund.post_fund()
        self.assertEqual(
            result["params"]["type"],
            "danger",
            "Should return a danger notification when posting a non-draft fund.",
        )

    def test_fund_cancel_transitions_from_draft(self):
        """Cancelling a draft fund transitions it to 'cancelled' state."""
        fund = self.env["spp.program.fund"].create(
            {
                "program_id": self.program.id,
                "amount": 8_000.0,
                "date_posted": fields.Date.today(),
            }
        )
        fund.cancel_fund()
        self.assertEqual(fund.state, "cancelled", "Fund should be 'cancelled' after cancellation.")

    def test_fund_cancel_non_draft_returns_notification(self):
        """Attempting to cancel a posted fund returns a danger notification."""
        fund = self.env["spp.program.fund"].create(
            {
                "name": "Posted Fund [TEST]",
                "program_id": self.program.id,
                "amount": 2_000.0,
                "state": "posted",
                "date_posted": fields.Date.today(),
            }
        )
        result = fund.cancel_fund()
        self.assertEqual(
            result["params"]["type"],
            "danger",
            "Should return a danger notification when cancelling a non-draft fund.",
        )

    def test_fund_reset_to_draft_from_cancelled(self):
        """Resetting a cancelled fund transitions it back to 'draft' state."""
        fund = self.env["spp.program.fund"].create(
            {
                "program_id": self.program.id,
                "amount": 3_000.0,
                "date_posted": fields.Date.today(),
            }
        )
        fund.cancel_fund()
        self.assertEqual(fund.state, "cancelled")
        fund.reset_draft()
        self.assertEqual(fund.state, "draft", "Fund should be back to 'draft' after reset.")

    def test_fund_reset_non_cancelled_returns_notification(self):
        """Resetting a draft fund (not cancelled) returns a danger notification."""
        fund = self.env["spp.program.fund"].create(
            {
                "program_id": self.program.id,
                "amount": 1_500.0,
                "date_posted": fields.Date.today(),
            }
        )
        # State is 'draft', not 'cancelled' — reset should fail
        result = fund.reset_draft()
        self.assertEqual(
            result["params"]["type"],
            "danger",
            "Should return a danger notification when resetting a non-cancelled fund.",
        )

    def test_fund_delete_blocked_when_posted(self):
        """Deleting a posted fund raises UserError."""
        fund = self.env["spp.program.fund"].create(
            {
                "name": "To Delete [TEST]",
                "program_id": self.program.id,
                "amount": 500.0,
                "date_posted": fields.Date.today(),
            }
        )
        fund.post_fund()
        self.assertEqual(fund.state, "posted")
        with self.assertRaises(UserError):
            fund.unlink()

    def test_fund_delete_allowed_when_draft(self):
        """Deleting a draft fund is allowed."""
        fund = self.env["spp.program.fund"].create(
            {
                "program_id": self.program.id,
                "amount": 500.0,
                "date_posted": fields.Date.today(),
            }
        )
        fund_id = fund.id
        fund.unlink()
        self.assertFalse(
            self.env["spp.program.fund"].browse(fund_id).exists(),
            "Draft fund should be deletable.",
        )

    # -------------------------------------------------------------------------
    # account.journal extension tests
    # -------------------------------------------------------------------------

    def test_account_journal_has_beneficiary_disb_field(self):
        """account.journal has the custom is_beneficiary_disb boolean field."""
        journal = self.env["account.journal"].search([], limit=1)
        self.assertTrue(
            hasattr(journal, "is_beneficiary_disb"),
            "account.journal should have the 'is_beneficiary_disb' field.",
        )

    def test_account_journal_is_beneficiary_disb_defaults_false(self):
        """The is_beneficiary_disb field on account.journal defaults to False."""
        journal = self.env["account.journal"].create(
            {
                "name": "Test Beneficiary Journal [TEST]",
                "type": "bank",
                "code": "TSTBNF",
            }
        )
        self.assertFalse(
            journal.is_beneficiary_disb,
            "New account.journal should default is_beneficiary_disb to False.",
        )

    def test_account_journal_is_beneficiary_disb_can_be_set(self):
        """The is_beneficiary_disb field can be toggled to True on an account.journal."""
        journal = self.env["account.journal"].create(
            {
                "name": "Test Beneficiary Journal 2 [TEST]",
                "type": "bank",
                "code": "TSTBN2",
                "is_beneficiary_disb": True,
            }
        )
        self.assertTrue(
            journal.is_beneficiary_disb,
            "account.journal should allow is_beneficiary_disb to be set to True.",
        )

    def test_program_journal_created_by_create_journal(self):
        """Program.create_journal() creates a journal marked as a beneficiary disbursement journal."""
        # The program in setUpClass already has a journal created.
        self.assertTrue(
            self.program.journal_id,
            "Program should have a journal after create_journal() is called.",
        )
        self.assertTrue(
            self.program.journal_id.is_beneficiary_disb,
            "The program's journal should be flagged as a beneficiary disbursement journal.",
        )
