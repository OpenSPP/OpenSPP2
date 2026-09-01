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
    # btree_not_null: a plain btree would index every NULL ended_date (the
    # open-membership majority) for no query benefit, amplifying writes.
    ended_date = fields.Datetime(index="btree_not_null")
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

    @api.model
    def _is_ended_as_of(self, ended_date, now):
        """Single home of the "membership is ended at time T" predicate.

        Used by both stored computes, the archiving onchange and the
        repair-cron domains; keep external consumers (raw-SQL readers of
        ``is_ended`` in spp_registry/models/group.py, spp_api_v2_gis,
        spp_cel_domain, spp_gis_report) in mind when changing it (#421).
        """
        return bool(ended_date and ended_date <= now)

    @api.depends("ended_date")
    def _compute_is_ended(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.is_ended = self._is_ended_as_of(rec.ended_date, now)

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
        self._schedule_ended_status_repair([vals])
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        # Invalidate metrics for all affected groups
        groups = res.mapped("group")
        self._invalidate_group_metrics(groups)
        self._schedule_ended_status_repair(vals_list)
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
        now = fields.Datetime.now()
        for record in self:
            # check if membership end date available and less than current date
            record.status = "inactive" if self._is_ended_as_of(record.ended_date, now) else "active"

    def _schedule_ended_status_repair(self, vals_list):
        """Point the repair cron at every future ``ended_date`` being written.

        The stored computes go stale the moment the clock crosses
        ``ended_date`` (see ``_cron_recompute_ended_status``); a persistent
        ``ir.cron.trigger`` at exactly that time shrinks the staleness
        window from the sweep cadence to about a minute. A stale or
        duplicate trigger is harmless — it just runs the idempotent sweep.
        """
        now = fields.Datetime.now()
        at_list = {
            ended
            for vals in vals_list
            if (ended := fields.Datetime.to_datetime(vals.get("ended_date"))) and ended > now
        }
        if at_list:
            self.env.ref("spp_registry.cron_recompute_membership_ended_status")._trigger(at=at_list)

    @api.model
    def _stale_ended_status_domains(self, now):
        """Domains selecting rows whose stored ``status``/``is_ended``
        disagree with the clock, one conjunctive leg per (date-window,
        stale-column) pair so each search stays servable by the
        ``ended_date`` index instead of forcing a full-table read.
        """
        return [
            # Ended by the clock, still stored as active.
            [("ended_date", "<=", now), ("is_ended", "=", False)],
            [("ended_date", "<=", now), ("status", "!=", "inactive")],
            # Not (or no longer) ended, still stored as ended.
            [("ended_date", "=", False), ("is_ended", "=", True)],
            [("ended_date", "=", False), ("status", "!=", "active")],
            [("ended_date", ">", now), ("is_ended", "=", True)],
            [("ended_date", ">", now), ("status", "!=", "active")],
        ]

    @api.model
    def _repair_null_is_ended(self, now):
        """Repair rows holding ``is_ended = NULL`` that should read active.

        Rows written behind the ORM can leave ``is_ended`` NULL, and every
        raw-SQL consumer of the column treats NULL as ended. The ORM
        cannot repair the open-membership case — NULL reads back from the
        cache as False, so a recompute writes nothing — hence this one
        SQL-level leg mirroring ``_is_ended_as_of``. (NULL rows whose
        ``ended_date`` has passed need no special casing: the computed
        True differs from the cached False, so the ORM legs repair them.)
        """
        self.flush_model(["is_ended", "ended_date"])
        self.env.cr.execute(
            "UPDATE spp_group_membership SET is_ended = false "
            "WHERE is_ended IS NULL AND (ended_date IS NULL OR ended_date > %s) "
            "RETURNING id",
            (now,),
        )
        ids = [row[0] for row in self.env.cr.fetchall()]
        if not ids:
            return self.browse()
        repaired = self.browse(ids)
        repaired.invalidate_recordset()
        self._invalidate_group_metrics(repaired.mapped("group"))
        return repaired

    @api.model
    def _cron_recompute_ended_status(self, batch_size=5000):
        """Repair stored ``status``/``is_ended`` on rows the clock has crossed.

        Both computes depend only on ``ended_date`` and compare it against
        *now*, so a recompute fires on a write to ``ended_date`` but never
        when time passes it: a future-dated departure would stay stored as
        active forever. Writes of a future ``ended_date`` schedule a cron
        trigger at exactly that moment (``_schedule_ended_status_repair``),
        so this periodic sweep is the safety net — it self-heals rows
        already stale in pre-existing databases and rows written behind
        the ORM. It finds rows whose stored values disagree with the clock
        and re-triggers the computes through the normal ORM path. Archived
        rows are included — the UI onchange archives memberships ended in
        the past, and those must be repaired too. ``active`` itself is
        deliberately left untouched: archiving changes record visibility
        everywhere and is a separate decision from the stored computes
        (see issue #417).

        Two write-path side effects intentionally differ from a real
        write: the recompute flush still stamps ``write_uid``/``write_date``
        (repaired rows show the cron user as last modified — e.g.
        ``changed_by`` in the API's membership history reads ``write_uid``),
        and the repair is invisible to ``spp_audit`` write-rules, which
        hook ``write()``. Both are accepted: the repair only restores what
        a timely recompute would have stored.

        Rows are repaired in ``batch_size`` chunks, each committed via
        ``ir.cron._commit_progress``: a large backlog drains within one
        run, a run that exhausts the cron time budget is resumed ASAP
        instead of waiting a full sweep interval, and a serialization
        failure rolls back only its own chunk. The chunk size follows the
        5,000-record cap in docs/principles/performance-scalability.md.

        Returns the repaired memberships.
        """
        if batch_size < 1:
            raise ValueError("batch_size must be a positive number of rows")
        memberships = self.with_context(active_test=False)
        repaired = memberships._repair_null_is_ended(fields.Datetime.now())
        while True:
            # Re-read the clock every pass: a row whose ended_date is
            # crossed while the run is in flight recomputes to the very
            # values a stale `now` would keep selecting it for.
            now = fields.Datetime.now()
            chunk = memberships.browse()
            for leg in self._stale_ended_status_domains(now):
                chunk |= memberships.search(leg, limit=batch_size)
            chunk = chunk[:batch_size]
            if not chunk:
                break
            chunk.modified(["ended_date"])
            # The recompute flushes through low-level SQL and bypasses this
            # model's write() override, so the metric-invalidation hook must
            # be called explicitly.
            self._invalidate_group_metrics(chunk.mapped("group"))
            repaired |= chunk
            self.env.flush_all()
            # A short chunk means every leg came back exhausted, so the
            # backlog is drained (repaired rows drop out of the domains).
            drained = len(chunk) < batch_size
            time_left = self.env["ir.cron"]._commit_progress(len(chunk), remaining=0 if drained else batch_size)
            if drained:
                break
            if not time_left:
                _logger.info("[spp.registry] Ended-status backlog remains; the cron will be re-triggered to continue")
                break
        if repaired:
            _logger.info(
                "[spp.registry] Repaired ended-status on %d group membership(s)",
                len(repaired),
            )
        return repaired

    @api.constrains("ended_date")
    def _check_ended_date(self):
        for record in self:
            if record.ended_date and record.ended_date < record.start_date:
                raise ValidationError(_("End Date cannot be earlier than Start Date"))

    @api.onchange("ended_date")
    def _onchange_ended_date(self):
        now = fields.Datetime.now()
        for record in self:
            # if ended date is less than current date, set active to false
            record.active = not self._is_ended_as_of(record.ended_date, now)
