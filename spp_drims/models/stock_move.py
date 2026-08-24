# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    # DRIMS specific
    drims_request_line_id = fields.Many2one(
        "spp.drims.request.line",
        string="Request Line",
        help="Link to the request line this move fulfills",
    )
    drims_allocation_id = fields.Many2one(
        "spp.drims.request.allocation",
        string="Request Allocation",
        help="Link to the per-warehouse allocation this move dispatches",
    )
    drims_donation_line_id = fields.Many2one(
        "spp.drims.donation.line",
        string="Donation Line",
        help="Link to the donation line this move receives",
    )

    def _action_done(self, cancel_backorder=False):
        """Reconcile the request's dispatch counter once moves are validated.

        Needed because Odoo has more than one way to drop undelivered demand:
        declining "Create Backorder" leaves the move done at the picked quantity
        without cancelling anything, so the shortfall is invisible to a
        cancellation hook (OP#1087).
        """
        lines = self.drims_request_line_id
        result = super()._action_done(cancel_backorder=cancel_backorder)
        lines.exists()._reconcile_quantity_dispatched()
        return result

    def _action_cancel(self):
        """Reconcile the request's dispatch counter when moves are cancelled.

        Covers a cancelled backorder and a cancelled dispatch: neither quantity
        ever shipped, so neither may keep counting as dispatched (OP#1087).
        """
        lines = self.drims_request_line_id
        result = super()._action_cancel()
        lines.exists()._reconcile_quantity_dispatched()
        return result

    @api.model
    def _prepare_merge_moves_distinct_fields(self):
        """Keep DRIMS donation/request lines distinct when Odoo merges moves.

        Without this, a multi-line donation for the same product collapses
        into a single move on the receipt picking and the per-line
        ``drims_donation_line_id`` link is lost — which OP#1030's stocking
        logic relies on to exclude non-accept dispositions.
        """
        fields_list = super()._prepare_merge_moves_distinct_fields()
        fields_list += ["drims_donation_line_id", "drims_request_line_id", "drims_allocation_id"]
        return fields_list
