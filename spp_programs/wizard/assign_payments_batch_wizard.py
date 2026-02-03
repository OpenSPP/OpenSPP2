# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging
from uuid import uuid4

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPAssignPaymentsBatchWizard(models.TransientModel):
    _name = "spp.assign.payments.batch.wizard"
    _description = "Add Payments to Batch Wizard"

    cycle_id = fields.Many2one("spp.cycle", "Cycle", readonly=True)
    internal_batch_ref = fields.Char("Internal Batch Reference #", default=str(uuid4()), readonly=True)

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if self.env.context.get("active_ids"):
            # Get the first selected payment and get its cycle_id
            payment_id = self.env.context.get("active_ids")[0]
            payment = self.env["spp.payment"].search(
                [
                    ("id", "=", payment_id),
                ]
            )
            cycle_id = payment.cycle_id and payment.cycle_id.id or None
            res["cycle_id"] = cycle_id
            return res
        else:
            raise UserError(_("There are no selected payments!"))

    def assign_payment(self):
        if self.env.context.get("active_ids"):
            payment_ids = self.env.context.get("active_ids")
            _logger.info("Assign to Batch Wizard with %s payment record(s)", len(payment_ids))
            ctr = 0
            ig_ctr = 0
            ok_ctr = 0
            vals = []
            payments_to_add_ids = []
            for rec in self.env["spp.payment"].search([("id", "in", payment_ids)]):
                ctr += 1
                _logger.info("Processing payment %s of %s", ctr, len(payment_ids))
                if not rec.batch_id:
                    ok_ctr += 1
                    vals.append((4, rec.id))
                    payments_to_add_ids.append(rec.id)
                    _logger.info("Adding to Payment Batch")
                else:
                    ig_ctr += 1
                    _logger.info("Payment was ignored because already in Payment Batch")
            _logger.info(
                "Total selected payments: %s, Total ignored: %s, Total added to batch: %s",
                ctr,
                ig_ctr,
                ok_ctr,
            )
            # Check if there are no selected payments added to new batch
            if ig_ctr == ctr:
                raise UserError(_("All selected payments are already assigned to another batch."))
            else:
                # Create a new batch
                new_batch_vals = {
                    "name": self.internal_batch_ref,
                    "cycle_id": self.cycle_id.id,
                    "payment_ids": vals,
                    "stats_datetime": fields.Datetime.now(),
                }
                # Add processed payments to new batch
                batch_id = self.env["spp.payment.batch"].create(new_batch_vals)
                # Update processed payments batch_id
                self.env["spp.payment"].browse(payments_to_add_ids).update({"batch_id": batch_id})

    def open_wizard(self):
        return {
            "name": "Add to Payment Batch",
            "view_mode": "form",
            "res_model": "spp.assign.payments.batch.wizard",
            "view_id": self.env.ref("spp_programs.assign_payments_batch_wizard_form_view").id,
            "type": "ir.actions.act_window",
            "target": "new",
            "context": self.env.context,
        }
