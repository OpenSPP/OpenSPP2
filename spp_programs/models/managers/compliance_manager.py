# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Compliance Manager for ongoing beneficiary compliance verification.

This module provides the compliance criteria management system, separate from
eligibility management. While eligibility determines WHO can enroll in a program,
compliance determines if enrolled beneficiaries meet ONGOING conditions.

Architecture:
- spp.compliance.manager: Wrapper model (like spp.eligibility.manager)
- spp.compliance.manager.base: Abstract base with interface definition
- spp.compliance.manager.default: Default implementation with CEL support
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SppComplianceManager(models.Model):
    """Wrapper model for compliance managers.

    Uses the manager mixin pattern to allow different compliance implementations.
    """

    _name = "spp.compliance.manager"
    _inherit = ["spp.manager.mixin"]
    _description = "Compliance Criteria Manager"

    program_id = fields.Many2one(
        comodel_name="spp.program",
        string="Program",
        required=True,
        ondelete="cascade",
        readonly=True,
    )

    @api.model
    def _selection_manager_ref_id(self):
        res = super()._selection_manager_ref_id()
        for item in [
            ("spp.compliance.manager.default", "Default Compliance"),
        ]:
            if item not in res:
                res.append(item)
        return res


class BaseComplianceManager(models.AbstractModel):
    """Abstract base model for compliance managers.

    Defines the interface that all compliance manager implementations must follow.
    """

    _name = "spp.compliance.manager.base"
    _inherit = "spp.base.programs.manager"
    _description = "Base Compliance Manager"

    name = fields.Char("Manager Name", required=True)
    program_id = fields.Many2one("spp.program", string="Program", required=True)

    def verify_compliance(self, cycle, membership):
        """Check if beneficiaries meet compliance criteria.

        Args:
            cycle: The cycle to check compliance for
            membership: Cycle membership records to verify

        Returns:
            Recordset of compliant cycle memberships
        """
        raise NotImplementedError()

    def get_compliance_domain(self, membership=None):
        """Return domain for compliance filtering.

        Args:
            membership: Optional cycle membership records to filter

        Returns:
            Domain list for finding compliant registrants
        """
        raise NotImplementedError()


