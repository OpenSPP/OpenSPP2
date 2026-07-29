# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging
from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HazardIncident(models.Model):
    _inherit = "spp.hazard.incident"

    # Coordination
    coordination_mode_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Coordination Mode",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:coordination-modes')]",
        help="Model for coordinating multi-agency disaster response:\n"
        "• Lead Agency Model - Single government agency leads, partners support\n"
        "• Cluster Coordination - UN OCHA cluster system with sector leads\n"
        "• Consortium Model - NGO partnership with shared leadership\n"
        "• Bilateral Coordination - Direct government-to-government or agency-to-agency\n"
        "• Decentralized Response - Local authorities lead with minimal central coordination",
    )

    # DRIMS KPIs (stored computed fields for dashboard)
    drims_donation_count = fields.Integer(
        string="Donations",
        compute="_compute_drims_kpis",
        store=True,
    )
    drims_donation_value = fields.Float(
        string="Donation Value",
        compute="_compute_drims_kpis",
        store=True,
    )
    drims_request_count = fields.Integer(
        string="Requests",
        compute="_compute_drims_kpis",
        store=True,
    )
    drims_request_pending = fields.Integer(
        string="Pending Requests",
        compute="_compute_drims_kpis",
        store=True,
    )
    drims_stock_value = fields.Float(
        string="Stock Value",
        compute="_compute_drims_stock_kpis",
        store=True,
    )
    drims_distributed_value = fields.Float(
        string="Distributed Value",
        compute="_compute_drims_stock_kpis",
        store=True,
    )
    drims_total_stock_units = fields.Float(
        string="Total Stock Units",
        compute="_compute_drims_stock_kpis",
        store=True,
        help="Total quantity of items in stock across all incident warehouses",
    )
    drims_stock_item_count = fields.Integer(
        string="Stock Items",
        compute="_compute_drims_stock_kpis",
        store=True,
        help="Number of distinct products in stock across all incident warehouses",
    )
    drims_beneficiaries_served = fields.Integer(
        string="Beneficiaries Served",
        compute="_compute_drims_stock_kpis",
        store=True,
        help="Total beneficiaries served in the last 30 days from completed distributions",
    )

    # Alert KPIs
    drims_alert_count = fields.Integer(
        string="Active Alerts",
        compute="_compute_drims_alert_kpis",
        store=True,
    )
    drims_critical_alert_count = fields.Integer(
        string="Critical Alerts",
        compute="_compute_drims_alert_kpis",
        store=True,
    )

    # Return KPIs
    drims_return_count = fields.Integer(
        string="Returns",
        compute="_compute_drims_return_kpis",
        store=True,
    )
    drims_return_value = fields.Float(
        string="Return Value",
        compute="_compute_drims_return_kpis",
        store=True,
    )

    # Related records
    drims_donation_ids = fields.One2many(
        "spp.drims.donation",
        "incident_id",
        string="Donations",
    )
    drims_request_ids = fields.One2many(
        "spp.drims.request",
        "incident_id",
        string="Requests",
    )
    drims_warehouse_ids = fields.Many2many(
        "stock.warehouse",
        string="DRIMS Warehouses",
        compute="_compute_drims_warehouses",
        inverse="_inverse_drims_warehouses",
        domain="[('is_drims_warehouse', '=', True)]",
        help="Warehouses responding to this incident. Editable here or from a warehouse's Active Incidents.",
    )
    drims_picking_ids = fields.One2many(
        "stock.picking",
        "incident_id",
        string="Stock Pickings",
    )
    drims_alert_ids = fields.One2many(
        "spp.drims.alert",
        "incident_id",
        string="Alerts",
    )
    drims_return_ids = fields.One2many(
        "spp.drims.return",
        "incident_id",
        string="Returns",
    )

    # Alert Threshold Overrides
    drims_low_stock_threshold_override = fields.Float(
        string="Low Stock Threshold Override (%)",
        help="Override the global low stock threshold for this incident.\n"
        "When set, alerts for this incident will use this percentage instead of the global setting.\n"
        "Leave empty to use the global threshold from DRIMS configuration.",
    )
    drims_expiry_warning_override = fields.Integer(
        string="Expiry Warning Override (Days)",
        help="Override the global expiry warning threshold for this incident.\n"
        "When set, alerts for this incident will use this number of days instead of the global setting.\n"
        "Leave empty to use the global threshold from DRIMS configuration.",
    )
    drims_expiry_critical_override = fields.Integer(
        string="Expiry Critical Override (Days)",
        help="Override the global expiry critical threshold for this incident.\n"
        "When set, alerts for this incident will use this number of days instead of the global setting.\n"
        "Leave empty to use the global threshold from DRIMS configuration.",
    )
    drims_sla_warning_override = fields.Integer(
        string="SLA Warning Override (Days)",
        help="Override the global SLA warning threshold for this incident.\n"
        "When set, alerts for this incident will use this number of days instead of the global setting.\n"
        "Leave empty to use the global threshold from DRIMS configuration.",
    )

    def _compute_drims_warehouses(self):
        """Compute warehouses linked to this incident.

        Returns DRIMS-enabled warehouses that have been associated with
        this incident for receiving/distributing relief supplies.
        """
        Warehouse = self.env["stock.warehouse"]
        for rec in self:
            rec.drims_warehouse_ids = Warehouse.search(
                [
                    ("incident_ids", "in", rec.id),
                    ("is_drims_warehouse", "=", True),
                ]
            )

    def _inverse_drims_warehouses(self):
        """OP#1164: allow defining an incident's warehouses from the incident.

        Writes back to the ``stock.warehouse.incident_ids`` many2many (the same
        link editable from the warehouse's "Active Incidents"), so both sides
        stay in sync. Writing through ``stock.warehouse.write`` also lets the
        OP#1094 stock-KPI cache invalidation fire for the affected incidents.
        """
        Warehouse = self.env["stock.warehouse"]
        for rec in self:
            current = Warehouse.search([("incident_ids", "in", rec.id), ("is_drims_warehouse", "=", True)])
            target = rec.drims_warehouse_ids
            (target - current).write({"incident_ids": [(4, rec.id)]})
            (current - target).write({"incident_ids": [(3, rec.id)]})

    @api.depends(
        "drims_donation_ids",
        "drims_donation_ids.total_value",
        "drims_request_ids",
        "drims_request_ids.approval_state",
    )
    def _compute_drims_kpis(self):
        """Compute donation and request KPIs.

        Uses hybrid approach for expensive drims_donation_value:
        1. Try to read from spp.data.value cache
        2. Fall back to direct computation if cache miss
        """
        if not self:
            return

        DataValue = self.env["spp.data.value"]

        # Try to read cached donation values for all records
        # Note: variable_name implicitly identifies subject_model (no explicit filter needed)
        cached_values = DataValue.read_values(
            "drims_donation_value",
            self.ids,
            period_key="current",
        )

        for rec in self:
            donations = rec.drims_donation_ids
            requests = rec.drims_request_ids

            # Cheap KPIs - always compute directly (just counts)
            rec.drims_donation_count = len(donations)
            rec.drims_request_count = len(requests)
            rec.drims_request_pending = len(requests.filtered(lambda r: r.approval_state in ("pending", "draft")))

            # Expensive KPI - use cache with fallback
            if rec.id in cached_values:
                rec.drims_donation_value = cached_values[rec.id]
                _logger.debug("Cache hit for drims_donation_value on incident %s", rec.id)
            else:
                # Cache miss - compute directly
                rec.drims_donation_value = sum(donations.mapped("total_value"))
                _logger.debug("Cache miss for drims_donation_value on incident %s", rec.id)

    def _drims_incident_stock_units(self):
        """OP#1160: units + distinct-product count of stock related to THIS
        incident, across any warehouse.

        "Related to the incident" = items stocked in from this incident's
        donations, net of what its requests have committed out (allocated,
        which already covers dispatched). This is deliberately NOT the physical
        contents of the incident's warehouses (which mixes in unrelated stock).

        Returns:
            tuple(float, int): (total net units, number of distinct products
            with a positive net).
        """
        self.ensure_one()
        Picking = self.env["stock.picking"]

        # Stocked in: done moves on this incident's donation-receipt pickings.
        stocked = defaultdict(float)
        receipts = Picking.search(
            [
                ("incident_id", "=", self.id),
                ("drims_type", "=", "donation_receipt"),
                ("state", "=", "done"),
            ]
        )
        for move in receipts.mapped("move_ids").filtered(lambda m: m.state == "done"):
            stocked[move.product_id.id] += move.quantity

        # Committed out: quantity allocated by this incident's request lines
        # (allocation covers what is subsequently dispatched).
        allocated = defaultdict(float)
        for line in self.drims_request_ids.mapped("line_ids"):
            if line.quantity_allocated:
                allocated[line.product_id.id] += line.quantity_allocated

        total_units = 0.0
        product_count = 0
        for product_id, qty_in in stocked.items():
            net = qty_in - allocated.get(product_id, 0.0)
            if net > 0:
                total_units += net
                product_count += 1
        return total_units, product_count

    def _drims_distributed_net(self):
        """OP#1160: distributed value net of returns.

        Value dispatched via completed request dispatches, minus the value of
        returned items (returns that are past draft and not cancelled) — those
        items came back and are therefore no longer distributed. Floored at 0.
        """
        self.ensure_one()
        Picking = self.env["stock.picking"]
        pickings = Picking.search(
            [
                ("incident_id", "=", self.id),
                ("state", "=", "done"),
                ("drims_type", "=", "request_dispatch"),
            ]
        )
        dispatched_value = 0.0
        for picking in pickings:
            for move in picking.move_ids.filtered(lambda m: m.state == "done"):
                dispatched_value += move.quantity * (move.product_id.standard_price or 0.0)

        returned_value = sum(
            self.drims_return_ids.filtered(lambda r: r.state not in ("draft", "cancelled")).mapped("total_value")
        )
        return max(0.0, dispatched_value - returned_value)

    @api.depends(
        "drims_picking_ids",
        "drims_picking_ids.state",
        "drims_picking_ids.drims_type",
        "drims_request_ids.line_ids.quantity_allocated",
        "drims_request_ids.line_ids.product_id",
        "drims_return_ids.total_value",
        "drims_return_ids.state",
    )
    def _compute_drims_stock_kpis(self):
        """Compute stock and distributed KPIs.

        - Units / product count (OP#1160): computed live from incident-related
          stock (donations stocked in, net of request allocations).
        - Stock value (monetary): warehouse contents, cached with fallback.
        - Distributed value (OP#1160): dispatched net of returns, cached with
          fallback.
        """
        if not self:
            return

        DataValue = self.env["spp.data.value"]

        # Cached monetary aggregations (variable_name implies subject_model).
        cached_stock_values = DataValue.read_values("drims_stock_value", self.ids, period_key="current")
        cached_distributed_values = DataValue.read_values("drims_distributed_value", self.ids, period_key="current")

        Warehouse = self.env["stock.warehouse"]
        Quant = self.env["stock.quant"]
        Picking = self.env["stock.picking"]

        for rec in self:
            # OP#1160: Units / Products — stock related to THIS incident.
            rec.drims_total_stock_units, rec.drims_stock_item_count = rec._drims_incident_stock_units()

            # Stock value (monetary) still reflects warehouse contents — cached.
            if rec.id in cached_stock_values:
                rec.drims_stock_value = cached_stock_values[rec.id]
            else:
                warehouses = Warehouse.search(
                    [
                        ("incident_ids", "in", rec.id),
                        ("is_drims_warehouse", "=", True),
                    ]
                )
                stock_value = 0.0
                if warehouses:
                    location_ids = warehouses.mapped("lot_stock_id").ids
                    if location_ids:
                        quants = Quant.search(
                            [
                                ("location_id", "child_of", location_ids),
                                ("quantity", ">", 0),
                            ]
                        )
                        stock_value = sum(q.quantity * (q.product_id.standard_price or 0.0) for q in quants)
                rec.drims_stock_value = stock_value

            # OP#1160: Distributed = dispatched net of returns — cached with fallback.
            if rec.id in cached_distributed_values:
                rec.drims_distributed_value = cached_distributed_values[rec.id]
            else:
                rec.drims_distributed_value = rec._drims_distributed_net()

            # Beneficiaries served - count from completed dispatches in last 30 days.
            thirty_days_ago = fields.Date.today() - timedelta(days=30)
            recent_pickings = Picking.search(
                [
                    ("incident_id", "=", rec.id),
                    ("state", "=", "done"),
                    ("drims_type", "=", "request_dispatch"),
                    ("date_done", ">=", thirty_days_ago),
                ]
            )
            rec.drims_beneficiaries_served = sum(recent_pickings.mapped("beneficiary_count"))

    def action_set_alert(self):
        """OP#1157: flag the incident into the 'alert' state.

        The 'alert' status exists in the base state machine but had no setter;
        this exposes it via the "Flag As Alert" header button.
        """
        self.write({"status": "alert"})

    def _drims_ensure_open(self, action):
        """OP#1158: block DRIMS operations once an incident is closed.

        Raises a UserError if any incident in the recordset is closed. Callers
        pass a short label (e.g. "approve a request") for the message. An empty
        recordset is a no-op.
        """
        for rec in self:
            if rec.status == "closed":
                raise UserError(
                    _("Cannot %(action)s: incident '%(name)s' is closed.")
                    % {"action": action, "name": rec.display_name}
                )

    def action_view_drims_donations(self):
        """Open list view of donations for this incident.

        Returns:
            dict: Action window configuration for donations list/form view.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Donations",
            "res_model": "spp.drims.donation",
            "view_mode": "list,form",
            "domain": [("incident_id", "=", self.id)],
            "context": {"default_incident_id": self.id},
        }

    def action_view_drims_requests(self):
        """Open list view of supply requests for this incident.

        Returns:
            dict: Action window configuration for requests list/form view.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Requests",
            "res_model": "spp.drims.request",
            "view_mode": "list,form",
            "domain": [("incident_id", "=", self.id)],
            "context": {"default_incident_id": self.id},
        }

    @api.depends(
        "drims_alert_ids",
        "drims_alert_ids.state",
        "drims_alert_ids.priority",
    )
    def _compute_drims_alert_kpis(self):
        """Compute alert counts for dashboard display."""
        for rec in self:
            alerts = rec.drims_alert_ids.filtered(lambda a: a.state in ("active", "acknowledged"))
            rec.drims_alert_count = len(alerts)
            rec.drims_critical_alert_count = len(alerts.filtered(lambda a: a.priority == "critical"))

    @api.depends(
        "drims_return_ids",
        "drims_return_ids.total_value",
    )
    def _compute_drims_return_kpis(self):
        """Compute return counts and values for dashboard display.

        Uses hybrid approach for expensive drims_return_value:
        1. Try to read from spp.data.value cache
        2. Fall back to direct computation if cache miss
        """
        if not self:
            return

        DataValue = self.env["spp.data.value"]

        # Try to read cached return values for all records
        # Note: variable_name implicitly identifies subject_model (no explicit filter needed)
        cached_values = DataValue.read_values(
            "drims_return_value",
            self.ids,
            period_key="current",
        )

        for rec in self:
            returns = rec.drims_return_ids

            # Cheap KPI - always compute directly (just count)
            rec.drims_return_count = len(returns)

            # Expensive KPI - use cache with fallback
            if rec.id in cached_values:
                rec.drims_return_value = cached_values[rec.id]
                _logger.debug("Cache hit for drims_return_value on incident %s", rec.id)
            else:
                # Cache miss - compute directly
                rec.drims_return_value = sum(returns.mapped("total_value"))
                _logger.debug("Cache miss for drims_return_value on incident %s", rec.id)

    def action_view_drims_alerts(self):
        """Open list view of alerts for this incident."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Alerts",
            "res_model": "spp.drims.alert",
            "view_mode": "list,form",
            "domain": [("incident_id", "=", self.id)],
            "context": {"default_incident_id": self.id},
        }

    def action_view_drims_returns(self):
        """Open list view of returns for this incident."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Returns",
            "res_model": "spp.drims.return",
            "view_mode": "list,form",
            "domain": [("incident_id", "=", self.id)],
            "context": {"default_incident_id": self.id},
        }

    # ═══════════════════════════════════════════════════════════════════════
    # KPI CACHE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def _refresh_incident_kpi_cache(self):
        """Refresh cached KPI values for incidents.

        Computes all expensive KPIs and stores them in spp.data.value cache:
        - drims_donation_value (TTL: 3600s / 1 hour)
        - drims_stock_value (TTL: 1800s / 30 min)
        - drims_distributed_value (TTL: 1800s / 30 min)
        - drims_return_value (TTL: 3600s / 1 hour)

        This method is called by cron to pre-warm the cache for active incidents.
        """
        if not self:
            return

        DataValue = self.env["spp.data.value"]
        Warehouse = self.env["stock.warehouse"]
        Quant = self.env["stock.quant"]
        Picking = self.env["stock.picking"]

        values_to_upsert = []

        for incident in self:
            # 1. Compute donation value
            donations = incident.drims_donation_ids
            donation_value = sum(donations.mapped("total_value"))
            values_to_upsert.append(
                {
                    "variable_name": "drims_donation_value",
                    "subject_model": "spp.hazard.incident",
                    "subject_id": incident.id,
                    "period_key": "current",
                    "value_json": {"value": donation_value},
                    "value_type": "number",
                    "source_type": "aggregate",
                    "ttl_seconds": 3600,  # 1 hour
                }
            )

            # 2. Compute stock value
            warehouses = Warehouse.search(
                [
                    ("incident_ids", "in", incident.id),
                    ("is_drims_warehouse", "=", True),
                ]
            )
            stock_value = 0.0
            warehouse_count = len(warehouses)
            if warehouses:
                location_ids = warehouses.mapped("lot_stock_id").ids
                if location_ids:
                    quants = Quant.search(
                        [
                            ("location_id", "child_of", location_ids),
                            ("quantity", ">", 0),
                        ]
                    )
                    stock_value = sum(q.quantity * (q.product_id.standard_price or 0.0) for q in quants)
            values_to_upsert.append(
                {
                    "variable_name": "drims_stock_value",
                    "subject_model": "spp.hazard.incident",
                    "subject_id": incident.id,
                    "period_key": "current",
                    "value_json": {
                        "value": stock_value,
                        "warehouse_count": warehouse_count,
                    },
                    "value_type": "number",
                    "source_type": "aggregate",
                    "ttl_seconds": 1800,  # 30 minutes
                }
            )

            # 3. Compute distributed value (OP#1160: net of returns).
            pickings = Picking.search(
                [
                    ("incident_id", "=", incident.id),
                    ("state", "=", "done"),
                    ("drims_type", "=", "request_dispatch"),
                ]
            )
            picking_count = len(pickings)
            distributed_value = incident._drims_distributed_net()
            values_to_upsert.append(
                {
                    "variable_name": "drims_distributed_value",
                    "subject_model": "spp.hazard.incident",
                    "subject_id": incident.id,
                    "period_key": "current",
                    "value_json": {
                        "value": distributed_value,
                        "picking_count": picking_count,
                    },
                    "value_type": "number",
                    "source_type": "aggregate",
                    "ttl_seconds": 1800,  # 30 minutes
                }
            )

            # 4. Compute return value
            returns = incident.drims_return_ids
            return_value = sum(returns.mapped("total_value"))
            values_to_upsert.append(
                {
                    "variable_name": "drims_return_value",
                    "subject_model": "spp.hazard.incident",
                    "subject_id": incident.id,
                    "period_key": "current",
                    "value_json": {"value": return_value},
                    "value_type": "number",
                    "source_type": "aggregate",
                    "ttl_seconds": 3600,  # 1 hour
                }
            )

        # Bulk upsert all values
        if values_to_upsert:
            result = DataValue.upsert_values(values_to_upsert)
            _logger.info(
                "Refreshed KPI cache for %d incidents: %s",
                len(self),
                result,
            )

        return True

    @api.model
    def _cron_refresh_drims_kpis(self):
        """Cron job to refresh DRIMS KPIs for active incidents.

        Refreshes cached KPI values for incidents in active states to ensure
        dashboard displays fresh data without expensive real-time computation.

        Called by scheduled action (recommended frequency: every 30 minutes).
        """
        # Find active incidents (not closed)
        # status field values: alert, active, recovery, closed
        active_incidents = self.search(
            [
                ("status", "!=", "closed"),
            ]
        )

        if not active_incidents:
            _logger.info("No active incidents found for KPI refresh")
            return

        _logger.info("Starting KPI refresh for %d active incidents", len(active_incidents))
        active_incidents._refresh_incident_kpi_cache()
        _logger.info("Completed KPI refresh for %d active incidents", len(active_incidents))

    # ═══════════════════════════════════════════════════════════════════════
    # ALERT THRESHOLD HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    def get_threshold(self, threshold_name):
        """Get threshold value, checking incident override first.

        Retrieves alert threshold values with the following priority:
        1. Incident-specific override (if set)
        2. Global configuration setting (fallback)

        Args:
            threshold_name (str): Name of the threshold to retrieve.
                Valid values: 'low_stock_threshold', 'expiry_warning_days',
                'expiry_critical_days', 'sla_warning_days'

        Returns:
            float or int: The threshold value to use for this incident.

        Raises:
            ValueError: If threshold_name is not recognized.
        """
        self.ensure_one()

        ConfigSettings = self.env["res.config.settings"]

        # Map threshold names to override fields and global getters
        threshold_map = {
            "low_stock_threshold": {
                "override_field": "drims_low_stock_threshold_override",
                "global_getter": ConfigSettings.get_low_stock_threshold,
                "convert_percent": True,
            },
            "expiry_warning_days": {
                "override_field": "drims_expiry_warning_override",
                "global_getter": ConfigSettings.get_expiry_warning_days,
                "convert_percent": False,
            },
            "expiry_critical_days": {
                "override_field": "drims_expiry_critical_override",
                "global_getter": ConfigSettings.get_expiry_critical_days,
                "convert_percent": False,
            },
            "sla_warning_days": {
                "override_field": "drims_sla_warning_override",
                "global_getter": ConfigSettings.get_delivery_sla_warning_days,
                "convert_percent": False,
            },
        }

        if threshold_name not in threshold_map:
            raise ValueError(
                f"Unknown threshold name: {threshold_name}. Valid values: {', '.join(threshold_map.keys())}"
            )

        config = threshold_map[threshold_name]
        override_value = self[config["override_field"]]

        # Check if override is set (not False, not 0)
        if override_value:
            # For low_stock_threshold, convert percentage to decimal
            if config["convert_percent"]:
                return override_value / 100.0
            return override_value

        # Fall back to global setting
        return config["global_getter"]()
