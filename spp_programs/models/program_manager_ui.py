# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Program Manager UI Extensions

This module provides user-friendly UI extensions for program manager configuration.
It adds computed summary fields and action methods to simplify the configuration experience.
"""

from odoo import _, api, fields, models

# Manager type metadata for user-friendly display
# Note: Using plain strings here instead of _() because this is evaluated at module import time.
# Translation happens at runtime when these strings are displayed in the UI.
MANAGER_TYPE_INFO = {
    # Eligibility Managers
    "spp.program.membership.manager.default": {
        "name": "Area & Filters",
        "icon": "fa-map-marker",
        "description": "Define eligibility by geographic area and registrant filters",
        "category": "eligibility",
    },
    "spp.program.membership.manager.sql": {
        "name": "SQL Query",
        "icon": "fa-database",
        "description": "Write custom SQL to identify eligible beneficiaries",
        "category": "eligibility",
    },
    "spp.program.membership.manager.tags": {
        "name": "Tag-based",
        "icon": "fa-tags",
        "description": "Select beneficiaries based on assigned tags",
        "category": "eligibility",
    },
    # Entitlement Managers
    "spp.program.entitlement.manager.default": {
        "name": "Basic Cash",
        "icon": "fa-gift",
        "description": "Basic entitlement configuration",
        "category": "entitlement",
    },
    "spp.program.entitlement.manager.cash": {
        "name": "Cash Transfer",
        "icon": "fa-money",
        "description": "Configure cash-based entitlements with amounts and rules",
        "category": "entitlement",
    },
    "spp.program.entitlement.manager.inkind": {
        "name": "In-Kind",
        "icon": "fa-cube",
        "description": "Configure in-kind benefits (goods, vouchers)",
        "category": "entitlement",
    },
    "spp.program.entitlement.manager.basket": {
        "name": "Entitlement Basket",
        "icon": "fa-shopping-basket",
        "description": "Configure basket of multiple entitlement items",
        "category": "entitlement",
    },
    # Cycle Managers
    "spp.cycle.manager.default": {
        "name": "Default",
        "icon": "fa-calendar",
        "description": "Standard cycle management with recurrence options",
        "category": "cycle",
    },
    # Program Managers
    "spp.program.manager.default": {
        "name": "Default",
        "icon": "fa-cogs",
        "description": "Standard program management",
        "category": "program",
    },
    # Payment Managers
    "spp.program.payment.manager.default": {
        "name": "Default",
        "icon": "fa-credit-card",
        "description": "Standard payment processing",
        "category": "payment",
    },
    # Deduplication Managers
    "spp.deduplication.manager.default": {
        "name": "Default",
        "icon": "fa-copy",
        "description": "Basic deduplication checks",
        "category": "deduplication",
    },
    "spp.deduplication.manager.phone_number": {
        "name": "Phone Number",
        "icon": "fa-phone",
        "description": "Detect duplicates by phone number",
        "category": "deduplication",
    },
    "spp.deduplication.manager.id_dedup": {
        "name": "ID Document",
        "icon": "fa-id-card",
        "description": "Detect duplicates by ID documents",
        "category": "deduplication",
    },
    # Compliance Managers
    "spp.compliance.manager.default": {
        "name": "CEL Expression",
        "icon": "fa-check-circle",
        "description": "Define ongoing compliance criteria using CEL expressions",
        "category": "compliance",
    },
    # NOTE: SMS notification manager moved to spp_programs_sms bridge module
}


class ProgramManagerUI(models.Model):
    """Extends Program with UI-friendly manager configuration."""

    _inherit = "spp.program"

    # ==================== Computed Summary Fields ====================

    eligibility_manager_summary = fields.Text(
        string="Eligibility Summary",
        compute="_compute_eligibility_summary",
    )
    eligibility_manager_type = fields.Char(
        string="Eligibility Type",
        compute="_compute_eligibility_summary",
    )
    eligibility_configured = fields.Boolean(
        string="Eligibility Configured",
        compute="_compute_eligibility_summary",
    )

    entitlement_manager_summary = fields.Text(
        string="Entitlement Summary",
        compute="_compute_entitlement_summary",
    )
    entitlement_manager_type = fields.Char(
        string="Entitlement Type",
        compute="_compute_entitlement_summary",
    )
    entitlement_configured = fields.Boolean(
        string="Entitlement Configured",
        compute="_compute_entitlement_summary",
    )

    cycle_manager_summary = fields.Text(
        string="Cycle Summary",
        compute="_compute_cycle_summary",
    )
    cycle_configured = fields.Boolean(
        string="Cycle Configured",
        compute="_compute_cycle_summary",
    )

    payment_manager_summary = fields.Text(
        string="Payment Summary",
        compute="_compute_payment_summary",
    )
    payment_configured = fields.Boolean(
        string="Payment Configured",
        compute="_compute_payment_summary",
    )

    deduplication_manager_summary = fields.Text(
        string="Deduplication Summary",
        compute="_compute_deduplication_summary",
    )
    deduplication_configured = fields.Boolean(
        string="Deduplication Configured",
        compute="_compute_deduplication_summary",
    )

    notification_manager_summary = fields.Text(
        string="Notification Summary",
        compute="_compute_notification_summary",
    )
    notification_configured = fields.Boolean(
        string="Notification Configured",
        compute="_compute_notification_summary",
    )

    compliance_manager_summary = fields.Text(
        string="Compliance Summary",
        compute="_compute_compliance_summary",
    )
    compliance_manager_type = fields.Char(
        string="Compliance Type",
        compute="_compute_compliance_summary",
    )
    compliance_configured = fields.Boolean(
        string="Compliance Configured",
        compute="_compute_compliance_summary",
    )

    @api.depends("eligibility_manager_ids", "eligibility_manager_ids.manager_ref_id")
    def _compute_eligibility_summary(self):
        for rec in self:
            if rec.eligibility_manager_ids and rec.eligibility_manager_ids[0].manager_ref_id:
                manager = rec.eligibility_manager_ids[0].manager_ref_id
                model_name = manager._name
                type_info = MANAGER_TYPE_INFO.get(model_name, {})
                rec.eligibility_manager_type = type_info.get("name", model_name)
                rec.eligibility_configured = True
                # Build summary - prefer template name over other details
                summary_parts = []
                if hasattr(manager, "source_expression_id") and manager.source_expression_id:
                    # Show template name when available
                    summary_parts.append(manager.source_expression_id.name)
                else:
                    # Fallback to other summary details
                    if hasattr(manager, "admin_area_ids") and manager.admin_area_ids:
                        areas = ", ".join(manager.admin_area_ids[:3].mapped("name"))
                        if len(manager.admin_area_ids) > 3:
                            areas += f" (+{len(manager.admin_area_ids) - 3} more)"
                        summary_parts.append(f"Areas: {areas}")
                    if hasattr(manager, "eligibility_domain") and manager.eligibility_domain != "[]":
                        summary_parts.append("Custom filters applied")
                rec.eligibility_manager_summary = " • ".join(summary_parts) if summary_parts else "Configured"
            else:
                rec.eligibility_manager_type = False
                rec.eligibility_manager_summary = False
                rec.eligibility_configured = False

    @api.depends("entitlement_manager_ids", "entitlement_manager_ids.manager_ref_id")
    def _compute_entitlement_summary(self):
        for rec in self:
            if rec.entitlement_manager_ids and rec.entitlement_manager_ids[0].manager_ref_id:
                manager = rec.entitlement_manager_ids[0].manager_ref_id
                model_name = manager._name
                type_info = MANAGER_TYPE_INFO.get(model_name, {})
                rec.entitlement_manager_type = type_info.get("name", model_name)
                rec.entitlement_configured = True
                # Build summary
                summary_parts = []
                if hasattr(manager, "max_amount") and manager.max_amount:
                    summary_parts.append(f"Max: {manager.max_amount}")
                if hasattr(manager, "entitlement_item_ids"):
                    count = len(manager.entitlement_item_ids)
                    if count:
                        summary_parts.append(f"{count} entitlement rules")
                rec.entitlement_manager_summary = " • ".join(summary_parts) if summary_parts else "Configured"
            else:
                rec.entitlement_manager_type = False
                rec.entitlement_manager_summary = False
                rec.entitlement_configured = False

    @api.depends("cycle_manager_ids", "cycle_manager_ids.manager_ref_id")
    def _compute_cycle_summary(self):
        for rec in self:
            if rec.cycle_manager_ids and rec.cycle_manager_ids[0].manager_ref_id:
                manager = rec.cycle_manager_ids[0].manager_ref_id
                rec.cycle_configured = True
                summary_parts = []
                if hasattr(manager, "cycle_duration") and hasattr(manager, "rrule_type"):
                    duration = manager.cycle_duration
                    rrule = manager.rrule_type
                    if rrule and duration:
                        summary_parts.append(f"Every {duration} {rrule}")
                if hasattr(manager, "auto_approve_entitlements") and manager.auto_approve_entitlements:
                    summary_parts.append("Auto-approve enabled")
                rec.cycle_manager_summary = " • ".join(summary_parts) if summary_parts else "Configured"
            else:
                rec.cycle_manager_summary = False
                rec.cycle_configured = False

    @api.depends("payment_manager_ids", "payment_manager_ids.manager_ref_id")
    def _compute_payment_summary(self):
        for rec in self:
            if rec.payment_manager_ids and rec.payment_manager_ids[0].manager_ref_id:
                manager = rec.payment_manager_ids[0].manager_ref_id
                rec.payment_configured = True
                summary_parts = []
                if hasattr(manager, "create_batch") and manager.create_batch:
                    summary_parts.append("Auto-create batch")
                rec.payment_manager_summary = " • ".join(summary_parts) if summary_parts else "Configured"
            else:
                rec.payment_manager_summary = False
                rec.payment_configured = False

    @api.depends("deduplication_manager_ids", "deduplication_manager_ids.manager_ref_id")
    def _compute_deduplication_summary(self):
        for rec in self:
            if rec.deduplication_manager_ids:
                rec.deduplication_configured = True
                types = []
                for mgr in rec.deduplication_manager_ids:
                    if mgr.manager_ref_id:
                        type_info = MANAGER_TYPE_INFO.get(mgr.manager_ref_id._name, {})
                        types.append(type_info.get("name", "Custom"))
                rec.deduplication_manager_summary = ", ".join(types) if types else "Configured"
            else:
                rec.deduplication_manager_summary = False
                rec.deduplication_configured = False

    @api.depends("notification_manager_ids", "notification_manager_ids.manager_ref_id")
    def _compute_notification_summary(self):
        for rec in self:
            if rec.notification_manager_ids:
                rec.notification_configured = True
                types = []
                for mgr in rec.notification_manager_ids:
                    if mgr.manager_ref_id:
                        type_info = MANAGER_TYPE_INFO.get(mgr.manager_ref_id._name, {})
                        types.append(type_info.get("name", "Custom"))
                rec.notification_manager_summary = ", ".join(types) if types else "Configured"
            else:
                rec.notification_manager_summary = False
                rec.notification_configured = False

    @api.depends("compliance_manager_ids", "compliance_manager_ids.manager_ref_id")
    def _compute_compliance_summary(self):
        for rec in self:
            if rec.compliance_manager_ids and rec.compliance_manager_ids[0].manager_ref_id:
                manager = rec.compliance_manager_ids[0].manager_ref_id
                model_name = manager._name
                type_info = MANAGER_TYPE_INFO.get(model_name, {})
                rec.compliance_manager_type = type_info.get("name", model_name)
                rec.compliance_configured = True
                # Build summary - prefer template name over raw expression
                summary_parts = []
                if hasattr(manager, "source_expression_id") and manager.source_expression_id:
                    # Show template name when available
                    summary_parts.append(manager.source_expression_id.name)
                elif hasattr(manager, "compliance_cel_expression") and manager.compliance_cel_expression:
                    # Fallback to truncated CEL expression
                    expr = manager.compliance_cel_expression
                    if len(expr) > 50:
                        expr = expr[:47] + "..."
                    summary_parts.append(f"CEL: {expr}")
                rec.compliance_manager_summary = " • ".join(summary_parts) if summary_parts else "Configured"
            else:
                rec.compliance_manager_type = False
                rec.compliance_manager_summary = False
                rec.compliance_configured = False

    # ==================== Action Methods ====================

    def action_configure_eligibility(self):
        """Open eligibility manager configuration."""
        self.ensure_one()
        readonly = not self.can_edit_configuration
        if self.eligibility_manager_ids and self.eligibility_manager_ids[0].manager_ref_id:
            return self.eligibility_manager_ids[0].open_manager_form(readonly=readonly)
        # No manager yet - open wizard to create one (only if can edit)
        if not readonly:
            return self._open_manager_setup_wizard("eligibility")
        return False

    def action_configure_entitlement(self):
        """Open entitlement manager configuration."""
        self.ensure_one()
        readonly = not self.can_edit_configuration
        if self.entitlement_manager_ids and self.entitlement_manager_ids[0].manager_ref_id:
            return self.entitlement_manager_ids[0].open_manager_form(readonly=readonly)
        if not readonly:
            return self._open_manager_setup_wizard("entitlement")
        return False

    def action_configure_cycle(self):
        """Open cycle manager configuration."""
        self.ensure_one()
        readonly = not self.can_edit_configuration
        if self.cycle_manager_ids and self.cycle_manager_ids[0].manager_ref_id:
            return self.cycle_manager_ids[0].open_manager_form(readonly=readonly)
        if not readonly:
            return self._open_manager_setup_wizard("cycle")
        return False

    def action_configure_payment(self):
        """Open payment manager configuration."""
        self.ensure_one()
        readonly = not self.can_edit_configuration
        if self.payment_manager_ids and self.payment_manager_ids[0].manager_ref_id:
            return self.payment_manager_ids[0].open_manager_form(readonly=readonly)
        if not readonly:
            return self._open_manager_setup_wizard("payment")
        return False

    def action_configure_deduplication(self):
        """Open deduplication manager configuration."""
        self.ensure_one()
        readonly = not self.can_edit_configuration
        if self.deduplication_manager_ids and self.deduplication_manager_ids[0].manager_ref_id:
            return self.deduplication_manager_ids[0].open_manager_form(readonly=readonly)
        if not readonly:
            return self._open_manager_setup_wizard("deduplication")
        return False

    def action_configure_notification(self):
        """Open notification manager configuration."""
        self.ensure_one()
        readonly = not self.can_edit_configuration
        if self.notification_manager_ids and self.notification_manager_ids[0].manager_ref_id:
            return self.notification_manager_ids[0].open_manager_form(readonly=readonly)
        if not readonly:
            return self._open_manager_setup_wizard("notification")
        return False

    def action_configure_compliance(self):
        """Open compliance manager configuration."""
        self.ensure_one()
        readonly = not self.can_edit_configuration
        if self.compliance_manager_ids and self.compliance_manager_ids[0].manager_ref_id:
            return self.compliance_manager_ids[0].open_manager_form(readonly=readonly)
        if not readonly:
            return self._open_manager_setup_wizard("compliance")
        return False

    def _open_manager_setup_wizard(self, manager_type):
        """Open wizard to set up a new manager of the specified type."""
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Setup Required"),
                "message": _("Please add a %s manager first using the list below.") % manager_type,
                "sticky": False,
                "type": "warning",
            },
        }

    def get_manager_type_options(self, category):
        """Get available manager type options for a category."""
        options = []
        for model_name, info in MANAGER_TYPE_INFO.items():
            if info.get("category") == category:
                # Check if the model exists (module might not be installed)
                if model_name in self.env:
                    options.append(
                        {
                            "model": model_name,
                            "name": info.get("name", model_name),
                            "icon": info.get("icon", "fa-cog"),
                            "description": info.get("description", ""),
                        }
                    )
        return options
