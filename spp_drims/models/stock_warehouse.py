# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import json

from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    # DRIMS Configuration
    is_drims_warehouse = fields.Boolean(
        string="DRIMS Warehouse",
        default=False,
        help="Enable for disaster relief warehouses",
    )
    drims_capacity = fields.Float(
        string="Storage Capacity (m³)",
        help="Maximum storage capacity in cubic meters",
    )
    incident_ids = fields.Many2many(
        "spp.hazard.incident",
        string="Active Incidents",
        help="Incidents this warehouse is responding to",
    )
    area_id = fields.Many2one(
        "spp.area",
        string="Coverage Area",
        help="Geographic area this warehouse serves",
    )
    gis_location = fields.GeoPointField(
        string="GPS Location",
        help="Geographic location of the warehouse for GIS mapping",
    )
    # OP#959: warehouse tier per docs/DATA_MODEL.md:185-195
    # central — strategic stockpile (national / regional hub)
    # regional — provincial / district distribution centre
    # mobile — temporary / field-deployed warehouse near the incident
    tier = fields.Selection(
        selection=[
            ("central", "Central"),
            ("regional", "Regional"),
            ("mobile", "Mobile"),
        ],
        string="Warehouse Tier",
        help=(
            "Operational tier of this warehouse: Central (strategic stockpile), "
            "Regional (provincial / district hub), or Mobile (field-deployed)."
        ),
        index=True,
    )

    # Contact
    emergency_contact = fields.Char(string="Emergency Contact")
    emergency_phone = fields.Char(string="Emergency Phone")

    # Computed KPIs
    drims_donation_count = fields.Integer(
        compute="_compute_drims_counts",
    )
    drims_dispatch_count = fields.Integer(
        compute="_compute_drims_counts",
    )

    # Stock Health Indicators
    drims_stock_health = fields.Selection(
        selection=[
            ("critical", "Critical"),
            ("warning", "Warning"),
            ("good", "Good"),
        ],
        string="Stock Health",
        compute="_compute_drims_stock_health",
        store=False,
        help="Overall health status based on active alerts",
    )
    drims_active_alert_count = fields.Integer(
        string="Active Alerts",
        compute="_compute_drims_stock_health",
    )

    def _compute_drims_counts(self):
        Donation = self.env["spp.drims.donation"]
        Picking = self.env["stock.picking"]
        for rec in self:
            rec.drims_donation_count = Donation.search_count([("warehouse_id", "=", rec.id)])
            rec.drims_dispatch_count = Picking.search_count(
                [
                    ("picking_type_id.warehouse_id", "=", rec.id),
                    ("drims_type", "=", "request_dispatch"),
                ]
            )

    def _compute_drims_stock_health(self):
        """Compute stock health based on active alert count.

        Health levels:
        - critical: 3+ active alerts
        - warning: 1-2 active alerts
        - good: No active alerts
        """
        Alert = self.env["spp.drims.alert"]

        # Batch query all alert counts to avoid N+1 queries
        alert_data = Alert.read_group(
            domain=[
                ("warehouse_id", "in", self.ids),
                ("state", "in", ["active", "acknowledged"]),
            ],
            fields=["warehouse_id"],
            groupby=["warehouse_id"],
        )

        # Build warehouse_id -> count mapping
        alert_counts = {item["warehouse_id"][0]: item["warehouse_id_count"] for item in alert_data}

        for rec in self:
            alert_count = alert_counts.get(rec.id, 0)
            rec.drims_active_alert_count = alert_count
            if alert_count >= 3:
                rec.drims_stock_health = "critical"
            elif alert_count >= 1:
                rec.drims_stock_health = "warning"
            else:
                rec.drims_stock_health = "good"

    def action_view_active_alerts(self):
        """Open view showing active alerts for this warehouse."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Alerts - {self.name}",
            "res_model": "spp.drims.alert",
            "view_mode": "list,form",
            "domain": [
                ("warehouse_id", "=", self.id),
                ("state", "in", ["active", "acknowledged"]),
            ],
            "context": {"default_warehouse_id": self.id},
        }

    def action_view_expired_stock(self):
        """View expired stock in this warehouse (GAP-INV-003).

        Opens stock quants view filtered to show items with
        expired lots in this warehouse.
        """
        self.ensure_one()
        today = fields.Date.today()
        return {
            "type": "ir.actions.act_window",
            "name": f"Expired Stock - {self.name}",
            "res_model": "stock.quant",
            "view_mode": "list,form",
            "domain": [
                ("location_id", "child_of", self.lot_stock_id.id),
                ("lot_id.expiration_date", "<", today),
                ("quantity", ">", 0),
            ],
            "context": {
                "search_default_productgroup": 1,
            },
        }

    def action_dispose_expired_stock(self):
        """Open wizard to dispose expired stock (GAP-INV-003)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Dispose Expired Items",
            "res_model": "spp.drims.stock.adjustment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_warehouse_id": self.id,
                "default_reason": "expired",
            },
        }

    def action_open_gis_map(self):
        """Open the unified DRIMS Operations Map."""
        return self.env.ref("spp_drims.action_drims_operations_map").read()[0]

    def set_gis_location_from_coordinates(self, longitude, latitude):
        """Set GIS location from coordinate values.

        :param longitude: The longitude value (x coordinate)
        :param latitude: The latitude value (y coordinate)
        """
        self.ensure_one()
        if longitude and latitude:
            self.gis_location = json.dumps(
                {
                    "type": "Point",
                    "coordinates": [longitude, latitude],
                }
            )
        else:
            self.gis_location = False
