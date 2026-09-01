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

    def _run_cron(self, model=None, time_left=float("inf"), **kwargs):
        """Run the repair cron with ``ir.cron._commit_progress`` stubbed out.

        The real method commits, which on a TestCursor releases the test
        savepoint and leaks this test's rows into the rest of the class.
        The stub records ``(processed, remaining)`` per chunk so tests can
        assert the chunking behaviour; ``time_left`` is what the stub
        reports back as the remaining cron time budget.
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
            repaired = target._cron_recompute_ended_status(**kwargs)
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
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE spp_group_membership SET is_ended = NULL, status = NULL, ended_date = NULL WHERE id = %s",
            (rec.id,),
        )
        rec.invalidate_recordset()
        self.assertEqual(self._read_stored_columns(rec), (None, None))

        repaired, _calls = self._run_cron()

        self.assertIn(rec, repaired)
        self.assertEqual(self._read_stored_columns(rec), ("active", False))

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

    def test_future_ended_date_schedules_cron_trigger(self):
        cron = self.env.ref("spp_registry.cron_recompute_membership_ended_status")
        Trigger = self.env["ir.cron.trigger"]
        # A minute-aligned departure gets its trigger at exactly that time.
        future = fields.Datetime.now().replace(second=0) + timedelta(days=30)

        before = Trigger.search([("cron_id", "=", cron.id)])
        rec = self._make_membership(self.individual_a, ended_date=future)
        created = Trigger.search([("cron_id", "=", cron.id)]) - before
        self.assertEqual(len(created), 1)
        self.assertEqual(created.call_at, future)

        # A mid-minute departure is rounded up to the next full minute
        # (cron precision), never scheduled before the date itself.
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
        cron = self.env.ref("spp_registry.cron_recompute_membership_ended_status")
        Trigger = self.env["ir.cron.trigger"]
        future = fields.Datetime.now().replace(second=0) + timedelta(days=30)

        before = Trigger.search([("cron_id", "=", cron.id)])
        rec = self.Membership.with_context(default_ended_date=future).create(
            {"group": self.group.id, "individual": self.individual_a.id}
        )
        self.assertEqual(rec.ended_date, future)
        created = Trigger.search([("cron_id", "=", cron.id)]) - before
        self.assertEqual(len(created), 1)
        self.assertEqual(created.call_at, future)

    def test_past_ended_date_schedules_no_cron_trigger(self):
        # A past departure is recomputed correctly at write time; only a
        # future one needs the clock-crossing repair scheduled.
        cron = self.env.ref("spp_registry.cron_recompute_membership_ended_status")
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

    def test_cron_record_registered(self):
        cron = self.env.ref("spp_registry.cron_recompute_membership_ended_status")
        self.assertEqual(cron.model_id.model, "spp.group.membership")
        self.assertTrue(cron.active)
        self.assertIn("_cron_recompute_ended_status", cron.code)
        # Daily safety net only — the common path is the per-row trigger
        # scheduled at the exact ended_date.
        self.assertEqual(cron.interval_number, 1)
        self.assertEqual(cron.interval_type, "days")
        # Superuser pin: the unsudo'd searches must see memberships of
        # disabled registrants despite the global ir.rule pair.
        self.assertEqual(cron.user_id, self.env.ref("base.user_root"))
