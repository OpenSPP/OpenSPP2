# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools.sql import column_exists, create_column


class StockMove(models.Model):
    _inherit = "stock.move"
    entitlement_id = fields.Many2one("spp.entitlement.inkind", "In-kind Entitlement", index=True)

    @api.model
    def _prepare_merge_moves_distinct_fields(self):
        distinct_fields = super()._prepare_merge_moves_distinct_fields()
        distinct_fields.append("entitlement_id")
        return distinct_fields

    def _get_source_document(self):
        res = super()._get_source_document()
        return self.entitlement_id.cycle_id or res

    def _assign_picking_post_process(self, new=False):
        super()._assign_picking_post_process(new=new)
        if new:
            picking_id = self.mapped("picking_id")
            entitlement_ids = self.mapped("entitlement_id.cycle_id")
            for entitlement_id in entitlement_ids:
                picking_id.message_post_with_source(
                    "mail.message_origin_link",
                    render_values={"self": picking_id, "origin": entitlement_id},
                    subtype_id=self.env.ref("mail.mt_note").id,
                )
        return


# Odoo 19: procurement.group replaced with stock.reference
class StockReference(models.Model):
    _inherit = "stock.reference"

    cycle_id = fields.Many2one("spp.cycle", "Cycle")


class StockRule(models.Model):
    _inherit = "stock.rule"

    def _get_custom_move_fields(self):
        fields = super()._get_custom_move_fields()
        fields += ["entitlement_id"]
        return fields


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # Odoo 19: group_id replaced with reference_ids (Many2many)
    # We'll compute cycle_id from the first reference that has a cycle
    cycle_id = fields.Many2one(
        "spp.cycle",
        string="Cycle",
        compute="_compute_cycle_id",
        store=True,
        readonly=False,
    )

    @api.depends("reference_ids", "reference_ids.cycle_id")
    def _compute_cycle_id(self):
        for picking in self:
            # Get cycle from first reference that has one
            cycle = picking.reference_ids.filtered(lambda r: r.cycle_id)[:1].cycle_id
            picking.cycle_id = cycle

    def _auto_init(self):
        """
        Create cycle_id column if needed for performance.
        Odoo 19: No longer a related field, computed from reference_ids.
        """
        if not column_exists(self.env.cr, "stock_picking", "cycle_id"):
            create_column(self.env.cr, "stock_picking", "cycle_id", "int4")
        return super()._auto_init()
