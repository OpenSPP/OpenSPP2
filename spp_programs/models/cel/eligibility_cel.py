import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class DefaultEligibilityManagerCEL(models.Model):
    """Extends the Default Eligibility Manager to support CEL expressions."""

    _inherit = "spp.program.membership.manager.default"

    # Mode selection: CEL expression (default)
    eligibility_mode = fields.Selection(
        selection=[
            ("cel", "CEL Expression"),
        ],
        string="Eligibility Mode",
        default="cel",
        help="Define eligibility criteria using CEL expressions.\n"
        "Examples:\n"
        "- age_years(me.birthdate) >= 60\n"
        "- me.gender == 'female' and age_years(me.birthdate) >= 18\n"
        "- members.exists(m, age_years(m.birthdate) < 5)",
    )

    # CEL expression field
    cel_expression = fields.Text(
        string="CEL Expression",
        help="Write eligibility criteria using CEL syntax.\n"
        "Examples:\n"
        "- age_years(me.birthdate) >= 60\n"
        "- me.gender == 'female' and age_years(me.birthdate) >= 18\n"
        "- members.exists(m, age_years(m.birthdate) < 5)\n"
        "- metric('household.size') >= 4",
    )

    # -------------------------------------------------------------------------
    # Template Lineage Tracking (Option C: Hybrid)
    # -------------------------------------------------------------------------
    source_expression_id = fields.Many2one(
        comodel_name="spp.cel.expression",
        string="Based On",
        help="The template expression this criteria was derived from (for tracking/governance)",
    )
    is_eligibility_locked = fields.Boolean(
        string="Eligibility Locked",
        default=False,
        help="When checked, the eligibility expression cannot be modified. " "This is enforced by a Python constraint.",
    )
    has_drifted_from_template = fields.Boolean(
        string="Modified from Template",
        compute="_compute_has_drifted",
        store=True,
        help="True if the local expression differs from the source template",
    )

    # -------------------------------------------------------------------------
    # CEL Profile (computed for widget context)
    # -------------------------------------------------------------------------
    eligibility_cel_profile = fields.Char(
        string="CEL Profile",
        compute="_compute_eligibility_cel_profile",
        store=False,
        help="CEL profile based on program target type (registry_groups or registry_individuals)",
    )

    # -------------------------------------------------------------------------
    # Preview fields (computed)
    # -------------------------------------------------------------------------
    cel_preview_count = fields.Integer(
        string="Matching Beneficiaries",
        compute="_compute_cel_preview",
        help="Number of registrants matching the current expression",
    )
    cel_preview_error = fields.Text(
        string="Expression Error",
        compute="_compute_cel_preview",
    )
    cel_is_valid = fields.Boolean(
        string="Expression Valid",
        compute="_compute_cel_preview",
    )

    # -------------------------------------------------------------------------
    # Compute Methods for Lineage Tracking
    # -------------------------------------------------------------------------
    @api.depends("cel_expression", "source_expression_id.cel_expression")
    def _compute_has_drifted(self):
        """Detect if local expression differs from the source template."""
        for rec in self:
            if rec.source_expression_id:
                rec.has_drifted_from_template = rec.cel_expression != rec.source_expression_id.cel_expression
            else:
                rec.has_drifted_from_template = False

    @api.depends("program_id.target_type")
    def _compute_eligibility_cel_profile(self):
        """Compute the CEL profile based on program target type."""
        for rec in self:
            rec.eligibility_cel_profile = (
                "registry_groups" if rec.program_id.target_type == "group" else "registry_individuals"
            )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    @api.constrains("cel_expression", "is_eligibility_locked")
    def _check_locked_expression(self):
        """Enforce hard lock: prevent modification of locked eligibility criteria."""
        for rec in self:
            if not rec.is_eligibility_locked:
                continue
            # Only check on update (not create) - use _origin to detect changes
            if rec._origin and rec._origin.cel_expression != rec.cel_expression:
                raise ValidationError(
                    _(
                        "Cannot modify locked eligibility criteria. "
                        "This expression is standardized for compliance purposes. "
                        "Contact an administrator to unlock if changes are required."
                    )
                )

    @api.depends("cel_expression", "program_id.target_type")
    def _compute_cel_preview(self):
        for rec in self:
            rec.cel_preview_count = 0
            rec.cel_preview_error = ""
            rec.cel_is_valid = False

            if not rec.cel_expression:
                continue

            try:
                # Determine profile based on program target type
                profile = "registry_groups" if rec.program_id.target_type == "group" else "registry_individuals"

                # Use CEL service facade to compile and preview
                base_domain = [["disabled", "=", False]]

                service = self.env["spp.cel.service"]
                result = service.compile_expression(
                    rec.cel_expression, profile=profile, base_domain=base_domain, limit=0
                )

                if result.get("valid"):
                    rec.cel_preview_count = result.get("count", 0)
                    rec.cel_is_valid = True
                else:
                    rec.cel_preview_error = result.get("error", _("Unknown error"))

            except Exception as e:
                rec.cel_preview_error = _("Error: %s") % str(e)

    def _prepare_eligible_domain(self, membership=None):
        """Override to support CEL expressions."""
        # If no CEL expression defined, use parent implementation
        if not self.cel_expression:
            return super()._prepare_eligible_domain(membership)

        # CEL mode: compile expression to domain
        domain = []
        if membership is not None:
            ids = membership.mapped("partner_id.id")
            domain += [("id", "in", ids)]

        # Base restrictions
        domain += [("disabled", "=", False)]

        # Compile CEL expression
        try:
            profile = "registry_groups" if self.program_id.target_type == "group" else "registry_individuals"

            service = self.env["spp.cel.service"]
            result = service.compile_expression(self.cel_expression, profile=profile, base_domain=domain, limit=0)

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

    def action_open_cel_builder(self):
        """Open the CEL Expression Builder wizard."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("CEL Expression Builder"),
            "res_model": "spp.cel.builder.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_eligibility_manager_id": self.id,
                "default_cel_expression": self.cel_expression or "",
                "default_target_type": self.program_id.target_type or "group",
            },
        }

    def action_test_cel_expression(self):
        """Test the CEL expression and show results."""
        self.ensure_one()
        if not self.cel_expression:
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
        if not self.cel_expression:
            raise ValidationError(_("Please enter a CEL expression first."))

        try:
            profile = "registry_groups" if self.program_id.target_type == "group" else "registry_individuals"
            base_domain = [["disabled", "=", False]]

            service = self.env["spp.cel.service"]
            result = service.compile_expression(
                self.cel_expression,
                profile=profile,
                base_domain=base_domain,
                limit=0,
                materialize_sql=True,  # Required for window actions - domain must be serializable
            )

            if not result.get("valid"):
                error_msg = result.get("error", "Unknown error")
                raise ValidationError(_("Error previewing: %s") % error_msg)

            domain = result.get("domain", [])
            list_view_id = (
                "spp_registry.view_groups_list_tree"
                if self.program_id.target_type == "group"
                else "spp_registry.view_individuals_list_tree"
            )
            form_view_id = "spp_registry.view_individuals_form"

            return {
                "type": "ir.actions.act_window",
                "name": _("Matching Beneficiaries (%d)") % result.get("count", 0),
                "res_model": "res.partner",
                "view_mode": "list,form",
                "domain": domain,
                "target": "current",
                "context": {"create": False},
            }

        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(_("Error previewing: %s") % str(e)) from e
