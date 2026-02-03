# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging
from datetime import timedelta

from odoo import _, api, fields, models

from .constants import (
    ALERT_EXPIRY,
    ALERT_LOW_STOCK,
    ALERT_SLA_BREACH,
    ALERT_SLA_WARNING,
    VOCAB_ALERT_TYPES,
)

_logger = logging.getLogger(__name__)

# Color map for alert type badges (Odoo color indices 1-11)
ALERT_TYPE_COLORS = {
    ALERT_LOW_STOCK: 1,  # Red - critical
    ALERT_EXPIRY: 3,  # Yellow - warning
    ALERT_SLA_WARNING: 4,  # Blue - info
    ALERT_SLA_BREACH: 1,  # Red - critical
}


class DrimsAlert(models.Model):
    """DRIMS-specific alert extension.

    Extends the base spp.alert model with DRIMS-specific fields and business logic
    for disaster relief inventory monitoring. Adds links to incidents, warehouses,
    products, and requests. Includes automated monitoring via scheduled jobs for:
    - Low stock conditions
    - Expiring inventory
    - SLA breaches and warnings
    """

    _name = "spp.drims.alert"
    _description = "DRIMS Alert"
    _inherit = "spp.alert"

    # DRIMS-specific relationship fields
    incident_id = fields.Many2one(
        "spp.hazard.incident",
        string="Incident",
        index=True,
        help="Related hazard incident",
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
        index=True,
        help="Related DRIMS warehouse",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        index=True,
        help="Related product",
    )
    request_id = fields.Many2one(
        "spp.drims.request",
        string="Request",
        index=True,
        help="Related DRIMS request",
    )

    # Override alert_type_id domain to use DRIMS namespace
    alert_type_id = fields.Many2one(
        domain=f"[('vocabulary_id.namespace_uri', '=', '{VOCAB_ALERT_TYPES}')]",
    )

    # ============================================
    # UX Enhancement Fields (ALT-001/002)
    # ============================================

    # Urgency indicators for quick scanning
    urgency_state = fields.Selection(
        [
            ("overdue", "Overdue"),
            ("urgent", "Urgent"),
            ("soon", "Soon"),
            ("normal", "Normal"),
        ],
        string="Urgency State",
        compute="_compute_urgency_state",
        store=True,
        index=True,
        help="Computed urgency state for styling and filtering",
    )

    urgency_label = fields.Char(
        string="Urgency",
        compute="_compute_urgency_label",
        help="Human-readable urgency indicator (e.g., '2 days overdue', 'Tomorrow')",
    )

    # Alert type color for badges
    alert_type_color = fields.Integer(
        string="Alert Type Color",
        compute="_compute_alert_type_color",
        store=True,
        help="Color code for alert type badge (1-11)",
    )

    # Deadline date for calendar view
    deadline_date = fields.Date(
        string="Deadline Date",
        compute="_compute_deadline_date",
        store=True,
        help="Computed deadline for calendar view",
    )

    # Alert age for staleness detection
    age_hours = fields.Float(
        string="Age (Hours)",
        compute="_compute_age",
        help="Hours since alert was created",
    )

    age_label = fields.Char(
        string="Age",
        compute="_compute_age",
        help="Human-readable age (e.g., '2h ago', '3d ago')",
    )

    # Assignment for team coordination
    assigned_to_id = fields.Many2one(
        "res.users",
        string="Assigned To",
        tracking=True,
        index=True,
        help="User responsible for handling this alert",
    )

    @api.depends("days_until", "state")
    def _compute_urgency_state(self):
        """Compute urgency state for styling and filtering (stored)."""
        for alert in self:
            if alert.state == "resolved":
                alert.urgency_state = "normal"
                continue

            days = alert.days_until or 0

            # Overdue (negative days)
            if days < 0:
                alert.urgency_state = "overdue"
            # Urgent (0-2 days)
            elif days <= 2:
                alert.urgency_state = "urgent"
            # Soon (3-7 days)
            elif days <= 7:
                alert.urgency_state = "soon"
            # Normal (8+ days)
            else:
                alert.urgency_state = "normal"

    @api.depends("days_until", "state")
    def _compute_urgency_label(self):
        """Compute human-readable urgency label (not stored)."""
        for alert in self:
            if alert.state == "resolved":
                alert.urgency_label = _("Resolved")
                continue

            days = alert.days_until or 0

            # Overdue (negative days)
            if days < 0:
                if days == -1:
                    alert.urgency_label = _("1 day overdue")
                else:
                    alert.urgency_label = _("%d days overdue") % abs(days)
            # Urgent (0-2 days)
            elif days <= 2:
                if days == 0:
                    alert.urgency_label = _("Today")
                elif days == 1:
                    alert.urgency_label = _("Tomorrow")
                else:
                    alert.urgency_label = _("%d days") % days
            # Soon or Normal (3+ days)
            else:
                alert.urgency_label = _("%d days") % days

    @api.depends("alert_type")
    def _compute_alert_type_color(self):
        """Assign colors to alert types for visual distinction."""
        for alert in self:
            alert.alert_type_color = ALERT_TYPE_COLORS.get(alert.alert_type, 7)  # Default gray

    @api.depends("days_until", "create_date")
    def _compute_deadline_date(self):
        """Compute actual deadline date from days_until for calendar view."""
        for alert in self:
            if alert.days_until is not None and alert.create_date:
                alert.deadline_date = fields.Date.to_date(alert.create_date) + timedelta(days=alert.days_until)
            else:
                alert.deadline_date = False

    @api.depends("create_date")
    def _compute_age(self):
        """Compute alert age for staleness detection."""
        now = fields.Datetime.now()
        for alert in self:
            if alert.create_date:
                delta = now - alert.create_date
                hours = delta.total_seconds() / 3600
                alert.age_hours = hours

                if hours < 1:
                    minutes = int(delta.total_seconds() / 60)
                    alert.age_label = _("%dm ago") % minutes
                elif hours < 24:
                    alert.age_label = _("%dh ago") % int(hours)
                else:
                    days = int(hours / 24)
                    alert.age_label = _("%dd ago") % days
            else:
                alert.age_hours = 0
                alert.age_label = ""

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to use DRIMS-specific sequence."""
        for vals in vals_list:
            if vals.get("reference", _("New")) == _("New"):
                # Use DRIMS-specific sequence (ALT-) instead of base (ALR-)
                vals["reference"] = self.env["ir.sequence"].sudo().next_by_code("spp.drims.alert") or _("New")
        return super().create(vals_list)

    @api.model
    def _cron_check_low_stock(self):
        """Scheduled action to check for low stock situations."""
        _logger.info("DRIMS Alert Engine: Checking low stock levels...")
        AlertType = self.env["spp.vocabulary.code"]
        low_stock_type = AlertType.search(
            [
                ("vocabulary_id.namespace_uri", "=", VOCAB_ALERT_TYPES),
                ("code", "=", ALERT_LOW_STOCK),
            ],
            limit=1,
        )
        if not low_stock_type:
            _logger.warning("Low stock alert type not found")
            return

        # Check DRIMS warehouses
        warehouses = self.env["stock.warehouse"].search(
            [
                ("is_drims_warehouse", "=", True),
            ]
        )
        for wh in warehouses:
            # Get active incidents linked to this warehouse
            incidents = self.env["spp.hazard.incident"].search(
                [
                    ("status", "=", "active"),
                ]
            )
            for incident in incidents:
                self._check_incident_stock_levels(incident, wh, low_stock_type)
        _logger.info("DRIMS Alert Engine: Low stock check completed")

    def _check_incident_stock_levels(self, incident, warehouse, alert_type):
        """Check stock levels for an incident's requested products.

        Uses batch SQL operations to avoid N+1 query patterns.
        """
        # Get products needed from pending requests using SQL aggregation
        self.env.cr.execute(
            """
            SELECT
                rl.product_id,
                SUM(rl.quantity_requested - rl.quantity_delivered) as quantity_needed
            FROM spp_drims_request_line rl
            JOIN spp_drims_request r ON r.id = rl.request_id
            WHERE r.incident_id = %s
              AND r.approval_state IN ('pending', 'approved')
            GROUP BY rl.product_id
            HAVING SUM(rl.quantity_requested - rl.quantity_delivered) > 0
        """,
            (incident.id,),
        )
        products_needed = {row[0]: row[1] for row in self.env.cr.fetchall()}

        if not products_needed:
            return

        # Batch fetch product records
        product_ids = list(products_needed.keys())
        products = self.env["product.product"].browse(product_ids)
        product_map = {p.id: p for p in products}

        # Get available quantities for all products at once using SQL
        self.env.cr.execute(
            """
            SELECT
                sq.product_id,
                COALESCE(SUM(sq.quantity - sq.reserved_quantity), 0) as available
            FROM stock_quant sq
            JOIN stock_location sl ON sl.id = sq.location_id
            WHERE sq.product_id = ANY(%s)
              AND sl.parent_path LIKE %s
            GROUP BY sq.product_id
        """,
            (product_ids, f"{warehouse.lot_stock_id.parent_path}%"),
        )
        available_qty = {row[0]: row[1] for row in self.env.cr.fetchall()}

        # Get existing active alerts in batch
        existing_alerts = self.search(
            [
                ("alert_type_id", "=", alert_type.id),
                ("incident_id", "=", incident.id),
                ("warehouse_id", "=", warehouse.id),
                ("product_id", "in", product_ids),
                ("state", "in", ("active", "acknowledged")),
            ]
        )
        existing_product_ids = set(existing_alerts.mapped("product_id.id"))

        # Prepare alerts to create in batch
        alerts_to_create = []
        for product_id, qty_needed in products_needed.items():
            if product_id in existing_product_ids:
                continue
            product = product_map.get(product_id)
            if not product:
                continue
            available = available_qty.get(product_id, 0)
            threshold = qty_needed * 0.5
            if available < threshold:
                alerts_to_create.append(
                    {
                        "alert_type_id": alert_type.id,
                        "priority": "high" if available == 0 else "medium",
                        "title": _("Low Stock: %s") % product.name,
                        "description": _(
                            "Stock level for %s at %s is below threshold.\n"
                            "Available: %.2f, Needed: %.2f, Threshold: %.2f"
                        )
                        % (product.name, warehouse.name, available, qty_needed, threshold),
                        "incident_id": incident.id,
                        "warehouse_id": warehouse.id,
                        "product_id": product.id,
                        "current_value": available,
                        "threshold_value": threshold,
                    }
                )

        # Batch create alerts
        if alerts_to_create:
            self.create(alerts_to_create)

    @api.model
    def _cron_check_expiry(self):
        """Scheduled action to check for items nearing expiry.

        Uses batch SQL operations to avoid N+1 query patterns.
        Requires product_expiry module to be installed.
        """
        _logger.info("DRIMS Alert Engine: Checking expiry dates...")

        # Check if product_expiry module is installed (provides expiration_date field)
        if not self.env["ir.module.module"].search(
            [
                ("name", "=", "product_expiry"),
                ("state", "=", "installed"),
            ],
            limit=1,
        ):
            _logger.info("DRIMS Alert Engine: product_expiry module not installed, skipping expiry check")
            return

        AlertType = self.env["spp.vocabulary.code"]
        expiry_type = AlertType.search(
            [
                ("vocabulary_id.namespace_uri", "=", VOCAB_ALERT_TYPES),
                ("code", "=", ALERT_EXPIRY),
            ],
            limit=1,
        )
        if not expiry_type:
            _logger.warning("Expiry alert type not found")
            return

        today = fields.Date.today()
        expiry_threshold = today + timedelta(days=30)

        # Get expiring lots with warehouse info in a single query
        # Note: expiration_date is a datetime field from product_expiry module
        # We sum quantities from stock_quant since product_qty is computed
        self.env.cr.execute(
            """
            SELECT
                sl.id as lot_id,
                sl.name as lot_name,
                sl.expiration_date::date as expiration_date,
                COALESCE(SUM(sq.quantity), 0) as total_qty,
                pp.id as product_id,
                pt.name as product_name,
                sw.id as warehouse_id
            FROM stock_lot sl
            JOIN product_product pp ON pp.id = sl.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            JOIN stock_quant sq ON sq.lot_id = sl.id AND sq.quantity > 0
            JOIN stock_location loc ON loc.id = sq.location_id
            JOIN stock_warehouse sw ON loc.parent_path LIKE CONCAT(sw.lot_stock_id::text, '/%%')
            WHERE sl.expiration_date IS NOT NULL
              AND sl.expiration_date::date <= %s
              AND sw.is_drims_warehouse = TRUE
            GROUP BY sl.id, sl.name, sl.expiration_date, pp.id, pt.name, sw.id
            HAVING COALESCE(SUM(sq.quantity), 0) > 0
        """,
            (expiry_threshold,),
        )
        expiring_data = self.env.cr.fetchall()

        if not expiring_data:
            _logger.info("DRIMS Alert Engine: No expiring items found")
            return

        # Get product IDs for batch checks
        product_ids = list(set(row[4] for row in expiring_data))

        # Batch check for existing alerts
        existing_alerts = self.search(
            [
                ("alert_type_id", "=", expiry_type.id),
                ("product_id", "in", product_ids),
                ("state", "in", ("active", "acknowledged")),
            ]
        )
        existing_product_ids = set(existing_alerts.mapped("product_id.id"))

        # Prepare alerts to create in batch
        alerts_to_create = []
        for row in expiring_data:
            lot_id, lot_name, expiration_date, total_qty, product_id, product_name, warehouse_id = row
            if product_id in existing_product_ids:
                continue

            days_until = (expiration_date - today).days
            priority = "critical" if days_until <= 7 else ("high" if days_until <= 14 else "medium")

            alerts_to_create.append(
                {
                    "alert_type_id": expiry_type.id,
                    "priority": priority,
                    "title": _("Expiring: %s (Lot %s)") % (product_name, lot_name),
                    "description": _("Lot %s of %s will expire on %s (%d days).\n" "Current quantity: %.2f")
                    % (lot_name, product_name, expiration_date, days_until, total_qty),
                    "warehouse_id": warehouse_id,
                    "product_id": product_id,
                    "days_until": days_until,
                    "current_value": total_qty,
                }
            )
            # Mark as existing to avoid duplicates within this batch
            existing_product_ids.add(product_id)

        # Batch create alerts
        if alerts_to_create:
            self.create(alerts_to_create)
            _logger.info("DRIMS Alert Engine: Created %d expiry alerts", len(alerts_to_create))
        _logger.info("DRIMS Alert Engine: Expiry check completed")

    @api.model
    def _cron_check_sla(self):
        """Scheduled action to check for SLA breaches on requests."""
        _logger.info("DRIMS Alert Engine: Checking SLA compliance...")
        AlertType = self.env["spp.vocabulary.code"]
        sla_type = AlertType.search(
            [
                ("vocabulary_id.namespace_uri", "=", VOCAB_ALERT_TYPES),
                ("code", "=", ALERT_SLA_BREACH),
            ],
            limit=1,
        )
        if not sla_type:
            _logger.warning("SLA breach alert type not found")
            return

        today = fields.Date.today()
        # Find requests past their needed date that aren't delivered
        overdue_requests = self.env["spp.drims.request"].search(
            [
                ("date_needed", "<", today),
                ("state", "not in", ("delivered", "rejected")),
                ("approval_state", "in", ("approved", "pending")),
            ]
        )

        for request in overdue_requests:
            days_overdue = (today - request.date_needed).days
            priority = "critical" if days_overdue > 7 else ("high" if days_overdue > 3 else "medium")

            # Check if alert already exists
            existing = self.search(
                [
                    ("alert_type_id", "=", sla_type.id),
                    ("request_id", "=", request.id),
                    ("state", "in", ("active", "acknowledged")),
                ]
            )
            if not existing:
                self.create(
                    {
                        "alert_type_id": sla_type.id,
                        "priority": priority,
                        "title": _("SLA Breach: %s") % request.reference,
                        "description": _(
                            "Request %s was due on %s but is still not delivered.\n"
                            "Days overdue: %d\nDestination: %s\nTotal value: %.2f"
                        )
                        % (
                            request.reference,
                            request.date_needed,
                            days_overdue,
                            request.destination_area_id.name,
                            request.total_value,
                        ),
                        "incident_id": request.incident_id.id,
                        "request_id": request.id,
                        "days_until": -days_overdue,  # Negative = overdue
                    }
                )

        # Also check requests approaching deadline (within 2 days)
        upcoming_deadline = today + timedelta(days=2)
        at_risk_requests = self.env["spp.drims.request"].search(
            [
                ("date_needed", "<=", upcoming_deadline),
                ("date_needed", ">=", today),
                ("state", "not in", ("delivered", "dispatched", "rejected")),
                ("approval_state", "in", ("approved", "pending")),
            ]
        )

        sla_warning_type = AlertType.search(
            [
                ("vocabulary_id.namespace_uri", "=", VOCAB_ALERT_TYPES),
                ("code", "=", ALERT_SLA_WARNING),
            ],
            limit=1,
        )
        if sla_warning_type:
            for request in at_risk_requests:
                days_until = (request.date_needed - today).days
                existing = self.search(
                    [
                        ("alert_type_id", "=", sla_warning_type.id),
                        ("request_id", "=", request.id),
                        ("state", "in", ("active", "acknowledged")),
                    ]
                )
                if not existing:
                    self.create(
                        {
                            "alert_type_id": sla_warning_type.id,
                            "priority": "high" if days_until <= 1 else "medium",
                            "title": _("SLA Warning: %s") % request.reference,
                            "description": _(
                                "Request %s is due in %d day(s) and is not yet dispatched.\n"
                                "Destination: %s\nState: %s"
                            )
                            % (request.reference, days_until, request.destination_area_id.name, request.state),
                            "incident_id": request.incident_id.id,
                            "request_id": request.id,
                            "days_until": days_until,
                        }
                    )
        _logger.info("DRIMS Alert Engine: SLA check completed")

    # Action links for quick navigation (GAP-ALT-003)
    def _action_view_related(self, field_name, model_name, view_name):
        """Generic helper to navigate to a related record.

        Args:
            field_name: Name of the Many2one field on this model
            model_name: Technical name of the related model
            view_name: Display name for the window title

        Returns:
            dict: Window action to open the related record, or False if not set
        """
        self.ensure_one()
        related_record = getattr(self, field_name)
        if not related_record:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _(view_name),
            "res_model": model_name,
            "res_id": related_record.id,
            "view_mode": "form",
        }

    def action_view_incident(self):
        """Navigate to the related incident."""
        return self._action_view_related("incident_id", "spp.hazard.incident", "Incident")

    def action_view_warehouse(self):
        """Navigate to the related warehouse."""
        return self._action_view_related("warehouse_id", "stock.warehouse", "Warehouse")

    def action_view_product(self):
        """Navigate to the related product."""
        return self._action_view_related("product_id", "product.product", "Product")

    def action_view_request(self):
        """Navigate to the related request."""
        return self._action_view_related("request_id", "spp.drims.request", "Request")
