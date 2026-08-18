# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security scan finding: "Batch payment creation leaves payment batches empty".

The chunked batch-assignment path in ``payment_manager._prepare_payments``
creates payments and assigns them with
``batch_payments.write({"batch_id": curr_batch.id})``. But
``spp.payment.batch.payment_ids`` is an *independent* Many2many field, not the
inverse of ``spp.payment.batch_id`` (a separate Many2one), so writing
``batch_id`` alone leaves the batch's ``payment_ids`` empty. Views
(``payment_batch_view.xml``) and the batch ``unlink`` cleanup
(``record.payment_ids.unlink()``) rely on ``payment_ids``.

The fix populates ``curr_batch.payment_ids`` explicitly in the manager. This
test drives ``_prepare_payments`` and asserts every generated batch lists its
payments.
"""

import uuid

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPaymentBatchPaymentIds(TransactionCase):
    def setUp(self):
        super().setUp()
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})
        self.journal = self.env["account.journal"].create(
            {"name": "Test Journal", "type": "bank", "code": f"TJ{uuid.uuid4().hex[:4].upper()}"}
        )
        self.program.journal_id = self.journal.id
        self.cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle",
                "program_id": self.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        self.payment_manager = self.env["spp.program.payment.manager.default"].create(
            {
                "name": "Test Payment Manager",
                "program_id": self.program.id,
                "create_batch": True,
            }
        )
        batch_tag = self.env["spp.payment.batch.tag"].create(
            {"name": "Test Tag", "order": 1, "domain": "[]", "max_batch_size": 500}
        )
        self.payment_manager.batch_tag_ids = [(4, batch_tag.id)]

        self.entitlements = self.env["spp.entitlement"]
        for i in range(5):
            reg = self.env["res.partner"].create({"name": f"Registrant {i}", "is_registrant": True})
            self.entitlements |= self.env["spp.entitlement"].create(
                {
                    "partner_id": reg.id,
                    "cycle_id": self.cycle.id,
                    "initial_amount": 100.0,
                    "state": "approved",
                    "is_cash_entitlement": True,
                }
            )

    def test_generated_batches_list_their_payments(self):
        """Every batch created by _prepare_payments must populate payment_ids.

        Before the fix only batch_id (the Many2one) was set, leaving the batch's
        payment_ids Many2many empty so the batch displayed/iterated zero payments.
        """
        payments, batches = self.payment_manager._prepare_payments(self.cycle, self.entitlements)

        self.assertTrue(batches, "expected at least one payment batch to be created")
        total_in_batches = self.env["spp.payment"]
        for batch in batches:
            self.assertTrue(
                batch.payment_ids,
                f"batch {batch.name} has an empty payment_ids — it will display zero payments",
            )
            total_in_batches |= batch.payment_ids
            # payment_ids and batch_id must agree.
            for payment in batch.payment_ids:
                self.assertEqual(payment.batch_id, batch)

        # Every created payment is reachable through some batch's payment_ids.
        self.assertEqual(set(total_in_batches.ids), set(payments.ids))
