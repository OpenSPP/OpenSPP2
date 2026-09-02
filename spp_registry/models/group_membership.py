# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging
from datetime import timedelta

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
        if self and "ended_date" in vals:
            self._schedule_ended_status_repair([vals["ended_date"]])
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        # Invalidate metrics for all affected groups
        groups = res.mapped("group")
        self._invalidate_group_metrics(groups)
        # Read the dates back from the records, not vals_list: a missing
        # key can still be filled from a default_ended_date context key.
        self._schedule_ended_status_repair(res.mapped("ended_date"))
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

    def _schedule_ended_status_repair(self, ended_dates):
        """Point the repair cron at every future ``ended_date`` being written.

        The stored computes go stale the moment the clock crosses
        ``ended_date`` (see ``_cron_recompute_ended_status``); a persistent
        ``ir.cron.trigger`` at that time shrinks the staleness window from
        the sweep cadence to a couple of minutes. Each moment is rounded up
        to the next full minute *past* ``ended_date`` — unconditionally,
        because the cron machinery consumes triggers against the database
        clock while the repair predicate compares against the application
        clock, so a trigger firing exactly at ``ended_date`` could be
        consumed while the row still reads as not-yet-ended. Triggers
        already pending for the same minute are reused, so a cohort
        departure written one row per call files a single trigger; two
        concurrent transactions can still race to a duplicate, and a
        trigger orphaned by a later date change survives to its moment —
        both harmless, each just runs one idempotent index-served sweep.
        """
        now = fields.Datetime.now()
        at_list = set()
        for ended in ended_dates:
            ended = fields.Datetime.to_datetime(ended)
            if not ended or ended <= now:
                continue
            at_list.add(ended.replace(second=0, microsecond=0) + timedelta(minutes=1))
        if not at_list:
            return
        # raise_if_not_found=False: if the noupdate cron record has been
        # deleted, membership writes must degrade to the daily sweep, not
        # break the core registry write path over a latency optimisation.
        cron = self.env.ref(
            "spp_registry.cron_repair_crossed_membership_ended_status",
            raise_if_not_found=False,
        )
        if not cron:
            return
        pending = (
            self.env["ir.cron.trigger"]  # nosemgrep: odoo-sudo-without-context
            .sudo()  # system table ordinary users cannot read; _trigger creates as sudo anyway
            .search([("cron_id", "=", cron.id), ("call_at", "in", list(at_list))])
        )
        at_list -= set(pending.mapped("call_at"))
        if at_list:
            cron._trigger(at=at_list)

    @api.model
    def _crossed_ended_status_domains(self, now):
        """Domains selecting rows the clock has crossed: ``ended_date`` is
        past but a stored column still reads active. One conjunctive leg
        per stale column — no ORs, so both legs are served by the partial
        ``ended_date`` index. These are the only stale states the mere
        passage of time can produce, so the trigger-driven cron sweeps
        just these.
        """
        return [
            [("ended_date", "<=", now), ("is_ended", "=", False)],
            [("ended_date", "<=", now), ("status", "!=", "inactive")],
        ]

    @api.model
    def _stale_ended_status_domains(self, now):
        """All domains selecting rows whose stored ``status``/``is_ended``
        disagree with the clock. Beyond the crossed legs this adds the
        reactivation legs, which only guard rows whose ``ended_date`` was
        cleared or future-moved behind the ORM and are expected to match
        nothing. The two ``ended_date IS NULL`` legs cannot be served by
        the partial index (each probe is a full table scan), which is why
        only the daily safety net runs them — never the trigger-driven
        cron. If a registry ever accumulates enough non-ORM drift for
        those scans to matter, give them partial indexes or a last-swept
        watermark (see #421 for the planned collapse of the status legs).
        """
        return self._crossed_ended_status_domains(now) + [
            # Not (or no longer) ended, still stored as ended.
            [("ended_date", "=", False), ("is_ended", "=", True)],
            [("ended_date", "=", False), ("status", "!=", "active")],
            [("ended_date", ">", now), ("is_ended", "=", True)],
            [("ended_date", ">", now), ("status", "!=", "active")],
        ]

    @api.model
    def _repair_null_is_ended(self, now, batch_size):
        """Repair rows holding ``is_ended = NULL`` that should read active.

        Rows written behind the ORM can leave ``is_ended`` NULL, and every
        raw-SQL consumer of the column treats NULL as ended. The ORM
        cannot repair the open-membership case — NULL reads back from the
        cache as False, so a recompute writes nothing — hence this one
        SQL-level leg mirroring ``_is_ended_as_of``. (NULL rows whose
        ``ended_date`` has passed need no special casing: the computed
        True differs from the cached False, so the ORM legs repair them.)

        Expected to match nothing on a healthy database (the column has a
        Python default, so it was backfilled at creation) — but the
        ``is_ended IS NULL`` probe has no index behind it, so even proving
        that costs a full table scan, which is why only the daily safety
        net calls this, never the trigger-driven cron. The UPDATE stamps
        ``write_date``/``write_uid`` the way the ORM legs' flush does, so
        ``write_date``-keyed consumers (incremental syncs, the API's
        ``changed_by``) see the repair. Work is bounded to ``batch_size``
        rows per statement, with progress committed between batches.

        Returns ``(repaired, time_left)``: the repaired memberships and
        the cron time budget reported by the last progress commit — falsy
        when the budget ran out with NULL rows possibly left.
        """
        self.flush_model(["is_ended", "ended_date"])
        repaired = self.browse()
        time_left = float("inf")
        while True:
            self.env.cr.execute(
                "UPDATE spp_group_membership "
                "SET is_ended = false, write_date = %s, write_uid = %s "
                "WHERE id IN (SELECT id FROM spp_group_membership "
                "WHERE is_ended IS NULL AND (ended_date IS NULL OR ended_date > %s) LIMIT %s) "
                "RETURNING id",
                (now, self.env.uid, now, batch_size),
            )
            ids = [row[0] for row in self.env.cr.fetchall()]
            if not ids:
                break
            batch = self.browse(ids)
            batch.invalidate_recordset()
            self._invalidate_group_metrics(batch.mapped("group"))
            repaired |= batch
            if len(ids) < batch_size:
                self.env["ir.cron"]._commit_progress(len(ids), remaining=0)
                break
            # A full batch may not be the last: report the backlog so a
            # budget-exhausted run is continued ASAP instead of waiting a
            # full sweep interval on a "no work remaining" report.
            time_left = self.env["ir.cron"]._commit_progress(len(ids), remaining=1)
            if not time_left:
                break
        return repaired, time_left

    @api.model
    def _cron_repair_crossed_ended_status(self, batch_size=5000):
        """Trigger-driven repair: only the index-served crossed legs.

        ``_schedule_ended_status_repair`` points this cron at every future
        ``ended_date`` written, so it can run many times a day and must
        stay cheap — no NULL-drift legs (each of those probes is a full
        table scan; the daily ``_cron_recompute_ended_status`` sweeps
        them). See that method for the full story and the shared
        semantics.
        """
        return self._repair_stale_ended_status(batch_size, full=False)

    @api.model
    def _cron_recompute_ended_status(self, batch_size=5000):
        """Daily safety net: repair stored ``status``/``is_ended`` on every
        row whose stored values disagree with the clock.

        Both computes depend only on ``ended_date`` and compare it against
        *now*, so a recompute fires on a write to ``ended_date`` but never
        when time passes it: a future-dated departure would stay stored as
        active forever. Writes of a future ``ended_date`` schedule the
        lightweight ``_cron_repair_crossed_ended_status`` in the minute
        after that moment (``_schedule_ended_status_repair``), so this
        daily sweep self-heals what triggers cannot cover: rows already
        stale in pre-existing databases and rows written behind the ORM,
        including the full-scan NULL-drift legs and
        ``_repair_null_is_ended``. It finds stale rows and re-triggers the
        computes through the normal ORM path. Archived rows are included —
        the UI onchange archives memberships ended in the past, and those
        must be repaired too. ``active`` itself is deliberately left
        untouched: archiving changes record visibility everywhere and is a
        separate decision from the stored computes (see issue #417).

        Two write-path side effects intentionally differ from a real
        write: the recompute flush still stamps ``write_uid``/``write_date``
        (repaired rows show the cron user as last modified — e.g.
        ``changed_by`` in the API's membership history reads ``write_uid``;
        the raw NULL-repair UPDATE stamps the same columns itself), and
        the repair is invisible to ``spp_audit`` write-rules, which hook
        ``write()``. Both are accepted: the repair only restores what a
        timely recompute would have stored.

        Rows are repaired in ``batch_size`` chunks, each committed via
        ``ir.cron._commit_progress``: a serialization failure rolls back
        only its own chunk, and a backlog larger than the cron time budget
        drains across runs — a partially-done run is rescheduled ASAP
        instead of waiting a full sweep interval. ``_commit_progress`` is
        Odoo 19's sanctioned batching API for cron work and the deliberate
        exception to the AGENTS.md checklist's "no ``cr.commit()`` in
        loops" rule, which targets ad-hoc commits. Because of those
        commits, calling this outside a cron (e.g. from a shell) commits
        the current transaction. The chunk size follows the 5,000-record
        cap in docs/principles/performance-scalability.md.

        Returns the repaired memberships.
        """
        return self._repair_stale_ended_status(batch_size, full=True)

    @api.model
    def _repair_stale_ended_status(self, batch_size, full):
        """Shared repair loop; see ``_cron_recompute_ended_status``."""
        if batch_size < 1:
            raise ValueError("batch_size must be a positive number of rows")
        memberships = self.with_context(active_test=False)
        repaired_ids = set()
        time_left = float("inf")
        if full:
            null_repaired, time_left = memberships._repair_null_is_ended(fields.Datetime.now(), batch_size)
            repaired_ids.update(null_repaired.ids)
        domains = self._stale_ended_status_domains if full else self._crossed_ended_status_domains
        pass_no = 0
        while time_left:
            # Re-read the clock every pass: a row whose ended_date is
            # crossed while the run is in flight recomputes to the very
            # values a stale `now` would keep selecting it for.
            now = fields.Datetime.now()
            legs = domains(now)
            # Rotate the starting leg each pass so one direction's large
            # backlog cannot starve the other directions within a run.
            offset = pass_no % len(legs)
            pass_no += 1
            chunk = memberships.browse()
            exhausted = True
            for leg in legs[offset:] + legs[:offset]:
                quota = batch_size - len(chunk)
                if quota <= 0:
                    exhausted = False
                    break
                found = memberships.search(leg, limit=quota)
                if len(found) == quota:
                    # The leg may hold more. Exhaustion must be tracked
                    # per leg: the legs overlap and the union
                    # de-duplicates, so a short chunk alone is no proof
                    # the backlog is drained.
                    exhausted = False
                chunk |= found
            if not chunk:
                if repaired_ids:
                    # Close the progress report so a drained backlog isn't
                    # left marked partially done (and pointlessly
                    # rescheduled ASAP).
                    self.env["ir.cron"]._commit_progress(0, remaining=0)
                break
            chunk.modified(["ended_date"])
            # The recompute flushes through low-level SQL and bypasses this
            # model's write() override, so the metric-invalidation hook must
            # be called explicitly.
            self._invalidate_group_metrics(chunk.mapped("group"))
            repaired_ids.update(chunk.ids)
            self.env.flush_all()
            # `remaining` is a drained/not-drained signal, not a count.
            if exhausted:
                self.env["ir.cron"]._commit_progress(len(chunk), remaining=0)
                break
            time_left = self.env["ir.cron"]._commit_progress(len(chunk), remaining=1)
        if not time_left:
            _logger.info("[spp.registry] Ended-status backlog remains; the cron will be re-triggered to continue")
        repaired = memberships.browse(repaired_ids)
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
