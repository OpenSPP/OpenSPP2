# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SPPGroupMembership(models.Model):
    _name = "spp.group.membership"
    _description = "Group Membership"
    _order = "id desc"

    group = fields.Many2one(
        "res.partner",
        required=True,
        domain=[("is_group", "=", True), ("is_registrant", "=", True)],
        index=True,
    )
    individual = fields.Many2one(
        "res.partner",
        required=True,
        domain=[("is_group", "=", False), ("is_registrant", "=", True)],
        index=True,
    )
    membership_type_ids = fields.Many2many(
        "spp.vocabulary.code",
        string="Group Role",
        domain="[('namespace_uri', '=', 'urn:openspp:vocab:group-membership-type')]",
    )
    # True when the group-membership-type vocabulary has at least one code.
    # Drives column_invisible on the standalone Group Membership tree view
    # (the embedded lists on the registrant forms read this from
    # `parent.has_group_membership_type_codes` on res.partner instead).
    has_group_membership_type_codes = fields.Boolean(
        compute="_compute_has_group_membership_type_codes",
    )

    def _compute_has_group_membership_type_codes(self):
        has_codes = bool(
            self.env["spp.vocabulary.code"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search_count(
                [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:group-membership-type")],
                limit=1,
            )
        )
        for rec in self:
            rec.has_group_membership_type_codes = has_codes

    start_date = fields.Datetime(default=lambda self: fields.Datetime.now())
    ended_date = fields.Datetime(index=True)
    status = fields.Selection(
        [("inactive", "Inactive"), ("active", " ")],
        compute="_compute_status",
        store=True,
    )
    is_ended = fields.Boolean(default=False, compute="_compute_is_ended", store=True)
    individual_birthdate = fields.Date(related="individual.birthdate", readonly=True)
    individual_gender = fields.Many2one(
        related="individual.gender_id",
        readonly=True,
    )
    active = fields.Boolean(default=True)

    @api.onchange("membership_type_ids")
    def _membership_type_onchange(self):
        """Validate unique membership types (e.g., only one 'head' per group)."""
        # Get the 'head' vocabulary code - this is a unique membership type
        # Use sudo() because this validation should work regardless of user permissions
        # nosemgrep: odoo-sudo-without-context — public reference data
        head_code = self.env["spp.vocabulary.code"].sudo().get_code("urn:openspp:vocab:group-membership-type", "head")
        if not head_code:
            return

        for rec in self:
            # Check if current record has 'head' membership type
            if head_code not in rec.membership_type_ids:
                continue

            # Count how many members in this group have 'head' type
            head_count = 0
            for membership in rec.group.group_membership_ids:
                # Skip virtual/new records (contain 'x' in id string)
                if "x" in str(membership.id):
                    continue
                if head_code in membership.membership_type_ids:
                    head_count += 1

            # Include current record if it's new
            if rec._origin.id != rec.id or head_code not in rec._origin.membership_type_ids:
                head_count += 1

            if head_count > 1:
                raise ValidationError(_("Only one %s is allowed per group") % head_code.display)

    @api.constrains("individual")
    def _check_group_members(self):
        for rec in self:
            rec_count = 0
            for group_membership_id in rec.group.group_membership_ids:
                if rec.individual.id == group_membership_id.individual.id:
                    rec_count += 1
            if rec_count > 1:
                raise ValidationError(_("Duplication of Member is not allowed "))

    def _compute_display_name(self):
        res = super()._compute_display_name()
        for rec in self:
            name = "NONE"
            if rec.group:
                name = rec.group.name
            rec.display_name = name
        return res

    @api.model
    def _name_search(self, name, domain=None, operator="ilike", limit=100, order=None):
        domain = domain or []
        if name:
            domain = [("group", operator, name)] + domain
        return self._search(domain, limit=limit, order=order)

    @api.depends("ended_date")
    def _compute_is_ended(self):
        for rec in self:
            is_ended = False
            if rec.ended_date and rec.ended_date <= fields.Datetime.now():
                is_ended = True

            rec.is_ended = is_ended

    def _invalidate_group_metrics(self, groups):
        """Schedule metric invalidation for affected groups.

        Args:
            groups: res.partner recordset of groups to invalidate
        """
        if not groups:
            return

        # Delegate to the group model's invalidation method
        groups.invalidate_group_metrics()

        _logger.debug(
            "[spp.registry] Membership change triggered invalidation for groups: %s",
            groups.ids,
        )

    def write(self, vals):
        # Capture affected groups before write (in case group changes)
        affected_groups = self.mapped("group")

        res = super().write(vals)

        # If group field changed, also invalidate new groups
        if "group" in vals:
            affected_groups |= self.mapped("group")

        self._invalidate_group_metrics(affected_groups)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        # Invalidate metrics for all affected groups
        groups = res.mapped("group")
        self._invalidate_group_metrics(groups)
        return res

    def unlink(self):
        # Capture groups before deletion
        groups = self.mapped("group")
        res = super().unlink()
        self._invalidate_group_metrics(groups)
        return res

    def open_individual_form(self):
        return {
            "name": "Individual Member",
            "view_mode": "form",
            "res_model": "res.partner",
            "res_id": self.individual.id,
            "view_id": self.env.ref("spp_registry.view_individuals_form").id,
            "type": "ir.actions.act_window",
            "target": "new",
            "context": {"default_is_group": False},
            "flags": {"mode": "readonly"},
        }

    def open_group_form(self):
        return {
            "name": "Group Membership",
            "view_mode": "form",
            "res_model": "res.partner",
            "res_id": self.group.id,
            "view_id": self.env.ref("spp_registry.view_individuals_form").id,
            "type": "ir.actions.act_window",
            "target": "new",
            "context": {"default_is_group": True},
            "flags": {"mode": "readonly"},
        }

    @api.depends("ended_date")
    def _compute_status(self):
        for record in self:
            # check if memebership end date available and less than current date
            if record.ended_date and record.ended_date <= fields.Datetime.now():
                record.status = "inactive"
            else:
                record.status = "active"

    @api.model
    def _cron_recompute_ended_status(self, batch_size=10000):
        """Repair stored ``status``/``is_ended`` on rows the clock has crossed.

        Both computes depend only on ``ended_date`` and compare it against
        *now*, so a recompute fires on a write to ``ended_date`` but never
        when time passes it: a future-dated departure would stay stored as
        active forever. This cron finds rows whose stored values disagree
        with the clock and re-triggers the computes through the normal ORM
        path. Archived rows are included — the UI onchange archives
        memberships ended in the past, and those must be repaired too.
        ``active`` itself is deliberately left untouched: archiving changes
        record visibility everywhere and is a separate decision from the
        stored computes (see issue #417).

        At most ``batch_size`` rows per direction are repaired per run so a
        large backlog (e.g. the first run on a database that predates this
        cron) cannot exceed the cron time limit; the repaired rows drop out
        of the domains, so subsequent runs drain the remainder.

        Returns the repaired memberships.
        """
        now = fields.Datetime.now()
        memberships = self.with_context(active_test=False)
        to_end = memberships.search(
            [
                ("ended_date", "<=", now),
                "|",
                ("is_ended", "=", False),
                ("status", "!=", "inactive"),
            ],
            limit=batch_size,
        )
        to_reactivate = memberships.search(
            [
                "|",
                ("ended_date", "=", False),
                ("ended_date", ">", now),
                "|",
                ("is_ended", "=", True),
                ("status", "!=", "active"),
            ],
            limit=batch_size,
        )
        stale = to_end | to_reactivate
        if stale:
            stale.modified(["ended_date"])
            # The recompute flushes through low-level SQL and bypasses this
            # model's write() override, so the metric-invalidation hook must
            # be called explicitly.
            self._invalidate_group_metrics(stale.mapped("group"))
            _logger.info(
                "[spp.registry] Scheduled ended-status recompute for %d group membership(s)",
                len(stale),
            )
        if len(to_end) == batch_size or len(to_reactivate) == batch_size:
            _logger.info("[spp.registry] Ended-status backlog remains; the next cron run will continue")
        return stale

    @api.constrains("ended_date")
    def _check_ended_date(self):
        for record in self:
            if record.ended_date and record.ended_date < record.start_date:
                raise ValidationError(_("End Date cannot be earlier than Start Date"))

    @api.onchange("ended_date")
    def _onchange_ended_date(self):
        for record in self:
            record.active = True
            # if ended date is less than current date, set active to false
            if record.ended_date and record.ended_date <= fields.Datetime.now():
                record.active = False
