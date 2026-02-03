# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DRIMS Configuration Parameter Helpers.

This module provides helper methods to read DRIMS configuration parameters
from ir.config_parameter. The parameters are owned by spp_drims with defaults
set in data/config_defaults.xml.

The optional spp_studio_drims module provides a Settings UI to modify these
parameters without requiring technical access.

Parameter Naming Convention:
    drims.sla.*          - Approval SLA settings
    drims.delivery_sla.* - Delivery deadline settings
    drims.alerts.*       - Alert threshold settings
    drims.performance.*  - Performance tuning settings
"""

from odoo import api, models


class ResConfigSettings(models.TransientModel):
    """DRIMS configuration parameter accessors.

    Provides class methods to retrieve DRIMS configuration values from
    ir.config_parameter with sensible defaults. These defaults match
    the values in data/config_defaults.xml.
    """

    _inherit = "res.config.settings"

    # =========================================================================
    # APPROVAL SLA HELPERS
    # =========================================================================

    @api.model
    def get_approval_sla_hours(self, priority_code):
        """Get approval SLA hours for a given priority code.

        Args:
            priority_code: One of 'critical', 'high', 'routine', 'low'

        Returns:
            int: Hours allowed to approve requests of this priority
        """
        ICP = self.env["ir.config_parameter"].sudo()
        defaults = {"critical": 4, "high": 8, "routine": 24, "low": 48}
        param_key = f"drims.sla.hours.{priority_code}"
        return int(ICP.get_param(param_key, defaults.get(priority_code, 24)))

    @api.model
    def get_approval_sla_warning_pct(self):
        """Get approval SLA warning threshold as percentage (0-100).

        Returns:
            int: Percentage of SLA time at which to show warning (default 75)
        """
        ICP = self.env["ir.config_parameter"].sudo()
        return int(ICP.get_param("drims.sla.warning_threshold_pct", 75))

    # =========================================================================
    # DELIVERY SLA HELPERS
    # =========================================================================

    @api.model
    def is_delivery_sla_enabled(self):
        """Check if delivery SLA alerts are enabled.

        Returns:
            bool: True if delivery SLA alerts should be generated
        """
        ICP = self.env["ir.config_parameter"].sudo()
        return ICP.get_param("drims.delivery_sla.enabled", "True") == "True"

    @api.model
    def get_delivery_sla_warning_days(self):
        """Get days before deadline to show delivery SLA warning.

        Returns:
            int: Days before deadline (default 2)
        """
        ICP = self.env["ir.config_parameter"].sudo()
        return int(ICP.get_param("drims.delivery_sla.warning_days", 2))

    @api.model
    def get_delivery_sla_critical_days(self):
        """Get days overdue to escalate to critical.

        Returns:
            int: Days overdue (default 3)
        """
        ICP = self.env["ir.config_parameter"].sudo()
        return int(ICP.get_param("drims.delivery_sla.critical_days", 3))

    @api.model
    def get_delivery_sla_escalate_days(self):
        """Get days overdue to escalate to highest priority.

        Returns:
            int: Days overdue (default 7)
        """
        ICP = self.env["ir.config_parameter"].sudo()
        return int(ICP.get_param("drims.delivery_sla.escalate_days", 7))

    # =========================================================================
    # INVENTORY ALERT HELPERS
    # =========================================================================

    @api.model
    def get_low_stock_threshold(self):
        """Get low stock threshold as decimal (0.0 to 1.0).

        Returns:
            float: Threshold as decimal (default 0.50 = 50%)
        """
        ICP = self.env["ir.config_parameter"].sudo()
        pct = float(ICP.get_param("drims.alerts.low_stock_threshold_pct", 50))
        return pct / 100.0

    @api.model
    def get_expiry_warning_days(self):
        """Get days before expiry to show warning alert.

        Returns:
            int: Days before expiry (default 30)
        """
        ICP = self.env["ir.config_parameter"].sudo()
        return int(ICP.get_param("drims.alerts.expiry_warning_days", 30))

    @api.model
    def get_expiry_high_days(self):
        """Get days before expiry to show high priority alert.

        Returns:
            int: Days before expiry (default 14)
        """
        ICP = self.env["ir.config_parameter"].sudo()
        return int(ICP.get_param("drims.alerts.expiry_high_days", 14))

    @api.model
    def get_expiry_critical_days(self):
        """Get days before expiry to show critical alert.

        Returns:
            int: Days before expiry (default 7)
        """
        ICP = self.env["ir.config_parameter"].sudo()
        return int(ICP.get_param("drims.alerts.expiry_critical_days", 7))

    @api.model
    def is_auto_resolve_enabled(self):
        """Check if alerts should auto-resolve when conditions are fixed.

        Returns:
            bool: True if auto-resolve is enabled (default True)
        """
        ICP = self.env["ir.config_parameter"].sudo()
        return ICP.get_param("drims.alerts.auto_resolve", "True") == "True"

    # =========================================================================
    # PERFORMANCE HELPERS
    # =========================================================================

    @api.model
    def get_kpi_cache_ttl_minutes(self):
        """Get KPI cache time-to-live in minutes.

        Returns:
            int: Cache TTL in minutes (default 30)
        """
        ICP = self.env["ir.config_parameter"].sudo()
        return int(ICP.get_param("drims.performance.kpi_cache_ttl_minutes", 30))
