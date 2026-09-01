# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import base64
import csv
import logging
from io import StringIO

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class PaymentManager(models.Model):
    _inherit = "spp.program.payment.manager"

    @api.model
    def _selection_manager_ref_id(self):
        selection = super()._selection_manager_ref_id()
        new_manager = ("spp.program.payment.manager.csv", "Bank File (CSV)")
        if new_manager not in selection:
            selection.append(new_manager)
        return selection


class CSVFilePaymentManager(models.Model):
    """Payment manager that renders each payment batch as a CSV disbursement
    file attached to the batch, ready to be forwarded to the bank.

    Payments are issued to the registered payee of the beneficiary's family
    (the mother, or the family head as fallback), never to the beneficiary
    child directly.
    """

    _name = "spp.program.payment.manager.csv"
    _inherit = "spp.program.payment.manager.default"
    _description = "Bank File (CSV) Payment Manager"

    # The parent model pins an explicit m2m relation table whose columns are
    # named after the parent model; a prototype-inherited model needs its own.
    batch_tag_ids = fields.Many2many(
        "spp.payment.batch.tag",
        "spp_pay_batch_tag_pay_manager_csv",
        string="Batch Tags",
        ondelete="cascade",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "name" in fields_list:
            res["name"] = _("Bank File (CSV)")
        return res

    # ------------------------------------------------------------------
    # Payee resolution
    # ------------------------------------------------------------------
    def _get_payee(self, child):
        """The person who receives the money on the child's behalf."""
        Vocab = self.env["spp.vocabulary.code"]
        memberships = self.env["spp.group.membership"].search([("individual", "=", child.id), ("is_ended", "=", False)])
        families = memberships.mapped("group").filtered(lambda g: g.group_type_id.code == "family")
        for role_code in ("mother", "head"):
            role = Vocab.get_code("urn:openspp:vocab:group-membership-type", role_code)
            if not role:
                continue
            payee_memberships = families.mapped("group_membership_ids").filtered(
                lambda m, role=role: not m.is_ended and role.id in m.membership_type_ids.ids
            )
            if payee_memberships:
                return payee_memberships[0].individual
        return child

    def _prepare_payments(self, cycle, entitlements):
        payments, batches = super()._prepare_payments(cycle, entitlements)
        if not payments:
            return payments, batches
        sequence = self.env["ir.sequence"]
        for payment in payments:
            payee = self._get_payee(payment.partner_id)
            vals = {"name": sequence.next_by_code("spp.child.benefit.payment")}
            if payee != payment.partner_id and payee.bank_ids:
                vals["account_number"] = payee.bank_ids[0].acc_number
            payment.write(vals)
        return payments, batches

    # ------------------------------------------------------------------
    # Bank file rendering
    # ------------------------------------------------------------------
    def _send_payments(self, batches):
        if not batches:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Payment"),
                    "message": _("No payment batches to process."),
                    "sticky": True,
                    "type": "warning",
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }
        for batch in batches:
            attachment = self._render_batch_csv(batch)
            batch.payment_ids.filtered(lambda p: p.state == "issued").write({"state": "sent"})
            _logger.info("Bank file %s generated for batch %s", attachment.name, batch.id)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Payment"),
                "message": _("%s bank file(s) generated and attached to the batches.") % len(batches),
                "sticky": False,
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _render_batch_csv(self, batch):
        data = StringIO()
        writer = csv.writer(data, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(
            [
                "row_number",
                "payment_reference",
                "beneficiary_name",
                "payee_name",
                "bank",
                "account_number",
                "amount",
                "currency",
                "narration",
            ]
        )
        total = 0.0
        for row, payment in enumerate(batch.payment_ids, start=1):
            child = payment.partner_id
            payee = self._get_payee(child)
            bank_name = payee.bank_ids[0].bank_id.name if payee.bank_ids and payee.bank_ids[0].bank_id else ""
            narration = f"{payment.program_id.name or ''} - {payment.cycle_id.name or ''}"
            writer.writerow(
                [
                    row,
                    payment.name,
                    child.name,
                    payee.name,
                    bank_name,
                    payment.account_number or "",
                    f"{payment.amount_issued:.2f}",
                    payment.currency_id.name or "",
                    narration,
                ]
            )
            total += payment.amount_issued
        writer.writerow([])
        writer.writerow(["total_transactions", len(batch.payment_ids), "total_amount", f"{total:.2f}"])
        filename = f"{batch.name}.csv"
        return self.env["ir.attachment"].create(
            {
                "name": filename,
                "res_model": "spp.payment.batch",
                "res_id": batch.id,
                "type": "binary",
                "mimetype": "text/csv",
                "datas": base64.b64encode(data.getvalue().encode("utf-8")),
            }
        )
