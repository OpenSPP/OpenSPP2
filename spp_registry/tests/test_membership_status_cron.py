# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Repair of stored ``status``/``is_ended`` stale against the clock — see
``_cron_recompute_ended_status`` (#417) for the full story.

The stale state cannot be produced through the ORM (writing ``ended_date``
recomputes at write time), so these tests age rows behind the ORM's back with
raw SQL — exactly how production rows drift.
"""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged

from .test_membership_constraints import MembershipCommon
from .test_metric_invalidation import _patch_invalidate_funnel


@tagged("post_install", "-at_install")
class TestMembershipEndedStatusCron(MembershipCommon):
    """``_cron_recompute_ended_status`` — repair rows the clock has crossed."""

    def _make_membership(self, individual, **vals):
        vals.update({"group": self.group.id, "individual": individual.id})
        return self.Membership.create(vals)

    def _age_row(self, rec, ended_date=None, active=True):
        """Rewrite the date window (and ``active``) behind the ORM's back so
        the stored computes keep their now-wrong values. Defaults to a
        departure one year ago; ``start_date`` is derived so the row stays
        consistent with the start/end constraint."""
        if ended_date is None:
            ended_date = fields.Datetime.now() - timedelta(days=365)
        start_date = ended_date - timedelta(days=365)
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE spp_group_membership SET start_date = %s, ended_date = %s, active = %s WHERE id = %s",
            (start_date, ended_date, active, rec.id),
        )
        rec.invalidate_recordset()

    def _read_stored_columns(self, rec):
        """Read ``status``/``is_ended`` straight from the SQL columns, the way
        the raw-SQL consumers of ``is_ended`` do — bypassing the ORM cache,
        which would recompute pending fields on read and mask a missing
        column write."""
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT status, is_ended FROM spp_group_membership WHERE id = %s",
            (rec.id,),
        )
        return self.env.cr.fetchone()

    def _run_cron(self, model=None, time_left=float("inf"), method="_cron_recompute_ended_status", **kwargs):
        """Run a repair cron with ``ir.cron._commit_progress`` stubbed out.

        The real method commits, which on a TestCursor releases the test
        savepoint and leaks this test's rows into the rest of the class.
        The stub records ``(processed, remaining)`` per chunk so tests can
        assert the chunking behaviour; ``time_left`` is what the stub
        reports back as the remaining cron time budget. ``method`` picks
        the cron entrypoint (daily full sweep by default).
        """
        calls = []

        def fake_commit_progress(_cron, processed=0, remaining=None, **_kw):
            calls.append((processed, remaining))
            return time_left

        # `is None`, not `or`: a model handle is an empty recordset and
        # therefore falsy — `model or ...` would silently fall back to the
        # superuser-bound self.Membership.
        target = self.Membership if model is None else model
        with patch.object(
            type(self.env["ir.cron"]),
            "_commit_progress",
            autospec=True,
            side_effect=fake_commit_progress,
        ):
            repaired = getattr(target, method)(**kwargs)
        return repaired, calls

    def test_cron_ends_membership_the_clock_has_crossed(self):
        rec = self._make_membership(self.individual_a)
        self._age_row(rec)

        # Stale precondition: departed a year ago, still stored as active.
        self.assertEqual(self._read_stored_columns(rec), ("active", False))
        self.assertEqual(rec.status, "active")
        self.assertFalse(rec.is_ended)

        repaired, _calls = self._run_cron()

        self.assertIn(rec, repaired)
        self.assertEqual(rec.status, "inactive")
        self.assertTrue(rec.is_ended)
        # The SQL columns must be repaired too — four consumers read
        # is_ended in raw SQL and never see the ORM cache.
        self.assertEqual(self._read_stored_columns(rec), ("inactive", True))

    def test_cron_reactivates_membership_whose_end_moved_to_future(self):
        past = fields.Datetime.now() - timedelta(days=365)
        rec = self._make_membership(
            self.individual_a,
            start_date=past - timedelta(days=1),
            ended_date=past,
        )
        self.assertEqual(rec.status, "inactive")
        self.assertTrue(rec.is_ended)

        # The end date is pushed to the future behind the ORM's back; the
        # stored "inactive" is now wrong in the other direction.
        future = fields.Datetime.now() + timedelta(days=365)
        self._age_row(rec, future)
        self.assertEqual(rec.status, "inactive")
        self.assertTrue(rec.is_ended)

        repaired, _calls = self._run_cron()

        self.assertIn(rec, repaired)
        self.assertEqual(rec.status, "active")
        self.assertFalse(rec.is_ended)
        self.assertEqual(self._read_stored_columns(rec), ("active", False))

    def test_cron_repairs_archived_rows(self):
        rec = self._make_membership(self.individual_a)
        self._age_row(rec, active=False)
        self.assertEqual(rec.status, "active")
        self.assertFalse(rec.is_ended)

        self._run_cron()

        self.assertEqual(rec.status, "inactive")
        self.assertTrue(rec.is_ended)
        # The cron repairs the computes only; archiving stays as it was.
        self.assertFalse(rec.active)

    def test_cron_repairs_null_is_ended_row(self):
        # A raw INSERT that omits the nullable computed columns: every
        # raw-SQL consumer treats NULL is_ended as ended, and the ORM alone
        # cannot repair NULL -> False (the cache reads NULL as False, so a
        # recompute writes nothing).
        rec = self._make_membership(self.individual_a)
        old_stamp = fields.Datetime.now() - timedelta(days=365)
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE spp_group_membership SET is_ended = NULL, status = NULL, ended_date = NULL, "
            "write_date = %s WHERE id = %s",
            (old_stamp, rec.id),
        )
        rec.invalidate_recordset()
        self.assertEqual(self._read_stored_columns(rec), (None, None))

        repaired, _calls = self._run_cron()

        self.assertIn(rec, repaired)
        self.assertEqual(self._read_stored_columns(rec), ("active", False))
        # The raw repair stamps write metadata the way the ORM legs' flush
        # does, so write_date-keyed consumers (incremental syncs, the
        # API's changed_by) see the repair.
        self.env.cr.execute(
            "SELECT write_date, write_uid FROM spp_group_membership WHERE id = %s",
            (rec.id,),
        )
        write_date, write_uid = self.env.cr.fetchone()
        self.assertGreater(write_date, old_stamp)
        self.assertEqual(write_uid, self.env.uid)

    def test_cron_repairs_null_columns_with_past_ended_date(self):
        # NULL is_ended/status with a departure already in the past must be
        # repaired by the ORM legs: the computed True/"inactive" differs
        # from the cached False, so — unlike the NULL-and-active case — a
        # normal recompute does write. Pins the ORM-internals assumption
        # documented on _repair_null_is_ended.
        rec = self._make_membership(self.individual_a)
        now = fields.Datetime.now()
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE spp_group_membership SET is_ended = NULL, status = NULL, "
            "start_date = %s, ended_date = %s WHERE id = %s",
            (now - timedelta(days=730), now - timedelta(days=365), rec.id),
        )
        rec.invalidate_recordset()
        self.assertEqual(self._read_stored_columns(rec), (None, None))

        repaired, _calls = self._run_cron()

        self.assertIn(rec, repaired)
        self.assertEqual(self._read_stored_columns(rec), ("inactive", True))

    def test_cron_repairs_memberships_of_disabled_registrants(self):
        # Two global ir.rule records hide memberships of disabled
        # registrants from ordinary users; the cron record pins
        # user_id=base.user_root precisely so the sweep sees them. An
        # officer-run sweep misses the row, the root-run sweep repairs it.
        rec = self._make_membership(self.individual_a)
        self._age_row(rec)
        self.individual_a.disabled = fields.Datetime.now()
        # Flush: the rule domain is evaluated in SQL, which must see the
        # disabled stamp, not the pending cache value.
        self.env.flush_all()

        officer = self._make_user("status_cron_officer", ["spp_registry.group_registry_officer"])
        missed, _calls = self._run_cron(model=self.Membership.with_user(officer))
        self.assertNotIn(rec, missed)
        self.assertEqual(self._read_stored_columns(rec), ("active", False))

        repaired, _calls = self._run_cron()
        self.assertIn(rec, repaired)
        self.assertEqual(self._read_stored_columns(rec), ("inactive", True))

    def test_cron_leaves_correct_rows_untouched(self):
        open_ended = self._make_membership(self.individual_a)
        past = fields.Datetime.now() - timedelta(days=365)
        already_ended = self._make_membership(
            self.individual_b,
            start_date=past - timedelta(days=1),
            ended_date=past,
        )

        repaired, _calls = self._run_cron()

        # An over-matching domain would sweep these rows in; they must not
        # be selected at all, not merely end up with unchanged values.
        self.assertFalse(repaired & (open_ended | already_ended))
        self.assertEqual(open_ended.status, "active")
        self.assertFalse(open_ended.is_ended)
        self.assertEqual(already_ended.status, "inactive")
        self.assertTrue(already_ended.is_ended)

    def test_cron_invalidates_group_metrics(self):
        rec = self._make_membership(self.individual_a)
        self._age_row(rec)

        # The recompute flushes through low-level SQL and bypasses write(),
        # so the cron must call the metric-invalidation funnel itself.
        with _patch_invalidate_funnel(self.env) as funnel:
            self._run_cron()

        self.assertTrue(funnel.called)
        invalidated = self.env["res.partner"].browse()
        for call in funnel.call_args_list:
            invalidated |= call.args[0]
        self.assertIn(self.group, invalidated)

    def test_cron_drains_backlog_in_batches(self):
        carol = self.Partner.create({"name": "Carol", "is_registrant": True, "is_group": False})
        rows = self.Membership.browse()
        for individual in (self.individual_a, self.individual_b, carol):
            rec = self._make_membership(individual)
            self._age_row(rec)
            rows |= rec

        repaired, calls = self._run_cron(batch_size=2)

        # One run drains the whole backlog in batch_size chunks, each
        # reported (and committed) through _commit_progress. Assertions
        # stay scoped to the three rows this test created — ambient stale
        # rows on a demo-seeded DB may only add to the totals.
        self.assertTrue(all(rec in repaired for rec in rows))
        for rec in rows:
            self.assertEqual(rec.status, "inactive")
            self.assertTrue(rec.is_ended)
        self.assertGreaterEqual(len(calls), 2)
        self.assertGreaterEqual(sum(processed for processed, _remaining in calls), len(rows))
        self.assertTrue(all(processed <= 2 for processed, _remaining in calls))
        # A short final chunk reports the backlog as drained. (Guarded: if
        # ambient stale rows ever pad the backlog to a multiple of the
        # batch size, the last full chunk legitimately reports more work.)
        if calls[-1][0] < 2:
            self.assertEqual(calls[-1][1], 0)

    def test_cron_resumes_after_time_budget_exhausted(self):
        # The production path for any real backlog: _commit_progress
        # reports no time left, the run stops after its current chunk with
        # the backlog flagged, and the rescheduled run finishes the job.
        carol = self.Partner.create({"name": "Carol", "is_registrant": True, "is_group": False})
        rows = self.Membership.browse()
        for individual in (self.individual_a, self.individual_b, carol):
            rec = self._make_membership(individual)
            self._age_row(rec)
            rows |= rec

        first, calls = self._run_cron(batch_size=1, time_left=0.0)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 1)
        self.assertNotEqual(calls[0][1], 0)  # backlog reported as remaining
        self.assertEqual(len(first & rows), 1)

        second, _calls = self._run_cron(batch_size=1)

        self.assertEqual((first | second) & rows, rows)
        for rec in rows:
            self.assertEqual(rec.status, "inactive")
            self.assertTrue(rec.is_ended)

    def test_overlapping_legs_do_not_end_run_early(self):
        # Rows stale on both columns match the first two legs at once and
        # the chunk union de-duplicates, so a chunk shorter than
        # batch_size is no proof the backlog is drained — exhaustion must
        # be tracked per leg, or rows stale on one column only are left
        # behind with the run reported fully done.
        status_only = self.Membership.browse()
        for name in ("Dave", "Erin"):
            individual = self.Partner.create({"name": name, "is_registrant": True, "is_group": False})
            rec = self._make_membership(individual)
            self._age_row(rec)
            # is_ended already correct; only status is stale (leg 2 only).
            self.env.cr.execute(
                "UPDATE spp_group_membership SET is_ended = true WHERE id = %s",
                (rec.id,),
            )
            rec.invalidate_recordset()
            status_only |= rec
        # Newer ids — searched first under `id desc` — stale on both.
        carol = self.Partner.create({"name": "Carol", "is_registrant": True, "is_group": False})
        both_stale = self.Membership.browse()
        for individual in (self.individual_a, self.individual_b, carol):
            rec = self._make_membership(individual)
            self._age_row(rec)
            both_stale |= rec

        repaired, calls = self._run_cron(batch_size=4)

        # One run repairs every row: pass 1 fills mostly from leg 1 and
        # its leg-2 quota only re-finds chunk rows, so a union-size
        # drained check would have stopped here with the status-only rows
        # unrepaired until the next daily sweep.
        rows = both_stale | status_only
        self.assertEqual(repaired & rows, rows)
        for rec in rows:
            self.assertEqual(self._read_stored_columns(rec), ("inactive", True))
        self.assertEqual(calls[-1][1], 0)

    def test_crossed_cron_repairs_only_index_served_legs(self):
        crossed = self._make_membership(self.individual_a)
        self._age_row(crossed)
        null_row = self._make_membership(self.individual_b)
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE spp_group_membership SET is_ended = NULL, status = NULL, ended_date = NULL WHERE id = %s",
            (null_row.id,),
        )
        null_row.invalidate_recordset()

        repaired, _calls = self._run_cron(method="_cron_repair_crossed_ended_status")

        self.assertIn(crossed, repaired)
        self.assertEqual(self._read_stored_columns(crossed), ("inactive", True))
        # NULL drift needs full-scan probes; the trigger-driven cron runs
        # per departure and must leave those to the daily safety net.
        self.assertNotIn(null_row, repaired)
        self.assertEqual(self._read_stored_columns(null_row), (None, None))

        repaired, _calls = self._run_cron()

        self.assertIn(null_row, repaired)
        self.assertEqual(self._read_stored_columns(null_row), ("active", False))

    def _make_null_rows(self):
        rows = self.Membership.browse()
        for individual in (self.individual_a, self.individual_b):
            rows |= self._make_membership(individual)
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE spp_group_membership SET is_ended = NULL, ended_date = NULL WHERE id IN %s",
            (tuple(rows.ids),),
        )
        rows.invalidate_recordset()
        return rows

    def test_null_repair_drains_in_batches(self):
        rows = self._make_null_rows()

        repaired, calls = self._run_cron(batch_size=1)

        self.assertEqual(repaired & rows, rows)
        for rec in rows:
            self.assertEqual(self._read_stored_columns(rec), ("active", False))
        # Every batch is bounded and reported; the run closes with the
        # backlog reported drained.
        self.assertTrue(all(processed <= 1 for processed, _remaining in calls))
        self.assertGreaterEqual(sum(processed for processed, _remaining in calls), len(rows))
        self.assertEqual(calls[-1][1], 0)

    def test_null_repair_stops_when_time_budget_exhausted(self):
        # A NULL row with no ended_date matches none of the ORM legs, so
        # the NULL loop itself must report the backlog: with the budget
        # gone after one batch, the run stops flagged partially done and
        # is continued ASAP — not a day later on a "fully done" report.
        rows = self._make_null_rows()

        first, calls = self._run_cron(batch_size=1, time_left=0.0)

        self.assertEqual(calls, [(1, 1)])
        self.assertEqual(len(first & rows), 1)

        second, _calls = self._run_cron(batch_size=1)

        self.assertEqual((first | second) & rows, rows)
        for rec in rows:
            self.assertEqual(self._read_stored_columns(rec), ("active", False))

    def test_future_ended_date_schedules_cron_trigger(self):
        cron = self.env.ref("spp_registry.cron_repair_crossed_membership_ended_status")
        Trigger = self.env["ir.cron.trigger"]
        # Every departure is scheduled in the minute *after* ended_date —
        # even a minute-aligned one: the cron machinery consumes triggers
        # against the database clock while the repair predicate compares
        # the application clock, so an exact-time trigger could be
        # consumed a hair before the row reads as ended.
        future = fields.Datetime.now().replace(second=0) + timedelta(days=30)

        before = Trigger.search([("cron_id", "=", cron.id)])
        rec = self._make_membership(self.individual_a, ended_date=future)
        created = Trigger.search([("cron_id", "=", cron.id)]) - before
        self.assertEqual(len(created), 1)
        self.assertEqual(created.call_at, future + timedelta(minutes=1))

        # A mid-minute departure lands in the next full minute as well,
        # never scheduled at or before the date itself.
        later = future + timedelta(days=5, seconds=30)
        before = Trigger.search([("cron_id", "=", cron.id)])
        rec.write({"ended_date": later})
        created = Trigger.search([("cron_id", "=", cron.id)]) - before
        self.assertEqual(len(created), 1)
        self.assertEqual(created.call_at, later.replace(second=0) + timedelta(minutes=1))

    def test_default_ended_date_context_schedules_cron_trigger(self):
        # default_get fills a missing ended_date from the context; the
        # trigger must still be scheduled (create reads the records back,
        # not the raw vals).
        cron = self.env.ref("spp_registry.cron_repair_crossed_membership_ended_status")
        Trigger = self.env["ir.cron.trigger"]
        future = fields.Datetime.now().replace(second=0) + timedelta(days=30)

        before = Trigger.search([("cron_id", "=", cron.id)])
        rec = self.Membership.with_context(default_ended_date=future).create(
            {"group": self.group.id, "individual": self.individual_a.id}
        )
        self.assertEqual(rec.ended_date, future)
        created = Trigger.search([("cron_id", "=", cron.id)]) - before
        self.assertEqual(len(created), 1)
        self.assertEqual(created.call_at, future + timedelta(minutes=1))

    def test_past_ended_date_schedules_no_cron_trigger(self):
        # A past departure is recomputed correctly at write time; only a
        # future one needs the clock-crossing repair scheduled.
        cron = self.env.ref("spp_registry.cron_repair_crossed_membership_ended_status")
        Trigger = self.env["ir.cron.trigger"]
        past = fields.Datetime.now() - timedelta(days=365)

        before = Trigger.search([("cron_id", "=", cron.id)])
        rec = self._make_membership(
            self.individual_a,
            start_date=past - timedelta(days=1),
            ended_date=past,
        )
        rec.write({"ended_date": past + timedelta(days=1)})
        self.assertFalse(Trigger.search([("cron_id", "=", cron.id)]) - before)

    def test_same_minute_departures_share_one_trigger(self):
        # A cohort exit written one membership per call must not file one
        # trigger row per membership — pending triggers for the same
        # minute are reused (ir.cron._trigger itself never de-duplicates
        # across calls).
        cron = self.env.ref("spp_registry.cron_repair_crossed_membership_ended_status")
        Trigger = self.env["ir.cron.trigger"]
        future = fields.Datetime.now().replace(second=0) + timedelta(days=30)

        before = Trigger.search([("cron_id", "=", cron.id)])
        self._make_membership(self.individual_a, ended_date=future)
        self._make_membership(self.individual_b, ended_date=future + timedelta(seconds=30))
        created = Trigger.search([("cron_id", "=", cron.id)]) - before
        self.assertEqual(len(created), 1)
        self.assertEqual(created.call_at, future + timedelta(minutes=1))

    def test_missing_trigger_cron_degrades_to_daily_sweep(self):
        # The trigger cron is a latency optimisation. If the noupdate
        # record was deleted by an admin, writing a membership must still
        # succeed — the daily sweep repairs the row eventually — rather
        # than raising from env.ref on the core registry write path.
        self.env.ref("spp_registry.cron_repair_crossed_membership_ended_status").unlink()
        future = fields.Datetime.now() + timedelta(days=30)

        rec = self._make_membership(self.individual_a, ended_date=future)

        self.assertEqual(rec.ended_date, future)

    def test_cron_record_registered(self):
        # Daily full safety net — the common path is the per-departure
        # trigger on the crossed cron below.
        cron = self.env.ref("spp_registry.cron_recompute_membership_ended_status")
        self.assertEqual(cron.model_id.model, "spp.group.membership")
        self.assertTrue(cron.active)
        self.assertIn("_cron_recompute_ended_status", cron.code)
        self.assertEqual(cron.interval_number, 1)
        self.assertEqual(cron.interval_type, "days")
        # Trigger target for exact-time repairs: crossed legs only, so a
        # per-departure run stays index-served.
        crossed = self.env.ref("spp_registry.cron_repair_crossed_membership_ended_status")
        self.assertEqual(crossed.model_id.model, "spp.group.membership")
        self.assertTrue(crossed.active)
        self.assertIn("_cron_repair_crossed_ended_status", crossed.code)
        # Superuser pin on both: the unsudo'd searches must see
        # memberships of disabled registrants despite the global ir.rule
        # pair.
        root = self.env.ref("base.user_root")
        self.assertEqual(cron.user_id, root)
        self.assertEqual(crossed.user_id, root)

    def test_scheduled_sweeps_are_offset(self):
        # Both crons sweep the same two crossed legs, and
        # `_order = "id desc"` makes their `search(leg, limit=quota)`
        # calls return the same rows in the same order. With a shared
        # nextcall two cron workers pick the two jobs at once (each
        # ir_cron row is taken with FOR NO KEY UPDATE SKIP LOCKED, so
        # neither blocks the other) and UPDATE the same ids; under
        # Odoo's REPEATABLE READ the run that commits second dies with
        # "could not serialize access due to concurrent update" and is
        # logged as a failure. The window is widest on the first sweep
        # after upgrading a registry with a stale backlog. Their
        # scheduled runs must therefore start apart — both being daily,
        # the initial offset is preserved on every later run.
        daily = self.env.ref("spp_registry.cron_recompute_membership_ended_status")
        crossed = self.env.ref("spp_registry.cron_repair_crossed_membership_ended_status")
        self.assertGreaterEqual(
            abs(daily.nextcall - crossed.nextcall),
            timedelta(minutes=30),
        )
