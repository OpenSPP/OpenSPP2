# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Program Manager UI Extensions

This module provides user-friendly UI extensions for program manager configuration.
It adds computed summary fields and action methods to simplify the configuration experience.
"""

from odoo import _, api, fields, models


def _format_recurrence(duration, rrule_type):
    """Human-readable recurrence label.

    Turns rrule_type values ('daily', 'weekly', 'monthly', 'yearly') + an
    interval into natural English ("Monthly" vs "Every 2 months" etc.),
    replacing the literal "Every 1 monthly" that confused QA.
    """
    if not rrule_type or not duration:
        return ""
    singular = {
        "daily": _("Daily"),
        "weekly": _("Weekly"),
        "monthly": _("Monthly"),
        "yearly": _("Yearly"),
    }
    plural = {
        "daily": _("days"),
        "weekly": _("weeks"),
        "monthly": _("months"),
        "yearly": _("years"),
    }
    if duration == 1:
        return singular.get(rrule_type, rrule_type.capitalize())
    return _("Every %(n)s %(unit)s") % {"n": duration, "unit": plural.get(rrule_type, rrule_type)}


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
        "name": "Default Cycle Schedule",
        "icon": "fa-calendar",
        "description": "Standard cycle management with recurrence options",
        "category": "cycle",
    },
    # Program Managers
    "spp.program.manager.default": {
        "name": "Default Program Manager",
        "icon": "fa-cogs",
        "description": "Standard program management",
        "category": "program",
    },
    # Payment Managers
    "spp.program.payment.manager.default": {
        "name": "Default Payment",
        "icon": "fa-credit-card",
        "description": "Standard payment processing",
        "category": "payment",
    },
    # Deduplication Managers
    "spp.deduplication.manager.default": {
        "name": "Default Deduplication",
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

    # --- Single-vs-multi manager layout helpers (one per banner).
    # When a banner has exactly one manager configured, the UI collapses the
    # Method / Details header row into a single-manager view and renders the
    # full configuration detail in a full-width block below, instead of a
    # list widget. These computes drive that layout.
    eligibility_manager_count = fields.Integer(compute="_compute_banner_layout_helpers")
    eligibility_manager_display = fields.Char(compute="_compute_banner_layout_helpers")
    eligibility_manager_detail = fields.Text(compute="_compute_banner_layout_helpers")

    entitlement_manager_count = fields.Integer(compute="_compute_banner_layout_helpers")
    entitlement_manager_display = fields.Char(compute="_compute_banner_layout_helpers")
    entitlement_manager_detail = fields.Text(compute="_compute_banner_layout_helpers")

    cycle_manager_count = fields.Integer(compute="_compute_banner_layout_helpers")
    cycle_manager_display = fields.Char(compute="_compute_banner_layout_helpers")
    cycle_manager_detail = fields.Text(compute="_compute_banner_layout_helpers")

    compliance_manager_count = fields.Integer(compute="_compute_banner_layout_helpers")
    compliance_manager_display = fields.Char(compute="_compute_banner_layout_helpers")
    compliance_manager_detail = fields.Text(compute="_compute_banner_layout_helpers")

    payment_manager_count = fields.Integer(compute="_compute_banner_layout_helpers")
    payment_manager_display = fields.Char(compute="_compute_banner_layout_helpers")
    payment_manager_detail = fields.Text(compute="_compute_banner_layout_helpers")

    deduplication_manager_count = fields.Integer(compute="_compute_banner_layout_helpers")
    deduplication_manager_display = fields.Char(compute="_compute_banner_layout_helpers")
    deduplication_manager_detail = fields.Text(compute="_compute_banner_layout_helpers")

    @api.depends("eligibility_manager_ids", "eligibility_manager_ids.manager_ref_id")
    def _compute_eligibility_summary(self):
        for rec in self:
            if rec.eligibility_manager_ids and rec.eligibility_manager_ids[0].manager_ref_id:
                manager = rec.eligibility_manager_ids[0].manager_ref_id
                model_name = manager._name
                type_info = MANAGER_TYPE_INFO.get(model_name, {})
                # Show "CEL Expression" when mode is CEL, otherwise use model type
                if hasattr(manager, "eligibility_mode") and manager.eligibility_mode == "cel":
                    rec.eligibility_manager_type = "CEL Expression"
                else:
                    rec.eligibility_manager_type = type_info.get("name", model_name)
                rec.eligibility_configured = True
                # Build summary - prefer template name over other details
                summary_parts = []
                if hasattr(manager, "source_expression_id") and manager.source_expression_id:
                    # Show template name when available
                    summary_parts.append(manager.source_expression_id.name)
                elif hasattr(manager, "cel_expression") and manager.cel_expression:
                    # Show truncated CEL expression
                    expr = manager.cel_expression
                    if len(expr) > 50:
                        expr = expr[:47] + "..."
                    summary_parts.append(f"CEL: {expr}")
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
                        summary_parts.append(_format_recurrence(duration, rrule))
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

    @api.depends(
        "eligibility_manager_ids",
        "eligibility_manager_ids.manager_ref_id",
        "entitlement_manager_ids",
        "entitlement_manager_ids.manager_ref_id",
        "cycle_manager_ids",
        "cycle_manager_ids.manager_ref_id",
        "compliance_manager_ids",
        "compliance_manager_ids.manager_ref_id",
        "payment_manager_ids",
        "payment_manager_ids.manager_ref_id",
        "deduplication_manager_ids",
        "deduplication_manager_ids.manager_ref_id",
    )
    def _compute_banner_layout_helpers(self):
        """Populate the `<banner>_manager_count / _display / _detail` fields
        that drive the single-vs-multi layout on each manager banner."""
        banners = (
            ("eligibility_manager_ids", "eligibility"),
            ("entitlement_manager_ids", "entitlement"),
            ("cycle_manager_ids", "cycle"),
            ("compliance_manager_ids", "compliance"),
            ("payment_manager_ids", "payment"),
            ("deduplication_manager_ids", "deduplication"),
        )
        for rec in self:
            for field_name, prefix in banners:
                wrappers = rec[field_name].filtered(lambda w: w.manager_ref_id)
                count = len(wrappers)
                rec[f"{prefix}_manager_count"] = count
                display = ""
                detail = ""
                if count == 1:
                    concrete = wrappers[0].manager_ref_id
                    display = concrete.display_name or concrete.name or ""
                    detail = rec._manager_detail_for(prefix, concrete)
                elif count > 1:
                    display = _("%d methods configured") % count
                rec[f"{prefix}_manager_display"] = display
                rec[f"{prefix}_manager_detail"] = detail

    def _manager_detail_for(self, prefix, concrete):
        """Method-specific detail rendering for a single manager.

        Dispatches by field signature: CEL expression → show it, entitlement
        items → expand rules, flat-amount entitlement → spell out amounts,
        otherwise fall back to the existing short summary.
        """
        self.ensure_one()
        # CEL managers (eligibility / compliance)
        cel_detail = self._manager_detail_cel(concrete)
        if cel_detail is not None:
            return cel_detail
        # Entitlement manager with items
        if hasattr(concrete, "entitlement_item_ids") and concrete.entitlement_item_ids:
            return self._manager_detail_entitlement_items(concrete)
        # "Basic Cash" entitlement — flat amount + per-person multiplier
        if hasattr(concrete, "amount_per_cycle") or hasattr(concrete, "amount_per_individual_in_group"):
            return self._manager_detail_basic_cash(concrete)
        # Fallback to existing summary
        summary = self[f"{prefix}_manager_summary"] if f"{prefix}_manager_summary" in self._fields else ""
        if summary and summary != "Configured":
            return summary
        return ""

    def _manager_detail_cel(self, concrete):
        """Return CEL-based detail or None if not a CEL manager."""
        if hasattr(concrete, "cel_expression"):
            cel = getattr(concrete, "cel_expression", "") or ""
        elif hasattr(concrete, "compliance_cel_expression"):
            cel = getattr(concrete, "compliance_cel_expression", "") or ""
        else:
            return None
        if cel:
            return cel
        # Empty CEL — warn that every target-type registrant will match.
        target = (self.target_type or "").strip().lower()
        target_label = {
            "group": _("groups / households"),
            "individual": _("individuals"),
        }.get(target, _("registrants"))
        return (
            _(
                "No CEL expression defined. With an empty expression, every %s registrant of this "
                "program will match — click Edit above to narrow the criteria."
            )
            % target_label
        )

    @staticmethod
    def _format_money(amount, currency):
        """Render a Float amount with thousands grouping + 2-decimal precision,
        prefixed by the currency symbol on the left. We don't use
        odoo.tools.misc.format_amount here because it honours the currency's
        `position` field — which puts the symbol after the amount for some
        currency records — and the program overview should always show the
        symbol on the left for consistency.
        """
        precision = currency.decimal_places if currency else 2
        formatted = f"{amount:,.{precision}f}"
        if not currency:
            return formatted
        symbol = currency.symbol or currency.name or ""
        return f"{symbol} {formatted}".strip()

    def _manager_detail_entitlement_items(self, concrete):
        """Render each entitlement_item line readably."""
        lines = []
        for item in concrete.entitlement_item_ids:
            amount_expr = getattr(item, "amount_cel_expression", "") or ""
            amount = getattr(item, "amount", 0) or 0
            multiplier_field = getattr(item, "multiplier_field", False)
            condition = getattr(item, "condition", "") or ""
            currency = getattr(item, "currency_id", False)
            amount_with_sym = self._format_money(amount, currency)
            if amount_expr:
                line = _("Amount per beneficiary: %s") % amount_expr
            elif multiplier_field:
                mult_label = multiplier_field.field_description or multiplier_field.name
                line = _("Amount per beneficiary: %(amount)s × %(mult)s") % {
                    "amount": amount_with_sym,
                    "mult": mult_label,
                }
            else:
                line = _("Amount per beneficiary: %(amount)s per cycle") % {"amount": amount_with_sym}
            if condition and condition.strip() not in ("[]", ""):
                line += _(" — only if %s") % condition
            lines.append(line)
        if len(concrete.entitlement_item_ids) > 1:
            lines.insert(0, _("%d entitlement rule(s):") % len(concrete.entitlement_item_ids))
        return "\n".join(lines)

    def _manager_detail_basic_cash(self, concrete):
        """Render the Basic Cash entitlement fields readably."""
        per_cycle = getattr(concrete, "amount_per_cycle", 0) or 0
        per_person = getattr(concrete, "amount_per_individual_in_group", 0) or 0
        max_people = getattr(concrete, "max_individual_in_group", 0) or 0
        fee_pct = getattr(concrete, "transfer_fee_pct", 0) or 0
        fee_amount = getattr(concrete, "transfer_fee_amount", 0) or 0
        currency = getattr(concrete, "currency_id", False)

        def _fmt(amt):
            return self._format_money(amt, currency)

        lines = []
        if per_cycle:
            lines.append(_("Amount per cycle: %s") % _fmt(per_cycle))
        if per_person:
            line = _("Amount per person in group: %s") % _fmt(per_person)
            if max_people:
                line += _(" (up to %s people)") % max_people
            lines.append(line)
        if fee_pct:
            lines.append(_("Transfer fee: %s%% of amount") % fee_pct)
        elif fee_amount:
            lines.append(_("Transfer fee: %s flat") % _fmt(fee_amount))
        if not lines:
            return _("No amount configured yet — click Edit above to set how much each beneficiary receives per cycle.")
        return "\n".join(lines)

    # ==================== Action Methods ====================

    def action_configure_eligibility(self):
        """Open eligibility manager configuration."""
        self.ensure_one()
        readonly = not self.can_edit_configuration
        if self.eligibility_manager_ids and self.eligibility_manager_ids[0].manager_ref_id:
            return self.eligibility_manager_ids[0].open_manager_form(readonly=readonly, title=_("Who Qualifies?"))
        # No manager yet - open wizard to create one (only if can edit)
        if not readonly:
            return self._open_manager_setup_wizard("eligibility")
        return False

    def action_configure_entitlement(self):
        """Open entitlement manager configuration."""
        self.ensure_one()
        readonly = not self.can_edit_configuration
        if self.entitlement_manager_ids and self.entitlement_manager_ids[0].manager_ref_id:
            return self.entitlement_manager_ids[0].open_manager_form(
                readonly=readonly, title=_("What Do They Receive?")
            )
        if not readonly:
            return self._open_manager_setup_wizard("entitlement")
        return False

    def action_configure_cycle(self):
        """Open cycle manager configuration."""
        self.ensure_one()
        readonly = not self.can_edit_configuration
        if self.cycle_manager_ids and self.cycle_manager_ids[0].manager_ref_id:
            return self.cycle_manager_ids[0].open_manager_form(readonly=readonly, title=_("Program Schedule"))
        if not readonly:
            return self._open_manager_setup_wizard("cycle")
        return False

    def action_configure_payment(self):
        """Open payment manager configuration."""
        self.ensure_one()
        readonly = not self.can_edit_configuration
        if self.payment_manager_ids and self.payment_manager_ids[0].manager_ref_id:
            return self.payment_manager_ids[0].open_manager_form(readonly=readonly, title=_("Payment Processing"))
        if not readonly:
            return self._open_manager_setup_wizard("payment")
        return False

    def action_configure_deduplication(self):
        """Open deduplication configuration.

        Unlike compliance or payment, a program may have several deduplication
        methods — by ID and by phone, say. Opening ``[0]`` would silently edit
        the first and leave the rest unreachable, so the card only offers this
        button when there is exactly one; with several, each method has its own
        cog in the card body (OP#1171).
        """
        self.ensure_one()
        readonly = not self.can_edit_configuration
        configured = self.deduplication_manager_ids.filtered(lambda wrapper: wrapper.manager_ref_id)
        if len(configured) == 1:
            return configured.open_manager_form(readonly=readonly, title=_("Deduplication"))
        if len(configured) > 1:
            # Not target="new": a list in a dialog cannot drill into a form, so
            # it renders as a dead end — rows look clickable and do nothing.
            # Opening it in the breadcrumb keeps the rows navigable. The card
            # itself lists the methods with their own buttons, so this is a
            # fallback for programmatic callers rather than the normal route.
            return {
                "type": "ir.actions.act_window",
                "name": _("Duplicate Detection"),
                "res_model": "spp.deduplication.manager",
                "view_mode": "list,form",
                "domain": [("id", "in", configured.ids)],
                "context": {"create": False, "default_program_id": self.id},
            }
        if not readonly:
            return self.action_add_deduplication_manager()
        return False

    def action_configure_notification(self):
        """Open notification manager configuration."""
        self.ensure_one()
        readonly = not self.can_edit_configuration
        if self.notification_manager_ids and self.notification_manager_ids[0].manager_ref_id:
            return self.notification_manager_ids[0].open_manager_form(readonly=readonly, title=_("Notifications"))
        if not readonly:
            return self._open_manager_setup_wizard("notification")
        return False

    def action_configure_compliance(self):
        """Open compliance manager configuration."""
        self.ensure_one()
        readonly = not self.can_edit_configuration
        if self.compliance_manager_ids and self.compliance_manager_ids[0].manager_ref_id:
            return self.compliance_manager_ids[0].open_manager_form(readonly=readonly, title=_("Compliance Criteria"))
        if not readonly:
            return self._open_manager_setup_wizard("compliance")
        return False

    def action_add_compliance_manager(self):
        """Open the default compliance manager form in create mode.

        The program form's compliance banner shows a `+ Add` zero-state
        button when no compliance manager is configured. We open the
        concrete model (`spp.compliance.manager.default`) in create mode
        with `default_program_id` and `_spp_wrapper_model` in context.
        Saving the dialog runs the source-mixin's `create()` override,
        which auto-creates the wrapper (see source_mixin.py). Dismissing
        the dialog with `X` leaves nothing in the DB — that's the whole
        point of #953.
        """
        self.ensure_one()
        if not self.can_edit_configuration:
            return False
        if self.compliance_manager_ids:
            return self.action_configure_compliance()
        Concrete = self.env["spp.compliance.manager.default"]
        return {
            "type": "ir.actions.act_window",
            "name": _("Compliance Criteria"),
            "res_model": Concrete._name,
            "view_mode": "form",
            "views": [(Concrete.get_manager_view_id(), "form")],
            "target": "new",
            "context": {
                "default_program_id": self.id,
                # The mixin's create() will create the wrapper and rely
                # on its `program_id` inverse to populate the program's
                # One2many `compliance_manager_ids` automatically — no
                # m2m write needed.
                "_spp_wrapper_model": "spp.compliance.manager",
            },
        }

    def action_add_payment_manager(self):
        """Open the default payment manager form in create mode.

        Mirrors `action_add_compliance_manager`. The concrete model's
        `create()` override auto-creates the default batch tag if the
        form was saved with `create_batch=True` and no tag selected —
        so we don't have to pre-create it here (which would orphan the
        tag if the user dismisses the dialog). The source-mixin's
        `create()` override creates the wrapper, then writes it into
        the program's `payment_manager_ids` Many2many because that
        field doesn't auto-resolve via the wrapper's `program_id`
        inverse. See #953.
        """
        self.ensure_one()
        if not self.can_edit_configuration:
            return False
        if self.payment_manager_ids:
            return self.action_configure_payment()
        Concrete = self.env["spp.program.payment.manager.default"]
        return {
            "type": "ir.actions.act_window",
            "name": _("Payment Processing"),
            "res_model": Concrete._name,
            "view_mode": "form",
            "views": [(Concrete.get_manager_view_id(), "form")],
            "target": "new",
            "context": {
                "default_program_id": self.id,
                "_spp_wrapper_model": "spp.program.payment.manager",
                "_spp_program_m2m_field": "payment_manager_ids",
            },
        }

    def action_add_deduplication_manager(self):
        """Open the two-step dialog for adding a deduplication method (OP#1171).

        Compliance and Payment open their single concrete model directly
        (#952, #953). Deduplication has three methods rather than one, so the
        dialog has to ask which before it can ask for a name — the wizard does
        both, then creates the concrete record with the context that makes
        `source_mixin.create()` build the wrapper alongside it.

        Adding is offered even when a method already exists, because a program
        may legitimately check by ID *and* by phone.
        """
        self.ensure_one()
        if not self.can_edit_configuration:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Add a Deduplication Method"),
            "res_model": "spp.deduplication.setup.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_program_id": self.id},
        }

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
