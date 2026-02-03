"""Studio Dashboard - simple landing page for Studio features."""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StudioDashboard(models.TransientModel):
    """Simple landing page for OpenSPP Studio.

    Provides navigation to the various Studio configuration modules.
    """

    _name = "spp.studio.dashboard"
    _description = "Studio Dashboard"

    def action_open_expressions(self):
        """Navigate to Expressions."""
        self.ensure_one()
        if "spp.cel.expression" not in self.env:
            return self._show_not_available_notification("Expressions")

        return {
            "type": "ir.actions.act_window",
            "name": "Expressions",
            "res_model": "spp.cel.expression",
            "view_mode": "list,form",
            "target": "current",
        }

    def action_open_variables(self):
        """Navigate to Variables."""
        self.ensure_one()
        if "spp.cel.variable" not in self.env:
            return self._show_not_available_notification("Variables")

        return {
            "type": "ir.actions.act_window",
            "name": "Variables",
            "res_model": "spp.cel.variable",
            "view_mode": "list,form",
            "target": "current",
        }

    def action_manage_registry_fields(self):
        """Navigate to Custom Fields management."""
        self.ensure_one()
        if "spp.studio.field" not in self.env:
            return self._show_not_available_notification("Custom Fields")

        return {
            "type": "ir.actions.act_window",
            "name": "Custom Fields",
            "res_model": "spp.studio.field",
            "view_mode": "list,form",
            "target": "current",
        }

    def action_manage_event_types(self):
        """Navigate to Event Types management."""
        self.ensure_one()
        if "spp.studio.event.type" not in self.env:
            return self._show_not_available_notification("Event Types")

        return {
            "type": "ir.actions.act_window",
            "name": "Event Types",
            "res_model": "spp.studio.event.type",
            "view_mode": "list,form",
            "target": "current",
        }

    def action_manage_change_request_types(self):
        """Navigate to Change Request Types management."""
        self.ensure_one()
        if "spp.studio.change.request.type" not in self.env:
            return self._show_not_available_notification("Change Requests")

        return {
            "type": "ir.actions.act_window",
            "name": "Change Request Types",
            "res_model": "spp.studio.change.request.type",
            "view_mode": "list,form",
            "target": "current",
        }

    def _show_not_available_notification(self, feature_name):
        """Show notification that a feature is not yet available."""
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": f"{feature_name} Not Available",
                "message": f"The {feature_name} module has not been installed yet.",
                "type": "warning",
                "sticky": False,
            },
        }
