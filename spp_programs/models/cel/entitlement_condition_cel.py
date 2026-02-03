import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


class CashEntitlementItemCEL(models.Model):
    """Extends Cash Entitlement Item to support CEL expressions."""

    _inherit = "spp.program.entitlement.manager.cash.item"

    # Mode selection: domain (legacy) or CEL (new)
    condition_mode = fields.Selection(
        selection=[
            ("domain", "Domain"),
            ("cel", "CEL Expression"),
        ],
        string="Condition Mode",
        default="domain",
        help="Choose how to define entitlement conditions:\n"
        "- Domain: Use Odoo's domain filter\n"
        "- CEL Expression: Write readable expressions like 'age_years(me.birthdate) >= 18'",
    )

    # CEL expression field
    cel_condition = fields.Text(
        string="CEL Condition",
        default=False,
        help="Write condition criteria using CEL syntax.\n"
        "Examples:\n"
        "- age_years(me.birthdate) >= 60\n"
        "- me.gender == 'female' and age_years(me.birthdate) >= 18\n"
        "- members.exists(m, age_years(m.birthdate) < 5)\n"
        "- metric('household.size') >= 4",
    )

    # Preview fields (computed)
    cel_preview_count = fields.Integer(
        string="Matching Beneficiaries",
        compute="_compute_cel_preview",
        help="Number of beneficiaries matching the current expression",
    )
    cel_preview_error = fields.Text(
        string="Expression Error",
        compute="_compute_cel_preview",
    )
    cel_is_valid = fields.Boolean(
        string="Expression Valid",
        compute="_compute_cel_preview",
    )

    @api.depends("cel_condition", "condition_mode")
    def _compute_cel_preview(self):
        for rec in self:
            rec.cel_preview_count = 0
            rec.cel_preview_error = ""
            rec.cel_is_valid = False

            if rec.condition_mode != "cel" or not rec.cel_condition:
                rec.cel_is_valid = rec.condition_mode == "domain"
                continue

            try:
                # Use CEL service facade to compile and preview
                # For entitlements, we always work with res.partner (beneficiaries)
                base_domain = []

                # Determine profile based on program target type
                profile = "registry_individuals"  # Default to individuals
                if rec.entitlement_id and rec.entitlement_id.program_id:
                    profile = (
                        "registry_groups"
                        if rec.entitlement_id.program_id.target_type == "group"
                        else "registry_individuals"
                    )

                service = self.env["spp.cel.service"]
                result = service.compile_expression(
                    rec.cel_condition, profile=profile, base_domain=base_domain, limit=0
                )

                if result.get("valid"):
                    rec.cel_preview_count = result.get("count", 0)
                    rec.cel_is_valid = True
                else:
                    rec.cel_preview_error = result.get("error", _("Unknown error"))

            except Exception as e:
                rec.cel_preview_error = _("Error: %s") % str(e)

    def action_test_cel_expression(self):
        """Test the CEL expression and show results."""
        self.ensure_one()
        if not self.cel_condition:
            raise ValidationError(_("Please enter a CEL expression first."))

        # Force recompute
        self._compute_cel_preview()

        if self.cel_preview_error:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Expression Error"),
                    "message": self.cel_preview_error,
                    "type": "danger",
                    "sticky": True,
                },
            }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Expression Valid"),
                "message": _("%d beneficiaries match this expression.") % self.cel_preview_count,
                "type": "success",
                "sticky": False,
            },
        }

    def action_preview_beneficiaries(self):
        """Open a list view of matching beneficiaries."""
        self.ensure_one()
        if self.condition_mode != "cel" or not self.cel_condition:
            raise ValidationError(_("Please enter a CEL expression first."))

        try:
            # Determine profile based on program target type
            profile = "registry_individuals"  # Default to individuals
            if self.entitlement_id and self.entitlement_id.program_id:
                profile = (
                    "registry_groups"
                    if self.entitlement_id.program_id.target_type == "group"
                    else "registry_individuals"
                )

            service = self.env["spp.cel.service"]
            result = service.compile_expression(
                self.cel_condition,
                profile=profile,
                base_domain=[],
                limit=0,
                materialize_sql=True,  # Required for window actions - domain must be serializable
            )

            if not result.get("valid"):
                error_msg = result.get("error", "Unknown error")
                raise ValidationError(_("Error previewing: %s") % error_msg)

            domain = result.get("domain", [])

            return {
                "type": "ir.actions.act_window",
                "name": _("Matching Beneficiaries (%d)") % result.get("count", 0),
                "res_model": "res.partner",
                "view_mode": "list,form",
                "domain": domain,
                "target": "new",
                "context": {"create": False},
            }

        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(_("Error previewing: %s") % str(e)) from e

    def _compile_cel_to_domain(self, base_domain=None):
        """
        Compile the CEL expression to an Odoo domain.

        :param base_domain: Optional base domain to combine with CEL domain
        :return: Compiled domain list
        """
        if self.condition_mode != "cel" or not self.cel_condition:
            return base_domain or []

        try:
            # Determine profile based on program target type
            profile = "registry_individuals"  # Default to individuals
            if self.entitlement_id and self.entitlement_id.program_id:
                profile = (
                    "registry_groups"
                    if self.entitlement_id.program_id.target_type == "group"
                    else "registry_individuals"
                )

            service = self.env["spp.cel.service"]
            result = service.compile_expression(
                self.cel_condition, profile=profile, base_domain=base_domain or [], limit=0
            )

            if not result.get("valid"):
                error_msg = result.get("error", "Unknown error")
                _logger.error("CEL expression error: %s", error_msg)
                raise ValidationError(_("Invalid CEL expression: %s") % error_msg)

            # Return the compiled domain
            cel_domain = result.get("domain", [])
            _logger.debug("CEL compiled domain: %s", cel_domain)
            return cel_domain

        except ValidationError:
            raise
        except Exception as e:
            _logger.error("CEL expression error: %s", e)
            raise ValidationError(_("Invalid CEL expression: %s") % str(e)) from e


