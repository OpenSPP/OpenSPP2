# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging
from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SPPIndividual(models.Model):
    """Individual registrant model.

    This model consolidates:
    - Base individual functionality (spp_registry_individual)
    - Membership functionality (spp_registry_membership)
    """

    _inherit = "res.partner"

    # Individual fields
    family_name = fields.Char(translate=False)
    given_name = fields.Char(translate=False)
    addl_name = fields.Char("Additional Name", translate=False)
    birth_place = fields.Char()
    birthdate_not_exact = fields.Boolean("Approximate Birthdate")
    birthdate = fields.Date("Date of Birth")
    age = fields.Char(compute="_compute_calc_age", size=50, readonly=True)
    # Gender field - uses vocabulary codes if spp_vocabulary is installed
    gender_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Gender",
        domain="[('namespace_uri', '=', 'urn:iso:std:iso:5218')]",
        tracking=True,
    )

    # Care status
    in_institutional_care = fields.Boolean(
        "In Institutional Care",
        help="Indicates if the individual is currently residing in institutional care "
        "(e.g., nursing home, care facility, orphanage)",
        tracking=True,
    )

    # Membership fields
    individual_membership_ids = fields.One2many("spp.group.membership", "individual", "Membership to Groups")

    # Fields that trigger name recomputation
    _name_fields = {"family_name", "given_name", "addl_name"}

    @api.model
    def _format_individual_name(self, family_name, given_name, addl_name):
        """Compute display name from individual name parts.

        Format: "FAMILY_NAME, GIVEN_NAME ADDL_NAME" (uppercase).
        Used by onchange (UI), create, and write to ensure consistent naming.
        """
        name_vals = [
            f"{family_name}," if family_name and (given_name or addl_name) else f"{family_name}" if family_name else "",
            given_name,
            addl_name,
        ]
        return " ".join(filter(None, name_vals)).upper()

    @api.onchange("is_group", "family_name", "given_name", "addl_name")
    def name_change(self):
        if not self.is_group:
            name = self._format_individual_name(self.family_name, self.given_name, self.addl_name)
            self.update({"name": name})

    @api.depends("birthdate")
    def _compute_calc_age(self):
        for line in self:
            line.age = self.compute_age_from_dates(line.birthdate)

    def compute_age_from_dates(self, partner_dob):
        now = datetime.strptime(str(fields.Datetime.now())[:10], "%Y-%m-%d")
        if partner_dob:
            dob = partner_dob
            delta = relativedelta(now, dob)
            # years_months_days = str(delta.years) +"y "+ str(delta.months) +"m "+ str(delta.days)+"d"
            years_months_days = str(delta.years)
        else:
            years_months_days = "No Birthdate!"
        return years_months_days

    @api.onchange("birthdate")
    def _birthdate_onchange(self):
        """
        This function is used to validate and reset birthdate in case
        the birthdate date is being set greater than the date today.
        Resets to previous birthdate value if available, otherwise None.
        """
        for rec in self:
            if rec.birthdate and rec.birthdate > fields.Date.today():
                # Restore previous birthdate or set to None if new record
                rec.birthdate = rec._origin.birthdate if rec._origin.id else None
                return {
                    "warning": {
                        "title": _("Invalid Birthdate"),
                        "message": _("You can't select a date of birth greater than today. The field has been reset."),
                    }
                }

    @api.constrains("birthdate")
    def _check_birthdate_not_future(self):
        """Server-side backstop for future dates of birth.

        ``_birthdate_onchange`` only runs in the form UI, so ORM
        ``create`` / ``write``, CSV/Excel import, and API writes
        (XML-RPC, API v2, DCI) bypass it and a future birthdate persists.
        ``birthdate`` is a stored, writeable field, so this constraint
        fires on every write path and keeps the non-stored ``age``
        compute from ever rendering a negative string.
        """
        today = fields.Date.today()
        for record in self:
            if record.birthdate and record.birthdate > today:
                raise ValidationError(_("Date of birth cannot be in the future."))

    def _recompute_parent_groups(self, records):
        field = self.env["res.partner"]._fields["force_recompute_canary"]
        # Get the 'head' vocabulary code - this is a unique membership type
        # Use sudo() because this validation should work regardless of user permissions
        # nosemgrep: odoo-sudo-without-context
        head_code = self.env["spp.vocabulary.code"].sudo().get_code("urn:openspp:vocab:group-membership-type", "head")
        for line in records:
            if line.is_registrant and not line.is_group:
                try:
                    groups = line.individual_membership_ids.mapped("group")
                    if head_code:
                        for group in groups:
                            head_count = sum(
                                1 for rec in group.group_membership_ids if head_code.id in rec.membership_type_ids.ids
                            )
                            if head_count > 1:
                                raise ValidationError(_("Only one %s is allowed per group") % head_code.display)
                except Exception as e:
                    _logger.error("_recompute_parent_groups: exception: %s", e)
                    raise
                else:
                    self.env.add_to_compute(field, groups)

    def write(self, vals):
        """Override to recompute name and invalidate group metrics."""
        # Recompute name if a name part changed and no explicit name is being
        # written (only for non-group individuals). An explicit name in vals
        # is preserved.
        name_updates = {}
        if self._name_fields & vals.keys() and not vals.get("name") and not self.env.context.get("skip_name_format"):
            for rec in self.filtered(lambda r: not r.is_group):
                name_updates[rec.id] = self._format_individual_name(
                    vals.get("family_name", rec.family_name),
                    vals.get("given_name", rec.given_name),
                    vals.get("addl_name", rec.addl_name),
                )

        res = super().write(vals)

        # Apply computed names after super to avoid interfering with the main write
        if name_updates:
            for rec_id, name in name_updates.items():
                super(SPPIndividual, self.browse(rec_id).with_context(skip_name_format=True)).write({"name": name})
        self._recompute_parent_groups(self)

        # Fields that affect group-level metrics
        demographic_fields = {"birthdate", "gender_id", "disabled"}

        if any(f in vals for f in demographic_fields):
            # Find individuals (not groups) that were updated
            individuals = self.filtered(lambda p: not p.is_group and p.is_registrant)

            if individuals:
                self._invalidate_parent_group_metrics(individuals)

        return res

    def _invalidate_parent_group_metrics(self, individuals):
        """Invalidate metrics for groups containing these individuals.

        Args:
            individuals: res.partner recordset of individuals
        """
        if not individuals:
            return

        # Check if spp_indicators is installed
        if "spp.indicator.invalidation.buffer" not in self.env:
            return

        # Find parent groups via active memberships
        memberships = self.env["spp.group.membership"].search(
            [
                ("individual", "in", individuals.ids),
                ("is_ended", "=", False),  # Only active memberships
            ]
        )

        if memberships:
            groups = memberships.mapped("group")
            groups.invalidate_group_metrics()

            _logger.debug(
                "[spp.registry] Individual demographic change triggered invalidation for %d groups",
                len(groups),
            )

    @api.model_create_multi
    def create(self, vals_list):
        # Compute name from parts before create (injects into vals, no extra write).
        # An explicitly-provided name is preserved (e.g. demo stories set a
        # human-friendly "Given Family" display name alongside the parts).
        for vals in vals_list:
            if not vals.get("is_group") and self._name_fields & vals.keys() and not vals.get("name"):
                vals["name"] = self._format_individual_name(
                    vals.get("family_name", ""),
                    vals.get("given_name", ""),
                    vals.get("addl_name", ""),
                )
        res = super().create(vals_list)
        self._recompute_parent_groups(res)
        return res
