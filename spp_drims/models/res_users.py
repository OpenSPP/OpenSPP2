# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    # DRIMS Defaults
    drims_default_incident_id = fields.Many2one(
        "spp.hazard.incident",
        string="Default Incident",
        help="Pre-selected incident for new requests",
    )
    drims_default_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Default Warehouse",
        help="Pre-selected warehouse for warehouse staff",
    )

    # Area assignments for record rules
    drims_area_ids = fields.Many2many(
        "spp.area",
        "drims_user_area_rel",
        "user_id",
        "area_id",
        string="DRIMS Areas",
        help="Areas this user can access in DRIMS",
    )

    # Warehouse assignments
    drims_warehouse_ids = fields.Many2many(
        "stock.warehouse",
        "drims_user_warehouse_rel",
        "user_id",
        "warehouse_id",
        string="DRIMS Warehouses",
        help="Warehouses this user can access in DRIMS",
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + [
            "drims_default_incident_id",
            "drims_default_warehouse_id",
            "drims_area_ids",
            "drims_warehouse_ids",
        ]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + [
            "drims_default_incident_id",
            "drims_default_warehouse_id",
        ]