class CashEntitlementManagerCEL(models.Model):
    """Extend Cash Entitlement Manager to handle CEL conditions in items."""

    _inherit = "spp.program.entitlement.manager.cash"

    def _apply_compliance_filtering(self, cycle, beneficiaries):
        """Apply compliance filtering when the automated filtering mechanism is enabled.

        When the filtering mechanism is set to "2" (filter on entitlement creation),
        only beneficiaries who pass the compliance criteria will receive entitlements.

        :param cycle: The cycle being processed
        :param beneficiaries: Cycle membership records to filter
        :return: Filtered cycle membership records
        """
        # Check if user has permission (program managers only)
        if not self.env.user.has_group("spp_programs.group_programs_manager"):
            raise AccessError(
                _(
                    "You do not have permission to prepare entitlements using compliance criteria. "
                    "This operation is restricted to program managers."
                )
            )

        automated_filtering_mechanism = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(
                "spp_programs_compliance_criteria.beneficiaries_automated_filtering_mechanism",
                "0",
            )
        )
        has_compliance = bool(cycle.program_id.compliance_manager_ids)

        if automated_filtering_mechanism == "2" and has_compliance:
            _logger.info("Applying compliance filtering on entitlement creation")
            domain = cycle._get_compliance_criteria_domain()
            if domain:
                # Use sudo() for cross-program compliance lookup on registrants
                satisfied_registrant_ids = (
                    self.env["res.partner"]
                    .sudo()  # nosemgrep: odoo-sudo-on-sensitive-models
                    .search(domain)
                    .ids
                )
                original_count = len(beneficiaries)
                beneficiaries = beneficiaries.filtered(
                    lambda cm: cm.partner_id.id in satisfied_registrant_ids
                )
                _logger.info(
                    "Compliance filtering: %d -> %d beneficiaries",
                    original_count,
                    len(beneficiaries),
                )

        return beneficiaries

    def _get_all_beneficiaries(self, all_beneficiaries_ids, condition, evaluate_one_item):
        """
        Override to support CEL expressions in addition to domain conditions.

        This method is called by prepare_entitlements() to filter beneficiaries
        based on the entitlement item's condition.

        :param all_beneficiaries_ids: List of beneficiary IDs to filter
        :param condition: Either a domain string (legacy) or an entitlement item record
        :param evaluate_one_item: Boolean if true will evaluate all beneficiaries if it should be removed
        :return: Filtered list of beneficiary IDs
        """
        # Check if we're dealing with an entitlement item with CEL mode
        # The condition parameter might be passed from the context
        ctx_item = self.env.context.get("current_entitlement_item")

        if ctx_item and hasattr(ctx_item, "condition_mode") and ctx_item.condition_mode == "cel":
            # CEL mode: compile expression to domain
            domain = [("id", "in", all_beneficiaries_ids)]
            cel_domain = ctx_item._compile_cel_to_domain(base_domain=domain)

            beneficiaries_ids = self.env["res.partner"].search(cel_domain).ids

            # Check if single evaluation
            if evaluate_one_item:
                # Remove beneficiaries_ids from all_beneficiaries_ids
                for bid in beneficiaries_ids:
                    if bid in all_beneficiaries_ids:
                        all_beneficiaries_ids.remove(bid)

            return beneficiaries_ids if not evaluate_one_item else all_beneficiaries_ids

        # Legacy domain mode: use parent implementation
        return super()._get_all_beneficiaries(all_beneficiaries_ids, condition, evaluate_one_item)

    def prepare_entitlements(self, cycle, beneficiaries):
        """
        Override to pass entitlement item context for CEL evaluation.

        This ensures that when _get_all_beneficiaries is called, it has access
        to the current entitlement item to check for CEL mode.

        Also applies compliance filtering when the automated filtering mechanism
        is set to filter on entitlement creation.
        """
        # Apply compliance filtering if enabled
        beneficiaries = self._apply_compliance_filtering(cycle, beneficiaries)

        if not self.entitlement_item_ids:
            raise ValidationError(_("There are no items entered for this entitlement manager."))

        all_beneficiaries_ids = beneficiaries.mapped("partner_id.id")

        new_entitlements_to_create = {}
        for rec in self.entitlement_item_ids:
            _logger.info("Processing entitlement item with amount: %s", rec.amount)

            # Determine how to filter beneficiaries based on condition mode
            if rec.condition_mode == "cel" and rec.cel_condition:
                # CEL mode: compile expression to domain
                base_domain = [("id", "in", all_beneficiaries_ids)]
                cel_domain = rec._compile_cel_to_domain(base_domain=base_domain)
                beneficiaries_ids = self.env["res.partner"].search(cel_domain).ids

                # Check if single evaluation
                if self.evaluate_one_item:
                    # Remove beneficiaries_ids from all_beneficiaries_ids
                    original_ids = all_beneficiaries_ids.copy()
                    all_beneficiaries_ids = [bid for bid in all_beneficiaries_ids if bid not in beneficiaries_ids]
                    beneficiaries_ids = [bid for bid in beneficiaries_ids if bid in original_ids]

            elif rec.condition:
                # Legacy domain mode
                beneficiaries_ids = self.with_context(current_entitlement_item=rec)._get_all_beneficiaries(
                    all_beneficiaries_ids.copy() if self.evaluate_one_item else all_beneficiaries_ids,
                    rec.condition,
                    self.evaluate_one_item,
                )
            else:
                # No condition
                beneficiaries_ids = all_beneficiaries_ids

            _logger.info("Found %d matching beneficiaries for entitlement item", len(beneficiaries_ids))

            beneficiaries_with_entitlements = (
                self.env["spp.entitlement"]
                .search(
                    [
                        ("cycle_id", "=", cycle.id),
                        ("partner_id", "in", beneficiaries_ids),
                    ]
                )
                .mapped("partner_id.id")
            )
            entitlements_to_create = [
                beneficiaries_id
                for beneficiaries_id in beneficiaries_ids
                if beneficiaries_id not in beneficiaries_with_entitlements
            ]

            entitlement_start_validity = cycle.start_date
            entitlement_end_validity = cycle.end_date
            entitlement_currency = rec.currency_id.id

            beneficiaries_with_entitlements_to_create = self.env["res.partner"].browse(entitlements_to_create)

            for beneficiary_id in beneficiaries_with_entitlements_to_create:
                # Check if CEL amount calculation is available (from spp_entitlement_amount_cel)
                if hasattr(rec, "amount_cel_expression") and rec.amount_cel_expression:
                    try:
                        amount = rec._calculate_cel_amount(beneficiary_id)
                        _logger.debug(
                            "CEL amount for beneficiary_id=%s: %s (formula: %s)",
                            beneficiary_id.id,
                            amount,
                            rec.amount_cel_expression,
                        )
                    except Exception as e:
                        _logger.error(
                            "Failed to calculate CEL amount for beneficiary_id=%s: %s. Skipping.",
                            beneficiary_id.id,
                            str(e),
                        )
                        continue
                else:
                    # Legacy fixed amount with multiplier
                    if rec.multiplier_field:
                        # Get the multiplier value from multiplier_field else return the default multiplier=1
                        multiplier = beneficiary_id.mapped(rec.multiplier_field.name)
                        if multiplier:
                            multiplier = multiplier[0] or 0
                    else:
                        multiplier = 1
                    if rec.max_multiplier > 0 and multiplier > rec.max_multiplier:
                        multiplier = rec.max_multiplier
                    _logger.debug("Calculated multiplier: %s", multiplier)
                    amount = rec.amount * float(multiplier)

                # Compute the sum of cash entitlements
                if beneficiary_id.id in new_entitlements_to_create:
                    amount = amount + new_entitlements_to_create[beneficiary_id.id]["initial_amount"]
                # Check if amount > max_amount; ignore if max_amount is set to 0
                if self.max_amount > 0.0 and amount > self.max_amount:
                    amount = self.max_amount

                new_entitlements_to_create[beneficiary_id.id] = {
                    "cycle_id": cycle.id,
                    "partner_id": beneficiary_id.id,
                    "initial_amount": amount,
                    "currency_id": entitlement_currency,
                    "state": "draft",
                    "is_cash_entitlement": True,
                    "valid_from": entitlement_start_validity,
                    "valid_until": entitlement_end_validity,
                }
                # Check if there are additional fields to be added in entitlements
                addl_fields = self._get_addl_entitlement_fields(beneficiary_id)
                if addl_fields:
                    new_entitlements_to_create[beneficiary_id.id].update(addl_fields)

        # Create entitlement records
        for ent in new_entitlements_to_create:
            initial_amount = new_entitlements_to_create[ent]["initial_amount"]
            new_entitlements_to_create[ent]["initial_amount"] = self._check_subsidy(initial_amount)
            # Create non-zero entitlements only
            if new_entitlements_to_create[ent]["initial_amount"] > 0.0:
                self.env["spp.entitlement"].create(new_entitlements_to_create[ent])
