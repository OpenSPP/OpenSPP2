# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import models


class ApprovalReview(models.Model):
    """Approving or rejecting from the Approvals app decides the record too.

    The review's own actions only stamp the review row. A reviewer who works
    from the Approvals list therefore leaves the change request pending and
    never applied, while the same click on the request's form runs the full
    approval. Delegate to the record: its approval marks this review, runs its
    hooks (auto-apply included) and notifies the submitter. Reviews whose
    record is not pending, or that are being marked by that very record
    approval, fall through to the plain stamp.
    """

    _inherit = "spp.approval.review"

    def _pending_record(self):
        self.ensure_one()
        record = self.get_record()
        if (
            self.status == "pending"
            and record
            and hasattr(record, "_do_approve")
            and getattr(record, "approval_state", None) == "pending"
        ):
            return record
        return None

    def action_approve(self, comment=None):
        for review in self:
            record = review._pending_record()
            if record is not None:
                record.action_approve(comment=comment)
            else:
                super(ApprovalReview, review).action_approve(comment=comment)
        return True

    def action_reject(self, comment=None):
        for review in self:
            record = review._pending_record()
            if record is not None and hasattr(record, "_do_reject"):
                record._do_reject(comment or self.env._("Rejected from the approvals list."))
            # The record's reject stamps only multi-tier reviews; make sure this
            # review row is closed as well.
            review.invalidate_recordset(["status"])
            if review.status == "pending":
                super(ApprovalReview, review).action_reject(comment=comment)
        return True