class DefaultComplianceManager(models.Model):
    """Default compliance manager implementation using CEL expressions.

    Supports defining compliance criteria using CEL (Common Expression Language)
    expressions that are evaluated at cycle time to identify non-compliant
    beneficiaries.
    """

    _name = "spp.compliance.manager.default"
    _inherit = ["spp.compliance.manager.base", "spp.manager.source.mixin"]
    _description = "Default Compliance Manager"

    # Mode selection
    compliance_cel_mode = fields.Selection(
        selection=[
            ("cel", "CEL Expression"),
        ],
        string="Compliance Mode",
        default="cel",
        help="Define compliance criteria using CEL expressions.\n"
        "Examples:\n"
        "- age_years(me.birthdate) >= 60\n"
        "- me.gender == 'female' and age_years(me.birthdate) >= 18\n"
        "- members.exists(m, age_years(m.birthdate) < 5)",
    )

    # CEL expression field for compliance
    compliance_cel_expression = fields.Text(
        string="Compliance CEL Expression",
        default=False,
        help="Write compliance criteria using CEL syntax.\n"
        "Examples:\n"
        "- age_years(me.birthdate) >= 60\n"
        "- me.gender == 'female' and age_years(me.birthdate) >= 18\n"
        "- members.exists(m, age_years(m.birthdate) < 5)\n"
        "- metric('household.size') >= 4",
    )

    # Template lineage tracking (for governance)
    source_expression_id = fields.Many2one(
        comodel_name="spp.cel.expression",
        string="Source Criteria Template",
        readonly=True,
        ondelete="set null",
        help="The CEL expression template this compliance criteria was derived from.",
    )
    is_compliance_locked = fields.Boolean(
        string="Compliance Locked",
        default=False,
        help="When checked, the compliance expression cannot be modified.",
    )

    # CEL Profile (computed for widget context)
    compliance_cel_profile = fields.Char(
        string="CEL Profile",
        compute="_compute_compliance_cel_profile",
        store=False,
        help="CEL profile based on program target type (registry_groups or registry_individuals)",
    )

    # Preview fields (computed)
    compliance_cel_preview_count = fields.Integer(
        string="Matching Enrolled Beneficiaries",
        compute="_compute_compliance_cel_preview",
        help="Number of enrolled beneficiaries matching the current compliance expression",
    )
    compliance_cel_preview_error = fields.Text(
        string="Expression Error",
        compute="_compute_compliance_cel_preview",
    )
    compliance_cel_is_valid = fields.Boolean(
        string="Expression Valid",
        compute="_compute_compliance_cel_preview",
    )

    @api.depends("program_id.target_type")
    def _compute_compliance_cel_profile(self):
        """Compute the CEL profile based on program target type."""
        for rec in self:
            rec.compliance_cel_profile = (
                "registry_groups" if rec.program_id.target_type == "group" else "registry_individuals"
            )

    @api.depends("compliance_cel_expression", "program_id.target_type", "program_id.program_membership_ids")
    def _compute_compliance_cel_preview(self):
        for rec in self:
            rec.compliance_cel_preview_count = 0
            rec.compliance_cel_preview_error = ""
            rec.compliance_cel_is_valid = False

            if not rec.compliance_cel_expression:
                continue

            try:
                # Determine profile based on program target type
                profile = "registry_groups" if rec.program_id.target_type == "group" else "registry_individuals"

                # Get enrolled beneficiaries from the program
                # Compliance only applies to enrolled members, not all registrants
                enrolled_members = rec.program_id.program_membership_ids.filtered(
                    lambda m: m.state == "enrolled"
                )
                enrolled_partner_ids = enrolled_members.mapped("partner_id.id")

                # Build base domain filtering only enrolled beneficiaries
                base_domain = [["disabled", "=", False]]
                if enrolled_partner_ids:
                    base_domain.append(["id", "in", enrolled_partner_ids])
                else:
                    # No enrolled beneficiaries = count is 0
                    rec.compliance_cel_is_valid = True
                    continue

                # Use CEL service facade to compile and preview
                # Use sudo() as CEL may access vocabulary records
                service = self.env["spp.cel.service"].sudo()
                result = service.compile_expression(
                    rec.compliance_cel_expression, profile=profile, base_domain=base_domain, limit=0
                )

                if result.get("valid"):
                    rec.compliance_cel_preview_count = result.get("count", 0)
                    rec.compliance_cel_is_valid = True
                else:
                    rec.compliance_cel_preview_error = result.get("error", _("Unknown error"))

            except Exception as e:
                rec.compliance_cel_preview_error = _("Error: %s") % str(e)

    def get_compliance_domain(self, membership=None):
        """Return domain for compliance filtering.

        This is the main method used by cycles to filter compliant beneficiaries.

        Args:
            membership: Optional cycle membership records to filter

        Returns:
            Domain list for compliance criteria
        """
        # If no compliance expression, return empty domain (all pass)
        if not self.compliance_cel_expression:
            return []

        # Build base domain
        domain = []
        if membership is not None:
            ids = membership.mapped("partner_id.id")
            domain += [("id", "in", ids)]

        # Base restrictions
        domain += [("disabled", "=", False)]
        if self.program_id.target_type == "group":
            domain += [("is_group", "=", True), ("is_registrant", "=", True)]
        if self.program_id.target_type == "individual":
            domain += [("is_group", "=", False), ("is_registrant", "=", True)]

        # Compile CEL expression
        # Use sudo() for CEL service as it may need to access vocabulary records
        # The calling action (apply compliance criteria) is already restricted to program managers
        try:
            profile = "registry_groups" if self.program_id.target_type == "group" else "registry_individuals"

            service = self.env["spp.cel.service"].sudo()
            result = service.compile_expression(
                self.compliance_cel_expression, profile=profile, base_domain=domain, limit=0
            )

            if not result.get("valid"):
                error_msg = result.get("error", "Unknown error")
                _logger.error("Compliance CEL expression error: %s", error_msg)
                raise ValidationError(_("Invalid compliance CEL expression: %s") % error_msg)

            # Return the compiled domain
            cel_domain = result.get("domain", [])
            _logger.debug("Compliance CEL compiled domain: %s", cel_domain)
            return cel_domain

        except ValidationError:
            raise
        except Exception as e:
            _logger.error("Compliance CEL expression error: %s", e)
            raise ValidationError(_("Invalid compliance CEL expression: %s") % str(e)) from e

    def verify_compliance(self, cycle, membership):
        """Check if beneficiaries meet compliance criteria.

        Args:
            cycle: The cycle to check compliance for
            membership: Cycle membership records to verify

        Returns:
            Recordset of compliant cycle memberships
        """
        domain = self.get_compliance_domain(membership)
        if not domain:
            # No compliance criteria = all are compliant
            return membership

        # Use sudo() for search as CEL domain may reference vocabulary records
        # Access control is enforced at the action level (apply compliance criteria)
        compliant_partners = self.env["res.partner"].sudo().search(domain)
        return membership.filtered(lambda m: m.partner_id in compliant_partners)

    def action_open_compliance_cel_builder(self):
        """Open the CEL Expression Builder wizard for compliance."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Compliance CEL Expression Builder"),
            "res_model": "spp.cel.builder.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_compliance_manager_id": self.id,
                "default_cel_expression": self.compliance_cel_expression or "",
                "default_target_type": self.program_id.target_type or "group",
            },
        }

    def action_test_compliance_cel_expression(self):
        """Test the compliance CEL expression and show results."""
        self.ensure_one()
        if not self.compliance_cel_expression:
            raise ValidationError(_("Please enter a compliance CEL expression first."))

        # Force recompute
        self._compute_compliance_cel_preview()

        if self.compliance_cel_preview_error:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Expression Error"),
                    "message": self.compliance_cel_preview_error,
                    "type": "danger",
                    "sticky": True,
                },
            }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Expression Valid"),
                "message": _("%d enrolled beneficiaries match this compliance expression.") % self.compliance_cel_preview_count,
                "type": "success",
                "sticky": False,
            },
        }

    def action_preview_compliance_beneficiaries(self):
        """Open a list view of matching enrolled beneficiaries for compliance."""
        self.ensure_one()
        if not self.compliance_cel_expression:
            raise ValidationError(_("Please enter a compliance CEL expression first."))

        try:
            profile = "registry_groups" if self.program_id.target_type == "group" else "registry_individuals"

            # Get enrolled beneficiaries from the program
            # Compliance only applies to enrolled members, not all registrants
            enrolled_members = self.program_id.program_membership_ids.filtered(
                lambda m: m.state == "enrolled"
            )
            enrolled_partner_ids = enrolled_members.mapped("partner_id.id")

            # Build base domain filtering only enrolled beneficiaries
            base_domain = [["disabled", "=", False]]
            if enrolled_partner_ids:
                base_domain.append(["id", "in", enrolled_partner_ids])
            else:
                # No enrolled beneficiaries
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("No Enrolled Beneficiaries"),
                        "message": _("There are no enrolled beneficiaries in this program."),
                        "type": "warning",
                        "sticky": False,
                    },
                }

            # Use sudo() as CEL may access vocabulary records
            service = self.env["spp.cel.service"].sudo()
            result = service.compile_expression(
                self.compliance_cel_expression,
                profile=profile,
                base_domain=base_domain,
                limit=0,
                materialize_sql=True,  # Required for window actions - domain must be serializable
            )

            if not result.get("valid"):
                error_msg = result.get("error", "Unknown error")
                raise ValidationError(_("Error previewing: %s") % error_msg)

            domain = result.get("domain", [])

            return {
                "type": "ir.actions.act_window",
                "name": _("Compliant Enrolled Beneficiaries (%d)") % result.get("count", 0),
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
